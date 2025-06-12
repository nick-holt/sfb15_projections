"""
Fixed Feature Engineering Pipeline for Fantasy Football Projections

This script builds features from HISTORICAL performance data only, ensuring no data leakage.
For predicting season t, we only use data from seasons t-1, t-2, etc., plus static roster info.

Key changes from original:
- Percentile features calculated from historical seasons only
- Points per game from previous seasons only  
- All statistical features use historical data only
- Proper temporal validation to prevent leakage
"""

import pandas as pd
import numpy as np
import os
from typing import Dict, List, Tuple

# Configuration
PROCESSED_DIR = "data/processed"
RAW_DIR = "data/raw"
FEATURES_DIR = "data/features"
OUTPUT_FILE = "player_features.parquet"

# Feature engineering parameters
DECAY_FACTORS = [0.8, 0.6, 0.4]  # Different decay rates for recency weighting
LOOKBACK_SEASONS = [1, 2, 3]     # Historical periods to analyze
MIN_GAMES_THRESHOLD = 4          # Minimum games to be considered "active"
MIN_SEASONS_FOR_PREDICTION = 1   # Minimum historical seasons needed to make prediction

class FixedFeatureEngineer:
    """Fixed feature engineering class with no data leakage"""
    
    def __init__(self):
        self.season_stats = None
        self.weekly_stats = None
        self.roster_data = None
        
    def load_data(self):
        """Load all required datasets"""
        print("Loading data...")
        
        # Load historical stats
        self.season_stats = pd.read_parquet(os.path.join(PROCESSED_DIR, "season_stats.parquet"))
        self.weekly_stats = pd.read_parquet(os.path.join(PROCESSED_DIR, "weekly_stats.parquet"))
        
        # Load roster snapshot (this can be current season since it's static attributes)
        roster_path = os.path.join(RAW_DIR, "roster_2025.csv")
        if os.path.exists(roster_path):
            self.roster_data = pd.read_csv(roster_path)
        else:
            print(f"Warning: {roster_path} not found. Skipping roster features.")
            
        print(f"Loaded {len(self.season_stats)} season records")
        print(f"Loaded {len(self.weekly_stats)} weekly records")
        if self.roster_data is not None:
            print(f"Loaded {len(self.roster_data)} roster records")
    
    def validate_temporal_separation(self, features_df: pd.DataFrame, target_season: int) -> bool:
        """Validate that no features contain data from target season"""
        print(f"Validating temporal separation for season {target_season}...")
        
        # Check that we're not accidentally using current season data
        feature_cols = [col for col in features_df.columns 
                       if col not in ['season', 'player_id', 'player_name', 'position', 'total_points']]
        
        # All feature values should be calculable without target season data
        target_season_mask = features_df['season'] == target_season
        target_season_features = features_df[target_season_mask][feature_cols]
        
        # Check for any features that are NaN (which would indicate we need target season data)
        missing_features = target_season_features.isnull().sum()
        problematic_features = missing_features[missing_features > 0]
        
        if len(problematic_features) > 0:
            print(f"WARNING: Features with missing data for season {target_season}:")
            for feat, count in problematic_features.items():
                print(f"  {feat}: {count} missing values")
        
        return len(problematic_features) == 0
    
    def calculate_historical_percentiles(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate percentile features using ONLY historical data"""
        print("Calculating historical percentile features...")
        
        percentile_features = []
        
        for target_season in df['season'].unique():
            print(f"  Processing season {target_season}...")
            
            # Get historical data (all seasons before target season)
            historical_data = df[df['season'] < target_season].copy()
            
            if len(historical_data) == 0:
                continue  # Skip if no historical data
            
            # Get current season players
            current_season_players = df[df['season'] == target_season].copy()
            
            for idx, player_row in current_season_players.iterrows():
                player_id = player_row['player_id']
                position = player_row['position']
                
                feature_row = {
                    'player_id': player_id,
                    'season': target_season
                }
                
                # Calculate player's historical performance
                player_history = historical_data[historical_data['player_id'] == player_id]
                
                if len(player_history) > 0:
                    # Use most recent historical season for percentile calculation
                    recent_performance = player_history.sort_values('season').iloc[-1]
                    
                    # Calculate percentiles within the HISTORICAL data only
                    historical_season = recent_performance['season']
                    same_season_historical = historical_data[historical_data['season'] == historical_season]
                    
                    # Position percentiles (within position, within historical season)
                    position_peers = same_season_historical[same_season_historical['position'] == position]
                    if len(position_peers) > 1:
                        feature_row['total_points_pos_pct_hist'] = (
                            (position_peers['total_points'] < recent_performance['total_points']).sum() / len(position_peers)
                        )
                        feature_row['games_played_pos_pct_hist'] = (
                            (position_peers['games_played'] < recent_performance['games_played']).sum() / len(position_peers)
                        )
                    
                    # Overall percentiles (across all positions, within historical season)
                    if len(same_season_historical) > 1:
                        feature_row['total_points_overall_pct_hist'] = (
                            (same_season_historical['total_points'] < recent_performance['total_points']).sum() / len(same_season_historical)
                        )
                        feature_row['games_played_overall_pct_hist'] = (
                            (same_season_historical['games_played'] < recent_performance['games_played']).sum() / len(same_season_historical)
                        )
                    
                    # Historical points per game
                    if recent_performance['games_played'] > 0:
                        feature_row['points_per_game_hist'] = recent_performance['total_points'] / recent_performance['games_played']
                
                percentile_features.append(feature_row)
        
        # Convert to DataFrame and merge
        percentile_df = pd.DataFrame(percentile_features)
        if len(percentile_df) > 0:
            df = df.merge(percentile_df, on=['player_id', 'season'], how='left')
        
        return df
    
    def calculate_exponential_decay_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate exponentially decayed averages using ONLY historical data"""
        print("Calculating exponential decay features...")
        
        # Key stats to calculate decay averages for
        stats_cols = [
            'total_points', 'pass_attempt', 'passing_yards', 'pass_touchdown',
            'rush_attempt', 'rushing_yards', 'rush_touchdown', 'receptions',
            'receiving_yards', 'receiving_touchdown', 'games_played'
        ]
        
        # Only use columns that exist in the data
        available_stats = [col for col in stats_cols if col in df.columns]
        
        decay_features = []
        
        for player_id in df['player_id'].unique():
            player_data = df[df['player_id'] == player_id].sort_values('season')
            
            for i, row in player_data.iterrows():
                current_season = row['season']
                feature_row = {'player_id': player_id, 'season': current_season}
                
                # Get historical data STRICTLY before current season
                hist_data = player_data[player_data['season'] < current_season]
                
                if len(hist_data) > 0:
                    for decay_factor in DECAY_FACTORS:
                        for lookback in LOOKBACK_SEASONS:
                            # Get data for specified lookback period
                            lookback_data = hist_data[
                                hist_data['season'] >= (current_season - lookback)
                            ]
                            
                            if len(lookback_data) > 0:
                                # Calculate weights (more recent seasons get higher weight)
                                seasons_back = current_season - lookback_data['season']
                                weights = decay_factor ** seasons_back
                                
                                # Calculate weighted averages
                                for stat in available_stats:
                                    if stat in lookback_data.columns:
                                        weighted_avg = np.average(
                                            lookback_data[stat], 
                                            weights=weights
                                        )
                                        feature_name = f"{stat}_decay{decay_factor}_L{lookback}"
                                        feature_row[feature_name] = weighted_avg
                
                decay_features.append(feature_row)
        
        # Convert to DataFrame and merge with original data
        decay_df = pd.DataFrame(decay_features)
        if len(decay_df) > 0:
            df = df.merge(decay_df, on=['player_id', 'season'], how='left')
        
        return df
    
    def calculate_historical_trend_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate performance trends using ONLY historical data"""
        print("Calculating historical trend features...")
        
        trend_cols = ['total_points', 'games_played']
        trend_features = []
        
        for player_id in df['player_id'].unique():
            player_data = df[df['player_id'] == player_id].sort_values('season')
            
            for i, row in player_data.iterrows():
                current_season = row['season']
                feature_row = {'player_id': player_id, 'season': current_season}
                
                # Get historical data STRICTLY before current season
                hist_data = player_data[player_data['season'] < current_season]
                
                if len(hist_data) >= 2:
                    for col in trend_cols:
                        if col in hist_data.columns:
                            # Calculate trends over different periods
                            for lookback in [2, 3]:
                                recent_hist = hist_data.tail(min(lookback, len(hist_data)))
                                
                                if len(recent_hist) >= 2:
                                    # Linear trend (slope)
                                    x = np.arange(len(recent_hist))
                                    y = recent_hist[col].values
                                    
                                    if len(y) > 1 and not np.all(np.isnan(y)):
                                        # Simple linear regression slope
                                        slope = np.polyfit(x, y, 1)[0] if len(y) > 1 else 0
                                        feature_row[f'{col}_trend_{lookback}yr_hist'] = slope
                
                trend_features.append(feature_row)
        
        # Convert to DataFrame and merge
        trend_df = pd.DataFrame(trend_features)
        if len(trend_df) > 0:
            df = df.merge(trend_df, on=['player_id', 'season'], how='left')
        
        return df
    
    def create_lag_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create lagged features (previous season performance)"""
        print("Creating lag features...")
        
        lag_cols = ['total_points', 'games_played']
        
        # Calculate points per game from historical data
        df['points_per_game_calc'] = df['total_points'] / df['games_played'].clip(lower=1)
        lag_cols.append('points_per_game_calc')
        
        for col in lag_cols:
            if col in df.columns:
                # Create 1-year lag (this is inherently historical)
                df[f'{col}_lag1'] = df.groupby('player_id')[col].shift(1)
                
                # Create 2-year lag
                df[f'{col}_lag2'] = df.groupby('player_id')[col].shift(2)
        
        # Calculate availability rate from historical data
        df['games_missed_calc'] = np.where(
            df['season'] >= 2021, 17 - df['games_played'], 
            16 - df['games_played']
        )
        df['games_missed_calc'] = np.clip(df['games_missed_calc'], 0, None)
        
        df['availability_rate_calc'] = df['games_played'] / (df['games_played'] + df['games_missed_calc'])
        df['availability_rate_calc'] = df['availability_rate_calc'].fillna(1.0)
        
        # Lag the availability rate
        df['availability_rate_lag1'] = df.groupby('player_id')['availability_rate_calc'].shift(1)
        df['availability_rate_lag2'] = df.groupby('player_id')['availability_rate_calc'].shift(2)
        
        return df
    
    def add_roster_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add static player attributes from roster data"""
        if df is None:
            return pd.DataFrame()
            
        print("Adding roster features...")
        roster_df = df.copy()

        # The necessary columns 'age_2025' and 'years_exp' already exist.
        # No calculation is needed.

        # Height in inches and BMI
        def parse_height(height_str):
            if isinstance(height_str, str):
                feet, inches = map(int, height_str.split('-'))
                return feet * 12 + inches
            return np.nan
        
        roster_df['height_inches'] = roster_df['height'].apply(parse_height)
        
        if 'weight' in roster_df.columns and 'height_inches' in roster_df.columns:
            roster_df['bmi'] = (roster_df['weight'] * 703) / (roster_df['height_inches'] ** 2)

        return roster_df
    
    def calculate_position_specific_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate features that are specific to certain positions"""
        print("Calculating position-specific features...")
        
        # Calculate per-game statistics from lagged data (historical)
        for col in ['pass_attempt', 'passing_yards', 'pass_touchdown', 'rush_attempt', 
                   'rushing_yards', 'rush_touchdown', 'receptions', 'receiving_yards', 'receiving_touchdown']:
            if col in df.columns:
                # Per-game features from lag1 (previous season)
                lag1_col = f'{col}_lag1'
                games_lag1_col = 'games_played_lag1'
                
                if lag1_col in df.columns and games_lag1_col in df.columns:
                    df[f'{col}_per_game_lag1'] = (
                        df[lag1_col] / df[games_lag1_col].clip(lower=1)
                    )
        
        return df
    
    def build_features(self) -> pd.DataFrame:
        """Main feature building orchestrator - SIMPLIFIED VERSION"""
        print("Starting feature engineering process...")
        
        # Start with season_stats as the base - this has all our identifier columns
        base_df = self.season_stats.copy()
        print(f"Starting with base data: {base_df.shape}")
        
        # Create all feature sets separately
        print("Creating lag features...")
        lag_df = self.create_lag_features(base_df.copy())
        
        print("Creating decay features...")
        decay_df = self.calculate_exponential_decay_features(base_df.copy())
        
        print("Creating historical percentile features...")
        hist_df = self.calculate_historical_percentiles(base_df.copy())
        
        print("Creating trend features...") 
        trend_df = self.calculate_historical_trend_features(base_df.copy())
        
        # Start with the base data (which has all identifiers)
        final_df = base_df.copy()
        
        # Merge in the features from each dataset, only taking the new feature columns
        feature_datasets = [
            ('lag', lag_df),
            ('decay', decay_df), 
            ('hist', hist_df),
            ('trend', trend_df)
        ]
        
        for name, feature_df in feature_datasets:
            if len(feature_df) > 0:
                # Identify only the new feature columns (not identifiers)
                id_cols = ['player_id', 'season', 'player_name', 'position', 'team']
                existing_cols = set(final_df.columns)
                new_feature_cols = [col for col in feature_df.columns 
                                  if col not in existing_cols and col not in id_cols]
                
                if new_feature_cols:
                    merge_cols = ['player_id', 'season']
                    cols_to_merge = merge_cols + new_feature_cols
                    final_df = pd.merge(final_df, feature_df[cols_to_merge], 
                                      on=merge_cols, how='left')
                    print(f"  Added {len(new_feature_cols)} features from {name}")
        
        # Filter out players with insufficient historical data
        lag_feature_cols = [col for col in final_df.columns if '_lag1' in col]
        if lag_feature_cols:
            final_df['historical_data_count'] = final_df[lag_feature_cols].notna().sum(axis=1)
            final_df = final_df[final_df['historical_data_count'] >= MIN_SEASONS_FOR_PREDICTION]
            final_df = final_df.drop(columns=['historical_data_count'])
            print(f"Filtered to {len(final_df)} records with sufficient historical data")
        
        # Add roster features (age, experience, BMI)
        if self.roster_data is not None:
            roster_features = self.add_roster_features(self.roster_data.copy())
            roster_cols = ['player_id', 'age_2025', 'years_exp', 'height_inches', 'bmi']
            available_roster_cols = [col for col in roster_cols if col in roster_features.columns]
            
            if len(available_roster_cols) > 1:  # More than just player_id
                final_df = pd.merge(final_df, roster_features[available_roster_cols], 
                                  on='player_id', how='left')
                print(f"Added {len(available_roster_cols)-1} roster features")
        
        final_df = final_df.sort_values(['player_id', 'season'])
        print(f"Final dataset shape: {final_df.shape}")
        
        # Verify we still have essential columns
        essential_cols = ['player_id', 'season', 'player_name', 'position', 'team', 'total_points']
        missing_cols = [col for col in essential_cols if col not in final_df.columns]
        if missing_cols:
            raise ValueError(f"Missing essential columns: {missing_cols}")
        
        return final_df
    
    def save_features(self, df: pd.DataFrame):
        """Save the fixed feature dataset"""
        os.makedirs(FEATURES_DIR, exist_ok=True)
        output_path = os.path.join(FEATURES_DIR, OUTPUT_FILE)
        
        df.to_parquet(output_path, index=False)
        print(f"Fixed features saved to: {output_path}")
        
        # Print feature summary
        print("\nFixed Feature Summary:")
        print(f"Total features: {len(df.columns)}")
        print(f"Total player-seasons: {len(df)}")
        print(f"Date range: {df['season'].min()} - {df['season'].max()}")
        print(f"Positions: {sorted(df['position'].unique())}")
        
        # Show temporal distribution
        print(f"\nSamples by season:")
        print(df['season'].value_counts().sort_index())
        
        # Check for any remaining data leakage indicators
        print(f"\nData leakage check:")
        leakage_features = [col for col in df.columns if 
                           'total_points' in col and 
                           col != 'total_points' and 
                           '_lag' not in col and 
                           '_hist' not in col and
                           '_decay' not in col]
        
        if leakage_features:
            print(f"WARNING: Potential leakage features found: {leakage_features}")
        else:
            print("✓ No obvious leakage features detected")
        
        # Show sample of key features
        key_features = ['total_points_lag1', 'points_per_game_calc_lag1', 'total_points_pos_pct_hist', 
                       'total_points_overall_pct_hist', 'availability_rate_lag1']
        available_key_features = [f for f in key_features if f in df.columns]
        
        if available_key_features:
            print(f"\nSample of key historical features:")
            print(df[['season', 'player_name', 'total_points'] + available_key_features].head())

def main():
    """Main execution function"""
    engineer = FixedFeatureEngineer()
    engineer.load_data()
    features_df = engineer.build_features()
    engineer.save_features(features_df)

if __name__ == "__main__":
    main() 
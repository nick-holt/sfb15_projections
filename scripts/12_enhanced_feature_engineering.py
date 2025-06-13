"""
Enhanced Feature Engineering with Starter Probability and Injury Risk

This script adds starter probability and injury risk features to the training data
so models can learn complex interactions between these factors and other features.
"""

import pandas as pd
import numpy as np
from datetime import datetime
import os

class EnhancedFeatureEngineering:
    def __init__(self):
        self.historical_data = None
        self.player_features = None
        
    def load_data(self):
        """Load historical data and existing features"""
        print("Loading historical data...")
        self.historical_data = pd.read_parquet('data/processed/season_stats.parquet')
        print(f"Loaded {len(self.historical_data)} historical records")
        
        # Load existing features if available
        feature_files = [
            'data/features/qb_features.parquet',
            'data/features/rb_features.parquet', 
            'data/features/wr_features.parquet',
            'data/features/te_features.parquet'
        ]
        
        feature_dfs = []
        for file in feature_files:
            if os.path.exists(file):
                df = pd.read_parquet(file)
                feature_dfs.append(df)
        
        if feature_dfs:
            self.player_features = pd.concat(feature_dfs, ignore_index=True)
            print(f"Loaded {len(self.player_features)} existing feature records")
        else:
            print("No existing features found - will create from scratch")
    
    def calculate_historical_starter_probability(self):
        """Calculate historical starter probability features"""
        print("Calculating historical starter probability features...")
        
        # For each player-season, determine if they were the primary starter
        starter_features = []
        
        for season in self.historical_data['season'].unique():
            season_data = self.historical_data[self.historical_data['season'] == season]
            
            for team in season_data['team'].unique():
                for position in ['QB', 'RB', 'WR', 'TE']:
                    team_pos_players = season_data[
                        (season_data['team'] == team) & 
                        (season_data['position'] == position)
                    ].copy()
                    
                    if len(team_pos_players) == 0:
                        continue
                    
                    # Sort by games played and total points to identify starter
                    team_pos_players = team_pos_players.sort_values(
                        ['games_played', 'total_points'], ascending=False
                    )
                    
                    total_games = team_pos_players['games_played'].sum()
                    total_points = team_pos_players['total_points'].sum()
                    
                    for idx, (_, player) in enumerate(team_pos_players.iterrows()):
                        if total_games > 0:
                            games_share = player['games_played'] / max(total_games, 17)
                            points_share = player['total_points'] / max(total_points, 1) if total_points > 0 else 0
                        else:
                            games_share = 0
                            points_share = 0
                        
                        # Calculate starter probability based on usage
                        if idx == 0 and player['games_played'] >= 10:
                            starter_prob = min(0.95, 0.5 + games_share * 0.5)
                        elif idx == 0:
                            starter_prob = min(0.8, games_share * 0.8)
                        elif idx == 1 and player['games_played'] >= 8:
                            starter_prob = min(0.4, games_share * 0.6)
                        else:
                            starter_prob = min(0.2, games_share * 0.3)
                        
                        starter_features.append({
                            'player_id': player['player_id'],
                            'season': season,
                            'position': position,
                            'team': team,
                            'starter_probability_hist': starter_prob,
                            'games_share': games_share,
                            'points_share': points_share,
                            'depth_chart_rank': idx + 1
                        })
        
        starter_df = pd.DataFrame(starter_features)
        
        # Add rolling averages for starter probability
        starter_df = starter_df.sort_values(['player_id', 'season'])
        starter_df['starter_prob_prev_season'] = starter_df.groupby('player_id')['starter_probability_hist'].shift(1)
        starter_df['starter_prob_2yr_avg'] = starter_df.groupby('player_id')['starter_probability_hist'].rolling(2, min_periods=1).mean().values
        
        return starter_df
    
    def calculate_historical_injury_risk(self):
        """Calculate historical injury risk features"""
        print("Calculating historical injury risk features...")
        
        injury_features = []
        
        # Calculate for each player-season
        for _, player_season in self.historical_data.iterrows():
            player_id = player_season['player_id']
            season = player_season['season']
            position = player_season['position']
            age = player_season.get('age', None)
            games_played = player_season['games_played']
            
            # Calculate injury metrics
            games_missed = max(0, 17 - games_played)
            injury_rate = games_missed / 17
            
            # Position-specific injury baselines
            position_baselines = {
                'QB': 1.2, 'RB': 3.1, 'WR': 2.3, 'TE': 2.7
            }
            baseline_missed = position_baselines.get(position, 2.5)
            
            # Age-based injury risk
            age_risk_multiplier = 1.0
            if age:
                if position == 'QB':
                    if age <= 25:
                        age_risk_multiplier = 0.85
                    elif age <= 30:
                        age_risk_multiplier = 1.0
                    elif age <= 35:
                        age_risk_multiplier = 1.2
                    else:
                        age_risk_multiplier = 1.6
                elif position == 'RB':
                    if age <= 23:
                        age_risk_multiplier = 1.1
                    elif age <= 27:
                        age_risk_multiplier = 1.0
                    elif age <= 30:
                        age_risk_multiplier = 1.4
                    else:
                        age_risk_multiplier = 1.8
                else:  # WR/TE
                    if age <= 24:
                        age_risk_multiplier = 0.9
                    elif age <= 29:
                        age_risk_multiplier = 1.0
                    elif age <= 32:
                        age_risk_multiplier = 1.3
                    else:
                        age_risk_multiplier = 1.6
            
            # Calculate relative injury risk
            expected_games_missed = baseline_missed * age_risk_multiplier
            injury_risk_score = games_missed / max(expected_games_missed, 0.5)
            
            injury_features.append({
                'player_id': player_id,
                'season': season,
                'position': position,
                'age': age,
                'games_played': games_played,
                'games_missed': games_missed,
                'injury_rate': injury_rate,
                'age_risk_multiplier': age_risk_multiplier,
                'injury_risk_score': injury_risk_score,
                'expected_games_missed': expected_games_missed
            })
        
        injury_df = pd.DataFrame(injury_features)
        
        # Add historical injury trends
        injury_df = injury_df.sort_values(['player_id', 'season'])
        injury_df['injury_risk_prev_season'] = injury_df.groupby('player_id')['injury_risk_score'].shift(1)
        injury_df['injury_risk_2yr_avg'] = injury_df.groupby('player_id')['injury_risk_score'].rolling(2, min_periods=1).mean().values
        injury_df['games_missed_prev_season'] = injury_df.groupby('player_id')['games_missed'].shift(1)
        injury_df['career_injury_rate'] = injury_df.groupby('player_id')['injury_rate'].expanding().mean().values
        
        return injury_df
    
    def create_team_context_features(self):
        """Create team-level context features that affect individual projections"""
        print("Creating team context features...")
        
        team_features = []
        
        for season in self.historical_data['season'].unique():
            season_data = self.historical_data[self.historical_data['season'] == season]
            
            # Calculate team-level metrics
            team_stats = season_data.groupby('team').agg({
                'total_points': ['sum', 'mean', 'std'],
                'games_played': 'sum',
                'position': 'count'  # Total players
            }).round(2)
            
            team_stats.columns = ['team_total_points', 'team_avg_points', 'team_points_std', 
                                'team_total_games', 'team_roster_size']
            team_stats = team_stats.reset_index()
            team_stats['season'] = season
            
            # Calculate position concentration (how spread out scoring is)
            for position in ['QB', 'RB', 'WR', 'TE']:
                pos_data = season_data[season_data['position'] == position]
                pos_team_stats = pos_data.groupby('team')['total_points'].agg(['sum', 'count', 'std']).fillna(0)
                pos_team_stats.columns = [f'{position.lower()}_team_points', 
                                        f'{position.lower()}_team_count',
                                        f'{position.lower()}_team_std']
                team_stats = team_stats.merge(pos_team_stats, left_on='team', right_index=True, how='left')
            
            team_features.append(team_stats)
        
        team_df = pd.concat(team_features, ignore_index=True)
        team_df = team_df.fillna(0)
        
        return team_df
    
    def integrate_enhanced_features(self):
        """Integrate all enhanced features with existing feature set"""
        print("Integrating enhanced features...")
        
        # Calculate new feature sets
        starter_features = self.calculate_historical_starter_probability()
        injury_features = self.calculate_historical_injury_risk()
        team_features = self.create_team_context_features()
        
        # If we have existing features, merge with them
        if self.player_features is not None:
            print("Merging with existing features...")
            enhanced_features = self.player_features.copy()
            
            # Merge starter features
            enhanced_features = enhanced_features.merge(
                starter_features, 
                on=['player_id', 'season'], 
                how='left'
            )
            
            # Merge injury features  
            enhanced_features = enhanced_features.merge(
                injury_features,
                on=['player_id', 'season'],
                how='left'
            )
            
            # Merge team features
            enhanced_features = enhanced_features.merge(
                team_features,
                on=['team', 'season'],
                how='left'
            )
            
        else:
            print("Creating features from historical data...")
            # Start with historical data and add features
            enhanced_features = self.historical_data.copy()
            
            # Add starter features
            enhanced_features = enhanced_features.merge(
                starter_features,
                on=['player_id', 'season'],
                how='left'
            )
            
            # Add injury features
            enhanced_features = enhanced_features.merge(
                injury_features,
                on=['player_id', 'season'],
                how='left'
            )
            
            # Add team features
            enhanced_features = enhanced_features.merge(
                team_features,
                on=['team', 'season'],
                how='left'
            )
        
        # Fill missing values
        enhanced_features = enhanced_features.fillna(0)
        
        return enhanced_features
    
    def save_enhanced_features(self, enhanced_features):
        """Save enhanced features by position"""
        print("Saving enhanced features...")
        
        os.makedirs('data/features_enhanced', exist_ok=True)
        
        # Save by position
        for position in ['QB', 'RB', 'WR', 'TE']:
            pos_features = enhanced_features[enhanced_features['position'] == position]
            
            if len(pos_features) > 0:
                output_file = f'data/features_enhanced/{position.lower()}_features_enhanced.parquet'
                pos_features.to_parquet(output_file, index=False)
                print(f"Saved {len(pos_features)} {position} enhanced features to {output_file}")
        
        # Save combined file
        combined_file = 'data/features_enhanced/all_features_enhanced.parquet'
        enhanced_features.to_parquet(combined_file, index=False)
        print(f"Saved {len(enhanced_features)} total enhanced features to {combined_file}")
        
        # Create feature summary
        feature_summary = {
            'total_records': len(enhanced_features),
            'feature_count': len(enhanced_features.columns),
            'positions': enhanced_features['position'].value_counts().to_dict(),
            'seasons': sorted(enhanced_features['season'].unique().tolist()),
            'new_features': [
                'starter_probability_hist', 'starter_prob_prev_season', 'starter_prob_2yr_avg',
                'injury_risk_score', 'injury_risk_prev_season', 'career_injury_rate',
                'team_total_points', 'team_avg_points', 'qb_team_points', 'rb_team_points'
            ],
            'generated_timestamp': datetime.now().isoformat()
        }
        
        import json
        with open('data/features_enhanced/feature_summary.json', 'w') as f:
            json.dump(feature_summary, f, indent=2)
        
        print(f"Enhanced feature engineering complete!")
        print(f"Total features: {len(enhanced_features.columns)}")
        print(f"Key new features: starter probability, injury risk, team context")
        
        return enhanced_features
    
    def run_enhanced_feature_engineering(self):
        """Run complete enhanced feature engineering pipeline"""
        self.load_data()
        enhanced_features = self.integrate_enhanced_features()
        self.save_enhanced_features(enhanced_features)
        return enhanced_features

def main():
    engineer = EnhancedFeatureEngineering()
    enhanced_features = engineer.run_enhanced_feature_engineering()
    
    print(f"\nEnhanced feature engineering complete!")
    print(f"Ready to retrain models with {len(enhanced_features.columns)} features")
    print(f"Including starter probability and injury risk integration")

if __name__ == "__main__":
    main() 
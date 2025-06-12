"""
Generate 2025 NFL Fantasy Football Projections

This script uses our trained models to generate predictions for the 2025 season.
It creates projections for all active players based on their historical performance.
"""

import pandas as pd
import numpy as np
import os
import pickle
import json
import lightgbm as lgb
import catboost as cb
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

class Fantasy2025Projector:
    """Generate 2025 fantasy projections using trained ML models"""
    
    def __init__(self):
        self.features_data = None
        self.roster_2025 = None
        self.models = None
        self.predictions_2025 = None
        
    def load_data(self):
        """Load all necessary data"""
        print("Loading data for 2025 projections...")
        
        # Load feature dataset
        self.features_data = pd.read_parquet('data/features/player_features.parquet')
        print(f"Loaded {len(self.features_data)} historical records")
        
        # Load 2025 roster
        self.roster_2025 = pd.read_csv('data/raw/roster_2025.csv')
        print(f"Loaded {len(self.roster_2025)} players for 2025")
        
        # Load trained models
        self.load_trained_models()
    
    def load_trained_models(self):
        """Load the trained position-specific models"""
        print("Loading trained models...")
        self.models = {}
        
        positions = ['QB', 'RB', 'WR', 'TE']
        
        for position in positions:
            pos_lower = position.lower()
            
            # Load CatBoost model
            cb_path = f'data/models/catboost_model_{pos_lower}.cbm'
            lgb_path = f'data/models/lightgbm_model_{pos_lower}.txt'
            results_path = f'data/results/model_results_{pos_lower}.json'
            
            position_models = {}
            
            # Load CatBoost model
            if os.path.exists(cb_path):
                cb_model = cb.CatBoostRegressor()
                cb_model.load_model(cb_path)
                position_models['catboost'] = cb_model
                print(f"  Loaded CatBoost model for {position}")
            
            # Load LightGBM model
            if os.path.exists(lgb_path):
                lgb_model = lgb.Booster(model_file=lgb_path)
                position_models['lightgbm'] = lgb_model
                print(f"  Loaded LightGBM model for {position}")
            
            # Load model metadata (feature importance, etc.)
            if os.path.exists(results_path):
                with open(results_path, 'r') as f:
                    results_data = json.load(f)
                    
                # Extract feature names from CatBoost feature importance
                if 'advanced_models' in results_data and 'catboost' in results_data['advanced_models']:
                    cb_features = list(results_data['advanced_models']['catboost']['feature_importance'].keys())
                    position_models['features'] = cb_features
                    position_models['metadata'] = results_data
                    print(f"  Loaded {len(cb_features)} features for {position}")
            
            if position_models:
                self.models[position] = position_models
                print(f"Successfully loaded models for {position}")
            else:
                print(f"Warning: No models found for {position}")
        
        if not self.models:
            print("ERROR: No models loaded! Please run model training first.")
            return False
        
        print(f"Loaded models for {len(self.models)} positions")
        return True
    
    def create_2025_feature_base(self):
        """Create base feature set for 2025 predictions"""
        print("Creating 2025 feature base...")
        
        # Start with roster data
        base_2025 = self.roster_2025.copy()
        base_2025['season'] = 2025
        
        # Get latest historical data for each player
        latest_features = []
        
        for _, player in base_2025.iterrows():
            player_id = player['player_id']
            
            # Get player's historical data
            player_history = self.features_data[
                self.features_data['player_id'] == player_id
            ].sort_values('season')
            
            if len(player_history) > 0:
                # Use most recent season's features as base
                latest_record = player_history.iloc[-1].copy()
                
                # Update with 2025 roster info
                latest_record['season'] = 2025
                latest_record['team'] = player['team']
                latest_record['position'] = player['position']
                latest_record['player_name'] = player['player_name']
                
                # Update age and experience for 2025
                if 'age_2025' in player:
                    latest_record['age_2025'] = player['age_2025']
                if 'years_exp' in player:
                    latest_record['years_exp'] = player['years_exp']
                
                latest_features.append(latest_record)
            else:
                # For rookies or players without history, create minimal record
                rookie_record = {
                    'player_id': player_id,
                    'player_name': player['player_name'],
                    'position': player['position'],
                    'team': player['team'],
                    'season': 2025,
                    'age_2025': player.get('age_2025', 25),
                    'years_exp': player.get('years_exp', 0)
                }
                latest_features.append(pd.Series(rookie_record))
        
        features_2025 = pd.DataFrame(latest_features)
        print(f"Created 2025 feature base for {len(features_2025)} players")
        
        return features_2025
    
    def generate_position_predictions(self, position: str, features_2025: pd.DataFrame):
        """Generate predictions for a specific position using ML models + manual adjustments"""
        print(f"Generating {position} predictions...")
        
        # Filter to position
        pos_data = features_2025[features_2025['position'] == position].copy()
        
        if len(pos_data) == 0:
            print(f"No {position} players found")
            return pd.DataFrame()
            
        if position not in self.models:
            print(f"No model available for {position}")
            return pd.DataFrame()
        
        # Get model and features
        position_models = self.models[position]
        
        # Use model features if available
        if 'features' in position_models:
            model_features = position_models['features']
        else:
            # Fallback: use common features
            model_features = [col for col in pos_data.columns if col not in 
                            ['player_id', 'player_name', 'position', 'team', 'season', 'total_points']]
        
        # Prepare feature matrix
        available_features = [f for f in model_features if f in pos_data.columns]
        missing_features = [f for f in model_features if f not in pos_data.columns]
        
        if missing_features:
            print(f"  Warning: {len(missing_features)} features missing for {position}")
        
        X = pos_data[available_features].fillna(0)
        
        predictions = []
        model_names = []
        
        # Generate predictions from available models
        if 'catboost' in position_models:
            try:
                cb_pred = position_models['catboost'].predict(X)
                predictions.append(cb_pred)
                model_names.append('catboost')
                print(f"  Generated CatBoost predictions for {len(cb_pred)} {position} players")
            except Exception as e:
                print(f"  Error with CatBoost prediction: {e}")
        
        if 'lightgbm' in position_models:
            try:
                lgb_pred = position_models['lightgbm'].predict(X)
                predictions.append(lgb_pred)
                model_names.append('lightgbm')
                print(f"  Generated LightGBM predictions for {len(lgb_pred)} {position} players")
            except Exception as e:
                print(f"  Error with LightGBM prediction: {e}")
        
        # Create ensemble prediction if multiple models available
        if len(predictions) > 1:
            # Use model performance to weight predictions
            metadata = position_models.get('metadata', {})
            weights = []
            
            for model_name in model_names:
                if 'advanced_models' in metadata and model_name in metadata['advanced_models']:
                    cv_score = metadata['advanced_models'][model_name]['cv_score']
                    # Weight inversely proportional to CV score (lower is better)
                    weight = 1.0 / (cv_score + 1e-6)
                    weights.append(weight)
                else:
                    weights.append(1.0)  # Equal weight if no metadata
            
            # Normalize weights
            weights = np.array(weights) / sum(weights)
            final_pred = np.average(predictions, axis=0, weights=weights)
            print(f"  Created ensemble prediction with weights: {dict(zip(model_names, weights))}")
            
        elif len(predictions) == 1:
            final_pred = predictions[0]
            print(f"  Using single model prediction: {model_names[0]}")
        else:
            print(f"No ML predictions generated for {position}")
            return pd.DataFrame()
        
        # Apply manual adjustments for realism and validation
        final_pred = self.apply_manual_adjustments(final_pred, pos_data, position)
        
        # Create results dataframe
        results = pos_data[['player_id', 'player_name', 'position', 'team']].copy()
        results['projected_points'] = np.maximum(final_pred, 0)  # Ensure non-negative
        
        # Add confidence based on data quality and model agreement
        results['confidence'] = self.calculate_confidence(pos_data, predictions, position)
        
        # Add context features for analysis
        if 'total_points_lag1' in pos_data.columns:
            results['prev_season_points'] = pos_data['total_points_lag1'].values
        if 'games_played_lag1' in pos_data.columns:
            results['prev_season_games'] = pos_data['games_played_lag1'].values
        if 'age_2025' in pos_data.columns:
            results['age'] = pos_data['age_2025'].values
            
        return results
    
    def apply_manual_adjustments(self, predictions, player_data, position):
        """Apply manual adjustments to ML predictions for realism"""
        adjusted_predictions = predictions.copy()
        
        # Position-specific caps (based on 2024 elite performance)
        position_caps = {
            'QB': 700,  # Elite QBs like Allen can reach 650+ 
            'RB': 900,  # Elite RBs like Barkley can reach 850+
            'WR': 750,  # Elite WRs like Chase can reach 680+
            'TE': 600   # Elite TEs like Kelce can reach 560+
        }
        
        # Apply position cap
        if position in position_caps:
            adjusted_predictions = np.minimum(adjusted_predictions, position_caps[position])
        
        # Age adjustments if age data is available
        if 'age_2025' in player_data.columns:
            for i, age in enumerate(player_data['age_2025']):
                if pd.notna(age):
                    age_multiplier = self.get_age_multiplier(age, position)
                    adjusted_predictions[i] *= age_multiplier
        
        # Ensure minimum reasonable values
        adjusted_predictions = np.maximum(adjusted_predictions, 30)
        
        return adjusted_predictions
    
    def get_age_multiplier(self, age, position):
        """Get age-based adjustment multiplier"""
        if age <= 23:
            return 1.05  # Young players with upside
        elif age <= 26:
            return 1.02  # Prime years
        elif age <= 29:
            return 1.00  # Peak performance
        elif age <= 32:
            return 0.97  # Slight decline
        else:
            return 0.92  # More significant decline
    
    def calculate_confidence(self, player_data, predictions, position):
        """Calculate confidence levels based on data quality and model agreement"""
        confidence_scores = []
        
        for i in range(len(player_data)):
            score = 0
            
            # Historical data availability
            if 'total_points_lag1' in player_data.columns:
                if pd.notna(player_data['total_points_lag1'].iloc[i]) and player_data['total_points_lag1'].iloc[i] > 0:
                    score += 30  # Has recent performance data
            
            if 'games_played_lag1' in player_data.columns:
                games = player_data['games_played_lag1'].iloc[i]
                if pd.notna(games) and games >= 10:
                    score += 20  # Played significant games
                elif pd.notna(games) and games >= 5:
                    score += 10  # Some games played
            
            # Model agreement (if multiple predictions)
            if len(predictions) > 1:
                pred_std = np.std([pred[i] for pred in predictions])
                pred_mean = np.mean([pred[i] for pred in predictions])
                if pred_mean > 0:
                    cv = pred_std / pred_mean
                    if cv < 0.1:
                        score += 30  # High agreement
                    elif cv < 0.2:
                        score += 20  # Moderate agreement
                    else:
                        score += 10  # Low agreement
            else:
                score += 20  # Single model baseline
            
            # Age factor (prime age players more predictable)
            if 'age_2025' in player_data.columns:
                age = player_data['age_2025'].iloc[i]
                if pd.notna(age) and 24 <= age <= 30:
                    score += 20  # Prime age
                elif pd.notna(age):
                    score += 10  # Other ages
            
            confidence_scores.append(score)
        
        # Convert to categorical confidence levels
        confidence_levels = []
        for score in confidence_scores:
            if score >= 80:
                confidence_levels.append('High')
            elif score >= 50:
                confidence_levels.append('Medium')
            else:
                confidence_levels.append('Low')
        
        return confidence_levels
    
    def generate_all_predictions(self):
        """Generate predictions for all positions"""
        print("Generating 2025 projections for all positions...")
        
        # Create 2025 feature base
        features_2025 = self.create_2025_feature_base()
        
        all_predictions = []
        
        for position in ['QB', 'RB', 'WR', 'TE']:
            pos_predictions = self.generate_position_predictions(position, features_2025)
            if len(pos_predictions) > 0:
                all_predictions.append(pos_predictions)
        
        if all_predictions:
            self.predictions_2025 = pd.concat(all_predictions, ignore_index=True)
            print(f"Generated predictions for {len(self.predictions_2025)} players")
        else:
            print("No predictions generated")
    
    def add_rankings_and_tiers(self):
        """Add rankings and tier classifications"""
        if self.predictions_2025 is None:
            return
            
        print("Adding rankings and tiers...")
        
        # Overall rankings
        self.predictions_2025['overall_rank'] = self.predictions_2025['projected_points'].rank(ascending=False, method='min')
        
        # Position rankings
        self.predictions_2025['position_rank'] = self.predictions_2025.groupby('position')['projected_points'].rank(
            ascending=False, method='min'
        )
        
        # Create tiers within each position
        def assign_tiers(group):
            sorted_group = group.sort_values('projected_points', ascending=False)
            n_players = len(sorted_group)
            
            # Define tier sizes (approximate)
            if group.name == 'QB':
                tier_sizes = [12, 12, 8]  # QB1, QB2, QB3
            elif group.name in ['RB', 'WR']:
                tier_sizes = [12, 12, 12, 12]  # RB1/WR1, RB2/WR2, etc.
            else:  # TE
                tier_sizes = [12, 12]  # TE1, TE2
            
            tiers = []
            start_idx = 0
            
            for tier_num, tier_size in enumerate(tier_sizes, 1):
                end_idx = min(start_idx + tier_size, n_players)
                tiers.extend([tier_num] * (end_idx - start_idx))
                start_idx = end_idx
                
                if start_idx >= n_players:
                    break
            
            # Remaining players get the last tier + 1
            if len(tiers) < n_players:
                tiers.extend([len(tier_sizes) + 1] * (n_players - len(tiers)))
            
            return pd.Series(tiers, index=sorted_group.index)
        
        self.predictions_2025['tier'] = self.predictions_2025.groupby('position').apply(assign_tiers).values
        
        # Add descriptive tier labels
        tier_labels = {
            'QB': {1: 'Elite QB1', 2: 'QB1', 3: 'QB2', 4: 'Backup'},
            'RB': {1: 'Elite RB1', 2: 'RB1', 3: 'RB2', 4: 'RB3', 5: 'Handcuff'},
            'WR': {1: 'Elite WR1', 2: 'WR1', 3: 'WR2', 4: 'WR3', 5: 'Deep League'},
            'TE': {1: 'Elite TE1', 2: 'TE1', 3: 'Streamer'}
        }
        
        self.predictions_2025['tier_label'] = self.predictions_2025.apply(
            lambda row: tier_labels.get(row['position'], {}).get(row['tier'], 'Deep League'),
            axis=1
        )
    
    def create_summary_report(self):
        """Create summary report"""
        if self.predictions_2025 is None:
            return
            
        print("\n" + "="*60)
        print("2025 FANTASY FOOTBALL PROJECTIONS SUMMARY")
        print("="*60)
        
        # Overall stats
        print(f"Total players projected: {len(self.predictions_2025)}")
        print(f"Average projected points: {self.predictions_2025['projected_points'].mean():.1f}")
        
        # By position
        print("\nProjections by Position:")
        pos_summary = self.predictions_2025.groupby('position').agg({
            'projected_points': ['count', 'mean', 'max'],
            'player_name': 'count'
        }).round(1)
        print(pos_summary)
        
        # Top players overall
        print("\nTop 20 Overall Projected Players:")
        top_20 = self.predictions_2025.nsmallest(20, 'overall_rank')[
            ['overall_rank', 'player_name', 'position', 'team', 'projected_points', 'tier_label']
        ]
        for _, row in top_20.iterrows():
            print(f"{int(row['overall_rank']):2d}. {row['player_name']:<20} ({row['position']}, {row['team']}) - "
                  f"{row['projected_points']:.1f} pts ({row['tier_label']})")
        
        # Top 10 by position
        for position in ['QB', 'RB', 'WR', 'TE']:
            print(f"\nTop 10 {position}s:")
            pos_top = self.predictions_2025[
                self.predictions_2025['position'] == position
            ].nsmallest(10, 'position_rank')[
                ['position_rank', 'player_name', 'team', 'projected_points', 'tier_label']
            ]
            
            for _, row in pos_top.iterrows():
                print(f"{int(row['position_rank']):2d}. {row['player_name']:<20} ({row['team']}) - "
                      f"{row['projected_points']:.1f} pts ({row['tier_label']})")
    
    def save_projections(self):
        """Save projections to files"""
        if self.predictions_2025 is None:
            return
            
        print("\nSaving 2025 projections...")
        
        os.makedirs('projections/2025', exist_ok=True)
        
        # Save main projections file
        self.predictions_2025.to_csv('projections/2025/fantasy_projections_2025.csv', index=False)
        
        # Save position-specific files
        for position in ['QB', 'RB', 'WR', 'TE']:
            pos_data = self.predictions_2025[
                self.predictions_2025['position'] == position
            ].sort_values('position_rank')
            
            pos_data.to_csv(f'projections/2025/{position}_projections_2025.csv', index=False)
        
        # Save summary report
        with open('projections/2025/projection_summary.txt', 'w') as f:
            f.write(f"2025 Fantasy Football Projections\\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\\n")
            f.write(f"Total Players: {len(self.predictions_2025)}\\n\\n")
            
            # Position breakdown
            pos_counts = self.predictions_2025['position'].value_counts()
            for pos, count in pos_counts.items():
                f.write(f"{pos}: {count} players\\n")
        
        print(f"Projections saved to projections/2025/")
        print(f"- Main file: fantasy_projections_2025.csv")
        print(f"- Position files: QB/RB/WR/TE_projections_2025.csv")
        print(f"- Summary: projection_summary.txt")
    
    def run_projection_pipeline(self):
        """Run the complete projection pipeline"""
        self.load_data()
        self.generate_all_predictions()
        
        if self.predictions_2025 is not None:
            self.add_rankings_and_tiers()
            self.create_summary_report()
            self.save_projections()
        else:
            print("No projections generated")

def main():
    projector = Fantasy2025Projector()
    projector.run_projection_pipeline()

if __name__ == "__main__":
    main() 
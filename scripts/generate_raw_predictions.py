"""
Generate Raw Model Predictions for 2025 - No Caps or Transforms

This script generates completely raw model predictions with no adjustments,
caps, or transformations to see the true model output.
"""

import pandas as pd
import numpy as np
import os
import pickle
import lightgbm as lgb
import catboost as cb
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

class RawPredictionsGenerator:
    """Generate raw model predictions with no adjustments"""
    
    def __init__(self):
        self.historical_data = None
        self.roster_2025 = None
        self.models = {}
        
    def load_data(self):
        """Load necessary data"""
        print("Loading data for raw predictions...")
        
        # Load processed season stats for feature creation
        try:
            self.historical_data = pd.read_parquet('data/processed/season_stats.parquet')
            print(f"Loaded {len(self.historical_data)} historical season records")
        except Exception as e:
            print(f"Error loading season stats: {e}")
            return False
        
        # Load 2025 roster
        try:
            self.roster_2025 = pd.read_csv('data/raw/roster_2025.csv')
            print(f"Loaded {len(self.roster_2025)} players for 2025")
        except Exception as e:
            print(f"Error loading 2025 roster: {e}")
            return False
        
        return self.load_models()
    
    def load_models(self):
        """Load the trained models"""
        print("Loading models...")
        
        positions = ['qb', 'rb', 'wr', 'te']
        
        for position in positions:
            model_dir = f'models/final_proper/{position}'
            
            if os.path.exists(model_dir):
                position_models = {}
                
                # Load CatBoost model
                cb_path = f'{model_dir}/cb_model.cbm'
                if os.path.exists(cb_path):
                    try:
                        cb_model = cb.CatBoostRegressor()
                        cb_model.load_model(cb_path)
                        position_models['catboost'] = cb_model
                        print(f"  ✅ Loaded CatBoost model for {position.upper()}")
                    except Exception as e:
                        print(f"  ❌ Error loading CatBoost for {position}: {e}")
                
                # Load feature columns
                feature_path = f'{model_dir}/feature_columns.pkl'
                if os.path.exists(feature_path):
                    try:
                        with open(feature_path, 'rb') as f:
                            position_models['features'] = pickle.load(f)
                        print(f"  ✅ Loaded {len(position_models['features'])} features for {position.upper()}")
                    except Exception as e:
                        print(f"  ❌ Error loading features for {position}: {e}")
                
                if position_models:
                    self.models[position.upper()] = position_models
                    print(f"Successfully loaded models for {position.upper()}")
        
        print(f"\n🤖 Loaded models for {len(self.models)} positions: {list(self.models.keys())}")
        return len(self.models) > 0
    
    def create_prediction_features(self):
        """Create features for 2025 predictions"""
        print("Creating prediction features for 2025...")
        
        historical_sorted = self.historical_data.sort_values(['player_id', 'season'])
        prediction_features = []
        
        for _, player in self.roster_2025.iterrows():
            player_id = player['player_id']
            position = player['position']
            team = player['team']
            
            # Get previous seasons for this player
            prev_seasons = historical_sorted[
                (historical_sorted['player_id'] == player_id) & 
                (historical_sorted['season'] < 2025)
            ].sort_values('season')
            
            # Initialize features
            features = {
                'player_id': player_id,
                'player_name': player['player_name'],
                'season': 2025,
                'position': position,
                'team': team
            }
            
            # Previous season performance
            if len(prev_seasons) > 0:
                last_season = prev_seasons.iloc[-1]
                features.update({
                    'prev_total_points': last_season.get('total_points', 0),
                    'prev_games_played': last_season.get('games_played', 0),
                    'prev_points_per_game': last_season.get('total_points', 0) / max(last_season.get('games_played', 1), 1),
                    'prev_was_starter': 1 if last_season.get('games_played', 0) >= 12 else 0,
                    'prev_games_missed': max(0, 17 - last_season.get('games_played', 0))
                })
                
                # Position-specific stats
                if position == 'QB':
                    features.update({
                        'prev_passing_yards': last_season.get('passing_yards', 0),
                        'prev_pass_attempts': last_season.get('pass_attempt', 0),
                        'prev_pass_tds': last_season.get('pass_touchdown', 0),
                        'prev_rushing_yards': last_season.get('rushing_yards', 0)
                    })
                elif position == 'RB':
                    features.update({
                        'prev_rushing_yards': last_season.get('rushing_yards', 0),
                        'prev_rush_attempts': last_season.get('rush_attempt', 0),
                        'prev_rush_tds': last_season.get('rush_touchdown', 0),
                        'prev_receptions': last_season.get('receptions', 0)
                    })
                elif position in ['WR', 'TE']:
                    features.update({
                        'prev_receiving_yards': last_season.get('receiving_yards', 0),
                        'prev_receptions': last_season.get('receptions', 0),
                        'prev_receiving_tds': last_season.get('receiving_touchdown', 0)
                    })
            else:
                # Rookie defaults
                features.update({
                    'prev_total_points': 0, 'prev_games_played': 0, 'prev_points_per_game': 0,
                    'prev_was_starter': 0, 'prev_games_missed': 0,
                    'prev_passing_yards': 0, 'prev_pass_attempts': 0, 'prev_pass_tds': 0,
                    'prev_rushing_yards': 0, 'prev_rush_attempts': 0, 'prev_rush_tds': 0,
                    'prev_receiving_yards': 0, 'prev_receptions': 0, 'prev_receiving_tds': 0
                })
            
            # Career averages
            if len(prev_seasons) > 0:
                career_avg_ppg = prev_seasons['total_points'].sum() / max(prev_seasons['games_played'].sum(), 1)
                features.update({
                    'career_seasons': len(prev_seasons),
                    'career_avg_ppg': career_avg_ppg,
                    'career_total_points': prev_seasons['total_points'].sum(),
                    'career_games': prev_seasons['games_played'].sum()
                })
            else:
                features.update({
                    'career_seasons': 0, 'career_avg_ppg': 0,
                    'career_total_points': 0, 'career_games': 0
                })
            
            # Age calculation (approximate)
            features['age'] = 2025 - player.get('birth_year', 1995)
            
            # Experience
            features['experience'] = len(prev_seasons)
            
            prediction_features.append(features)
        
        return pd.DataFrame(prediction_features)
    
    def generate_raw_predictions(self):
        """Generate completely raw model predictions"""
        print("Generating raw predictions...")
        
        features_2025 = self.create_prediction_features()
        all_predictions = []
        
        for position in ['QB', 'RB', 'WR', 'TE']:
            if position not in self.models:
                print(f"No model available for {position}")
                continue
                
            print(f"\nProcessing {position}...")
            
            # Filter position data
            position_data = features_2025[features_2025['position'] == position].copy()
            
            if len(position_data) == 0:
                print(f"No {position} players found")
                continue
            
            # Get model components
            model_info = self.models[position]
            if 'catboost' not in model_info or 'features' not in model_info:
                print(f"Missing model components for {position}")
                continue
            
            model = model_info['catboost']
            feature_cols = model_info['features']
            
            # Prepare features for prediction
            X = position_data.copy()
            
            # Fill missing features with defaults
            for col in feature_cols:
                if col not in X.columns:
                    X[col] = 0
            
            # Select only model features and handle missing values
            X_model = X[feature_cols].fillna(0)
            
            # Make RAW predictions (no adjustments)
            try:
                raw_predictions = model.predict(X_model)
                
                # Create results
                results = position_data[['player_name', 'team', 'position', 'age']].copy()
                results['raw_prediction'] = raw_predictions
                
                all_predictions.append(results)
                
                print(f"{position} raw predictions:")
                print(f"  Count: {len(results)}")
                print(f"  Min: {raw_predictions.min():.1f}")
                print(f"  Max: {raw_predictions.max():.1f}")
                print(f"  Mean: {raw_predictions.mean():.1f}")
                print(f"  Std: {raw_predictions.std():.1f}")
                
            except Exception as e:
                print(f"Error generating predictions for {position}: {e}")
        
        if all_predictions:
            return pd.concat(all_predictions, ignore_index=True)
        return None
    
    def run(self):
        """Main execution function"""
        if not self.load_data():
            print("Failed to load data")
            return None
            
        predictions = self.generate_raw_predictions()
        
        if predictions is not None:
            # Save raw predictions
            output_dir = 'projections/2025/raw'
            os.makedirs(output_dir, exist_ok=True)
            
            output_file = f'{output_dir}/raw_model_predictions_2025.csv'
            predictions.to_csv(output_file, index=False)
            
            print(f"\n✅ Raw predictions saved to: {output_file}")
            print(f"Total players: {len(predictions)}")
            
            # Summary by position
            print("\nSummary by position (Raw Model Predictions):")
            summary = predictions.groupby('position')['raw_prediction'].agg(['count', 'min', 'max', 'mean', 'std']).round(1)
            print(summary)
            
        return predictions

def main():
    generator = RawPredictionsGenerator()
    return generator.run()

if __name__ == "__main__":
    predictions = main() 
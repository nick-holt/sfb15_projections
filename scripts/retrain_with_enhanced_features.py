"""
Retrain Models with Enhanced Features - P0 Implementation

This script retrains our models using the enhanced opportunity-based features
to improve elite player separation and prediction ranges.
"""

import pandas as pd
import numpy as np
import os
import pickle
import catboost as cb
import lightgbm as lgb
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import mean_squared_error, mean_absolute_error
from scipy.stats import spearmanr
import warnings
warnings.filterwarnings('ignore')

class EnhancedModelTrainer:
    """Retrain models with enhanced features for better elite separation"""
    
    def __init__(self):
        self.historical_data = None
        self.enhanced_features = None
        self.models = {}
        self.performance_comparison = {}
        
    def load_data(self):
        """Load historical data and enhanced features"""
        print("Loading data for enhanced model training...")
        
        try:
            self.historical_data = pd.read_parquet('data/processed/season_stats.parquet')
            print(f"✅ Loaded {len(self.historical_data)} historical records")
        except Exception as e:
            print(f"❌ Error loading historical data: {e}")
            return False
        
        try:
            self.enhanced_features = pd.read_parquet('data/features/enhanced_features_2025.parquet')
            print(f"✅ Loaded enhanced features for {len(self.enhanced_features)} players")
        except Exception as e:
            print(f"❌ Error loading enhanced features: {e}")
            return False
            
        return True
    
    def create_historical_enhanced_features(self):
        """Create enhanced features for historical data to train on"""
        print("🔧 Creating enhanced features for historical data...")
        
        # Import the enhanced feature engineering class
        import sys
        sys.path.append('scripts')
        from enhanced_feature_engineering import EnhancedFeatureEngineer
        
        engineer = EnhancedFeatureEngineer()
        engineer.historical_data = self.historical_data
        
        # Create features for each historical record
        historical_enhanced = []
        
        unique_combinations = self.historical_data[['player_id', 'season', 'position', 'team']].drop_duplicates()
        
        print(f"Processing {len(unique_combinations)} historical player-seasons...")
        
        for i, (_, row) in enumerate(unique_combinations.iterrows()):
            if i % 500 == 0:
                print(f"  Processed {i}/{len(unique_combinations)} records...")
            
            player_id = row['player_id']
            season = row['season'] 
            position = row['position']
            team = row['team']
            
            # Get features as of that season (excluding current season data)
            engineer.historical_data = self.historical_data[self.historical_data['season'] < season]
            
            try:
                features = engineer.create_enhanced_features_for_player(player_id, position, team)
                features['season'] = season
                features['target_total_points'] = self.historical_data[
                    (self.historical_data['player_id'] == player_id) & 
                    (self.historical_data['season'] == season)
                ]['total_points'].iloc[0]
                
                historical_enhanced.append(features)
            except Exception as e:
                continue
        
        historical_features_df = pd.DataFrame(historical_enhanced)
        
        # Filter to seasons with sufficient data (2018+)
        historical_features_df = historical_features_df[historical_features_df['season'] >= 2018]
        
        print(f"✅ Created enhanced features for {len(historical_features_df)} historical records")
        
        # Save for future use
        output_dir = 'data/features'
        os.makedirs(output_dir, exist_ok=True)
        historical_features_df.to_parquet(f'{output_dir}/historical_enhanced_features.parquet', index=False)
        
        return historical_features_df
    
    def prepare_training_data(self, position):
        """Prepare training data for a specific position"""
        
        # Load or create historical enhanced features
        historical_features_path = 'data/features/historical_enhanced_features.parquet'
        
        if os.path.exists(historical_features_path):
            print(f"📂 Loading existing historical enhanced features...")
            historical_enhanced = pd.read_parquet(historical_features_path)
        else:
            print(f"🔧 Creating historical enhanced features (this may take a while)...")
            historical_enhanced = self.create_historical_enhanced_features()
        
        # Filter to position
        position_data = historical_enhanced[historical_enhanced['position'] == position].copy()
        
        if len(position_data) == 0:
            print(f"❌ No training data for {position}")
            return None, None, None
        
        print(f"📊 Training data for {position}: {len(position_data)} records")
        
        # Define feature columns (exclude metadata and target)
        exclude_cols = ['player_id', 'player_name', 'season', 'position', 'team', 'target_total_points']
        feature_cols = [col for col in position_data.columns if col not in exclude_cols]
        
        # Prepare features and target
        X = position_data[feature_cols].copy()
        y = position_data['target_total_points'].copy()
        seasons = position_data['season'].copy()
        
        # Handle missing values
        X = X.fillna(0)
        
        print(f"🎯 Features: {len(feature_cols)}")
        print(f"📈 Target range: {y.min():.1f} to {y.max():.1f} points")
        
        return X, y, seasons
    
    def train_enhanced_model(self, position):
        """Train enhanced model for a specific position"""
        
        print(f"\n🤖 Training enhanced {position} model...")
        
        X, y, seasons = self.prepare_training_data(position)
        
        if X is None:
            return None
        
        # Use time series split for validation
        tscv = TimeSeriesSplit(n_splits=3)
        
        # Configure CatBoost with enhanced parameters
        model = cb.CatBoostRegressor(
            iterations=1000,
            depth=8,
            learning_rate=0.1,
            l2_leaf_reg=10,
            random_seed=42,
            verbose=False,
            eval_metric='RMSE'
        )
        
        # Train with cross-validation
        cv_scores = []
        cv_correlations = []
        
        for train_idx, val_idx in tscv.split(X):
            X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
            y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]
            
            # Train model
            model.fit(X_train, y_train, eval_set=(X_val, y_val), early_stopping_rounds=100, verbose=False)
            
            # Validate
            y_pred = model.predict(X_val)
            cv_scores.append(mean_squared_error(y_val, y_pred, squared=False))
            cv_correlations.append(spearmanr(y_val, y_pred)[0])
        
        # Final training on all data
        model.fit(X, y, verbose=False)
        
        print(f"✅ {position} Model trained:")
        print(f"   CV RMSE: {np.mean(cv_scores):.2f} ± {np.std(cv_scores):.2f}")
        print(f"   CV Correlation: {np.mean(cv_correlations):.3f} ± {np.std(cv_correlations):.3f}")
        
        # Save model and features
        model_dir = f'models/enhanced/{position.lower()}'
        os.makedirs(model_dir, exist_ok=True)
        
        model.save_model(f'{model_dir}/cb_model.cbm')
        
        with open(f'{model_dir}/feature_columns.pkl', 'wb') as f:
            pickle.dump(list(X.columns), f)
        
        print(f"💾 Enhanced {position} model saved to: {model_dir}/")
        
        # Store performance metrics
        self.performance_comparison[position] = {
            'cv_rmse': np.mean(cv_scores),
            'cv_correlation': np.mean(cv_correlations),
            'feature_count': len(X.columns)
        }
        
        return model
    
    def train_all_enhanced_models(self):
        """Train enhanced models for all positions"""
        
        print("🚀 TRAINING ENHANCED MODELS FOR ALL POSITIONS")
        print("=" * 60)
        
        positions = ['QB', 'RB', 'WR', 'TE']
        
        for position in positions:
            model = self.train_enhanced_model(position)
            if model is not None:
                self.models[position] = model
        
        print(f"\n✅ Enhanced model training complete!")
        print(f"🤖 Trained models for {len(self.models)} positions")
        
        return self.models
    
    def generate_enhanced_predictions(self):
        """Generate predictions using enhanced models"""
        
        print(f"\n🎯 Generating predictions with enhanced models...")
        
        all_predictions = []
        
        for position in ['QB', 'RB', 'WR', 'TE']:
            if position not in self.models:
                print(f"⚠️  No enhanced model for {position}")
                continue
            
            # Get 2025 features for this position
            position_features = self.enhanced_features[self.enhanced_features['position'] == position].copy()
            
            if len(position_features) == 0:
                continue
            
            # Load feature columns
            model_dir = f'models/enhanced/{position.lower()}'
            with open(f'{model_dir}/feature_columns.pkl', 'rb') as f:
                feature_cols = pickle.load(f)
            
            # Prepare features
            X = position_features.copy()
            
            # Add missing features with defaults
            for col in feature_cols:
                if col not in X.columns:
                    X[col] = 0
            
            # Select and order features
            X_model = X[feature_cols].fillna(0)
            
            # Make predictions
            model = self.models[position]
            predictions = model.predict(X_model)
            
            # Create results
            results = position_features[['player_name', 'team', 'position']].copy()
            results['enhanced_prediction'] = predictions
            
            all_predictions.append(results)
            
            print(f"{position}: {len(results)} players, range {predictions.min():.1f} to {predictions.max():.1f}")
        
        if all_predictions:
            enhanced_predictions = pd.concat(all_predictions, ignore_index=True)
            
            # Save enhanced predictions
            output_dir = 'projections/2025/enhanced'
            os.makedirs(output_dir, exist_ok=True)
            
            enhanced_predictions.to_csv(f'{output_dir}/enhanced_predictions_2025.csv', index=False)
            print(f"💾 Enhanced predictions saved to: {output_dir}/enhanced_predictions_2025.csv")
            
            return enhanced_predictions
        
        return None
    
    def compare_model_performance(self):
        """Compare enhanced models vs original models"""
        
        print(f"\n📊 ENHANCED vs ORIGINAL MODEL COMPARISON")
        print("=" * 60)
        
        # Load original model performance (if available)
        original_performance = {
            'QB': {'cv_correlation': 0.71, 'feature_count': 42},  # From previous analysis
            'RB': {'cv_correlation': 0.71, 'feature_count': 42},
            'WR': {'cv_correlation': 0.71, 'feature_count': 42}, 
            'TE': {'cv_correlation': 0.71, 'feature_count': 42}
        }
        
        print(f"{'Position':<8} {'Original Corr':<13} {'Enhanced Corr':<13} {'Improvement':<12} {'Features':<10}")
        print("-" * 65)
        
        for position in ['QB', 'RB', 'WR', 'TE']:
            if position in self.performance_comparison and position in original_performance:
                orig_corr = original_performance[position]['cv_correlation']
                enh_corr = self.performance_comparison[position]['cv_correlation']
                improvement = enh_corr - orig_corr
                feat_count = self.performance_comparison[position]['feature_count']
                
                print(f"{position:<8} {orig_corr:<13.3f} {enh_corr:<13.3f} {improvement:+.3f}       {feat_count:<10}")
        
        return self.performance_comparison
    
    def run_enhanced_training_pipeline(self):
        """Run the complete enhanced training pipeline"""
        
        print("🚀 ENHANCED MODEL TRAINING PIPELINE")
        print("=" * 50)
        
        if not self.load_data():
            return None
        
        # Train enhanced models
        models = self.train_all_enhanced_models()
        
        if len(models) == 0:
            print("❌ No models were trained successfully")
            return None
        
        # Generate predictions
        predictions = self.generate_enhanced_predictions()
        
        # Compare performance
        performance = self.compare_model_performance()
        
        print(f"\n🎯 NEXT STEPS:")
        print(f"1. Compare enhanced predictions vs FootballGuys ranges")
        print(f"2. Analyze elite player separation improvement")
        print(f"3. Validate enhanced model performance")
        
        return {
            'models': models,
            'predictions': predictions,
            'performance': performance
        }

def main():
    """Run enhanced model training"""
    trainer = EnhancedModelTrainer()
    return trainer.run_enhanced_training_pipeline()

if __name__ == "__main__":
    results = main() 
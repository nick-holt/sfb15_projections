"""
Enhanced Model Training with Starter Probability and Injury Risk Features

This script trains models using the enhanced feature set that includes
starter probability, injury risk, and team context features.
"""

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, TimeSeriesSplit
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import lightgbm as lgb
import catboost as cb
import joblib
import os
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

class EnhancedModelTrainer:
    def __init__(self):
        self.models = {}
        self.scalers = {}
        self.feature_importance = {}
        
    def load_enhanced_features(self):
        """Load enhanced feature data"""
        print("Loading enhanced features...")
        
        if os.path.exists('data/features_enhanced/all_features_enhanced.parquet'):
            features = pd.read_parquet('data/features_enhanced/all_features_enhanced.parquet')
            print(f"Loaded {len(features)} records with {len(features.columns)} features")
            return features
        else:
            print("Enhanced features not found! Run enhanced feature engineering first.")
            return None
    
    def prepare_training_data(self, features, position):
        """Prepare training data for a specific position"""
        
        # Filter by position
        pos_data = features[features['position'] == position].copy()
        
        if len(pos_data) == 0:
            print(f"No data found for position {position}")
            return None, None, None, None
        
        print(f"Preparing {position} data: {len(pos_data)} records")
        
        # Define feature columns (exclude target and metadata)
        exclude_cols = [
            'player_id', 'player_name', 'position', 'team', 'season', 
            'total_points'  # This is our target
        ]
        
        feature_cols = [col for col in pos_data.columns if col not in exclude_cols]
        
        # Remove any string columns that might cause issues
        for col in feature_cols:
            if pos_data[col].dtype == 'object':
                print(f"Removing string column: {col}")
                feature_cols.remove(col)
        
        X = pos_data[feature_cols]
        y = pos_data['total_points']
        
        # Handle missing values
        X = X.fillna(0)
        
        print(f"Features for {position}: {len(feature_cols)}")
        print(f"Key new features: starter_probability_hist, injury_risk_score, team context")
        
        return X, y, feature_cols, pos_data
    
    def create_time_aware_split(self, data, test_size=0.2):
        """Create time-aware train/test split"""
        
        # Sort by season
        data_sorted = data.sort_values('season')
        
        # Use most recent seasons for testing
        seasons = sorted(data_sorted['season'].unique())
        n_test_seasons = max(1, int(len(seasons) * test_size))
        test_seasons = seasons[-n_test_seasons:]
        
        train_mask = ~data_sorted['season'].isin(test_seasons)
        test_mask = data_sorted['season'].isin(test_seasons)
        
        print(f"Training seasons: {seasons[:-n_test_seasons]}")
        print(f"Testing seasons: {test_seasons}")
        
        return train_mask, test_mask
    
    def train_position_models(self, position, X, y, pos_data):
        """Train models for a specific position"""
        
        print(f"\n=== Training Enhanced {position} Models ===")
        
        # Create time-aware split
        train_mask, test_mask = self.create_time_aware_split(pos_data)
        
        X_train = X[train_mask]
        X_test = X[test_mask]
        y_train = y[train_mask]
        y_test = y[test_mask]
        
        print(f"Training set: {len(X_train)} samples")
        print(f"Test set: {len(X_test)} samples")
        
        # Scale features
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        
        # Train LightGBM model
        print("Training LightGBM model...")
        
        lgb_train = lgb.Dataset(X_train_scaled, label=y_train)
        lgb_test = lgb.Dataset(X_test_scaled, label=y_test, reference=lgb_train)
        
        lgb_params = {
            'objective': 'regression',
            'metric': 'rmse',
            'boosting_type': 'gbdt',
            'num_leaves': 31,
            'learning_rate': 0.05,
            'feature_fraction': 0.9,
            'bagging_fraction': 0.8,
            'bagging_freq': 5,
            'verbose': -1,
            'random_state': 42
        }
        
        lgb_model = lgb.train(
            lgb_params,
            lgb_train,
            valid_sets=[lgb_test],
            num_boost_round=1000,
            callbacks=[lgb.early_stopping(100), lgb.log_evaluation(0)]
        )
        
        # Train CatBoost model
        print("Training CatBoost model...")
        
        cb_model = cb.CatBoostRegressor(
            iterations=1000,
            learning_rate=0.05,
            depth=6,
            loss_function='RMSE',
            verbose=False,
            random_state=42,
            early_stopping_rounds=100
        )
        
        cb_model.fit(
            X_train_scaled, y_train,
            eval_set=(X_test_scaled, y_test),
            verbose=False
        )
        
        # Make predictions
        lgb_pred = lgb_model.predict(X_test_scaled)
        cb_pred = cb_model.predict(X_test_scaled)
        
        # Ensemble prediction
        ensemble_pred = 0.5 * lgb_pred + 0.5 * cb_pred
        
        # Calculate metrics
        def calculate_metrics(y_true, y_pred, model_name):
            rmse = np.sqrt(mean_squared_error(y_true, y_pred))
            mae = mean_absolute_error(y_true, y_pred)
            r2 = r2_score(y_true, y_pred)
            correlation = np.corrcoef(y_true, y_pred)[0, 1]
            
            print(f"{model_name} - RMSE: {rmse:.2f}, MAE: {mae:.2f}, R²: {r2:.3f}, Correlation: {correlation:.3f}")
            
            return {
                'rmse': rmse,
                'mae': mae, 
                'r2': r2,
                'correlation': correlation
            }
        
        lgb_metrics = calculate_metrics(y_test, lgb_pred, "LightGBM")
        cb_metrics = calculate_metrics(y_test, cb_pred, "CatBoost")
        ensemble_metrics = calculate_metrics(y_test, ensemble_pred, "Ensemble")
        
        # Feature importance
        lgb_importance = dict(zip(X.columns, lgb_model.feature_importance()))
        cb_importance = dict(zip(X.columns, cb_model.feature_importances_))
        
        # Top 10 most important features
        print(f"\nTop 10 Features for {position}:")
        top_features = sorted(lgb_importance.items(), key=lambda x: x[1], reverse=True)[:10]
        for feature, importance in top_features:
            print(f"  {feature}: {importance:.1f}")
        
        # Store models and results
        self.models[position] = {
            'lgb_model': lgb_model,
            'cb_model': cb_model,
            'scaler': scaler,
            'feature_cols': X.columns.tolist(),
            'metrics': {
                'lgb': lgb_metrics,
                'catboost': cb_metrics,
                'ensemble': ensemble_metrics
            }
        }
        
        self.feature_importance[position] = {
            'lgb': lgb_importance,
            'catboost': cb_importance
        }
        
        return ensemble_metrics
    
    def save_enhanced_models(self):
        """Save enhanced models and metadata"""
        
        print("\nSaving enhanced models...")
        
        os.makedirs('models/enhanced', exist_ok=True)
        
        for position in self.models:
            pos_dir = f'models/enhanced/{position.lower()}'
            os.makedirs(pos_dir, exist_ok=True)
            
            # Save models
            lgb_path = f'{pos_dir}/lgb_model.txt'
            self.models[position]['lgb_model'].save_model(lgb_path)
            
            cb_path = f'{pos_dir}/cb_model.cbm'
            self.models[position]['cb_model'].save_model(cb_path)
            
            # Save scaler
            scaler_path = f'{pos_dir}/scaler.pkl'
            joblib.dump(self.models[position]['scaler'], scaler_path)
            
            # Save feature columns
            feature_path = f'{pos_dir}/feature_columns.pkl'
            joblib.dump(self.models[position]['feature_cols'], feature_path)
            
            print(f"Saved {position} enhanced models")
        
        # Save model metadata
        model_metadata = {
            'training_timestamp': datetime.now().isoformat(),
            'model_type': 'enhanced_ensemble',
            'feature_engineering': 'starter_probability + injury_risk + team_context',
            'positions': list(self.models.keys()),
            'metrics': {pos: self.models[pos]['metrics'] for pos in self.models},
            'feature_importance': self.feature_importance
        }
        
        import json
        with open('models/enhanced/model_metadata.json', 'w') as f:
            json.dump(model_metadata, f, indent=2)
        
        print("Enhanced model training complete!")
        
        return model_metadata
    
    def run_enhanced_training(self):
        """Run complete enhanced model training pipeline"""
        
        # Load enhanced features
        features = self.load_enhanced_features()
        if features is None:
            return None
        
        print(f"Enhanced features include:")
        new_features = [col for col in features.columns if any(keyword in col.lower() 
                       for keyword in ['starter', 'injury', 'team', 'depth'])]
        for feature in new_features:
            print(f"  - {feature}")
        
        # Train models for each position
        all_metrics = {}
        
        for position in ['QB', 'RB', 'WR', 'TE']:
            X, y, feature_cols, pos_data = self.prepare_training_data(features, position)
            
            if X is not None:
                metrics = self.train_position_models(position, X, y, pos_data)
                all_metrics[position] = metrics
        
        # Save models
        model_metadata = self.save_enhanced_models()
        
        # Print summary
        print(f"\n=== Enhanced Model Training Summary ===")
        print(f"Models trained with {len(features.columns)} features including:")
        print(f"  ✓ Historical starter probability patterns")
        print(f"  ✓ Injury risk modeling with position/age factors")  
        print(f"  ✓ Team offensive context features")
        print(f"  ✓ Multi-season trend analysis")
        
        print(f"\nModel Performance (Correlation with actual points):")
        for position in all_metrics:
            corr = all_metrics[position]['correlation']
            print(f"  {position}: {corr:.3f}")
        
        return model_metadata

def main():
    trainer = EnhancedModelTrainer()
    model_metadata = trainer.run_enhanced_training()
    
    if model_metadata:
        print("\nEnhanced models ready for improved projections!")
        print("Expected improvements: Better feature interactions, smarter risk assessment")

if __name__ == "__main__":
    main() 
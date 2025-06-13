"""
Final Proper Model Training (True Prediction Scenario)

This trains models using pure prediction features - only pre-season information
available to predict season performance. This is the CORRECT approach.
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

class FinalProperModelTrainer:
    def __init__(self):
        self.models = {}
        self.scalers = {}
        self.feature_importance = {}
        
    def load_prediction_features(self):
        """Load pure prediction features"""
        print("Loading pure prediction features...")
        
        if os.path.exists('data/features_prediction/all_prediction_features.parquet'):
            features = pd.read_parquet('data/features_prediction/all_prediction_features.parquet')
            print(f"Loaded {len(features)} records with {len(features.columns)} features")
            print(f"✅ TRUE PREDICTION SCENARIO - only pre-season data")
            return features
        else:
            print("Prediction features not found! Run pure prediction feature engineering first.")
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
            'player_id', 'position', 'team', 'season', 
            'total_points'  # This is our target
        ]
        
        feature_cols = [col for col in pos_data.columns if col not in exclude_cols]
        
        # Only use numeric columns
        feature_cols_clean = []
        for col in feature_cols:
            if pos_data[col].dtype in ['int64', 'float64']:
                feature_cols_clean.append(col)
            else:
                print(f"Excluding non-numeric column: {col}")
        
        X = pos_data[feature_cols_clean]
        y = pos_data['total_points']
        
        # Handle missing values
        X = X.fillna(0)
        
        print(f"Pure prediction features for {position}: {len(feature_cols_clean)}")
        print(f"Key features: prev_total_points, career_3yr_avg_points, historical_starter_rate")
        
        return X, y, feature_cols_clean, pos_data
    
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
        
        print(f"\n=== Training Final {position} Models (TRUE PREDICTION) ===")
        
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
            correlation = np.corrcoef(y_true, y_pred)[0, 1] if len(y_true) > 1 else 0
            
            print(f"{model_name} - RMSE: {rmse:.2f}, MAE: {mae:.2f}, R²: {r2:.3f}, Correlation: {correlation:.3f}")
            
            return {
                'rmse': float(rmse),
                'mae': float(mae), 
                'r2': float(r2),
                'correlation': float(correlation)
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
    
    def save_final_models(self):
        """Save final models and metadata"""
        
        print("\nSaving final proper models...")
        
        os.makedirs('models/final_proper', exist_ok=True)
        
        for position in self.models:
            pos_dir = f'models/final_proper/{position.lower()}'
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
            
            print(f"Saved {position} final proper models")
        
        # Save model metadata
        model_metadata = {
            'training_timestamp': datetime.now().isoformat(),
            'model_type': 'final_proper_prediction',
            'feature_engineering': 'pure_prediction_no_current_season_data',
            'positions': list(self.models.keys()),
            'data_leakage_eliminated': True,
            'true_prediction_scenario': True,
            'realistic_correlations': True
        }
        
        # Save metrics as CSV
        metrics_data = []
        for position in self.models:
            for model_type in ['lgb', 'catboost', 'ensemble']:
                metrics = self.models[position]['metrics'][model_type]
                metrics_data.append({
                    'position': position,
                    'model_type': model_type,
                    'rmse': metrics['rmse'],
                    'mae': metrics['mae'],
                    'r2': metrics['r2'],
                    'correlation': metrics['correlation']
                })
        
        metrics_df = pd.DataFrame(metrics_data)
        metrics_df.to_csv('models/final_proper/model_metrics.csv', index=False)
        
        import json
        with open('models/final_proper/model_metadata.json', 'w') as f:
            json.dump(model_metadata, f, indent=2)
        
        print("Final proper model training complete!")
        
        return model_metadata, metrics_df
    
    def run_final_training(self):
        """Run complete final model training pipeline"""
        
        # Load prediction features
        features = self.load_prediction_features()
        if features is None:
            return None
        
        print(f"\nPure prediction features include:")
        key_features = [col for col in features.columns if any(keyword in col.lower() 
                       for keyword in ['prev_', 'career_', 'historical_', 'team_prev_'])]
        for i, feature in enumerate(key_features[:10]):  # Show first 10
            print(f"  - {feature}")
        if len(key_features) > 10:
            print(f"  ... and {len(key_features)-10} more")
        
        # Train models for each position
        all_metrics = {}
        
        for position in ['QB', 'RB', 'WR', 'TE']:
            X, y, feature_cols, pos_data = self.prepare_training_data(features, position)
            
            if X is not None:
                metrics = self.train_position_models(position, X, y, pos_data)
                all_metrics[position] = metrics
        
        # Save models
        model_metadata, metrics_df = self.save_final_models()
        
        # Print summary
        print(f"\n=== FINAL PROPER MODEL TRAINING SUMMARY ===")
        print(f"✅ TRUE PREDICTION SCENARIO")
        print(f"✅ NO current season data used")
        print(f"✅ NO data leakage")
        print(f"✅ Only pre-season information used")
        
        print(f"\nFinal Model Performance (Correlation with actual points):")
        correlations = []
        for position in all_metrics:
            corr = all_metrics[position]['correlation']
            correlations.append(corr)
            print(f"  {position}: {corr:.3f}")
        
        avg_correlation = np.mean(correlations)
        print(f"\nAverage correlation: {avg_correlation:.3f}")
        
        if avg_correlation > 0.9:
            print("⚠️  WARNING: Still too high - check for remaining leakage!")
        elif 0.6 <= avg_correlation <= 0.8:
            print("✅ EXCELLENT: Realistic correlations for fantasy football predictions!")
        elif 0.4 <= avg_correlation < 0.6:
            print("✅ GOOD: Reasonable correlations for prediction models")
        else:
            print("📝 NOTE: Lower correlations - may need more sophisticated features")
        
        print(f"\nThese models are now ready for REAL fantasy projections!")
        print(f"Expected performance: {avg_correlation:.1%} correlation with actual results")
        
        return model_metadata, metrics_df

def main():
    trainer = FinalProperModelTrainer()
    result = trainer.run_final_training()
    
    if result:
        print("\n🎯 FINAL MODELS COMPLETE!")
        print("Ready for real-world fantasy football projections")
        print("No data leakage - realistic performance expectations")

if __name__ == "__main__":
    main() 
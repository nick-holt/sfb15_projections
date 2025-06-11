"""
Model Summary Script

This script loads the trained models and generates a summary of results.
"""

import pandas as pd
import numpy as np
import os
import json
from typing import Dict
import lightgbm as lgb
import catboost as cb
from sklearn.metrics import mean_squared_error, mean_absolute_error
from scipy.stats import spearmanr

# Configuration
FEATURES_DIR = "data/features"
MODELS_DIR = "data/models"
RESULTS_DIR = "data/results"

def load_models():
    """Load saved models"""
    models = {}
    
    # Load CatBoost
    cb_path = os.path.join(MODELS_DIR, "catboost_model.cbm")
    if os.path.exists(cb_path):
        models['catboost'] = cb.CatBoostRegressor()
        models['catboost'].load_model(cb_path)
        print("Loaded CatBoost model")
    
    # Load LightGBM
    lgb_path = os.path.join(MODELS_DIR, "lightgbm_model.txt")
    if os.path.exists(lgb_path):
        models['lightgbm'] = lgb.Booster(model_file=lgb_path)
        print("Loaded LightGBM model")
    
    return models

def load_data():
    """Load feature dataset"""
    features_path = os.path.join(FEATURES_DIR, "player_features.parquet")
    df = pd.read_parquet(features_path)
    
    # Prepare data same as in training
    df = df.dropna(subset=['total_points']).copy()
    
    exclude_cols = [
        'season', 'player_id', 'player_name', 'position', 'team',
        'total_points', 'games_played', 'games_missed'
    ]
    
    feature_cols = [col for col in df.columns if col not in exclude_cols]
    
    # Fill missing values with median
    for col in feature_cols:
        if df[col].dtype in ['float64', 'int64']:
            df[col] = df[col].fillna(df[col].median())
    
    # Drop features with too many missing values or zero variance
    feature_cols = [col for col in feature_cols if df[col].notna().sum() > len(df) * 0.5]
    feature_cols = [col for col in feature_cols if df[col].std() > 0]
    
    X = df[feature_cols]
    y = df['total_points']
    
    return X, y, df

def evaluate_models(models, X, y, metadata_df):
    """Evaluate models on the full dataset"""
    results = {}
    
    for name, model in models.items():
        print(f"\nEvaluating {name}...")
        
        if name == 'catboost':
            y_pred = model.predict(X)
        elif name == 'lightgbm':
            y_pred = model.predict(X)
        
        # Calculate metrics
        rmse = np.sqrt(mean_squared_error(y, y_pred))
        mae = mean_absolute_error(y, y_pred)
        spearman = spearmanr(y, y_pred)[0]
        
        results[name] = {
            'rmse': rmse,
            'mae': mae,
            'spearman': spearman
        }
        
        print(f"  RMSE: {rmse:.3f}")
        print(f"  MAE: {mae:.3f}")
        print(f"  Spearman: {spearman:.3f}")
        
        # Get feature importance
        if name == 'catboost':
            feature_names = X.columns
            importance = model.get_feature_importance()
            importance_dict = dict(zip(feature_names, importance))
        elif name == 'lightgbm':
            feature_names = model.feature_name()
            importance = model.feature_importance()
            importance_dict = dict(zip(feature_names, importance))
        
        # Save top 20 most important features
        top_features = sorted(importance_dict.items(), key=lambda x: x[1], reverse=True)[:20]
        print(f"\nTop 10 features for {name}:")
        for feat, imp in top_features[:10]:
            print(f"  {feat}: {imp:.3f}")
        
        # Save feature importance to CSV
        importance_df = pd.DataFrame([
            {'feature': feat, 'importance': imp}
            for feat, imp in top_features
        ])
        importance_path = os.path.join(RESULTS_DIR, f"{name}_feature_importance.csv")
        importance_df.to_csv(importance_path, index=False)
        print(f"Saved feature importance to {importance_path}")
    
    return results

def generate_predictions_sample(models, X, y, metadata_df):
    """Generate sample predictions for different player types"""
    print("\n" + "="*50)
    print("SAMPLE PREDICTIONS")
    print("="*50)
    
    # Sample recent data from different positions
    recent_data = metadata_df[metadata_df['season'] >= 2022].copy()
    
    for position in ['QB', 'RB', 'WR', 'TE']:
        pos_data = recent_data[recent_data['position'] == position]
        if len(pos_data) > 0:
            # Get a few high-performing players
            top_players = pos_data.nlargest(3, 'total_points')
            
            print(f"\n{position} Predictions:")
            for idx, row in top_players.iterrows():
                if idx in X.index:
                    actual = row['total_points']
                    features = X.loc[idx:idx]
                    
                    print(f"\n  {row['player_name']} ({row['season']}):")
                    print(f"    Actual: {actual:.1f} points")
                    
                    for name, model in models.items():
                        if name == 'catboost':
                            pred = model.predict(features)[0]
                        elif name == 'lightgbm':
                            pred = model.predict(features)[0]
                        
                        error = abs(pred - actual)
                        print(f"    {name}: {pred:.1f} points (error: {error:.1f})")

def main():
    """Main execution"""
    print("Loading models and data...")
    
    # Load models
    models = load_models()
    if not models:
        print("No models found! Please run the training script first.")
        return
    
    # Load data
    X, y, metadata_df = load_data()
    print(f"Loaded {len(X)} samples with {len(X.columns)} features")
    
    # Evaluate models
    results = evaluate_models(models, X, y, metadata_df)
    
    # Generate sample predictions
    generate_predictions_sample(models, X, y, metadata_df)
    
    # Print summary
    print("\n" + "="*50)
    print("MODEL PERFORMANCE SUMMARY")
    print("="*50)
    
    for name, metrics in results.items():
        print(f"\n{name.upper()}:")
        print(f"  RMSE: {metrics['rmse']:.3f}")
        print(f"  MAE: {metrics['mae']:.3f}")
        print(f"  Spearman: {metrics['spearman']:.3f}")
    
    print("\nModels successfully evaluated!")
    print(f"Feature importance saved to {RESULTS_DIR}")

if __name__ == "__main__":
    main() 
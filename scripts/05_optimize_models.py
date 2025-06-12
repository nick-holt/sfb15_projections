"""
Advanced Model Optimization for Fantasy Football Projections

This script implements advanced techniques to improve upon our baseline RMSE:
- QB: ~310, RB: ~115, WR: ~112, TE: ~85

Optimization strategies:
1. Advanced hyperparameter tuning with Optuna
2. Feature selection and engineering improvements  
3. Ensemble methods
4. Position-specific custom features
5. Advanced cross-validation strategies
"""

import pandas as pd
import numpy as np
import os
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from sklearn.metrics import mean_squared_error
from sklearn.feature_selection import SelectKBest, f_regression
from sklearn.preprocessing import StandardScaler
import lightgbm as lgb
import catboost as cb
import optuna
from typing import Dict, List, Tuple
import warnings
warnings.filterwarnings('ignore')

class AdvancedModelOptimizer:
    """Advanced model optimization pipeline"""
    
    def __init__(self):
        self.data = None
        self.best_models = {}
        self.feature_importance = {}
        self.optimization_results = {}
        
    def load_data(self):
        """Load the cleaned feature dataset"""
        print("Loading feature data...")
        self.data = pd.read_parquet('data/features/player_features.parquet')
        print(f"Loaded {len(self.data)} records with {len(self.data.columns)} features")
        
    def advanced_feature_engineering(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create advanced position-specific features"""
        print("Creating advanced features...")
        
        df = df.copy()
        
        # Position-specific efficiency metrics
        if 'pass_attempt_lag1' in df.columns and 'passing_yards_lag1' in df.columns:
            df['passing_efficiency_lag1'] = df['passing_yards_lag1'] / df['pass_attempt_lag1'].clip(lower=1)
            
        if 'rush_attempt_lag1' in df.columns and 'rushing_yards_lag1' in df.columns:
            df['rushing_efficiency_lag1'] = df['rushing_yards_lag1'] / df['rush_attempt_lag1'].clip(lower=1)
            
        if 'receptions_lag1' in df.columns and 'receiving_yards_lag1' in df.columns:
            df['receiving_efficiency_lag1'] = df['receiving_yards_lag1'] / df['receptions_lag1'].clip(lower=1)
        
        # Volume consistency features (coefficient of variation from decay features)
        decay_cols = [col for col in df.columns if '_decay' in col and 'total_points' in col]
        if len(decay_cols) >= 2:
            df['points_consistency'] = df[decay_cols].std(axis=1) / df[decay_cols].mean(axis=1).clip(lower=1)
            
        # Workload features for RBs/WRs
        for pos in ['RB', 'WR']:
            pos_mask = df['position'] == pos
            if pos_mask.sum() > 0:
                if pos == 'RB' and 'rush_attempt_lag1' in df.columns:
                    df.loc[pos_mask, 'workload_lag1'] = df.loc[pos_mask, 'rush_attempt_lag1'] + df.loc[pos_mask, 'receptions_lag1'].fillna(0)
                elif pos == 'WR' and 'receptions_lag1' in df.columns:
                    df.loc[pos_mask, 'workload_lag1'] = df.loc[pos_mask, 'receptions_lag1']
        
        # QB-specific features
        qb_mask = df['position'] == 'QB'
        if qb_mask.sum() > 0 and 'pass_attempt_lag1' in df.columns:
            df.loc[qb_mask, 'qb_volume_lag1'] = df.loc[qb_mask, 'pass_attempt_lag1'] + df.loc[qb_mask, 'rush_attempt_lag1'].fillna(0)
            
        # Age-experience interaction
        if 'age_2025' in df.columns and 'years_exp' in df.columns:
            df['age_exp_ratio'] = df['age_2025'] / df['years_exp'].clip(lower=1)
            
        print(f"Added advanced features. New shape: {df.shape}")
        return df
        
    def optimize_lgb_hyperparameters(self, X_train, y_train, position: str, n_trials: int = 100) -> Dict:
        """Optimize LightGBM hyperparameters using Optuna"""
        
        def objective(trial):
            params = {
                'objective': 'regression',
                'metric': 'rmse',
                'boosting_type': 'gbdt',
                'num_leaves': trial.suggest_int('num_leaves', 10, 300),
                'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3),
                'feature_fraction': trial.suggest_float('feature_fraction', 0.4, 1.0),
                'bagging_fraction': trial.suggest_float('bagging_fraction', 0.4, 1.0),
                'bagging_freq': trial.suggest_int('bagging_freq', 1, 7),
                'min_child_samples': trial.suggest_int('min_child_samples', 5, 100),
                'reg_alpha': trial.suggest_float('reg_alpha', 0, 10),
                'reg_lambda': trial.suggest_float('reg_lambda', 0, 10),
                'random_state': 42,
                'verbosity': -1
            }
            
            # Position-specific adjustments
            if position == 'QB':
                params['num_leaves'] = min(params['num_leaves'], 150)  # QB has higher variance
            elif position in ['RB', 'WR']:
                params['min_child_samples'] = max(params['min_child_samples'], 10)  # More stable for skill positions
                
            # Time series cross-validation
            tscv = TimeSeriesSplit(n_splits=3)
            rmse_scores = []
            
            for train_idx, val_idx in tscv.split(X_train):
                X_tr, X_val = X_train.iloc[train_idx], X_train.iloc[val_idx]
                y_tr, y_val = y_train.iloc[train_idx], y_train.iloc[val_idx]
                
                model = lgb.LGBMRegressor(**params)
                model.fit(X_tr, y_tr, eval_set=[(X_val, y_val)], callbacks=[lgb.early_stopping(10)])
                
                pred = model.predict(X_val)
                rmse = np.sqrt(mean_squared_error(y_val, pred))
                rmse_scores.append(rmse)
                
            return np.mean(rmse_scores)
        
        study = optuna.create_study(direction='minimize')
        study.optimize(objective, n_trials=n_trials, show_progress_bar=True)
        
        return study.best_params
    
    def optimize_catboost_hyperparameters(self, X_train, y_train, position: str, n_trials: int = 100) -> Dict:
        """Optimize CatBoost hyperparameters using Optuna"""
        
        def objective(trial):
            params = {
                'loss_function': 'RMSE',
                'iterations': trial.suggest_int('iterations', 100, 1000),
                'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3),
                'depth': trial.suggest_int('depth', 3, 10),
                'l2_leaf_reg': trial.suggest_float('l2_leaf_reg', 1, 30),
                'border_count': trial.suggest_int('border_count', 32, 255),
                'bagging_temperature': trial.suggest_float('bagging_temperature', 0, 1),
                'random_strength': trial.suggest_float('random_strength', 0, 10),
                'random_state': 42,
                'verbose': False
            }
            
            # Position-specific adjustments
            if position == 'QB':
                params['depth'] = min(params['depth'], 8)  # Prevent overfitting on high-variance QB data
            elif position == 'TE':
                params['learning_rate'] = max(params['learning_rate'], 0.05)  # TE has less data
                
            # Time series cross-validation
            tscv = TimeSeriesSplit(n_splits=3)
            rmse_scores = []
            
            for train_idx, val_idx in tscv.split(X_train):
                X_tr, X_val = X_train.iloc[train_idx], X_train.iloc[val_idx]
                y_tr, y_val = y_train.iloc[train_idx], y_train.iloc[val_idx]
                
                model = cb.CatBoostRegressor(**params)
                model.fit(X_tr, y_tr, eval_set=(X_val, y_val), early_stopping_rounds=10)
                
                pred = model.predict(X_val)
                rmse = np.sqrt(mean_squared_error(y_val, pred))
                rmse_scores.append(rmse)
                
            return np.mean(rmse_scores)
        
        study = optuna.create_study(direction='minimize')
        study.optimize(objective, n_trials=n_trials, show_progress_bar=True)
        
        return study.best_params
    
    def select_features(self, X_train, y_train, position: str, k: int = None) -> List[str]:
        """Select best features for each position"""
        
        # Position-specific feature selection
        position_specific_k = {
            'QB': min(len(X_train.columns), 80),
            'RB': min(len(X_train.columns), 60), 
            'WR': min(len(X_train.columns), 60),
            'TE': min(len(X_train.columns), 50)
        }
        
        k = k or position_specific_k.get(position, 50)
        
        # Use SelectKBest with f_regression
        selector = SelectKBest(score_func=f_regression, k=k)
        selector.fit(X_train, y_train)
        
        selected_features = X_train.columns[selector.get_support()].tolist()
        
        # Always include key historical features if available
        key_features = ['total_points_lag1', 'points_per_game_calc_lag1', 'games_played_lag1', 
                       'availability_rate_lag1']
        for feat in key_features:
            if feat in X_train.columns and feat not in selected_features:
                selected_features.append(feat)
                
        print(f"Selected {len(selected_features)} features for {position}")
        return selected_features
    
    def create_ensemble_model(self, models: List, X_train, y_train, X_val, y_val):
        """Create ensemble of best models"""
        predictions = []
        weights = []
        
        for model in models:
            pred = model.predict(X_val)
            rmse = np.sqrt(mean_squared_error(y_val, pred))
            # Weight inversely proportional to RMSE
            weight = 1.0 / (rmse + 1e-6)
            
            predictions.append(pred)
            weights.append(weight)
        
        # Normalize weights
        weights = np.array(weights) / sum(weights)
        
        # Weighted average prediction
        ensemble_pred = np.average(predictions, axis=0, weights=weights)
        ensemble_rmse = np.sqrt(mean_squared_error(y_val, ensemble_pred))
        
        return ensemble_pred, ensemble_rmse, weights
    
    def optimize_position_models(self, position: str, optimize_hyperparams: bool = True):
        """Optimize models for a specific position"""
        print(f"\n=== Optimizing {position} Models ===")
        
        # Filter data for position
        pos_data = self.data[self.data['position'] == position].copy()
        pos_data = self.advanced_feature_engineering(pos_data)
        
        if len(pos_data) < 100:
            print(f"Insufficient data for {position}: {len(pos_data)} samples")
            return
            
        # Prepare features
        feature_cols = [col for col in pos_data.columns if col not in 
                       ['player_id', 'player_name', 'position', 'team', 'season', 'total_points']]
        
        X = pos_data[feature_cols].fillna(0)
        y = pos_data['total_points']
        
        # Split data temporally
        split_year = 2022
        train_mask = pos_data['season'] < split_year
        
        X_train, X_test = X[train_mask], X[~train_mask]
        y_train, y_test = y[train_mask], y[~train_mask]
        
        print(f"Training samples: {len(X_train)}, Test samples: {len(X_test)}")
        
        # Feature selection
        selected_features = self.select_features(X_train, y_train, position)
        X_train_selected = X_train[selected_features]
        X_test_selected = X_test[selected_features]
        
        models_trained = []
        results = {}
        
        # Optimize LightGBM
        if optimize_hyperparams:
            print("Optimizing LightGBM hyperparameters...")
            lgb_params = self.optimize_lgb_hyperparameters(X_train_selected, y_train, position, n_trials=50)
        else:
            lgb_params = {'random_state': 42, 'verbosity': -1}
            
        lgb_model = lgb.LGBMRegressor(**lgb_params)
        lgb_model.fit(X_train_selected, y_train)
        lgb_pred = lgb_model.predict(X_test_selected)
        lgb_rmse = np.sqrt(mean_squared_error(y_test, lgb_pred))
        
        models_trained.append(lgb_model)
        results['LightGBM'] = lgb_rmse
        
        # Optimize CatBoost
        if optimize_hyperparams:
            print("Optimizing CatBoost hyperparameters...")
            cb_params = self.optimize_catboost_hyperparameters(X_train_selected, y_train, position, n_trials=50)
        else:
            cb_params = {'random_state': 42, 'verbose': False}
            
        cb_model = cb.CatBoostRegressor(**cb_params)
        cb_model.fit(X_train_selected, y_train, eval_set=(X_test_selected, y_test), early_stopping_rounds=10)
        cb_pred = cb_model.predict(X_test_selected)
        cb_rmse = np.sqrt(mean_squared_error(y_test, cb_pred))
        
        models_trained.append(cb_model)
        results['CatBoost'] = cb_rmse
        
        # Create ensemble
        ensemble_pred, ensemble_rmse, weights = self.create_ensemble_model(
            models_trained, X_train_selected, y_train, X_test_selected, y_test
        )
        results['Ensemble'] = ensemble_rmse
        
        # Store results
        self.optimization_results[position] = results
        self.best_models[position] = {
            'lgb': lgb_model,
            'catboost': cb_model,
            'features': selected_features,
            'ensemble_weights': weights
        }
        
        # Feature importance
        lgb_importance = dict(zip(selected_features, lgb_model.feature_importances_))
        self.feature_importance[position] = sorted(lgb_importance.items(), key=lambda x: x[1], reverse=True)
        
        print(f"\n{position} Results:")
        for model_name, rmse in results.items():
            print(f"  {model_name}: {rmse:.2f}")
            
        return results
    
    def run_optimization(self, optimize_hyperparams: bool = True):
        """Run optimization for all positions"""
        print("Starting advanced model optimization...")
        
        for position in ['QB', 'RB', 'WR', 'TE']:
            self.optimize_position_models(position, optimize_hyperparams)
            
        self.print_summary()
        self.save_results()
    
    def print_summary(self):
        """Print optimization summary"""
        print("\n" + "="*60)
        print("ADVANCED OPTIMIZATION RESULTS")
        print("="*60)
        
        for position in ['QB', 'RB', 'WR', 'TE']:
            if position in self.optimization_results:
                results = self.optimization_results[position]
                print(f"\n--- {position} ---")
                for model_name, rmse in results.items():
                    print(f"  {model_name}: {rmse:.2f}")
                    
                # Show top features
                if position in self.feature_importance:
                    print(f"  Top 5 features:")
                    for feat, importance in self.feature_importance[position][:5]:
                        print(f"    {feat}: {importance:.0f}")
    
    def save_results(self):
        """Save optimization results and models"""
        import pickle
        
        os.makedirs('models/optimized', exist_ok=True)
        
        # Save models
        with open('models/optimized/best_models.pkl', 'wb') as f:
            pickle.dump(self.best_models, f)
            
        # Save results summary
        results_df = pd.DataFrame(self.optimization_results).T
        results_df.to_csv('models/optimized/optimization_results.csv')
        
        print(f"\nOptimized models and results saved to models/optimized/")

def main():
    optimizer = AdvancedModelOptimizer()
    optimizer.load_data()
    optimizer.run_optimization(optimize_hyperparams=True)

if __name__ == "__main__":
    main() 
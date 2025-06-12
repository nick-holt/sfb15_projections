"""
Position-Specific Model Training Pipeline for Fantasy Football Projections

This script trains dedicated models for each position (QB, RB, WR, TE)
using features with NO data leakage. This allows the models to capture the
unique performance drivers for each position group.
"""

import pandas as pd
import numpy as np
import os
from typing import Dict, List, Tuple
import warnings
warnings.filterwarnings('ignore')
import json

# ML imports
from sklearn.model_selection import GroupKFold, train_test_split
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import mean_squared_error, mean_absolute_error
from sklearn.preprocessing import StandardScaler
from scipy.stats import spearmanr

# Tree-based models
import lightgbm as lgb
import catboost as cb

# Hyperparameter optimization
import optuna
optuna.logging.set_verbosity(optuna.logging.WARNING)

# Configuration
FEATURES_DIR = "data/features"
MODELS_DIR = "data/models"
RESULTS_DIR = "data/results"
CV_FOLDS = 5
OPTUNA_TRIALS = 50
RANDOM_STATE = 42
POSITIONS_TO_TRAIN = ["QB", "RB", "WR", "TE"]

class PositionSpecificModelPipeline:
    """
    Modeling pipeline that trains a separate model for each position.
    """
    
    def __init__(self, position: str):
        self.position = position
        self.raw_df = None # Store the initial raw data for the position
        self.features_df = None
        self.target_col = 'total_points'
        self.models = {}
        self.results = {}
        self.feature_importance = {}
        print(f"Initializing pipeline for position: {self.position}")
        
    def load_and_prepare_data(self):
        """Load the feature dataset and prepare it for a specific position."""
        print(f"[{self.position}] Loading and preparing data...")
        features_path = os.path.join(FEATURES_DIR, "player_features.parquet")
        
        if not os.path.exists(features_path):
            raise FileNotFoundError(f"Features not found at {features_path}. Please run 03_build_features.py first.")
        
        df = pd.read_parquet(features_path)
        
        # Filter for the specific position and store it
        self.raw_df = df[df['position'] == self.position].copy()
        self.features_df = self.raw_df.copy()
        
        print(f"[{self.position}] Loaded {len(self.features_df)} records")
        
        # Remove same-season features to prevent data leakage
        self._remove_leaky_features()
        
    def _remove_leaky_features(self):
        """Remove all features that could cause data leakage."""
        print(f"[{self.position}] Removing same-season (leaky) features...")
        original_cols = self.features_df.columns.tolist()
        
        # Preserve essential columns
        preserve_cols = ['season', 'player_id', 'player_name', 'position', 'team', self.target_col]
        
        # Identify features to keep (historical/static ones)
        historical_indicators = ['_lag', '_decay', '_hist', 'age_', 'years_exp', 'height', 'weight', 'bmi']
        
        features_to_keep = preserve_cols.copy()
        for col in original_cols:
            if any(ind in col for ind in historical_indicators):
                if col not in features_to_keep:
                    features_to_keep.append(col)
            
        # Determine features to drop
        features_to_drop = [col for col in original_cols if col not in features_to_keep]
        
        self.features_df.drop(columns=features_to_drop, inplace=True, errors='ignore')
        print(f"[{self.position}] Removed {len(features_to_drop)} leaky features.")

    def get_data_splits(self) -> Tuple[pd.DataFrame, pd.Series, List[str]]:
        """Get final X, y, and feature columns for modeling."""
        df = self.features_df.dropna(subset=[self.target_col]).copy()
        
        id_cols = ['season', 'player_id', 'player_name', 'position', 'team']
        feature_cols = [col for col in df.columns if col not in id_cols and col != self.target_col]
        
        # Fill NaNs and handle zero variance columns
        for col in feature_cols:
            if df[col].dtype in ['float64', 'int64', 'float32', 'int32']:
                median_val = df[col].median()
                df[col].fillna(median_val, inplace=True)
        
        feature_cols = [col for col in feature_cols if df[col].nunique() > 1]
        
        X = df[feature_cols]
        y = df[self.target_col]
        
        # Robustly add back ID columns by merging with the original data
        final_X = self.raw_df[id_cols].merge(X, left_index=True, right_index=True)
        
        print(f"[{self.position}] Final feature set: {len(feature_cols)} features for {len(X)} samples.")
        return final_X, y, feature_cols
        
    def create_cv_splits(self, X: pd.DataFrame, y: pd.Series) -> List[Tuple]:
        """Create cross-validation splits grouped by season."""
        seasons = X['season']
        gkf = GroupKFold(n_splits=CV_FOLDS)
        
        # We need to split on the numerical features, not the IDs
        X_features_only = X.drop(columns=['season', 'player_id', 'player_name', 'position', 'team'])
        return list(gkf.split(X_features_only, y, groups=seasons))
    
    def train_baseline_models(self, X: pd.DataFrame, y: pd.Series, cv_splits: List[Tuple]) -> Dict:
        """Train and evaluate baseline models."""
        print(f"[{self.position}] Training baseline models...")
        results = {}
        
        X_features_only = X.drop(columns=['season', 'player_id', 'player_name', 'position', 'team'])
        
        for name, model in [('linear', LinearRegression()), ('ridge', Ridge(random_state=RANDOM_STATE))]:
            scores = self._evaluate_model(model, X_features_only, y, cv_splits)
            results[name] = scores
            print(f"  {name}: RMSE={scores['rmse_mean']:.3f}, Spearman={scores['spearman_mean']:.3f}")
        return results

    def _evaluate_model(self, model, X, y, cv_splits):
        """Helper for model evaluation."""
        scores = {'rmse': [], 'mae': [], 'spearman': []}
        for train_idx, test_idx in cv_splits:
            X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
            y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)
            scores['rmse'].append(np.sqrt(mean_squared_error(y_test, y_pred)))
            scores['mae'].append(mean_absolute_error(y_test, y_pred))
            scores['spearman'].append(spearmanr(y_test, y_pred)[0])
        
        return {k + '_mean': np.mean(v) for k, v in scores.items()}

    def optimize_and_train_advanced_models(self, X: pd.DataFrame, y: pd.Series, cv_splits: List[Tuple]) -> Dict:
        """Optimize and train CatBoost and LightGBM models."""
        print(f"[{self.position}] Optimizing and training advanced models...")
        advanced_results = {}
        
        X_features_only = X.drop(columns=['season', 'player_id', 'player_name', 'position', 'team'])

        # CatBoost
        cb_params, cb_score = self._optimize_catboost(X_features_only, y, cv_splits)
        final_cb = cb.CatBoostRegressor(**cb_params, random_state=RANDOM_STATE, verbose=False)
        final_cb.fit(X_features_only, y)
        self.models['catboost'] = final_cb
        advanced_results['catboost'] = {'cv_score': cb_score, 'params': cb_params, 'feature_importance': dict(zip(X_features_only.columns, final_cb.get_feature_importance()))}
        print(f"  CatBoost Best CV score: {cb_score:.3f}")

        # LightGBM
        lgb_params, lgb_score = self._optimize_lightgbm(X_features_only, y, cv_splits)
        
        # We need a validation set for early stopping
        X_train, X_val, y_train, y_val = train_test_split(X_features_only, y, test_size=0.2, random_state=RANDOM_STATE)
        
        final_lgb = lgb.train(lgb_params, lgb.Dataset(X_train, label=y_train), valid_sets=[lgb.Dataset(X_val, label=y_val)],
                              num_boost_round=1000, callbacks=[lgb.early_stopping(50), lgb.log_evaluation(0)])
        self.models['lightgbm'] = final_lgb
        advanced_results['lightgbm'] = {'cv_score': lgb_score, 'params': lgb_params, 'feature_importance': dict(zip(X_features_only.columns, final_lgb.feature_importance()))}
        print(f"  LightGBM Best CV score: {lgb_score:.3f}")

        return advanced_results

    def _optimizer_objective(self, trial, model_name, X, y, cv_splits):
        """Generic objective function for Optuna."""
        if model_name == 'catboost':
            params = {
                'iterations': trial.suggest_int('iterations', 100, 1000), 'depth': trial.suggest_int('depth', 4, 8),
                'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.2), 'l2_leaf_reg': trial.suggest_float('l2_leaf_reg', 1, 10),
                'random_strength': trial.suggest_float('random_strength', 1, 10), 'bagging_temperature': trial.suggest_float('bagging_temperature', 0, 1),
            }
        else: # lightgbm
            params = {
                'objective': 'regression', 'metric': 'rmse', 'num_leaves': trial.suggest_int('num_leaves', 20, 100),
                'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.2), 'feature_fraction': trial.suggest_float('feature_fraction', 0.5, 1.0),
                'bagging_fraction': trial.suggest_float('bagging_fraction', 0.5, 1.0), 'min_child_samples': trial.suggest_int('min_child_samples', 5, 50),
            }
        
        rmses = []
        for train_idx, test_idx in cv_splits:
            X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
            y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
            
            if model_name == 'catboost':
                model = cb.CatBoostRegressor(**params, random_state=RANDOM_STATE, verbose=False)
                model.fit(X_train, y_train)
            else:
                X_t, X_v, y_t, y_v = train_test_split(X_train, y_train, test_size=0.2, random_state=RANDOM_STATE)
                model = lgb.train(params, lgb.Dataset(X_t, label=y_t), valid_sets=[lgb.Dataset(X_v, label=y_v)],
                                  num_boost_round=100, callbacks=[lgb.early_stopping(10), lgb.log_evaluation(0)])

            preds = model.predict(X_test)
            rmses.append(np.sqrt(mean_squared_error(y_test, preds)))
        return np.mean(rmses)

    def _optimize_catboost(self, X, y, cv_splits):
        study = optuna.create_study(direction='minimize')
        study.optimize(lambda trial: self._optimizer_objective(trial, 'catboost', X, y, cv_splits), n_trials=OPTUNA_TRIALS)
        return study.best_params, study.best_value

    def _optimize_lightgbm(self, X, y, cv_splits):
        study = optuna.create_study(direction='minimize')
        study.optimize(lambda trial: self._optimizer_objective(trial, 'lightgbm', X, y, cv_splits), n_trials=OPTUNA_TRIALS)
        return study.best_params, study.best_value

    def save_artifacts(self, baseline_results: Dict, advanced_results: Dict):
        """Save models and results for the position."""
        print(f"[{self.position}] Saving artifacts...")
        os.makedirs(MODELS_DIR, exist_ok=True)
        os.makedirs(RESULTS_DIR, exist_ok=True)
        
        # Save models
        for name, model in self.models.items():
            model_path = os.path.join(MODELS_DIR, f"{name}_model_{self.position.lower()}.cbm" if name == 'catboost' else f"{name}_model_{self.position.lower()}.txt")
            model.save_model(model_path)
        
        # Save results
        results_path = os.path.join(RESULTS_DIR, f"model_results_{self.position.lower()}.json")
        summary = {'baseline_results': baseline_results, 'advanced_models': advanced_results}
        
        # Numpy types to python types for JSON
        def convert(o):
            if isinstance(o, np.generic): return o.item()
            raise TypeError
            
        with open(results_path, 'w') as f:
            json.dump(summary, f, indent=2, default=convert)
        print(f"[{self.position}] Artifacts saved successfully.")

def main():
    """Main execution function to run pipelines for all positions."""
    full_results = {}
    for position in POSITIONS_TO_TRAIN:
        print(f"\n{'='*20} TRAINING FOR: {position} {'='*20}")
        pipeline = PositionSpecificModelPipeline(position)
        pipeline.load_and_prepare_data()
        X, y, feature_cols = pipeline.get_data_splits()
        
        if len(X) < 100:
            print(f"[{position}] Skipping due to insufficient data ({len(X)} samples).")
            continue
            
        cv_splits = pipeline.create_cv_splits(X, y)
        baseline_results = pipeline.train_baseline_models(X, y, cv_splits)
        advanced_results = pipeline.optimize_and_train_advanced_models(X, y, cv_splits)
        pipeline.save_artifacts(baseline_results, advanced_results)
        
        full_results[position] = {
            'baseline': baseline_results,
            'advanced': advanced_results
        }
    
    print("\n\n" + "="*60)
    print("POSITION-SPECIFIC MODEL TRAINING SUMMARY")
    print("="*60)
    for pos, res in full_results.items():
        cb_score = res['advanced']['catboost']['cv_score']
        lgb_score = res['advanced']['lightgbm']['cv_score']
        print(f"\n--- {pos} ---")
        print(f"  CatBoost CV RMSE: {cb_score:.2f}")
        print(f"  LightGBM CV RMSE: {lgb_score:.2f}")
    print("\nAll position-specific models and results have been saved.")

if __name__ == "__main__":
    main() 
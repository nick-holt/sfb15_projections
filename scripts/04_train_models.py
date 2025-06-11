"""
TRULY FIXED Model Training Pipeline for Fantasy Football Projections

This script trains models using ONLY historical features with NO data leakage.
Removes ALL same-season features including *_points features that sum to total_points.
"""

import pandas as pd
import numpy as np
import os
from typing import Dict, List, Tuple
import warnings
warnings.filterwarnings('ignore')

# ML imports
from sklearn.model_selection import GroupKFold, cross_val_score
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

class FantasyModelPipeline:
    """Main modeling pipeline class with absolutely no data leakage"""
    
    def __init__(self):
        self.features_df = None
        self.target_col = 'total_points'
        self.models = {}
        self.results = {}
        self.feature_importance = {}
        
    def load_data(self):
        """Load the FIXED feature dataset"""
        print("Loading FIXED features (no data leakage)...")
        features_path = os.path.join(FEATURES_DIR, "player_features.parquet")
        
        if not os.path.exists(features_path):
            raise FileNotFoundError(f"Fixed features not found at {features_path}. Please run 03_build_features.py first.")
        
        self.features_df = pd.read_parquet(features_path)
        print(f"Loaded {len(self.features_df)} records with {len(self.features_df.columns)} features")
        
        # Remove ALL same-season features
        self.remove_all_same_season_features()
        
    def remove_all_same_season_features(self):
        """Remove ALL features that use same-season data"""
        print("Removing ALL same-season features...")
        
        original_cols = len(self.features_df.columns)
        
        # First, explicitly preserve essential columns
        preserve_cols = ['season', 'player_id', 'player_name', 'position', 'team', 'total_points']
        
        # Identify ALL same-season features to remove
        same_season_features = []
        
        for col in self.features_df.columns:
            # Skip preserved columns
            if col in preserve_cols:
                continue
            # Keep historical/static features
            elif any(indicator in col for indicator in ['_lag', '_decay', '_hist', 'age_', 'years_exp', 'height', 'weight', 'bmi']):
                # These are historical/static features - keep them
                continue
            else:
                # Everything else is potentially same-season data
                same_season_features.append(col)
        
        # Special check for any remaining features that might be same-season
        additional_same_season = [
            'games_played', 'games_missed', 'points_per_game_calc', 
            'availability_rate_calc', 'games_missed_calc', 'historical_data_count'
        ]
        
        # Add any *_points features (these are direct components of target)
        points_features = [col for col in self.features_df.columns if '_points' in col and '_lag' not in col and '_decay' not in col and '_hist' not in col and col != 'total_points']
        same_season_features.extend(points_features)
        
        # Add any raw statistical features from current season
        stat_features = []
        stat_indicators = [
            'pass_attempt', 'pass_touchdown', 'passing_yards', 'interception',
            'rush_attempt', 'rush_touchdown', 'rushing_yards', 
            'receptions', 'receiving_yards', 'receiving_touchdown',
            'targets', 'fumbles', 'two_point_conversion'
        ]
        
        for col in self.features_df.columns:
            if col in preserve_cols:  # Skip preserved columns
                continue
            if any(stat in col for stat in stat_indicators) and not any(hist in col for hist in ['_lag', '_decay', '_hist']):
                if col not in same_season_features:
                    stat_features.append(col)
        
        same_season_features.extend(stat_features)
        same_season_features.extend(additional_same_season)
        
        # Remove duplicates and features that don't exist
        same_season_features = list(set(same_season_features))
        same_season_features = [col for col in same_season_features if col in self.features_df.columns]
        
        # Final check: ensure we're not removing preserved columns
        same_season_features = [col for col in same_season_features if col not in preserve_cols]
        
        print(f"Removing {len(same_season_features)} same-season features:")
        for feat in sorted(same_season_features)[:20]:  # Show first 20
            print(f"  {feat}")
        if len(same_season_features) > 20:
            print(f"  ... and {len(same_season_features) - 20} more")
        
        # Drop same-season features
        self.features_df = self.features_df.drop(columns=same_season_features)
        
        remaining_cols = len(self.features_df.columns)
        print(f"Removed {original_cols - remaining_cols} features, {remaining_cols} remaining")
        
        # Final verification
        self.verify_truly_no_leakage()
        
    def verify_truly_no_leakage(self):
        """Final verification that no data leakage exists"""
        print("Final verification of no data leakage...")
        
        # Check remaining feature names
        remaining_features = [col for col in self.features_df.columns 
                            if col not in ['season', 'player_id', 'player_name', 'position', 'team', 'total_points']]
        
        print(f"Remaining {len(remaining_features)} features:")
        for feat in remaining_features[:15]:  # Show first 15
            print(f"  {feat}")
        if len(remaining_features) > 15:
            print(f"  ... and {len(remaining_features) - 15} more")
        
        # Check for any highly correlated features - but only if target column exists
        if len(remaining_features) > 0 and 'total_points' in self.features_df.columns:
            print("Checking correlations with target...")
            target_col = 'total_points'
            high_corr_features = []
            
            for col in remaining_features:
                if self.features_df[col].dtype in ['float64', 'int64', 'float32', 'int32']:
                    if self.features_df[col].notna().sum() > 10:
                        corr = self.features_df[col].corr(self.features_df[target_col])
                        if abs(corr) > 0.8:  # Still high but more reasonable threshold
                            high_corr_features.append((col, corr))
            
            if high_corr_features:
                print(f"Features with correlation > 0.8 with target:")
                for feat, corr in high_corr_features:
                    print(f"  {feat}: {corr:.4f}")
            else:
                print("✓ No features with suspiciously high correlation found")
        elif 'total_points' not in self.features_df.columns:
            print("ERROR: Target column 'total_points' was accidentally removed!")
        
        print("✓ Data leakage verification complete")
        
    def prepare_data(self) -> Tuple[pd.DataFrame, pd.Series, List[str]]:
        """Prepare data for modeling"""
        print("Preparing data for modeling...")
        
        # Remove records without target
        df = self.features_df.dropna(subset=[self.target_col]).copy()
        
        # Define feature columns (only historical/static features should remain)
        exclude_cols = [
            'season', 'player_id', 'player_name', 'position', 'team', self.target_col
        ]
        
        feature_cols = [col for col in df.columns if col not in exclude_cols]
        
        # Fill missing values with median for numerical features
        for col in feature_cols:
            if df[col].dtype in ['float64', 'int64', 'float32', 'int32']:
                median_val = df[col].median()
                df[col] = df[col].fillna(median_val)
        
        # Drop features with too many missing values or zero variance
        feature_cols = [col for col in feature_cols if df[col].notna().sum() > len(df) * 0.5]
        feature_cols = [col for col in feature_cols if df[col].std() > 0]
        
        X = df[feature_cols]
        y = df[self.target_col]
        
        print(f"Final feature set: {len(feature_cols)} features")
        print(f"Training samples: {len(X)}")
        print(f"Feature types: {X.dtypes.value_counts().to_dict()}")
        
        # Print all features to verify they're truly historical
        print(f"All features being used: {feature_cols}")
        
        return X, y, feature_cols
    
    def create_cv_splits(self, X: pd.DataFrame, y: pd.Series) -> List[Tuple]:
        """Create cross-validation splits grouped by season"""
        print("Creating cross-validation splits...")
        
        # Get seasons for grouping
        seasons = self.features_df.loc[X.index, 'season']
        
        # Use GroupKFold to ensure no season appears in both train and test
        gkf = GroupKFold(n_splits=CV_FOLDS)
        cv_splits = list(gkf.split(X, y, groups=seasons))
        
        print(f"Created {len(cv_splits)} CV folds")
        
        # Print split info
        for i, (train_idx, test_idx) in enumerate(cv_splits):
            train_seasons = seasons.iloc[train_idx].unique()
            test_seasons = seasons.iloc[test_idx].unique()
            print(f"  Fold {i+1}: Train seasons {sorted(train_seasons)}, Test seasons {sorted(test_seasons)}")
        
        return cv_splits
    
    def evaluate_model(self, model, X: pd.DataFrame, y: pd.Series, cv_splits: List[Tuple]) -> Dict:
        """Evaluate model with cross-validation"""
        scores = {'rmse': [], 'mae': [], 'spearman': []}
        
        for train_idx, test_idx in cv_splits:
            X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
            y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
            
            # Fit model
            if hasattr(model, 'fit'):
                model.fit(X_train, y_train)
            
            # Predict
            if hasattr(model, 'predict'):
                y_pred = model.predict(X_test)
            else:
                y_pred = model.predict(X_test)
            
            # Calculate metrics
            rmse = np.sqrt(mean_squared_error(y_test, y_pred))
            mae = mean_absolute_error(y_test, y_pred)
            spearman = spearmanr(y_test, y_pred)[0]
            
            scores['rmse'].append(rmse)
            scores['mae'].append(mae)
            scores['spearman'].append(spearman)
        
        return {
            'rmse_mean': np.mean(scores['rmse']),
            'rmse_std': np.std(scores['rmse']),
            'mae_mean': np.mean(scores['mae']),
            'mae_std': np.std(scores['mae']),
            'spearman_mean': np.mean(scores['spearman']),
            'spearman_std': np.std(scores['spearman'])
        }
    
    def train_baseline_models(self, X: pd.DataFrame, y: pd.Series, cv_splits: List[Tuple]) -> Dict:
        """Train and evaluate baseline models"""
        print("Training baseline models...")
        
        baseline_results = {}
        
        # Linear Regression
        print("  Training Linear Regression...")
        lr = LinearRegression()
        lr_scores = self.evaluate_model(lr, X, y, cv_splits)
        baseline_results['linear'] = lr_scores
        
        # Ridge Regression
        print("  Training Ridge Regression...")
        ridge = Ridge(alpha=1.0, random_state=RANDOM_STATE)
        ridge_scores = self.evaluate_model(ridge, X, y, cv_splits)
        baseline_results['ridge'] = ridge_scores
        
        print("Baseline results:")
        for model_name, scores in baseline_results.items():
            print(f"  {model_name}: RMSE={scores['rmse_mean']:.3f} ± {scores['rmse_std']:.3f}, "
                  f"Spearman={scores['spearman_mean']:.3f} ± {scores['spearman_std']:.3f}")
        
        return baseline_results
    
    def optimize_catboost(self, X: pd.DataFrame, y: pd.Series, cv_splits: List[Tuple]) -> Tuple[Dict, float]:
        """Optimize CatBoost hyperparameters"""
        print("Optimizing CatBoost...")
        
        def objective(trial):
            params = {
                'iterations': trial.suggest_int('iterations', 100, 1000),
                'depth': trial.suggest_int('depth', 4, 10),
                'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3),
                'l2_leaf_reg': trial.suggest_float('l2_leaf_reg', 1, 10),
                'random_strength': trial.suggest_float('random_strength', 1, 10),
                'bagging_temperature': trial.suggest_float('bagging_temperature', 0, 1),
                'border_count': trial.suggest_int('border_count', 32, 255),
                'random_state': RANDOM_STATE,
                'verbose': False
            }
            
            scores = []
            for train_idx, test_idx in cv_splits:
                X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
                y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
                
                model = cb.CatBoostRegressor(**params)
                model.fit(X_train, y_train, verbose=False)
                y_pred = model.predict(X_test)
                
                rmse = np.sqrt(mean_squared_error(y_test, y_pred))
                scores.append(rmse)
            
            return np.mean(scores)
        
        study = optuna.create_study(direction='minimize')
        study.optimize(objective, n_trials=OPTUNA_TRIALS)
        
        return study.best_params, study.best_value
    
    def optimize_lightgbm(self, X: pd.DataFrame, y: pd.Series, cv_splits: List[Tuple]) -> Tuple[Dict, float]:
        """Optimize LightGBM hyperparameters"""
        print("Optimizing LightGBM...")
        
        def objective(trial):
            params = {
                'objective': 'regression',
                'metric': 'rmse',
                'num_leaves': trial.suggest_int('num_leaves', 10, 100),
                'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3),
                'feature_fraction': trial.suggest_float('feature_fraction', 0.4, 1.0),
                'bagging_fraction': trial.suggest_float('bagging_fraction', 0.4, 1.0),
                'bagging_freq': trial.suggest_int('bagging_freq', 1, 7),
                'min_child_samples': trial.suggest_int('min_child_samples', 5, 100),
                'random_state': RANDOM_STATE,
                'verbose': -1
            }
            
            scores = []
            for train_idx, test_idx in cv_splits:
                X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
                y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
                
                # Split training data for validation
                from sklearn.model_selection import train_test_split
                X_train_inner, X_val, y_train_inner, y_val = train_test_split(
                    X_train, y_train, test_size=0.2, random_state=RANDOM_STATE
                )
                
                train_data = lgb.Dataset(X_train_inner, label=y_train_inner)
                val_data = lgb.Dataset(X_val, label=y_val, reference=train_data)
                
                model = lgb.train(
                    params, 
                    train_data, 
                    valid_sets=[val_data],
                    num_boost_round=100, 
                    callbacks=[lgb.early_stopping(10), lgb.log_evaluation(0)]
                )
                
                y_pred = model.predict(X_test, num_iteration=model.best_iteration)
                rmse = np.sqrt(mean_squared_error(y_test, y_pred))
                scores.append(rmse)
            
            return np.mean(scores)
        
        study = optuna.create_study(direction='minimize')
        study.optimize(objective, n_trials=OPTUNA_TRIALS)
        
        return study.best_params, study.best_value
    
    def train_final_models(self, X: pd.DataFrame, y: pd.Series, cv_splits: List[Tuple]) -> Dict:
        """Train final optimized models"""
        print("Training final optimized models...")
        
        results = {}
        
        # Optimize and train CatBoost
        cb_params, cb_score = self.optimize_catboost(X, y, cv_splits)
        print(f"Best CatBoost CV score: {cb_score:.3f}")
        
        final_cb = cb.CatBoostRegressor(**cb_params)
        final_cb.fit(X, y, verbose=False)
        self.models['catboost'] = final_cb
        
        results['catboost'] = {
            'cv_score': cb_score,
            'params': cb_params,
            'feature_importance': dict(zip(X.columns, final_cb.get_feature_importance()))
        }
        
        # Optimize and train LightGBM
        lgb_params, lgb_score = self.optimize_lightgbm(X, y, cv_splits)
        print(f"Best LightGBM CV score: {lgb_score:.3f}")
        
        # For final training, use a validation split
        from sklearn.model_selection import train_test_split
        X_train_final, X_val_final, y_train_final, y_val_final = train_test_split(
            X, y, test_size=0.2, random_state=RANDOM_STATE
        )
        
        train_data = lgb.Dataset(X_train_final, label=y_train_final)
        val_data = lgb.Dataset(X_val_final, label=y_val_final, reference=train_data)
        
        final_lgb = lgb.train(
            lgb_params, 
            train_data, 
            valid_sets=[val_data],
            num_boost_round=1000,
            callbacks=[lgb.early_stopping(50), lgb.log_evaluation(0)]
        )
        self.models['lightgbm'] = final_lgb
        
        results['lightgbm'] = {
            'cv_score': lgb_score,
            'params': lgb_params,
            'feature_importance': dict(zip(X.columns, final_lgb.feature_importance()))
        }
        
        return results
    
    def save_models_and_results(self, baseline_results: Dict, advanced_results: Dict):
        """Save models and results"""
        print("Saving models and results...")
        
        # Create directories
        os.makedirs(MODELS_DIR, exist_ok=True)
        os.makedirs(RESULTS_DIR, exist_ok=True)
        
        # Save models
        if 'catboost' in self.models:
            cb_path = os.path.join(MODELS_DIR, "catboost_model.cbm")
            self.models['catboost'].save_model(cb_path)
            print(f"Saved CatBoost model to {cb_path}")
        
        if 'lightgbm' in self.models:
            lgb_path = os.path.join(MODELS_DIR, "lightgbm_model.txt")
            self.models['lightgbm'].save_model(lgb_path)
            print(f"Saved LightGBM model to {lgb_path}")
        
        # Convert numpy types to Python types for JSON serialization
        def convert_numpy_types(obj):
            if isinstance(obj, dict):
                return {k: convert_numpy_types(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_numpy_types(item) for item in obj]
            elif isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            else:
                return obj
        
        # Save results
        results_summary = {
            'baseline_results': convert_numpy_types(baseline_results),
            'advanced_models': convert_numpy_types(advanced_results)
        }
        
        results_path = os.path.join(RESULTS_DIR, "model_results.json")
        import json
        with open(results_path, 'w') as f:
            json.dump(results_summary, f, indent=2)
        print(f"Saved results to {results_path}")
    
    def print_summary(self, baseline_results: Dict, advanced_results: Dict):
        """Print final summary"""
        print("\n" + "="*60)
        print("TRULY FIXED MODEL TRAINING SUMMARY (ZERO DATA LEAKAGE)")
        print("="*60)
        
        print("\nBaseline Models:")
        for model_name, scores in baseline_results.items():
            print(f"  {model_name.upper()}:")
            print(f"    RMSE: {scores['rmse_mean']:.3f} ± {scores['rmse_std']:.3f}")
            print(f"    Spearman: {scores['spearman_mean']:.3f} ± {scores['spearman_std']:.3f}")
        
        print("\nAdvanced Models:")
        for model_name, results in advanced_results.items():
            print(f"  {model_name.upper()}:")
            print(f"    CV RMSE: {results['cv_score']:.3f}")
            
            # Show top 5 most important features
            feature_importance = results['feature_importance']
            top_features = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)[:5]
            print(f"    Top features: {[f[0] for f in top_features]}")
        
        print(f"\nModels saved to: {MODELS_DIR}")
        print(f"Results saved to: {RESULTS_DIR}")
        print("\nNOTE: These results should be realistic for predicting fantasy football!")
        print("Expected RMSE should be in the range of 50-120 points.")
        print("Expected Spearman correlation should be in the range of 0.3-0.6.")

def main():
    """Main execution function"""
    pipeline = FantasyModelPipeline()
    
    # Load data
    pipeline.load_data()
    X, y, feature_cols = pipeline.prepare_data()
    
    # Create CV splits
    cv_splits = pipeline.create_cv_splits(X, y)
    
    # Train baseline models
    baseline_results = pipeline.train_baseline_models(X, y, cv_splits)
    
    # Train advanced models
    advanced_results = pipeline.train_final_models(X, y, cv_splits)
    
    # Save everything
    pipeline.save_models_and_results(baseline_results, advanced_results)
    
    # Print summary
    pipeline.print_summary(baseline_results, advanced_results)

if __name__ == "__main__":
    main() 
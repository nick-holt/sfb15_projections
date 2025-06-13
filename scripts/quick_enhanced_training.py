"""
Quick Enhanced Training - Fast P0 Validation

This script quickly tests enhanced features on recent data to validate 
improvements before full historical retraining.
"""

import pandas as pd
import numpy as np
import os
import pickle
import catboost as cb
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error
from scipy.stats import spearmanr
import warnings
warnings.filterwarnings('ignore')

class QuickEnhancedTrainer:
    """Quick test of enhanced features for validation"""
    
    def __init__(self):
        self.historical_data = None
        self.enhanced_features_2025 = None
        
    def load_data(self):
        """Load data"""
        print("Loading data for quick enhanced training test...")
        
        try:
            self.historical_data = pd.read_parquet('data/processed/season_stats.parquet')
            print(f"✅ Loaded {len(self.historical_data)} historical records")
        except Exception as e:
            print(f"❌ Error loading historical data: {e}")
            return False
        
        try:
            self.enhanced_features_2025 = pd.read_parquet('data/features/enhanced_features_2025.parquet')
            print(f"✅ Loaded enhanced features for {len(self.enhanced_features_2025)} players")
        except Exception as e:
            print(f"❌ Error loading enhanced features: {e}")
            return False
            
        return True
    
    def create_quick_enhanced_features(self, target_seasons=[2022, 2023, 2024]):
        """Create enhanced features for recent seasons only"""
        print(f"🔧 Creating enhanced features for {target_seasons}...")
        
        # Import enhanced feature engineering
        import sys
        sys.path.append('scripts')
        from enhanced_feature_engineering import EnhancedFeatureEngineer
        
        engineer = EnhancedFeatureEngineer()
        engineer.historical_data = self.historical_data
        
        quick_enhanced = []
        
        # Get unique players from target seasons
        target_data = self.historical_data[self.historical_data['season'].isin(target_seasons)]
        unique_players = target_data[['player_id', 'season', 'position', 'team', 'player_name']].drop_duplicates()
        
        print(f"Processing {len(unique_players)} player-seasons from {target_seasons}...")
        
        for i, (_, row) in enumerate(unique_players.iterrows()):
            if i % 100 == 0:
                print(f"  Processed {i}/{len(unique_players)} records...")
            
            player_id = row['player_id']
            season = row['season']
            position = row['position']
            team = row['team']
            player_name = row['player_name']
            
            # Get features as of that season (excluding current season)
            pre_season_data = self.historical_data[self.historical_data['season'] < season]
            engineer.historical_data = pre_season_data
            
            try:
                features = engineer.create_enhanced_features_for_player(player_id, position, team)
                features['season'] = season
                features['player_name'] = player_name
                
                # Get actual target from that season
                actual_points = target_data[
                    (target_data['player_id'] == player_id) & 
                    (target_data['season'] == season)
                ]['total_points']
                
                if len(actual_points) > 0:
                    features['target_total_points'] = actual_points.iloc[0]
                    quick_enhanced.append(features)
                    
            except Exception as e:
                continue
        
        quick_features_df = pd.DataFrame(quick_enhanced)
        print(f"✅ Created enhanced features for {len(quick_features_df)} records")
        
        return quick_features_df
    
    def test_enhanced_vs_original(self, position='QB'):
        """Test enhanced features vs original on recent data"""
        
        print(f"\n🧪 Testing enhanced features for {position}...")
        
        # Create enhanced features for recent data
        enhanced_data = self.create_quick_enhanced_features()
        position_data = enhanced_data[enhanced_data['position'] == position].copy()
        
        if len(position_data) < 20:
            print(f"⚠️  Not enough {position} data for testing ({len(position_data)} records)")
            return None
        
        print(f"📊 Testing on {len(position_data)} {position} records")
        
        # Prepare enhanced features
        exclude_cols = ['player_id', 'player_name', 'season', 'position', 'team', 'target_total_points']
        enhanced_feature_cols = [col for col in position_data.columns if col not in exclude_cols]
        
        X_enhanced = position_data[enhanced_feature_cols].fillna(0)
        y = position_data['target_total_points']
        
        print(f"🔥 Enhanced features: {len(enhanced_feature_cols)}")
        
        # Create "original" feature set (basic features only)
        basic_features = [col for col in enhanced_feature_cols if any(x in col.lower() for x in 
                         ['career_', 'prev_', 'recent_', 'best_', 'worst_', 'games_'])]
        
        if len(basic_features) < 5:
            basic_features = enhanced_feature_cols[:20]  # Use first 20 as "basic"
        
        X_basic = X_enhanced[basic_features]
        
        print(f"📊 Basic features: {len(basic_features)}")
        
        # Train and test both models
        X_train_enh, X_test_enh, y_train, y_test = train_test_split(
            X_enhanced, y, test_size=0.3, random_state=42
        )
        X_train_basic = X_train_enh[basic_features]
        X_test_basic = X_test_enh[basic_features]
        
        # Enhanced model
        model_enhanced = cb.CatBoostRegressor(
            iterations=500, depth=6, learning_rate=0.1, verbose=False, random_seed=42
        )
        model_enhanced.fit(X_train_enh, y_train)
        pred_enhanced = model_enhanced.predict(X_test_enh)
        
        # Basic model  
        model_basic = cb.CatBoostRegressor(
            iterations=500, depth=6, learning_rate=0.1, verbose=False, random_seed=42
        )
        model_basic.fit(X_train_basic, y_train)
        pred_basic = model_basic.predict(X_test_basic)
        
        # Compare performance
        rmse_enhanced = np.sqrt(mean_squared_error(y_test, pred_enhanced))
        rmse_basic = np.sqrt(mean_squared_error(y_test, pred_basic))
        
        corr_enhanced = spearmanr(y_test, pred_enhanced)[0]
        corr_basic = spearmanr(y_test, pred_basic)[0]
        
        print(f"\n📈 {position} PERFORMANCE COMPARISON:")
        print(f"{'Model':<12} {'Features':<10} {'RMSE':<8} {'Correlation':<12}")
        print("-" * 45)
        print(f"{'Basic':<12} {len(basic_features):<10} {rmse_basic:<8.1f} {corr_basic:<12.3f}")
        print(f"{'Enhanced':<12} {len(enhanced_feature_cols):<10} {rmse_enhanced:<8.1f} {corr_enhanced:<12.3f}")
        print(f"{'Improvement':<12} {len(enhanced_feature_cols)-len(basic_features):+<10} {rmse_basic-rmse_enhanced:+8.1f} {corr_enhanced-corr_basic:+12.3f}")
        
        # Feature importance for enhanced model
        feature_importance = model_enhanced.get_feature_importance()
        feature_names = X_enhanced.columns
        
        top_features = sorted(zip(feature_names, feature_importance), key=lambda x: x[1], reverse=True)[:10]
        
        print(f"\n🔝 Top 10 Enhanced Features for {position}:")
        for feat, imp in top_features:
            print(f"  {feat:<30} {imp:>6.1f}")
        
        # Save enhanced model for this position
        model_dir = f'models/enhanced_quick/{position.lower()}'
        os.makedirs(model_dir, exist_ok=True)
        
        model_enhanced.save_model(f'{model_dir}/cb_model.cbm')
        
        with open(f'{model_dir}/feature_columns.pkl', 'wb') as f:
            pickle.dump(list(X_enhanced.columns), f)
        
        print(f"💾 Enhanced {position} model saved to: {model_dir}/")
        
        return {
            'enhanced_rmse': rmse_enhanced,
            'basic_rmse': rmse_basic,
            'enhanced_corr': corr_enhanced,
            'basic_corr': corr_basic,
            'improvement': corr_enhanced - corr_basic,
            'top_features': top_features[:5]
        }
    
    def generate_quick_enhanced_predictions(self):
        """Generate predictions using enhanced models"""
        
        print(f"\n🎯 Generating enhanced predictions for 2025...")
        
        all_predictions = []
        
        for position in ['QB', 'RB', 'WR', 'TE']:
            model_dir = f'models/enhanced_quick/{position.lower()}'
            
            if not os.path.exists(f'{model_dir}/cb_model.cbm'):
                print(f"⚠️  No enhanced model for {position}")
                continue
            
            # Load model
            model = cb.CatBoostRegressor()
            model.load_model(f'{model_dir}/cb_model.cbm')
            
            with open(f'{model_dir}/feature_columns.pkl', 'rb') as f:
                feature_cols = pickle.load(f)
            
            # Get 2025 features
            position_features = self.enhanced_features_2025[
                self.enhanced_features_2025['position'] == position
            ].copy()
            
            if len(position_features) == 0:
                continue
            
            # Prepare features
            X = position_features.copy()
            for col in feature_cols:
                if col not in X.columns:
                    X[col] = 0
            
            X_model = X[feature_cols].fillna(0)
            
            # Make predictions
            predictions = model.predict(X_model)
            
            # Create results
            results = position_features[['player_name', 'team', 'position']].copy()
            results['enhanced_prediction'] = predictions
            
            all_predictions.append(results)
            
            print(f"{position}: {len(results)} players, range {predictions.min():.1f} to {predictions.max():.1f}")
        
        if all_predictions:
            enhanced_predictions = pd.concat(all_predictions, ignore_index=True)
            
            # Save
            output_dir = 'projections/2025/enhanced_quick'
            os.makedirs(output_dir, exist_ok=True)
            
            enhanced_predictions.to_csv(f'{output_dir}/enhanced_predictions_2025.csv', index=False)
            print(f"💾 Enhanced predictions saved to: {output_dir}/enhanced_predictions_2025.csv")
            
            return enhanced_predictions
        
        return None
    
    def run_quick_test(self):
        """Run quick enhanced feature test"""
        
        print("🚀 QUICK ENHANCED FEATURE VALIDATION")
        print("=" * 50)
        
        if not self.load_data():
            return None
        
        results = {}
        
        # Test each position
        for position in ['QB', 'RB', 'WR', 'TE']:
            result = self.test_enhanced_vs_original(position)
            if result:
                results[position] = result
        
        # Generate enhanced predictions
        predictions = self.generate_quick_enhanced_predictions()
        
        print(f"\n📊 QUICK TEST SUMMARY:")
        print(f"{'Position':<8} {'Improvement':<12} {'Enhanced Corr':<13}")
        print("-" * 35)
        
        for pos, result in results.items():
            print(f"{pos:<8} {result['improvement']:+.3f}       {result['enhanced_corr']:.3f}")
        
        return {
            'results': results,
            'predictions': predictions
        }

def main():
    """Run quick enhanced training test"""
    trainer = QuickEnhancedTrainer()
    return trainer.run_quick_test()

if __name__ == "__main__":
    test_results = main() 
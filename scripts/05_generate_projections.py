"""
Generate Final 2025 Fantasy Football Projections

This script loads the latest player features and applies the best-performing,
position-specific models to generate the final projections for the
upcoming 2025 season.

The output is a single CSV file containing the projections for all players,
which can then be used for drafting or further analysis.
"""

import pandas as pd
import numpy as np
import os
import catboost as cb

# Configuration
FEATURES_DIR = "data/features"
MODELS_DIR = "data/models"
RESULTS_DIR = "data/results"
TARGET_SEASON = 2025
POSITIONS = ["QB", "RB", "WR", "TE"]

def load_features_for_prediction():
    """Load the full feature set and filter for the target prediction year."""
    print("Loading features for prediction...")
    features_path = os.path.join(FEATURES_DIR, "player_features.parquet")
    if not os.path.exists(features_path):
        raise FileNotFoundError(f"Feature file not found at {features_path}. Run feature engineering first.")
    
    df = pd.read_parquet(features_path)
    
    # The features for predicting season N are based on data from season N-1
    # Our feature script generates features for year t+1 based on year t's data.
    # So, for 2025 predictions, we need the feature set where 'season' is 2024.
    # The 'season' column in our features_df actually represents the season the stats are FROM.
    # Let's adjust the logic slightly. The latest season in the file IS the feature set for the next year.
    latest_season = df['season'].max()
    print(f"Latest season in feature set is {latest_season}. Using this for {latest_season + 1} projections.")

    # In our case, the file is built to predict for the *next* season. So a row with season=2024 is used to predict 2025.
    predict_df = df[df['season'] == latest_season].copy()
    
    print(f"Loaded {len(predict_df)} players for {latest_season + 1} projection.")
    return predict_df

def load_positional_models():
    """Load the saved, position-specific CatBoost models."""
    print("Loading position-specific models...")
    models = {}
    for pos in POSITIONS:
        model_path = os.path.join(MODELS_DIR, f"catboost_model_{pos.lower()}.cbm")
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model for {pos} not found at {model_path}. Please train models first.")
        
        model = cb.CatBoostRegressor()
        model.load_model(model_path)
        models[pos] = model
        print(f"  Loaded model for {pos}.")
    return models

def generate_projections(df: pd.DataFrame, models: dict) -> pd.DataFrame:
    """Generate projections by applying the correct model to each player."""
    print("Generating projections...")
    all_projections = []
    
    # Get the feature names from one of the models (they should all be consistent)
    model_features = models['QB'].feature_names_
    
    # Ensure all required features are present in the dataframe
    missing_features = [f for f in model_features if f not in df.columns]
    if missing_features:
        raise ValueError(f"The following required features are missing from the prediction data: {missing_features}")

    for pos in POSITIONS:
        pos_df = df[df['position'] == pos].copy()
        if pos_df.empty:
            continue
            
        model = models[pos]
        
        # Select and align features for prediction
        X_predict = pos_df[model_features]
        
        # Fill any NaNs with median (same strategy as training)
        for col in X_predict.columns:
            if X_predict[col].isnull().any():
                # Note: In a production system, you'd save and load medians from the training set.
                # For now, we'll use the median of the prediction set as a proxy.
                median_val = X_predict[col].median()
                X_predict[col].fillna(median_val, inplace=True)
        
        pos_df['predicted_points'] = model.predict(X_predict)
        all_projections.append(pos_df)
        print(f"  Generated projections for {len(pos_df)} {pos}s.")
        
    final_df = pd.concat(all_projections)
    return final_df

def save_projections(df: pd.DataFrame):
    """Save the final projections to a CSV file."""
    output_cols = [
        'player_id', 'player_name', 'position', 'team',
        'age_2025', 'years_exp', 'predicted_points'
    ]
    
    # Add season to the columns to be clear
    df['projection_season'] = TARGET_SEASON
    output_cols.insert(1, 'projection_season')
    
    # Filter for necessary columns and sort
    final_projections = df[output_cols].sort_values(by='predicted_points', ascending=False)
    
    # Round predictions
    final_projections['predicted_points'] = final_projections['predicted_points'].round(2)
    
    output_path = os.path.join(RESULTS_DIR, f"{TARGET_SEASON}_fantasy_projections.csv")
    final_projections.to_csv(output_path, index=False)
    print(f"\nSuccessfully saved final {TARGET_SEASON} projections to: {output_path}")
    print(f"Top 10 players projected for {TARGET_SEASON}:")
    print(final_projections.head(10))

def main():
    """Main execution function."""
    print(f"{'='*20} GENERATING {TARGET_SEASON} PROJECTIONS {'='*20}")
    
    # 1. Load data for the target season
    prediction_df = load_features_for_prediction()
    
    # 2. Load the trained positional models
    models = load_positional_models()
    
    # 3. Generate predictions
    final_projections_df = generate_projections(prediction_df, models)
    
    # 4. Save the final output
    save_projections(final_projections_df)
    
    print(f"\n{'='*20} PROJECTION PIPELINE COMPLETE {'='*20}")

if __name__ == "__main__":
    main() 
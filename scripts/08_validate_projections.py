"""
Validate 2025 Projections Against 2024 Actual Results

This script compares our projection methodology against known 2024 results
to assess model accuracy and identify potential improvements.
"""

import pandas as pd
import numpy as np
import os
from scipy.stats import pearsonr, spearmanr
import matplotlib.pyplot as plt
import seaborn as sns

def load_2024_actuals():
    """Load 2024 actual fantasy results"""
    print("Loading 2024 actual results...")
    
    # Load from historical data
    season_stats = pd.read_parquet('data/processed/season_stats.parquet')
    actuals_2024 = season_stats[season_stats['season'] == 2024].copy()
    
    print(f"Loaded {len(actuals_2024)} players with 2024 actual results")
    return actuals_2024

def load_current_projections():
    """Load our current 2025 projections"""
    print("Loading current 2025 projections...")
    
    projections = pd.read_csv('projections/2025/fantasy_projections_2025.csv')
    print(f"Loaded {len(projections)} 2025 projections")
    return projections

def create_2024_projections():
    """Generate 2024 projections using our current methodology for validation"""
    print("Generating 2024 projections using current methodology...")
    
    # Load feature data
    features = pd.read_parquet('data/features/player_features.parquet')
    
    # Filter for 2023 data to predict 2024 (simulating our prediction process)
    features_2023 = features[features['season'] == 2023].copy()
    
    # Simple baseline projection using lag features
    projections_2024 = []
    
    for _, player in features_2023.iterrows():
        # Use lag features to predict 2024
        if pd.notna(player.get('total_points_lag1', 0)):
            # Weight recent performance heavily
            base_projection = player['total_points_lag1']
            
            # Age adjustment
            age = player.get('age_2025', 27) - 1  # Estimate 2024 age
            if age > 30:
                base_projection *= 0.95
            elif age < 25:
                base_projection *= 1.05
                
            # Games played adjustment
            if pd.notna(player.get('games_played_lag1', 0)):
                if player['games_played_lag1'] < 10:
                    base_projection *= 0.85  # Injury risk
                    
            projections_2024.append({
                'player_id': player['player_id'],
                'player_name': player['player_name'],
                'position': player['position'],
                'projected_points_2024': max(base_projection, 30)  # Floor
            })
    
    return pd.DataFrame(projections_2024)

def compare_projections_vs_actuals(projections_2024, actuals_2024):
    """Compare projections against actual results"""
    print("Comparing 2024 projections vs actuals...")
    
    # Merge projections with actuals
    comparison = projections_2024.merge(
        actuals_2024[['player_id', 'total_points', 'position', 'games_played']], 
        on='player_id', 
        how='inner',
        suffixes=('_proj', '_actual')
    )
    
    # Use the actual position for analysis
    if 'position_actual' in comparison.columns:
        comparison['position'] = comparison['position_actual']
    
    print(f"Found {len(comparison)} players with both projections and actuals")
    
    # Calculate metrics
    results = {}
    
    for position in ['QB', 'RB', 'WR', 'TE']:
        pos_data = comparison[comparison['position'] == position].copy()
        
        if len(pos_data) < 5:
            continue
            
        # Filter for players with meaningful playing time
        pos_data = pos_data[pos_data['games_played'] >= 5]
        
        if len(pos_data) < 5:
            continue
            
        # Calculate correlations
        pearson_corr, _ = pearsonr(pos_data['projected_points_2024'], pos_data['total_points'])
        spearman_corr, _ = spearmanr(pos_data['projected_points_2024'], pos_data['total_points'])
        
        # Calculate errors
        mae = np.mean(np.abs(pos_data['projected_points_2024'] - pos_data['total_points']))
        rmse = np.sqrt(np.mean((pos_data['projected_points_2024'] - pos_data['total_points'])**2))
        
        # Mean bias (over/under projection)
        bias = np.mean(pos_data['projected_points_2024'] - pos_data['total_points'])
        
        results[position] = {
            'n_players': len(pos_data),
            'pearson_corr': pearson_corr,
            'spearman_corr': spearman_corr,
            'mae': mae,
            'rmse': rmse,
            'bias': bias,
            'mean_projected': pos_data['projected_points_2024'].mean(),
            'mean_actual': pos_data['total_points'].mean()
        }
        
        print(f"\n{position} Results ({len(pos_data)} players):")
        print(f"  Pearson Correlation: {pearson_corr:.3f}")
        print(f"  Spearman Correlation: {spearman_corr:.3f}")
        print(f"  MAE: {mae:.1f}")
        print(f"  RMSE: {rmse:.1f}")
        print(f"  Bias: {bias:+.1f} (positive = over-projection)")
        print(f"  Mean Projected: {pos_data['projected_points_2024'].mean():.1f}")
        print(f"  Mean Actual: {pos_data['total_points'].mean():.1f}")
    
    return comparison, results

def identify_top_misses(comparison):
    """Identify biggest projection misses for analysis"""
    print("\nAnalyzing biggest projection misses...")
    
    comparison['error'] = comparison['projected_points_2024'] - comparison['total_points']
    comparison['abs_error'] = np.abs(comparison['error'])
    
    # Biggest overproductions (we projected low, they scored high)
    print("\nTop 10 Underproductions (we projected too low):")
    underproductions = comparison.nsmallest(10, 'error')[
        ['player_name', 'position', 'projected_points_2024', 'total_points', 'error']
    ]
    for _, row in underproductions.iterrows():
        print(f"  {row['player_name']} ({row['position']}): "
              f"Projected {row['projected_points_2024']:.0f}, Actual {row['total_points']:.0f} "
              f"(missed by {-row['error']:.0f})")
    
    # Biggest overprojections (we projected high, they scored low)  
    print("\nTop 10 Overprojections (we projected too high):")
    overprojections = comparison.nlargest(10, 'error')[
        ['player_name', 'position', 'projected_points_2024', 'total_points', 'error']
    ]
    for _, row in overprojections.iterrows():
        print(f"  {row['player_name']} ({row['position']}): "
              f"Projected {row['projected_points_2024']:.0f}, Actual {row['total_points']:.0f} "
              f"(overprojected by {row['error']:.0f})")

def check_current_projection_sanity():
    """Check if current 2025 projections pass sanity tests"""
    print("\n" + "="*60)
    print("SANITY CHECK: 2025 PROJECTIONS")
    print("="*60)
    
    projections = load_current_projections()
    
    # Position-wise analysis
    for position in ['QB', 'RB', 'WR', 'TE']:
        pos_data = projections[projections['position'] == position].copy()
        pos_data = pos_data.sort_values('projected_points', ascending=False)
        
        print(f"\n{position} Analysis:")
        print(f"  Players projected: {len(pos_data)}")
        print(f"  Top projection: {pos_data['projected_points'].max():.0f} ({pos_data.iloc[0]['player_name']})")
        print(f"  Average projection: {pos_data['projected_points'].mean():.0f}")
        print(f"  Median projection: {pos_data['projected_points'].median():.0f}")
        
        # Show top 5
        print(f"  Top 5 {position}s:")
        for i, (_, row) in enumerate(pos_data.head(5).iterrows(), 1):
            print(f"    {i}. {row['player_name']} ({row['team']}): {row['projected_points']:.0f} pts")
    
    # Reality checks
    print("\nReality Checks:")
    
    # Check for unrealistic highs
    unrealistic = projections[
        ((projections['position'] == 'QB') & (projections['projected_points'] > 700)) |
        ((projections['position'] == 'RB') & (projections['projected_points'] > 900)) |
        ((projections['position'] == 'WR') & (projections['projected_points'] > 750)) |
        ((projections['position'] == 'TE') & (projections['projected_points'] > 600))
    ]
    
    if len(unrealistic) > 0:
        print(f"  ⚠️  {len(unrealistic)} players with potentially unrealistic projections:")
        for _, row in unrealistic.iterrows():
            print(f"    {row['player_name']} ({row['position']}): {row['projected_points']:.0f} pts")
    else:
        print("  ✅ No unrealistically high projections found")
    
    # Check for unrealistic lows
    too_low = projections[projections['projected_points'] < 10]
    if len(too_low) > 0:
        print(f"  ⚠️  {len(too_low)} players with very low projections (< 10 pts)")
    else:
        print("  ✅ No unrealistically low projections found")

def main():
    """Main validation pipeline"""
    print("Starting projection validation...")
    
    # Load data
    actuals_2024 = load_2024_actuals()
    
    # Generate 2024 projections for validation
    projections_2024 = create_2024_projections()
    
    # Compare
    comparison, results = compare_projections_vs_actuals(projections_2024, actuals_2024)
    
    # Analyze misses
    identify_top_misses(comparison)
    
    # Check current projections
    check_current_projection_sanity()
    
    # Save validation results
    os.makedirs('data/validation', exist_ok=True)
    comparison.to_csv('data/validation/2024_validation_results.csv', index=False)
    
    print(f"\nValidation complete. Results saved to data/validation/2024_validation_results.csv")

if __name__ == "__main__":
    main() 
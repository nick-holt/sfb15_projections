"""
Compare Raw Model Predictions to FootballGuys Projections

This script compares our raw model output to professional projections
to understand how our models stack up against industry standards.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

def load_data():
    """Load both our predictions and FootballGuys projections"""
    
    # Load our raw predictions
    try:
        our_predictions = pd.read_csv('projections/2025/raw/raw_model_predictions_2025.csv')
        print(f"Loaded {len(our_predictions)} of our raw predictions")
    except Exception as e:
        print(f"Error loading our predictions: {e}")
        return None, None
    
    # Load FootballGuys projections
    try:
        fg_projections = pd.read_csv('sfb15_projections_from_footballguys.csv')
        fg_projections.columns = ['Rank', 'Player', 'Team', 'Pos', 'Age', 'Gms', 'FG_Points']
        print(f"Loaded {len(fg_projections)} FootballGuys projections")
    except Exception as e:
        print(f"Error loading FootballGuys projections: {e}")
        return None, None
    
    return our_predictions, fg_projections

def analyze_ranges_by_position(our_preds, fg_preds):
    """Compare prediction ranges by position"""
    
    print("\n" + "="*80)
    print("RANGE COMPARISON BY POSITION")
    print("="*80)
    
    # Summary stats
    comparison_data = []
    
    for position in ['QB', 'RB', 'WR', 'TE']:
        # Our predictions
        our_pos = our_preds[our_preds['position'] == position]['raw_prediction']
        
        # FootballGuys predictions
        fg_pos = fg_preds[fg_preds['Pos'] == position]['FG_Points']
        
        if len(our_pos) > 0 and len(fg_pos) > 0:
            comparison_data.append({
                'Position': position,
                'Our_Count': len(our_pos),
                'Our_Min': our_pos.min(),
                'Our_Max': our_pos.max(),
                'Our_Mean': our_pos.mean(),
                'Our_Std': our_pos.std(),
                'FG_Count': len(fg_pos),
                'FG_Min': fg_pos.min(),
                'FG_Max': fg_pos.max(),
                'FG_Mean': fg_pos.mean(),
                'FG_Std': fg_pos.std()
            })
    
    comparison_df = pd.DataFrame(comparison_data)
    
    # Display comparison
    print(f"{'Position':<8} {'Source':<12} {'Count':<6} {'Min':<8} {'Max':<8} {'Mean':<8} {'Std':<8}")
    print("-" * 70)
    
    for _, row in comparison_df.iterrows():
        pos = row['Position']
        print(f"{pos:<8} {'Our Model':<12} {row['Our_Count']:<6.0f} {row['Our_Min']:<8.1f} {row['Our_Max']:<8.1f} {row['Our_Mean']:<8.1f} {row['Our_Std']:<8.1f}")
        print(f"{'':<8} {'FootballGuys':<12} {row['FG_Count']:<6.0f} {row['FG_Min']:<8.1f} {row['FG_Max']:<8.1f} {row['FG_Mean']:<8.1f} {row['FG_Std']:<8.1f}")
        
        # Calculate differences
        mean_diff = row['Our_Mean'] - row['FG_Mean']
        max_diff = row['Our_Max'] - row['FG_Max']
        min_diff = row['Our_Min'] - row['FG_Min']
        
        print(f"{'':<8} {'Difference':<12} {'':<6} {min_diff:<8.1f} {max_diff:<8.1f} {mean_diff:<8.1f} {'':<8}")
        print()
    
    return comparison_df

def find_outliers_and_matches(our_preds, fg_preds):
    """Find where our predictions differ significantly from FootballGuys"""
    
    print("\n" + "="*80)
    print("NOTABLE DIFFERENCES AND PATTERNS")
    print("="*80)
    
    for position in ['QB', 'RB', 'WR', 'TE']:
        print(f"\n--- {position} Analysis ---")
        
        our_pos = our_preds[our_preds['position'] == position]
        fg_pos = fg_preds[fg_preds['Pos'] == position]
        
        if len(our_pos) == 0 or len(fg_pos) == 0:
            continue
        
        # Top players from each source
        print(f"\nTop 10 {position}s - Our Model:")
        our_top = our_pos.nlargest(10, 'raw_prediction')[['player_name', 'raw_prediction']]
        for _, player in our_top.iterrows():
            print(f"  {player['player_name']:<25} {player['raw_prediction']:>6.1f}")
        
        print(f"\nTop 10 {position}s - FootballGuys:")
        fg_top = fg_pos.nlargest(10, 'FG_Points')[['Player', 'FG_Points']]
        for _, player in fg_top.iterrows():
            print(f"  {player['Player']:<25} {player['FG_Points']:>6.1f}")
    
def create_distribution_plots(our_preds, fg_preds):
    """Create distribution plots comparing the two projection sets"""
    
    print("\n" + "="*80)
    print("CREATING DISTRIBUTION COMPARISON PLOTS")
    print("="*80)
    
    fig, axes = plt.subplots(2, 2, figsize=(15, 12))
    fig.suptitle('Prediction Distributions: Our Model vs FootballGuys', fontsize=16)
    
    positions = ['QB', 'RB', 'WR', 'TE']
    colors = ['blue', 'green', 'red', 'orange']
    
    for i, (position, color) in enumerate(zip(positions, colors)):
        row = i // 2
        col = i % 2
        ax = axes[row, col]
        
        # Our predictions
        our_pos = our_preds[our_preds['position'] == position]['raw_prediction']
        
        # FootballGuys predictions
        fg_pos = fg_preds[fg_preds['Pos'] == position]['FG_Points']
        
        if len(our_pos) > 0 and len(fg_pos) > 0:
            # Plot distributions
            ax.hist(our_pos, bins=20, alpha=0.6, label='Our Model', color=color, density=True)
            ax.hist(fg_pos, bins=20, alpha=0.6, label='FootballGuys', color='gray', density=True)
            
            # Add mean lines
            ax.axvline(our_pos.mean(), color=color, linestyle='--', linewidth=2, alpha=0.8, label=f'Our Mean: {our_pos.mean():.1f}')
            ax.axvline(fg_pos.mean(), color='black', linestyle='--', linewidth=2, alpha=0.8, label=f'FG Mean: {fg_pos.mean():.1f}')
            
            ax.set_title(f'{position} - Distribution Comparison')
            ax.set_xlabel('Fantasy Points')
            ax.set_ylabel('Density')
            ax.legend()
            ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    # Save plot
    output_dir = 'projections/2025/analysis'
    import os
    os.makedirs(output_dir, exist_ok=True)
    plt.savefig(f'{output_dir}/prediction_distributions_comparison.png', dpi=300, bbox_inches='tight')
    print(f"Distribution plots saved to: {output_dir}/prediction_distributions_comparison.png")
    
    plt.close()

def analyze_elite_vs_replacement_players(our_preds, fg_preds):
    """Analyze how we handle elite vs replacement level players"""
    
    print("\n" + "="*80)
    print("ELITE vs REPLACEMENT LEVEL ANALYSIS")
    print("="*80)
    
    for position in ['QB', 'RB', 'WR', 'TE']:
        print(f"\n--- {position} Elite vs Replacement ---")
        
        our_pos = our_preds[our_preds['position'] == position]['raw_prediction']
        fg_pos = fg_preds[fg_preds['Pos'] == position]['FG_Points']
        
        if len(our_pos) == 0 or len(fg_pos) == 0:
            continue
        
        # Define top 10% as elite, bottom 20% as replacement
        our_elite_threshold = our_pos.quantile(0.9)
        our_replacement_threshold = our_pos.quantile(0.2)
        
        fg_elite_threshold = fg_pos.quantile(0.9)
        fg_replacement_threshold = fg_pos.quantile(0.2)
        
        # Count players in each tier
        our_elite_count = (our_pos >= our_elite_threshold).sum()
        our_replacement_count = (our_pos <= our_replacement_threshold).sum()
        
        fg_elite_count = (fg_pos >= fg_elite_threshold).sum()
        fg_replacement_count = (fg_pos <= fg_replacement_threshold).sum()
        
        print(f"Elite Threshold (90th percentile):")
        print(f"  Our Model: {our_elite_threshold:.1f} ({our_elite_count} players)")
        print(f"  FootballGuys: {fg_elite_threshold:.1f} ({fg_elite_count} players)")
        print(f"  Difference: {our_elite_threshold - fg_elite_threshold:+.1f}")
        
        print(f"Replacement Threshold (20th percentile):")
        print(f"  Our Model: {our_replacement_threshold:.1f} ({our_replacement_count} players)")
        print(f"  FootballGuys: {fg_replacement_threshold:.1f} ({fg_replacement_count} players)")
        print(f"  Difference: {our_replacement_threshold - fg_replacement_threshold:+.1f}")
        
        # Calculate spreads
        our_spread = our_elite_threshold - our_replacement_threshold
        fg_spread = fg_elite_threshold - fg_replacement_threshold
        
        print(f"Elite-to-Replacement Spread:")
        print(f"  Our Model: {our_spread:.1f}")
        print(f"  FootballGuys: {fg_spread:.1f}")
        print(f"  Difference: {our_spread - fg_spread:+.1f}")

def main():
    """Main comparison function"""
    print("Comparing Raw Model Predictions to FootballGuys Projections")
    print("=" * 70)
    
    # Load data
    our_preds, fg_preds = load_data()
    
    if our_preds is None or fg_preds is None:
        print("Failed to load data. Exiting.")
        return
    
    print(f"\nData loaded successfully!")
    print(f"Our predictions: {len(our_preds)} players")
    print(f"FootballGuys: {len(fg_preds)} players")
    
    # Run analyses
    comparison_df = analyze_ranges_by_position(our_preds, fg_preds)
    find_outliers_and_matches(our_preds, fg_preds)
    analyze_elite_vs_replacement_players(our_preds, fg_preds)
    
    try:
        create_distribution_plots(our_preds, fg_preds)
    except Exception as e:
        print(f"Could not create plots: {e}")
    
    # Save comparison summary
    output_dir = 'projections/2025/analysis'
    import os
    os.makedirs(output_dir, exist_ok=True)
    
    comparison_df.to_csv(f'{output_dir}/comparison_summary.csv', index=False)
    print(f"\nComparison summary saved to: {output_dir}/comparison_summary.csv")

if __name__ == "__main__":
    main() 
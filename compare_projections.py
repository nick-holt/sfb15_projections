import pandas as pd
import numpy as np

# Load both projection sets
ml_proj = pd.read_csv('projections/2025/fantasy_projections_2025.csv')
manual_proj = pd.read_csv('projections/2025/realistic_projections_2025.csv')

print('=== PROJECTION COMPARISON ANALYSIS ===')
print(f'ML Projections: {len(ml_proj)} players')
print(f'Manual Projections: {len(manual_proj)} players')

# Position averages comparison
print('\n=== POSITION AVERAGES COMPARISON ===')
for pos in ['QB', 'RB', 'WR', 'TE']:
    ml_avg = ml_proj[ml_proj['position'] == pos]['projected_points'].mean()
    manual_avg = manual_proj[manual_proj['position'] == pos]['projected_points'].mean()
    ml_max = ml_proj[ml_proj['position'] == pos]['projected_points'].max()
    manual_max = manual_proj[manual_proj['position'] == pos]['projected_points'].max()
    print(f'{pos}: ML_avg={ml_avg:.1f}, Manual_avg={manual_avg:.1f} | ML_max={ml_max:.1f}, Manual_max={manual_max:.1f}')

# Elite players comparison
elite_players = ['Josh Allen', 'Patrick Mahomes', 'Lamar Jackson', 'Saquon Barkley', 
                'Ja\'Marr Chase', 'CeeDee Lamb', 'Travis Kelce', 'Tyreek Hill']

print('\n=== ELITE PLAYER COMPARISON ===')
for player in elite_players:
    ml_player = ml_proj[ml_proj['player_name'] == player]
    manual_player = manual_proj[manual_proj['player_name'] == player]
    
    if len(ml_player) > 0 and len(manual_player) > 0:
        ml_pts = ml_player['projected_points'].iloc[0]
        manual_pts = manual_player['projected_points'].iloc[0]
        diff = ml_pts - manual_pts
        print(f'{player:20}: ML={ml_pts:.1f}, Manual={manual_pts:.1f}, Diff={diff:+.1f}')
    elif len(ml_player) > 0:
        print(f'{player:20}: ML={ml_player["projected_points"].iloc[0]:.1f}, Manual=Not Found')
    elif len(manual_player) > 0:
        print(f'{player:20}: ML=Not Found, Manual={manual_player["projected_points"].iloc[0]:.1f}')

# Load 2024 actuals for validation
try:
    actuals_2024 = pd.read_parquet('data/features/player_features.parquet')
    actuals_2024 = actuals_2024[actuals_2024['season'] == 2024]
    
    print('\n=== 2024 ACTUAL vs 2025 PROJECTIONS ===')
    for player in elite_players:
        actual_2024 = actuals_2024[actuals_2024['player_name'] == player]
        ml_player = ml_proj[ml_proj['player_name'] == player]
        manual_player = manual_proj[manual_proj['player_name'] == player]
        
        if len(actual_2024) > 0:
            actual_pts = actual_2024['total_points'].iloc[0]
            ml_pts = ml_player['projected_points'].iloc[0] if len(ml_player) > 0 else 0
            manual_pts = manual_player['projected_points'].iloc[0] if len(manual_player) > 0 else 0
            
            print(f'{player:20}: 2024_Actual={actual_pts:.1f}, ML_2025={ml_pts:.1f}, Manual_2025={manual_pts:.1f}')
            
except Exception as e:
    print(f'Could not load 2024 actuals: {e}')

# Distribution analysis
print('\n=== PROJECTION DISTRIBUTION ANALYSIS ===')
for pos in ['QB', 'RB', 'WR', 'TE']:
    ml_pos = ml_proj[ml_proj['position'] == pos]['projected_points']
    manual_pos = manual_proj[manual_proj['position'] == pos]['projected_points']
    
    print(f'\n{pos} Distribution:')
    print(f'  ML: min={ml_pos.min():.1f}, median={ml_pos.median():.1f}, max={ml_pos.max():.1f}, std={ml_pos.std():.1f}')
    print(f'  Manual: min={manual_pos.min():.1f}, median={manual_pos.median():.1f}, max={manual_pos.max():.1f}, std={manual_pos.std():.1f}')

# Confidence analysis
print('\n=== CONFIDENCE DISTRIBUTION ===')
ml_conf = ml_proj['confidence'].value_counts()
manual_conf = manual_proj['confidence'].value_counts()

print('ML Confidence:')
for conf, count in ml_conf.items():
    print(f'  {conf}: {count} players ({count/len(ml_proj)*100:.1f}%)')

print('Manual Confidence:')
for conf, count in manual_conf.items():
    print(f'  {conf}: {count} players ({count/len(manual_proj)*100:.1f}%)')

print('\n=== ANALYSIS SUMMARY ===')
print('ML Projections:')
print('  + Uses sophisticated ensemble models (CatBoost + LightGBM)')
print('  + Incorporates 118 features per position')
print('  + Model-based confidence scoring')
print('  - Some projections still seem high (700+ for QBs)')
print('  - May overfit to historical patterns')

print('\nManual Projections:')
print('  + Conservative, realistic caps')
print('  + Simple, interpretable logic')
print('  + Quick to generate and adjust')
print('  - May be too conservative for elite players')
print('  - Less sophisticated feature usage')

print('\nRecommendation: Hybrid approach combining both methods') 
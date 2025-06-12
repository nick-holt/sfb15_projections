import pandas as pd

df = pd.read_parquet('data/features/player_features.parquet')

# Get top performers from each position in 2024
top_wr = df[(df['position'] == 'WR') & (df['season'] == 2024)].nlargest(1, 'total_points').iloc[0]
top_rb = df[(df['position'] == 'RB') & (df['season'] == 2024)].nlargest(1, 'total_points').iloc[0]

print("Scoring Comparison - Top WR vs Top RB in 2024:")
print(f"\nTop WR: {top_wr['player_name']} ({top_wr['total_points']:.1f} pts)")
print(f"Top RB: {top_rb['player_name']} ({top_rb['total_points']:.1f} pts)")

print(f"\nScoring Breakdown:")
print(f"{'Component':<25} {'WR':<15} {'RB':<15}")
print("-" * 55)

components = [
    ('rushing_yards_points', 'Rushing Yards'),
    ('rushing_td_points', 'Rushing TDs'),
    ('rushing_attempt_points', 'Rushing Attempts'),
    ('rushing_first_down_points', 'Rushing 1st Downs'),
    ('receiving_yards_points', 'Receiving Yards'),
    ('receiving_td_points', 'Receiving TDs'),
    ('receptions_points', 'Receptions'),
    ('receiving_first_down_points', 'Receiving 1st Downs'),
]

for col, label in components:
    wr_val = top_wr[col] if col in top_wr.index else 0
    rb_val = top_rb[col] if col in top_rb.index else 0
    print(f"{label:<25} {wr_val:<15.1f} {rb_val:<15.1f}")

print(f"\nKey Stats:")
print(f"{'Stat':<25} {'WR':<15} {'RB':<15}")
print("-" * 55)

# Get raw stats to understand the differences
stats_to_check = [
    ('rushing_yards', 'Rushing Yards'),
    ('rushing_touchdowns', 'Rushing TDs'),
    ('rushing_attempts', 'Rushing Attempts'),
    ('receiving_yards', 'Receiving Yards'),
    ('receiving_touchdowns', 'Receiving TDs'),
    ('receptions', 'Receptions'),
]

for col, label in stats_to_check:
    wr_val = top_wr[col] if col in top_wr.index else 0
    rb_val = top_rb[col] if col in top_rb.index else 0
    print(f"{label:<25} {wr_val:<15.0f} {rb_val:<15.0f}")

# Calculate per-game averages
print(f"\nPer-Game Averages:")
print(f"WR PPG: {top_wr['total_points'] / top_wr['games_played']:.1f}")
print(f"RB PPG: {top_rb['total_points'] / top_rb['games_played']:.1f}")

# Check reception scoring specifically
print(f"\nReception Analysis:")
print(f"WR Receptions: {top_wr['receptions']:.0f} x 2.5 = {top_wr['receptions'] * 2.5:.1f} pts")
print(f"RB Receptions: {top_rb['receptions']:.0f} x 2.5 = {top_rb['receptions'] * 2.5:.1f} pts") 
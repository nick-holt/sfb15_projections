import pandas as pd

df = pd.read_parquet('data/features/player_features.parquet')
lamar = df[(df['player_name'] == 'Lamar Jackson') & (df['season'] == 2024)]

# Manual calculation
passing_yards_pts = 4601 * 0.04
passing_td_pts = 45 * 6
rushing_yards_pts = 1035 * 0.1
rushing_td_pts = 4 * 6
rushing_attempts_pts = 161 * 0.5
rushing_first_down_pts = 55 * 1  # 1 point per first down

manual_total = passing_yards_pts + passing_td_pts + rushing_yards_pts + rushing_td_pts + rushing_attempts_pts + rushing_first_down_pts

print(f'Manual calculation with first downs:')
print(f'Passing yards: {passing_yards_pts}')
print(f'Passing TDs: {passing_td_pts}')
print(f'Rushing yards: {rushing_yards_pts}')
print(f'Rushing TDs: {rushing_td_pts}')
print(f'Rushing attempts: {rushing_attempts_pts}')
print(f'Rushing first downs: {rushing_first_down_pts}')
print(f'Total: {manual_total}')
print(f'Actual: {lamar["total_points"].iloc[0]}')
print(f'Match: {abs(manual_total - lamar["total_points"].iloc[0]) < 0.1}') 
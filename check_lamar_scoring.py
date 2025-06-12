import pandas as pd

df = pd.read_parquet('data/features/player_features.parquet')
lamar = df[(df['player_name'] == 'Lamar Jackson') & (df['season'] == 2024)]

print('Lamar Jackson 2024 point breakdown:')
cols = [col for col in lamar.columns if 'points' in col]
total_check = 0
for col in cols:
    value = lamar[col].iloc[0]
    print(f'{col}: {value}')
    total_check += value

print(f'\nTotal calculated: {total_check}')
print(f'Total in data: {lamar["total_points"].iloc[0]}')
print(f'Difference: {lamar["total_points"].iloc[0] - total_check}')

# Check for first down points
print(f'\nFirst down components:')
print(f'rushing_first_down_points: {lamar["rushing_first_down_points"].iloc[0] if "rushing_first_down_points" in lamar.columns else "Not found"}')
print(f'receiving_first_down_points: {lamar["receiving_first_down_points"].iloc[0] if "receiving_first_down_points" in lamar.columns else "Not found"}') 
import pandas as pd

df = pd.read_parquet('data/features/player_features.parquet')

# Check columns
print("Available columns with 'receiving' or 'rushing':")
cols = [col for col in df.columns if 'receiving' in col or 'rushing' in col]
for col in sorted(cols):
    print(f"  {col}")

print("\n" + "="*60)

# Get Chase and Barkley data
chase = df[(df['player_name'] == "Ja'Marr Chase") & (df['season'] == 2024)]
barkley = df[(df['player_name'] == 'Saquon Barkley') & (df['season'] == 2024)]

print("Ja'Marr Chase 2024:")
print(f"  Receiving yards: {chase['receiving_yards'].iloc[0]}")
print(f"  Receiving TDs: {chase['receiving_touchdown'].iloc[0]}")
print(f"  Receptions: {chase['receptions'].iloc[0]}")
print(f"  Total points: {chase['total_points'].iloc[0]:.1f}")

print("\nSaquon Barkley 2024:")
print(f"  Rushing yards: {barkley['rushing_yards'].iloc[0]}")
print(f"  Rushing TDs: {barkley['rushing_touchdown'].iloc[0] if 'rushing_touchdown' in barkley.columns else 'N/A'}")
print(f"  Rushing attempts: {barkley['rushing_attempt'].iloc[0] if 'rushing_attempt' in barkley.columns else 'N/A'}")
print(f"  Receiving yards: {barkley['receiving_yards'].iloc[0]}")
print(f"  Receiving TDs: {barkley['receiving_touchdown'].iloc[0]}")
print(f"  Receptions: {barkley['receptions'].iloc[0]}")
print(f"  Total points: {barkley['total_points'].iloc[0]:.1f}")

# Check all columns to find the right ones
print("\nAll columns containing 'attempt' or 'touchdown':")
cols = [col for col in df.columns if 'attempt' in col or 'touchdown' in col]
for col in sorted(cols):
    print(f"  {col}")

# Manual calculation for both using the point columns directly
print("\nUsing point columns directly:")
print("Ja'Marr Chase:")
print(f"  Receiving yards points: {chase['receiving_yards_points'].iloc[0]}")
print(f"  Receiving TD points: {chase['receiving_td_points'].iloc[0]}")
print(f"  Reception points: {chase['receptions_points'].iloc[0]}")
print(f"  Receiving first down points: {chase['receiving_first_down_points'].iloc[0]}")

print("\nSaquon Barkley:")
print(f"  Rushing yards points: {barkley['rushing_yards_points'].iloc[0]}")
print(f"  Rushing TD points: {barkley['rushing_td_points'].iloc[0]}")
print(f"  Rushing attempt points: {barkley['rushing_attempt_points'].iloc[0]}")
print(f"  Rushing first down points: {barkley['rushing_first_down_points'].iloc[0]}")
print(f"  Receiving yards points: {barkley['receiving_yards_points'].iloc[0]}")
print(f"  Receiving TD points: {barkley['receiving_td_points'].iloc[0]}")
print(f"  Reception points: {barkley['receptions_points'].iloc[0]}")
print(f"  Receiving first down points: {barkley['receiving_first_down_points'].iloc[0]}")

# Calculate totals
chase_total = (chase['receiving_yards_points'].iloc[0] + 
               chase['receiving_td_points'].iloc[0] + 
               chase['receptions_points'].iloc[0] + 
               chase['receiving_first_down_points'].iloc[0])

barkley_total = (barkley['rushing_yards_points'].iloc[0] + 
                 barkley['rushing_td_points'].iloc[0] + 
                 barkley['rushing_attempt_points'].iloc[0] + 
                 barkley['rushing_first_down_points'].iloc[0] +
                 barkley['receiving_yards_points'].iloc[0] + 
                 barkley['receiving_td_points'].iloc[0] + 
                 barkley['receptions_points'].iloc[0] + 
                 barkley['receiving_first_down_points'].iloc[0])

print(f"\nCalculated totals:")
print(f"Chase: {chase_total:.1f} vs actual {chase['total_points'].iloc[0]:.1f}")
print(f"Barkley: {barkley_total:.1f} vs actual {barkley['total_points'].iloc[0]:.1f}")

print(f"\nWhy RBs score higher:")
print(f"Barkley gets {barkley['rushing_attempt_points'].iloc[0]:.1f} points just from rushing attempts")
print(f"Barkley gets {barkley['rushing_first_down_points'].iloc[0]:.1f} points from rushing first downs")
print(f"These are bonus points that WRs don't get") 
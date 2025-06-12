import nfl_data_py as nfl
import pandas as pd
import os

# --- Configuration ---
YEARS = range(2014, 2025)
OUTPUT_DIR = "data/processed"
POSITIONS = ["QB", "RB", "WR", "TE", "K"]
SEASON_STATS_PATH = os.path.join(OUTPUT_DIR, "season_stats.parquet")
WEEKLY_STATS_PATH = os.path.join(OUTPUT_DIR, "weekly_stats.parquet")

print("Starting data ingestion...")

# Load data
pbp_df = nfl.import_pbp_data(years=list(YEARS), downcast=True)
roster_df = nfl.import_seasonal_rosters(years=list(YEARS))

# Prepare roster data
roster_df['player_id'] = roster_df['player_id'].astype(str)
roster_filtered = (
    roster_df[roster_df["position"].isin(POSITIONS)][['player_id', 'player_name', 'season', 'position', 'team']]
    .rename(columns={"player_id": "gsis_id"})
)

# FIXED: Process each player role separately to avoid double-counting
print("Processing passing stats...")
passing_stats = pbp_df[pbp_df['passer_player_id'].notna()].copy()
passing_stats = passing_stats.merge(
    roster_filtered, 
    left_on=['passer_player_id', 'season'], 
    right_on=['gsis_id', 'season'], 
    how='inner'
)
passing_stats = passing_stats.groupby(['season', 'week', 'gsis_id', 'player_name', 'position', 'team']).agg({
    'pass_attempt': 'sum',
    'complete_pass': 'sum', 
    'passing_yards': 'sum',
    'pass_touchdown': 'sum',
    'interception': 'sum'
}).reset_index()

print("Processing rushing stats...")
rushing_stats = pbp_df[pbp_df['rusher_player_id'].notna()].copy()
rushing_stats = rushing_stats.merge(
    roster_filtered,
    left_on=['rusher_player_id', 'season'],
    right_on=['gsis_id', 'season'],
    how='inner'
)
rushing_stats = rushing_stats.groupby(['season', 'week', 'gsis_id', 'player_name', 'position', 'team']).agg({
    'rush_attempt': 'sum',
    'rushing_yards': 'sum', 
    'rush_touchdown': 'sum',
    'first_down_rush': 'sum'
}).reset_index()

print("Processing receiving stats...")
receiving_stats = pbp_df[pbp_df['receiver_player_id'].notna()].copy()
receiving_stats = receiving_stats.merge(
    roster_filtered,
    left_on=['receiver_player_id', 'season'],
    right_on=['gsis_id', 'season'],
    how='inner'
)
# Calculate receptions properly
receiving_stats['receptions'] = (receiving_stats['complete_pass'] == 1).astype(int)
receiving_stats = receiving_stats.groupby(['season', 'week', 'gsis_id', 'player_name', 'position', 'team']).agg({
    'receptions': 'sum',
    'receiving_yards': 'sum',
    'touchdown': 'sum',  # This is receiving TDs
    'first_down_pass': 'sum'
}).reset_index()

print("Processing kicking stats...")
kicking_stats = pbp_df[pbp_df['kicker_player_id'].notna()].copy()
kicking_stats = kicking_stats.merge(
    roster_filtered,
    left_on=['kicker_player_id', 'season'],
    right_on=['gsis_id', 'season'],
    how='inner'
)
# Calculate kicking points
kicking_stats['fg_made'] = (kicking_stats['field_goal_result'] == 'made').astype(int)
kicking_stats['pat_made'] = (kicking_stats['extra_point_result'] == 'good').astype(int)
kicking_stats['fg_distance'] = kicking_stats['kick_distance'] * kicking_stats['fg_made']
kicking_stats = kicking_stats.groupby(['season', 'week', 'gsis_id', 'player_name', 'position', 'team']).agg({
    'fg_made': 'sum',
    'pat_made': 'sum',
    'fg_distance': 'sum'
}).reset_index()

print("Combining all stats...")
# Get all unique player-week combinations
all_players = []
for stats_df in [passing_stats, rushing_stats, receiving_stats, kicking_stats]:
    if len(stats_df) > 0:
        all_players.append(stats_df[['season', 'week', 'gsis_id', 'player_name', 'position', 'team']])

if all_players:
    all_players_df = pd.concat(all_players).drop_duplicates()
else:
    print("No player data found!")
    exit(1)

# Merge all stats
final_df = all_players_df.copy()

# Merge passing stats
final_df = final_df.merge(
    passing_stats[['season', 'week', 'gsis_id', 'pass_attempt', 'complete_pass', 'passing_yards', 'pass_touchdown', 'interception']], 
    on=['season', 'week', 'gsis_id'], 
    how='left'
)

# Merge rushing stats  
final_df = final_df.merge(
    rushing_stats[['season', 'week', 'gsis_id', 'rush_attempt', 'rushing_yards', 'rush_touchdown', 'first_down_rush']], 
    on=['season', 'week', 'gsis_id'], 
    how='left'
)

# Merge receiving stats
final_df = final_df.merge(
    receiving_stats[['season', 'week', 'gsis_id', 'receptions', 'receiving_yards', 'touchdown', 'first_down_pass']], 
    on=['season', 'week', 'gsis_id'], 
    how='left'
)

# Merge kicking stats
final_df = final_df.merge(
    kicking_stats[['season', 'week', 'gsis_id', 'fg_made', 'pat_made', 'fg_distance']], 
    on=['season', 'week', 'gsis_id'], 
    how='left'
)

# Fill NaN values with 0
final_df = final_df.fillna(0)

# Calculate fantasy points using SFB15 Sleeper scoring
final_df['passing_yards_points'] = final_df["passing_yards"] * 0.04
final_df['passing_td_points'] = final_df["pass_touchdown"] * 6
final_df['rushing_yards_points'] = final_df["rushing_yards"] * 0.1
final_df['rushing_td_points'] = final_df["rush_touchdown"] * 6
final_df['rushing_first_down_points'] = final_df["first_down_rush"] * 1.0
final_df['rushing_attempt_points'] = final_df["rush_attempt"] * 0.5
final_df['receptions_points'] = final_df["receptions"] * 2.5
final_df['receiving_yards_points'] = final_df["receiving_yards"] * 0.1
final_df['receiving_td_points'] = final_df["touchdown"] * 6  # This is receiving TDs
final_df['receiving_first_down_points'] = final_df["first_down_pass"] * 1.0
final_df['te_reception_bonus_points'] = ((final_df["receptions"] >= 1) & (final_df["position"] == "TE")) * final_df["receptions"] * 1.0
final_df['fg_made_points'] = final_df["fg_distance"] * 0.1
final_df['pat_made_points'] = final_df["pat_made"] * 3.3

# Calculate total points
point_cols = [col for col in final_df.columns if col.endswith("_points")]
final_df["total_points"] = final_df[point_cols].sum(axis=1)

# Create weekly stats
weekly_stats_df = final_df.copy()
weekly_stats_df = weekly_stats_df.rename(columns={
    'gsis_id': 'player_id',
    'complete_pass': 'completions',
    'touchdown': 'receiving_touchdown'
})

# Create season stats
season_stats_df = weekly_stats_df.groupby(["season", "player_id", "player_name", "position", "team"]).agg({
    **{col: "sum" for col in point_cols},
    'pass_attempt': 'sum',
    'completions': 'sum', 
    'passing_yards': 'sum',
    'pass_touchdown': 'sum',
    'interception': 'sum',
    'rush_attempt': 'sum',
    'rushing_yards': 'sum',
    'rush_touchdown': 'sum',
    'receptions': 'sum',
    'receiving_yards': 'sum',
    'receiving_touchdown': 'sum',
    'week': 'count'
}).reset_index()

season_stats_df["total_points"] = season_stats_df[point_cols].sum(axis=1)
season_stats_df = season_stats_df.rename(columns={"week": "games_played"})

# Save data
os.makedirs(OUTPUT_DIR, exist_ok=True)
weekly_stats_df.to_parquet(WEEKLY_STATS_PATH, index=False)
season_stats_df.to_parquet(SEASON_STATS_PATH, index=False)

print(f"Successfully saved weekly stats to {WEEKLY_STATS_PATH}")
print(f"Successfully saved seasonal stats to {SEASON_STATS_PATH}")
print(f"Processed {len(season_stats_df)} player-seasons") 
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
    roster_df[roster_df["position"].isin(POSITIONS)]
    .rename(columns={"player_id": "gsis_id"})
    .drop(columns=['week'])  # Remove week from roster to avoid conflict
    # Keep season information - don't drop duplicates yet
)

# Prepare player data
player_cols = ['passer_player_id', 'rusher_player_id', 'receiver_player_id']
pbp_players = pbp_df.dropna(subset=player_cols, how='all')

# Melt data
id_vars = ['play_id', 'game_id', 'season', 'week', 'posteam', 'defteam', 'down', 'ydstogo', 'yards_gained', 'complete_pass', 'pass_touchdown', 'rush_touchdown', 'first_down_rush', 'first_down_pass', 'touchdown', 'interception', 'pass_attempt', 'rush_attempt', 'passing_yards', 'rushing_yards', 'receiving_yards', 'kick_distance', 'extra_point_result']
pbp_melted = pd.melt(pbp_players, id_vars=id_vars, value_vars=player_cols, var_name='player_role', value_name='player_id').dropna(subset=['player_id'])

# Merge with roster (now includes season)
final_df = pbp_melted.merge(roster_filtered, left_on=['player_id', 'season'], right_on=['gsis_id', 'season'], how='inner')

# Calculate fantasy points
final_df['receptions'] = (final_df['complete_pass'] == 1) & (final_df['player_role'] == 'receiver_player_id')
final_df['passing_yards_points'] = final_df["passing_yards"] * 0.04
final_df['passing_td_points'] = final_df["pass_touchdown"] * 6
final_df['rushing_yards_points'] = final_df["rushing_yards"] * 0.1
final_df['rushing_td_points'] = final_df["rush_touchdown"] * 6
final_df['rushing_first_down_points'] = final_df["first_down_rush"] * 1.0
final_df['rushing_attempt_points'] = final_df["rush_attempt"] * 0.5
final_df['receptions_points'] = final_df["receptions"] * 2.5
final_df['receiving_yards_points'] = final_df["receiving_yards"] * 0.1
final_df['receiving_td_points'] = final_df["touchdown"] * 6
final_df['receiving_first_down_points'] = final_df["first_down_pass"] * 1.0
final_df['te_reception_bonus_points'] = ((final_df["receptions"] == 1) & (final_df["position"] == "TE")) * 1.0
final_df['fg_made_points'] = final_df["kick_distance"] * 0.1
final_df['pat_made_points'] = (final_df["extra_point_result"] == "good") * 3.3
final_df = final_df.fillna(0)

# Aggregate stats
point_cols = [col for col in final_df.columns if col.endswith("_points")]
raw_stats = {
    "pass_attempt": "sum", "complete_pass": "sum", "passing_yards": "sum",
    "pass_touchdown": "sum", "interception": "sum", "rush_attempt": "sum",
    "rushing_yards": "sum", "rush_touchdown": "sum", "receptions": "sum",
    "receiving_yards": "sum", "touchdown": "sum"
}
agg_dict = {**{col: "sum" for col in point_cols}, **raw_stats}

weekly_stats_df = final_df.groupby(["season", "week", "player_id", "player_name", "position"]).agg(agg_dict).reset_index()
weekly_stats_df["total_points"] = weekly_stats_df[point_cols].sum(axis=1)

season_stats_df = weekly_stats_df.groupby(["season", "player_id", "player_name", "position"]).agg({**agg_dict, 'week': 'count'}).reset_index()
season_stats_df["total_points"] = season_stats_df[point_cols].sum(axis=1)
season_stats_df = season_stats_df.rename(columns={"week": "games_played", "complete_pass": "completions", "touchdown": "receiving_touchdown"})


# Save data
os.makedirs(OUTPUT_DIR, exist_ok=True)
weekly_stats_df.to_parquet(WEEKLY_STATS_PATH, index=False)
season_stats_df.to_parquet(SEASON_STATS_PATH, index=False)

print(f"Successfully saved weekly stats to {WEEKLY_STATS_PATH}")
print(f"Successfully saved seasonal stats to {SEASON_STATS_PATH}") 
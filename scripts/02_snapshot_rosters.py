"""
Script to snapshot current NFL roster data for the 2025 season.
This creates a clean roster file with the most up-to-date player information.
"""

import nfl_data_py as nfl
import pandas as pd
import os
from datetime import datetime

# Configuration
OUTPUT_DIR = "data/raw"
POSITIONS = ["QB", "RB", "WR", "TE", "K"]
CURRENT_YEAR = 2024  # Most recent complete season

def main():
    print("Starting roster snapshot...")
    
    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Load the most recent roster data
    print(f"Loading {CURRENT_YEAR} roster data...")
    roster_df = nfl.import_seasonal_rosters(years=[CURRENT_YEAR])
    
    # Filter to relevant positions and clean up
    print("Filtering and cleaning roster data...")
    roster_clean = (
        roster_df[roster_df["position"].isin(POSITIONS)]
        .copy()
    )
    
    # Calculate age as of start of 2025 season (approximate)
    if 'birth_date' in roster_clean.columns:
        roster_clean['birth_date'] = pd.to_datetime(roster_clean['birth_date'])
        season_start_2025 = pd.to_datetime('2025-09-01')
        roster_clean['age_2025'] = (season_start_2025 - roster_clean['birth_date']).dt.days / 365.25
        roster_clean['age_2025'] = roster_clean['age_2025'].round(1)
    
    # Remove duplicate players, keeping the most recent entry
    roster_clean = (
        roster_clean
        .sort_values(['player_id', 'season'], ascending=[True, False])
        .drop_duplicates('player_id', keep='first')
    )
    
    # Select and order relevant columns
    key_columns = [
        'player_id', 'player_name', 'position', 'team', 'jersey_number',
        'height', 'weight', 'age', 'age_2025', 'years_exp', 'rookie_year',
        'college', 'draft_number', 'draft_club'
    ]
    
    # Only keep columns that exist in the data
    available_columns = [col for col in key_columns if col in roster_clean.columns]
    roster_final = roster_clean[available_columns].copy()
    
    # Add snapshot metadata
    snapshot_date = datetime.now().strftime('%Y-%m-%d')
    
    # Sort by position and name for easy browsing
    roster_final = roster_final.sort_values(['position', 'player_name'])
    
    # Save the snapshot
    output_file = os.path.join(OUTPUT_DIR, f"roster_snapshot_{snapshot_date}.csv")
    roster_final.to_csv(output_file, index=False)
    
    # Also save as a standard name for easy import
    standard_file = os.path.join(OUTPUT_DIR, "roster_2025.csv")
    roster_final.to_csv(standard_file, index=False)
    
    print(f"Roster snapshot saved to: {output_file}")
    print(f"Standard roster file saved to: {standard_file}")
    print(f"Total players: {len(roster_final)}")
    print(f"Position breakdown:")
    print(roster_final['position'].value_counts().sort_index())
    
    # Display sample of the data
    print(f"\nSample roster data:")
    print(roster_final.head(10))

if __name__ == "__main__":
    main() 
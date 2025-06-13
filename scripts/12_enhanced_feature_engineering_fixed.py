"""
Enhanced Feature Engineering with Starter Probability and Injury Risk (Fixed Version)
"""

import pandas as pd
import numpy as np
from datetime import datetime
import os

def create_enhanced_features():
    """Create enhanced features with starter probability and injury risk"""
    print("Loading historical data...")
    historical_data = pd.read_parquet('data/processed/season_stats.parquet')
    print(f"Loaded {len(historical_data)} historical records")
    
    # Start with base historical data
    enhanced_features = historical_data.copy()
    
    print("Adding starter probability features...")
    
    # Calculate historical starter probability for each player-season
    starter_features = []
    
    for season in historical_data['season'].unique():
        season_data = historical_data[historical_data['season'] == season]
        
        for team in season_data['team'].unique():
            for position in ['QB', 'RB', 'WR', 'TE']:
                team_pos_players = season_data[
                    (season_data['team'] == team) & 
                    (season_data['position'] == position)
                ].copy()
                
                if len(team_pos_players) == 0:
                    continue
                
                # Sort by games played and total points to identify starter
                team_pos_players = team_pos_players.sort_values(
                    ['games_played', 'total_points'], ascending=False
                )
                
                total_games = team_pos_players['games_played'].sum()
                total_points = team_pos_players['total_points'].sum()
                
                for idx, (_, player) in enumerate(team_pos_players.iterrows()):
                    player_id = player['player_id']
                    
                    if total_games > 0:
                        games_share = player['games_played'] / max(total_games, 17)
                        points_share = player['total_points'] / max(total_points, 1) if total_points > 0 else 0
                    else:
                        games_share = 0
                        points_share = 0
                    
                    # Calculate starter probability based on usage
                    if idx == 0 and player['games_played'] >= 10:
                        starter_prob = min(0.95, 0.5 + games_share * 0.5)
                    elif idx == 0:
                        starter_prob = min(0.8, games_share * 0.8)
                    elif idx == 1 and player['games_played'] >= 8:
                        starter_prob = min(0.4, games_share * 0.6)
                    else:
                        starter_prob = min(0.2, games_share * 0.3)
                    
                    starter_features.append({
                        'player_id': player_id,
                        'season': season,
                        'starter_probability_hist': starter_prob,
                        'games_share': games_share,
                        'points_share': points_share,
                        'depth_chart_rank': idx + 1
                    })
    
    starter_df = pd.DataFrame(starter_features)
    
    # Add rolling averages for starter probability
    starter_df = starter_df.sort_values(['player_id', 'season'])
    starter_df['starter_prob_prev_season'] = starter_df.groupby('player_id')['starter_probability_hist'].shift(1)
    starter_df['starter_prob_2yr_avg'] = starter_df.groupby('player_id')['starter_probability_hist'].rolling(2, min_periods=1).mean().values
    
    print("Adding injury risk features...")
    
    # Calculate injury risk features
    injury_features = []
    
    for _, player_season in historical_data.iterrows():
        player_id = player_season['player_id']
        season = player_season['season']
        position = player_season['position']
        games_played = player_season['games_played']
        
        # Calculate injury metrics
        games_missed = max(0, 17 - games_played)
        injury_rate = games_missed / 17
        
        # Position-specific injury baselines
        position_baselines = {
            'QB': 1.2, 'RB': 3.1, 'WR': 2.3, 'TE': 2.7
        }
        baseline_missed = position_baselines.get(position, 2.5)
        
        # Calculate relative injury risk
        injury_risk_score = games_missed / max(baseline_missed, 0.5)
        
        injury_features.append({
            'player_id': player_id,
            'season': season,
            'games_missed': games_missed,
            'injury_rate': injury_rate,
            'injury_risk_score': injury_risk_score,
            'baseline_games_missed': baseline_missed
        })
    
    injury_df = pd.DataFrame(injury_features)
    
    # Add injury history features
    injury_df = injury_df.sort_values(['player_id', 'season'])
    injury_df['injury_risk_prev_season'] = injury_df.groupby('player_id')['injury_risk_score'].shift(1)
    injury_df['injury_risk_2yr_avg'] = injury_df.groupby('player_id')['injury_risk_score'].rolling(2, min_periods=1).mean().values
    injury_df['games_missed_prev_season'] = injury_df.groupby('player_id')['games_missed'].shift(1)
    injury_df['career_injury_rate'] = injury_df.groupby('player_id')['injury_rate'].expanding().mean().values
    
    print("Adding team context features...")
    
    # Create team-level features
    team_features = []
    
    for season in historical_data['season'].unique():
        season_data = historical_data[historical_data['season'] == season]
        
        # Calculate team-level metrics
        team_stats = season_data.groupby('team').agg({
            'total_points': ['sum', 'mean', 'std'],
            'games_played': 'sum'
        }).round(2)
        
        team_stats.columns = ['team_total_points', 'team_avg_points', 'team_points_std', 'team_total_games']
        team_stats = team_stats.reset_index()
        team_stats['season'] = season
        
        # Add position-specific team stats
        for position in ['QB', 'RB', 'WR', 'TE']:
            pos_data = season_data[season_data['position'] == position]
            if len(pos_data) > 0:
                pos_team_stats = pos_data.groupby('team')['total_points'].agg(['sum', 'count']).fillna(0)
                pos_team_stats.columns = [f'{position.lower()}_team_points', f'{position.lower()}_team_count']
                team_stats = team_stats.merge(pos_team_stats, left_on='team', right_index=True, how='left')
        
        team_features.append(team_stats)
    
    team_df = pd.concat(team_features, ignore_index=True)
    team_df = team_df.fillna(0)
    
    print("Merging all features...")
    
    # Merge all features with base data
    # Merge starter features
    enhanced_features = enhanced_features.merge(
        starter_df, 
        on=['player_id', 'season'], 
        how='left'
    )
    
    # Merge injury features  
    enhanced_features = enhanced_features.merge(
        injury_df,
        on=['player_id', 'season'],
        how='left'
    )
    
    # Merge team features
    enhanced_features = enhanced_features.merge(
        team_df,
        on=['team', 'season'],
        how='left'
    )
    
    # Fill missing values
    enhanced_features = enhanced_features.fillna(0)
    
    print("Saving enhanced features...")
    
    os.makedirs('data/features_enhanced', exist_ok=True)
    
    # Save by position
    for position in ['QB', 'RB', 'WR', 'TE']:
        pos_features = enhanced_features[enhanced_features['position'] == position]
        
        if len(pos_features) > 0:
            output_file = f'data/features_enhanced/{position.lower()}_features_enhanced.parquet'
            pos_features.to_parquet(output_file, index=False)
            print(f"Saved {len(pos_features)} {position} enhanced features")
    
    # Save combined file
    combined_file = 'data/features_enhanced/all_features_enhanced.parquet'
    enhanced_features.to_parquet(combined_file, index=False)
    
    print(f"Enhanced feature engineering complete!")
    print(f"Total records: {len(enhanced_features)}")
    print(f"Total features: {len(enhanced_features.columns)}")
    print(f"New features include: starter_probability_hist, injury_risk_score, team context")
    
    return enhanced_features

if __name__ == "__main__":
    enhanced_features = create_enhanced_features() 
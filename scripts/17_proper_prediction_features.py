"""
Proper Prediction Features (Pure Forward-Looking)

This creates features for TRUE PREDICTION scenarios where we only use
information available BEFORE the season starts to predict season performance.

NO CURRENT SEASON DATA ALLOWED - only previous seasons and external factors.
"""

import pandas as pd
import numpy as np
from datetime import datetime
import os

def create_pure_prediction_features():
    """Create features for pure prediction - no current season data allowed"""
    print("Loading historical data...")
    historical_data = pd.read_parquet('data/processed/season_stats.parquet')
    print(f"Loaded {len(historical_data)} historical records")
    
    # Sort by player and season for proper lag calculations
    historical_data = historical_data.sort_values(['player_id', 'season'])
    
    print("Creating PURE prediction features (no current season data)...")
    print("Simulating prediction scenario: using only pre-season information")
    
    prediction_features = []
    
    for _, current_row in historical_data.iterrows():
        player_id = current_row['player_id']
        current_season = current_row['season']
        position = current_row['position']
        team = current_row['team']
        
        # Get all PREVIOUS seasons for this player (no current season!)
        prev_seasons = historical_data[
            (historical_data['player_id'] == player_id) & 
            (historical_data['season'] < current_season)
        ].sort_values('season')
        
        # Get team's PREVIOUS season performance (no current season!)
        prev_team_seasons = historical_data[
            (historical_data['team'] == team) & 
            (historical_data['season'] == current_season - 1)
        ]
        
        # Initialize features - ONLY metadata and target
        features = {
            'player_id': player_id,
            'season': current_season,
            'position': position,
            'team': team,
            'total_points': current_row['total_points']  # This is our TARGET (not a feature!)
        }
        
        # === PURE PREDICTION FEATURES (Pre-Season Information Only) ===
        
        # 1. Previous Season Performance (Most Recent Available)
        if len(prev_seasons) > 0:
            last_season = prev_seasons.iloc[-1]
            features['prev_total_points'] = last_season['total_points']
            features['prev_games_played'] = last_season['games_played']
            features['prev_points_per_game'] = last_season['total_points'] / max(last_season['games_played'], 1)
            features['prev_was_starter'] = 1 if last_season['games_played'] >= 12 else 0
            features['prev_games_missed'] = max(0, 17 - last_season['games_played'])
            
            # Previous season position-specific stats
            if position == 'QB':
                features['prev_passing_yards'] = last_season.get('passing_yards', 0)
                features['prev_pass_attempts'] = last_season.get('pass_attempt', 0)
                features['prev_pass_tds'] = last_season.get('pass_touchdown', 0)
                features['prev_rushing_yards'] = last_season.get('rushing_yards', 0)
            elif position == 'RB':
                features['prev_rushing_yards'] = last_season.get('rushing_yards', 0)
                features['prev_rush_attempts'] = last_season.get('rush_attempt', 0)
                features['prev_rush_tds'] = last_season.get('rush_touchdown', 0)
                features['prev_receptions'] = last_season.get('receptions', 0)
            elif position in ['WR', 'TE']:
                features['prev_receiving_yards'] = last_season.get('receiving_yards', 0)
                features['prev_receptions'] = last_season.get('receptions', 0)
                features['prev_receiving_tds'] = last_season.get('receiving_touchdown', 0)
            
        else:
            # Rookie - no previous NFL data
            features.update({
                'prev_total_points': 0, 'prev_games_played': 0, 'prev_points_per_game': 0,
                'prev_was_starter': 0, 'prev_games_missed': 0,
                'prev_passing_yards': 0, 'prev_pass_attempts': 0, 'prev_pass_tds': 0,
                'prev_rushing_yards': 0, 'prev_rush_attempts': 0, 'prev_rush_tds': 0,
                'prev_receiving_yards': 0, 'prev_receptions': 0, 'prev_receiving_tds': 0
            })
        
        # 2. Career Trends (Multi-Season Patterns)
        if len(prev_seasons) >= 3:
            # 3-year career averages
            last_three = prev_seasons.tail(3)
            features['career_3yr_avg_points'] = last_three['total_points'].mean()
            features['career_3yr_avg_games'] = last_three['games_played'].mean()
            features['career_3yr_points_std'] = last_three['total_points'].std()
            
            # Career trajectory (improving/declining)
            recent_2yr = prev_seasons.tail(2)['total_points'].mean()
            older_2yr = prev_seasons.tail(4).head(2)['total_points'].mean() if len(prev_seasons) >= 4 else recent_2yr
            features['career_trajectory'] = recent_2yr - older_2yr
            
        elif len(prev_seasons) >= 2:
            # 2-year averages
            last_two = prev_seasons.tail(2)
            features['career_3yr_avg_points'] = last_two['total_points'].mean()
            features['career_3yr_avg_games'] = last_two['games_played'].mean()
            features['career_3yr_points_std'] = last_two['total_points'].std()
            features['career_trajectory'] = last_two.iloc[-1]['total_points'] - last_two.iloc[0]['total_points']
            
        elif len(prev_seasons) == 1:
            # Single season
            features.update({
                'career_3yr_avg_points': prev_seasons.iloc[0]['total_points'],
                'career_3yr_avg_games': prev_seasons.iloc[0]['games_played'],
                'career_3yr_points_std': 0,
                'career_trajectory': 0
            })
        else:
            # Rookie
            features.update({
                'career_3yr_avg_points': 0, 'career_3yr_avg_games': 0,
                'career_3yr_points_std': 0, 'career_trajectory': 0
            })
        
        # 3. Experience and Age Proxies
        features['years_experience'] = len(prev_seasons)
        features['is_rookie'] = 1 if len(prev_seasons) == 0 else 0
        features['is_veteran'] = 1 if len(prev_seasons) >= 5 else 0
        features['estimated_age'] = 22 + len(prev_seasons)  # Rough age estimate
        
        # 4. Historical Reliability/Durability
        if len(prev_seasons) > 0:
            games_played_history = prev_seasons['games_played'].tolist()
            features['career_avg_games'] = np.mean(games_played_history)
            features['career_games_consistency'] = np.std(games_played_history) if len(games_played_history) > 1 else 0
            features['seasons_missed_significant_time'] = sum(1 for g in games_played_history if g < 12)
            features['best_season_points'] = prev_seasons['total_points'].max()
            features['worst_season_points'] = prev_seasons['total_points'].min()
        else:
            features.update({
                'career_avg_games': 0, 'career_games_consistency': 0,
                'seasons_missed_significant_time': 0, 'best_season_points': 0, 'worst_season_points': 0
            })
        
        # 5. Team Context (Previous Season Only)
        if len(prev_team_seasons) > 0:
            # Team's previous season (excluding current player)
            team_prev_others = prev_team_seasons[prev_team_seasons['player_id'] != player_id]
            
            if len(team_prev_others) > 0:
                features['team_prev_total_offense'] = team_prev_others['total_points'].sum()
                features['team_prev_avg_player_points'] = team_prev_others['total_points'].mean()
                
                # Position group context
                for pos in ['QB', 'RB', 'WR', 'TE']:
                    pos_prev = team_prev_others[team_prev_others['position'] == pos]
                    features[f'team_prev_{pos.lower()}_production'] = pos_prev['total_points'].sum()
                    features[f'team_prev_{pos.lower()}_depth'] = len(pos_prev)
            else:
                # New team/expansion
                features.update({
                    'team_prev_total_offense': 0, 'team_prev_avg_player_points': 0,
                    'team_prev_qb_production': 0, 'team_prev_qb_depth': 0,
                    'team_prev_rb_production': 0, 'team_prev_rb_depth': 0,
                    'team_prev_wr_production': 0, 'team_prev_wr_depth': 0,
                    'team_prev_te_production': 0, 'team_prev_te_depth': 0
                })
        else:
            features.update({
                'team_prev_total_offense': 0, 'team_prev_avg_player_points': 0,
                'team_prev_qb_production': 0, 'team_prev_qb_depth': 0,
                'team_prev_rb_production': 0, 'team_prev_rb_depth': 0,
                'team_prev_wr_production': 0, 'team_prev_wr_depth': 0,
                'team_prev_te_production': 0, 'team_prev_te_depth': 0
            })
        
        # 6. Position-Specific Risk Factors
        position_injury_rates = {'QB': 0.07, 'RB': 0.18, 'WR': 0.14, 'TE': 0.16}
        features['position_injury_risk'] = position_injury_rates.get(position, 0.15)
        
        # Historical injury pattern
        if len(prev_seasons) > 0:
            injury_seasons = sum(1 for _, season in prev_seasons.iterrows() if season['games_played'] < 14)
            features['historical_injury_rate'] = injury_seasons / len(prev_seasons)
        else:
            features['historical_injury_rate'] = features['position_injury_risk']  # Use position average for rookies
        
        # 7. Opportunity Indicators (Based on Historical Performance)
        if len(prev_seasons) > 0:
            # Historical starter rate
            starter_seasons = sum(1 for _, season in prev_seasons.iterrows() if season['games_played'] >= 12)
            features['historical_starter_rate'] = starter_seasons / len(prev_seasons)
            
            # Breakout potential (young player trending up)
            if len(prev_seasons) <= 3 and len(prev_seasons) >= 2:
                recent_trend = prev_seasons.tail(2)['total_points'].iloc[-1] - prev_seasons.tail(2)['total_points'].iloc[0]
                features['breakout_candidate'] = 1 if recent_trend > 50 else 0
            else:
                features['breakout_candidate'] = 0
        else:
            features['historical_starter_rate'] = 0.5  # Neutral for rookies
            features['breakout_candidate'] = 1 if position in ['RB', 'WR'] else 0  # Rookie potential
        
        # 8. Market/Draft Context (would be external data in real scenario)
        # For now, estimate based on historical performance
        if len(prev_seasons) > 0:
            best_season = prev_seasons['total_points'].max()
            if best_season > 250:
                features['player_tier'] = 1  # Elite
            elif best_season > 150:
                features['player_tier'] = 2  # Good
            elif best_season > 75:
                features['player_tier'] = 3  # Decent
            else:
                features['player_tier'] = 4  # Deep
        else:
            features['player_tier'] = 3  # Default for rookies
        
        prediction_features.append(features)
    
    # Create DataFrame
    prediction_df = pd.DataFrame(prediction_features)
    
    print(f"Created pure prediction features for {len(prediction_df)} player-seasons")
    print(f"✅ NO current season data used - true prediction scenario")
    
    # Save prediction features
    os.makedirs('data/features_prediction', exist_ok=True)
    
    # Save by position
    for position in ['QB', 'RB', 'WR', 'TE']:
        pos_features = prediction_df[prediction_df['position'] == position]
        
        if len(pos_features) > 0:
            output_file = f'data/features_prediction/{position.lower()}_prediction_features.parquet'
            pos_features.to_parquet(output_file, index=False)
            print(f"Saved {len(pos_features)} {position} prediction features")
    
    # Save combined file
    combined_file = 'data/features_prediction/all_prediction_features.parquet'
    prediction_df.to_parquet(combined_file, index=False)
    
    # Feature summary
    feature_summary = {
        'total_records': len(prediction_df),
        'feature_count': len(prediction_df.columns),
        'positions': prediction_df['position'].value_counts().to_dict(),
        'seasons': sorted(prediction_df['season'].unique().tolist()),
        'pure_prediction_features': [
            'prev_total_points', 'prev_games_played', 'career_3yr_avg_points',
            'years_experience', 'historical_starter_rate', 'team_prev_total_offense',
            'career_trajectory', 'historical_injury_rate', 'player_tier'
        ],
        'no_current_season_data': True,
        'true_prediction_scenario': True,
        'expected_correlations': '0.6-0.8 (realistic for pre-season projections)',
        'generated_timestamp': datetime.now().isoformat()
    }
    
    import json
    with open('data/features_prediction/feature_summary.json', 'w') as f:
        json.dump(feature_summary, f, indent=2)
    
    print(f"\nPure prediction feature engineering complete!")
    print(f"Total features: {len(prediction_df.columns)}")
    print(f"🎯 TRUE PREDICTION: Only pre-season info used")
    print(f"Expected correlations: 0.6-0.8 (realistic for fantasy football)")
    
    return prediction_df

if __name__ == "__main__":
    prediction_features = create_pure_prediction_features() 
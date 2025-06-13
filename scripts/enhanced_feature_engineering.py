"""
Enhanced Feature Engineering Pipeline - P0 Critical Improvements

This script implements the critical feature improvements identified in the audit
to better differentiate elite players and match industry projection standards.

Focus: Opportunity-based features that drive fantasy production differences.
"""

import pandas as pd
import numpy as np
import os
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

class EnhancedFeatureEngineer:
    """Enhanced feature engineering with opportunity-based metrics"""
    
    def __init__(self):
        self.historical_data = None
        self.roster_2025 = None
        
    def load_data(self):
        """Load historical and 2025 roster data"""
        print("Loading data for enhanced feature engineering...")
        
        try:
            self.historical_data = pd.read_parquet('data/processed/season_stats.parquet')
            print(f"✅ Loaded {len(self.historical_data)} historical records")
        except Exception as e:
            print(f"❌ Error loading historical data: {e}")
            return False
        
        try:
            self.roster_2025 = pd.read_csv('data/raw/roster_2025.csv')
            print(f"✅ Loaded {len(self.roster_2025)} players for 2025")
        except Exception as e:
            print(f"❌ Error loading 2025 roster: {e}")
            return False
            
        return True
    
    def create_qb_enhanced_features(self, player_seasons):
        """Create QB-specific enhanced features for rushing upside"""
        
        qb_features = {}
        
        # QB Rushing metrics - CRITICAL for elite separation
        qb_features.update({
            # Basic rushing per game metrics
            'career_rush_attempts_per_game': player_seasons['rush_attempt'].sum() / max(player_seasons['games_played'].sum(), 1),
            'career_rush_yards_per_game': player_seasons['rushing_yards'].sum() / max(player_seasons['games_played'].sum(), 1),
            'career_rush_tds_per_game': player_seasons['rush_touchdown'].sum() / max(player_seasons['games_played'].sum(), 1),
            
            # Recent rushing trends (last 2 seasons)
            'recent_rush_upside': 0,
            'rush_trend_improving': 0,
            'high_rush_game_frequency': 0,
            
            # Elite rushing indicators
            'has_elite_rushing_ceiling': 0,
            'mobility_score': 0
        })
        
        # Calculate recent rushing trends
        if len(player_seasons) >= 2:
            recent_seasons = player_seasons.tail(2)
            recent_rush_ypg = recent_seasons['rushing_yards'].sum() / max(recent_seasons['games_played'].sum(), 1)
            qb_features['recent_rush_upside'] = recent_rush_ypg
            
            # Check for improvement trend
            if len(recent_seasons) == 2:
                older_rypg = recent_seasons.iloc[0]['rushing_yards'] / max(recent_seasons.iloc[0]['games_played'], 1)
                newer_rypg = recent_seasons.iloc[1]['rushing_yards'] / max(recent_seasons.iloc[1]['games_played'], 1)
                if newer_rypg > older_rypg:
                    qb_features['rush_trend_improving'] = 1
        
        # Elite rushing ceiling indicators
        career_rush_ypg = qb_features['career_rush_yards_per_game']
        career_rush_apg = qb_features['career_rush_attempts_per_game']
        
        # Define elite rushing thresholds based on historical data
        if career_rush_ypg > 25:  # Elite rushers like Lamar, Josh Allen
            qb_features['has_elite_rushing_ceiling'] = 1
            qb_features['mobility_score'] = min(career_rush_ypg / 10, 10)  # Scale 0-10
        elif career_rush_ypg > 15:  # Solid rushing QBs
            qb_features['mobility_score'] = career_rush_ypg / 10
        
        # High rush game frequency (games with 50+ rush yards)
        if len(player_seasons) > 0:
            games_played = player_seasons['games_played'].sum()
            total_seasons = len(player_seasons)
            # Approximate high rush games (simplified calculation)
            estimated_high_rush_games = max(0, (career_rush_ypg - 20) * games_played / 50)
            qb_features['high_rush_game_frequency'] = estimated_high_rush_games / max(games_played, 1)
        
        return qb_features
    
    def create_rb_enhanced_features(self, player_seasons):
        """Create RB-specific enhanced features for usage and opportunity"""
        
        rb_features = {}
        
        # Reception/Target metrics - critical for PPR
        total_games = player_seasons['games_played'].sum()
        total_receptions = player_seasons['receptions'].sum() 
        total_rec_yards = player_seasons['receiving_yards'].sum()
        total_rec_tds = player_seasons['receiving_touchdown'].sum()
        
        rb_features.update({
            # Receiving role metrics
            'career_receptions_per_game': total_receptions / max(total_games, 1),
            'career_receiving_yards_per_game': total_rec_yards / max(total_games, 1),
            'career_receiving_tds_per_game': total_rec_tds / max(total_games, 1),
            
            # Estimated target share (simplified)
            'estimated_target_share': 0,
            'pass_catching_role': 0,
            
            # Usage intensity
            'workload_intensity': 0,
            'three_down_back_score': 0,
            
            # Efficiency metrics
            'yards_per_touch': 0,
            'red_zone_efficiency': 0
        })
        
        # Calculate receiving role strength
        rpg = rb_features['career_receptions_per_game']
        if rpg >= 4:  # High-usage receiving backs
            rb_features['pass_catching_role'] = 1
            rb_features['estimated_target_share'] = min(rpg * 1.2, 8)  # Estimate targets from receptions
        elif rpg >= 2:  # Moderate receiving role
            rb_features['pass_catching_role'] = 0.5
            rb_features['estimated_target_share'] = rpg * 1.3
        
        # Three-down back score (rushing + receiving)
        rush_ypg = player_seasons['rushing_yards'].sum() / max(total_games, 1)
        rec_ypg = rb_features['career_receiving_yards_per_game']
        
        if rush_ypg > 60 and rec_ypg > 20:  # Elite three-down back
            rb_features['three_down_back_score'] = 1
        elif rush_ypg > 40 and rec_ypg > 10:  # Solid three-down usage
            rb_features['three_down_back_score'] = 0.6
        elif rush_ypg > 60 or rec_ypg > 30:  # Specialist with upside
            rb_features['three_down_back_score'] = 0.4
        
        # Workload intensity (total touches per game)
        total_touches = player_seasons['rush_attempt'].sum() + total_receptions
        rb_features['workload_intensity'] = total_touches / max(total_games, 1)
        
        # Yards per touch efficiency
        total_yards = player_seasons['rushing_yards'].sum() + total_rec_yards
        if total_touches > 0:
            rb_features['yards_per_touch'] = total_yards / total_touches
        
        return rb_features
    
    def create_wr_enhanced_features(self, player_seasons):
        """Create WR-specific enhanced features for target share and usage"""
        
        wr_features = {}
        
        total_games = player_seasons['games_played'].sum()
        total_receptions = player_seasons['receptions'].sum()
        total_rec_yards = player_seasons['receiving_yards'].sum()
        total_rec_tds = player_seasons['receiving_touchdown'].sum()
        
        wr_features.update({
            # Reception metrics
            'career_receptions_per_game': total_receptions / max(total_games, 1),
            'career_receiving_yards_per_game': total_rec_yards / max(total_games, 1),
            'career_receiving_tds_per_game': total_rec_tds / max(total_games, 1),
            
            # Target and usage estimates
            'estimated_target_share': 0,
            'wr1_potential': 0,
            'red_zone_role': 0,
            
            # Efficiency and ceiling
            'yards_per_reception': 0,
            'big_play_ability': 0,
            'target_quality_score': 0
        })
        
        # Calculate target estimates and usage
        rpg = wr_features['career_receptions_per_game']
        ypg = wr_features['career_receiving_yards_per_game']
        
        # Estimate target share based on receptions (simplified model)
        if rpg >= 6:  # High-volume WR1 types
            wr_features['estimated_target_share'] = min(rpg * 1.4, 12)  # Scale to realistic targets
            wr_features['wr1_potential'] = 1
        elif rpg >= 4:  # Solid WR2/flex types
            wr_features['estimated_target_share'] = rpg * 1.5
            wr_features['wr1_potential'] = 0.6
        elif rpg >= 2.5:  # WR3/depth with upside
            wr_features['estimated_target_share'] = rpg * 1.6
            wr_features['wr1_potential'] = 0.3
        else:
            wr_features['estimated_target_share'] = rpg * 1.8
        
        # Red zone role based on TDs
        td_rate = wr_features['career_receiving_tds_per_game']
        if td_rate >= 0.5:  # High red zone usage
            wr_features['red_zone_role'] = 1
        elif td_rate >= 0.3:  # Moderate red zone role
            wr_features['red_zone_role'] = 0.6
        elif td_rate >= 0.15:  # Some red zone looks
            wr_features['red_zone_role'] = 0.3
        
        # Efficiency metrics
        if total_receptions > 0:
            wr_features['yards_per_reception'] = total_rec_yards / total_receptions
            
            # Big play ability (simplified)
            if wr_features['yards_per_reception'] > 14:  # Deep threat
                wr_features['big_play_ability'] = 1
            elif wr_features['yards_per_reception'] > 12:  # Good YAC/big plays
                wr_features['big_play_ability'] = 0.7
            elif wr_features['yards_per_reception'] > 10:  # Average
                wr_features['big_play_ability'] = 0.4
        
        # Target quality score (combination of volume and efficiency)
        target_vol = min(wr_features['estimated_target_share'] / 8, 1)  # Scale 0-1
        efficiency = min(wr_features['yards_per_reception'] / 15, 1)  # Scale 0-1
        wr_features['target_quality_score'] = (target_vol * 0.6) + (efficiency * 0.4)
        
        return wr_features
    
    def create_te_enhanced_features(self, player_seasons):
        """Create TE-specific enhanced features for role and usage"""
        
        te_features = {}
        
        total_games = player_seasons['games_played'].sum()
        total_receptions = player_seasons['receptions'].sum()
        total_rec_yards = player_seasons['receiving_yards'].sum()
        total_rec_tds = player_seasons['receiving_touchdown'].sum()
        
        te_features.update({
            # Reception metrics
            'career_receptions_per_game': total_receptions / max(total_games, 1),
            'career_receiving_yards_per_game': total_rec_yards / max(total_games, 1),
            'career_receiving_tds_per_game': total_rec_tds / max(total_games, 1),
            
            # Role definition
            'receiving_te_role': 0,
            'target_share_estimate': 0,
            'red_zone_priority': 0,
            
            # TE-specific metrics
            'te_ceiling_score': 0,
            'consistent_target_role': 0
        })
        
        # Determine receiving role strength
        rpg = te_features['career_receptions_per_game']
        ypg = te_features['career_receiving_yards_per_game']
        
        if rpg >= 4 and ypg >= 50:  # Elite receiving TE (Kelce tier)
            te_features['receiving_te_role'] = 1
            te_features['target_share_estimate'] = min(rpg * 1.3, 8)
            te_features['te_ceiling_score'] = 1
        elif rpg >= 3 and ypg >= 35:  # Strong receiving role
            te_features['receiving_te_role'] = 0.8
            te_features['target_share_estimate'] = rpg * 1.4
            te_features['te_ceiling_score'] = 0.7
        elif rpg >= 2 and ypg >= 20:  # Moderate receiving role
            te_features['receiving_te_role'] = 0.5
            te_features['target_share_estimate'] = rpg * 1.5
            te_features['te_ceiling_score'] = 0.4
        else:  # Blocking TE or minimal receiving
            te_features['receiving_te_role'] = 0.2
            te_features['target_share_estimate'] = rpg * 1.8
        
        # Red zone priority based on TDs
        td_rate = te_features['career_receiving_tds_per_game']
        if td_rate >= 0.4:  # High red zone usage
            te_features['red_zone_priority'] = 1
        elif td_rate >= 0.25:  # Moderate red zone looks
            te_features['red_zone_priority'] = 0.6
        elif td_rate >= 0.15:  # Some red zone opportunities
            te_features['red_zone_priority'] = 0.3
        
        # Consistent target role (games with 3+ receptions)
        if len(player_seasons) > 0:
            # Simplified consistency calculation
            if rpg >= 3:
                te_features['consistent_target_role'] = 1
            elif rpg >= 2:
                te_features['consistent_target_role'] = 0.7
            elif rpg >= 1:
                te_features['consistent_target_role'] = 0.4
        
        return te_features
    
    def create_team_context_features(self, player_seasons, team):
        """Create team context features for better situational modeling"""
        
        team_features = {}
        
        # Get recent team performance data (if available)
        recent_team_data = self.historical_data[
            (self.historical_data['team'] == team) & 
            (self.historical_data['season'] >= 2022)
        ]
        
        if len(recent_team_data) == 0:
            recent_team_data = self.historical_data[self.historical_data['team'] == team]
        
        if len(recent_team_data) > 0:
            # Team offensive efficiency
            team_total_points = recent_team_data['total_points'].mean()
            team_features.update({
                'team_offensive_strength': min(team_total_points / 300, 2),  # Scale relative to average
                'team_scoring_environment': 1 if team_total_points > 350 else 0.5 if team_total_points > 250 else 0,
                'high_scoring_offense': 1 if team_total_points > 400 else 0
            })
        else:
            # Default values for new/unknown teams
            team_features.update({
                'team_offensive_strength': 1,
                'team_scoring_environment': 0.5,
                'high_scoring_offense': 0
            })
        
        return team_features
    
    def create_enhanced_features_for_player(self, player_id, position, team):
        """Create all enhanced features for a single player"""
        
        # Get player's historical seasons
        player_seasons = self.historical_data[
            (self.historical_data['player_id'] == player_id) & 
            (self.historical_data['season'] < 2025)
        ].sort_values('season')
        
        # Start with basic features
        features = {
            'player_id': player_id,
            'position': position,
            'team': team,
            'career_seasons': len(player_seasons),
        }
        
        # Add basic career metrics
        if len(player_seasons) > 0:
            total_games = player_seasons['games_played'].sum()
            features.update({
                'career_games': total_games,
                'career_total_points': player_seasons['total_points'].sum(),
                'career_points_per_game': player_seasons['total_points'].sum() / max(total_games, 1),
                'games_per_season': total_games / len(player_seasons),
                'best_season_points': player_seasons['total_points'].max(),
                'worst_season_points': player_seasons['total_points'].min()
            })
            
            # Recent performance (last 2 seasons)
            recent_seasons = player_seasons.tail(2)
            features['recent_avg_ppg'] = recent_seasons['total_points'].sum() / max(recent_seasons['games_played'].sum(), 1)
            
            # Career trend
            if len(player_seasons) >= 3:
                early_avg = player_seasons.head(len(player_seasons)//2)['total_points'].mean()
                late_avg = player_seasons.tail(len(player_seasons)//2)['total_points'].mean()
                features['career_trend'] = 1 if late_avg > early_avg else 0
            else:
                features['career_trend'] = 0.5
        else:
            # Rookie defaults
            features.update({
                'career_games': 0,
                'career_total_points': 0,
                'career_points_per_game': 0,
                'games_per_season': 0,
                'best_season_points': 0,
                'worst_season_points': 0,
                'recent_avg_ppg': 0,
                'career_trend': 0.5
            })
        
        # Add position-specific enhanced features
        if position == 'QB':
            qb_features = self.create_qb_enhanced_features(player_seasons)
            features.update(qb_features)
        elif position == 'RB':
            rb_features = self.create_rb_enhanced_features(player_seasons)
            features.update(rb_features)
        elif position == 'WR':
            wr_features = self.create_wr_enhanced_features(player_seasons)
            features.update(wr_features)
        elif position == 'TE':
            te_features = self.create_te_enhanced_features(player_seasons)
            features.update(te_features)
        
        # Add team context features
        team_features = self.create_team_context_features(player_seasons, team)
        features.update(team_features)
        
        return features
    
    def generate_enhanced_features_2025(self):
        """Generate enhanced features for all 2025 players"""
        
        print("🚀 Generating enhanced features for 2025 players...")
        
        all_features = []
        
        for _, player in self.roster_2025.iterrows():
            player_id = player['player_id']
            position = player['position']
            team = player['team']
            player_name = player['player_name']
            
            try:
                features = self.create_enhanced_features_for_player(player_id, position, team)
                features['player_name'] = player_name
                all_features.append(features)
                
            except Exception as e:
                print(f"Warning: Error processing {player_name}: {e}")
                continue
        
        enhanced_features_df = pd.DataFrame(all_features)
        
        print(f"✅ Generated enhanced features for {len(enhanced_features_df)} players")
        
        # Save enhanced features
        output_dir = 'data/features'
        os.makedirs(output_dir, exist_ok=True)
        
        enhanced_features_df.to_parquet(f'{output_dir}/enhanced_features_2025.parquet', index=False)
        enhanced_features_df.to_csv(f'{output_dir}/enhanced_features_2025.csv', index=False)
        
        print(f"💾 Enhanced features saved to: {output_dir}/enhanced_features_2025.parquet")
        
        # Show summary by position
        print(f"\n📊 Enhanced Features Summary:")
        summary = enhanced_features_df.groupby('position').agg({
            'player_name': 'count',
            'career_points_per_game': ['mean', 'max'],
            'career_seasons': 'mean'
        }).round(2)
        print(summary)
        
        return enhanced_features_df
    
    def run_enhanced_feature_engineering(self):
        """Run the complete enhanced feature engineering pipeline"""
        
        print("🚀 STARTING ENHANCED FEATURE ENGINEERING PIPELINE")
        print("=" * 60)
        
        if not self.load_data():
            return None
        
        enhanced_features = self.generate_enhanced_features_2025()
        
        print(f"\n✅ Enhanced feature engineering complete!")
        print(f"📈 Next step: Retrain models with enhanced features")
        
        return enhanced_features

def main():
    """Run enhanced feature engineering"""
    engineer = EnhancedFeatureEngineer()
    return engineer.run_enhanced_feature_engineering()

if __name__ == "__main__":
    enhanced_features = main() 
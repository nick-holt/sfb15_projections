"""
VORP Calculator
Implements Value Over Replacement Player (VORP) methodology for fantasy football
Based on dynamic replacement levels calculated from actual draft data
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
import logging

class VORPCalculator:
    """Calculates VORP (Value Over Replacement Player) for fantasy football players"""
    
    def __init__(self, num_teams: int = 12):
        """
        Initialize VORP Calculator
        
        Args:
            num_teams: Number of teams in the league (default: 12)
        """
        self.num_teams = num_teams
        self.logger = logging.getLogger(__name__)
        
        # Define starting lineup requirements (standard fantasy)
        self.starting_lineup = {
            'QB': 1,   # 1 starting QB per team
            'RB': 2,   # 2 starting RBs per team  
            'WR': 3,   # 3 starting WRs per team (2 WR + 1 FLEX typically WR)
            'TE': 1    # 1 starting TE per team
        }
        
    def calculate_vorp_scores(self, projections: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate VORP scores for all players based on dynamic replacement levels
        
        Args:
            projections: DataFrame with player projections
            
        Returns:
            DataFrame with VORP scores and related metrics added
        """
        try:
            df = projections.copy()
            
            # Calculate replacement levels for each position
            replacement_levels = self._calculate_replacement_levels(df)
            self.logger.info(f"Calculated replacement levels: {replacement_levels}")
            
            # Add replacement points to each player
            df['replacement_points'] = df['position'].map(replacement_levels)
            
            # Calculate VORP for each player
            df['vorp_score'] = df['projected_points'] - df['replacement_points']
            
            # Ensure VORP is not negative (replacement level players have 0 VORP)
            df['vorp_score'] = df['vorp_score'].clip(lower=0)
            
            # Calculate VORP rank within position
            df['vorp_position_rank'] = df.groupby('position')['vorp_score'].rank(
                method='min', ascending=False
            )
            
            # Calculate overall VORP rank
            df['vorp_overall_rank'] = df['vorp_score'].rank(method='min', ascending=False)
            
            # Calculate VORP per game (accounting for expected games played)
            if 'expected_games_played' in df.columns:
                df['vorp_per_game'] = np.where(
                    df['expected_games_played'] > 0,
                    df['vorp_score'] / df['expected_games_played'],
                    0
                )
            else:
                df['vorp_per_game'] = df['vorp_score'] / 17  # Assume 17 game season
            
            # Calculate position scarcity adjusted VORP
            df['vorp_scarcity_adjusted'] = self._calculate_scarcity_adjusted_vorp(df)
            
            # Calculate draft value incorporating VORP
            df['vorp_draft_value'] = self._calculate_vorp_draft_value(df)
            
            # Add VORP tiers
            df['vorp_tier'] = self._assign_vorp_tiers(df['vorp_score'])
            
            self.logger.info(f"Calculated VORP scores for {len(df)} players")
            return df
            
        except Exception as e:
            self.logger.error(f"Error calculating VORP scores: {str(e)}")
            return projections
    
    def _calculate_replacement_levels(self, df: pd.DataFrame) -> Dict[str, float]:
        """
        Calculate dynamic replacement level points for each position
        Based on the number of starters needed across all teams
        
        Args:
            df: DataFrame with player projections
            
        Returns:
            Dictionary with replacement level points by position
        """
        replacement_levels = {}
        
        for position in ['QB', 'RB', 'WR', 'TE']:
            pos_players = df[df['position'] == position].copy()
            
            if len(pos_players) == 0:
                replacement_levels[position] = 0
                continue
            
            # Sort by projected points (descending)
            pos_players = pos_players.sort_values('projected_points', ascending=False)
            
            # Calculate replacement rank based on starting lineup needs
            starters_needed = self.starting_lineup[position] * self.num_teams
            replacement_rank = starters_needed + 1  # The next player after all starters
            
            # Get replacement level points
            if len(pos_players) >= replacement_rank:
                replacement_points = pos_players.iloc[replacement_rank - 1]['projected_points']
            else:
                # If not enough players, use the lowest available player
                replacement_points = pos_players.iloc[-1]['projected_points']
            
            replacement_levels[position] = replacement_points
            
            self.logger.debug(f"{position}: {starters_needed} starters needed, "
                            f"replacement rank {replacement_rank}, "
                            f"replacement points: {replacement_points:.1f}")
        
        return replacement_levels
    
    def _calculate_scarcity_adjusted_vorp(self, df: pd.DataFrame) -> pd.Series:
        """
        Calculate position scarcity adjusted VORP scores
        
        Args:
            df: DataFrame with VORP scores
            
        Returns:
            Series with scarcity adjusted VORP scores
        """
        # Position scarcity multipliers based on typical draft patterns
        scarcity_multipliers = {
            'QB': 0.8,   # QBs less scarce (only need 1, can wait)
            'RB': 1.3,   # RBs most scarce (need 2, limited quality)
            'WR': 1.1,   # WRs moderately scarce (need 3, but deep position)
            'TE': 1.2    # TEs scarce (need 1, but big dropoff after elite)
        }
        
        return df['vorp_score'] * df['position'].map(scarcity_multipliers)
    
    def _calculate_vorp_draft_value(self, df: pd.DataFrame) -> pd.Series:
        """
        Calculate comprehensive draft value incorporating VORP
        
        Args:
            df: DataFrame with VORP and projection data
            
        Returns:
            Series with draft value scores
        """
        # Normalize components to 0-100 scale
        max_vorp = df['vorp_score'].max() if df['vorp_score'].max() > 0 else 1
        max_scarcity = df['vorp_scarcity_adjusted'].max() if df['vorp_scarcity_adjusted'].max() > 0 else 1
        max_points = df['projected_points'].max() if df['projected_points'].max() > 0 else 1
        
        # Weight the components
        vorp_component = (df['vorp_score'] / max_vorp) * 50  # 50% weight to VORP
        scarcity_component = (df['vorp_scarcity_adjusted'] / max_scarcity) * 30  # 30% weight to scarcity
        projection_component = (df['projected_points'] / max_points) * 20  # 20% weight to raw projections
        
        return vorp_component + scarcity_component + projection_component
    
    def _assign_vorp_tiers(self, vorp_scores: pd.Series) -> pd.Series:
        """
        Assign VORP tiers based on score distribution
        
        Args:
            vorp_scores: Series with VORP scores
            
        Returns:
            Series with VORP tier labels
        """
        def get_vorp_tier(score):
            if score >= 80:
                return "Elite VORP"
            elif score >= 60:
                return "High VORP"
            elif score >= 40:
                return "Good VORP"
            elif score >= 20:
                return "Average VORP"
            elif score > 0:
                return "Low VORP"
            else:
                return "Replacement Level"
        
        return vorp_scores.apply(get_vorp_tier)
    
    def get_vorp_insights(self, df: pd.DataFrame) -> Dict[str, any]:
        """
        Generate insights based on VORP analysis
        
        Args:
            df: DataFrame with VORP calculations
            
        Returns:
            Dictionary with VORP insights
        """
        insights = {}
        
        # Position-specific insights
        for position in ['QB', 'RB', 'WR', 'TE']:
            pos_data = df[df['position'] == position].copy()
            if len(pos_data) == 0:
                continue
                
            pos_data = pos_data.sort_values('vorp_score', ascending=False)
            
            insights[position] = {
                'total_players': len(pos_data),
                'positive_vorp_players': len(pos_data[pos_data['vorp_score'] > 0]),
                'elite_vorp_players': len(pos_data[pos_data['vorp_tier'] == 'Elite VORP']),
                'top_vorp_player': pos_data.iloc[0]['player_name'] if len(pos_data) > 0 else None,
                'top_vorp_score': pos_data.iloc[0]['vorp_score'] if len(pos_data) > 0 else 0,
                'replacement_level': pos_data.iloc[0]['replacement_points'] if len(pos_data) > 0 else 0,
                'vorp_dropoff': self._calculate_vorp_dropoff(pos_data)
            }
        
        # Overall insights
        insights['overall'] = {
            'total_positive_vorp': len(df[df['vorp_score'] > 0]),
            'average_vorp': df['vorp_score'].mean(),
            'vorp_distribution': df['vorp_tier'].value_counts().to_dict(),
            'most_scarce_position': self._find_most_scarce_position(df)
        }
        
        return insights
    
    def _calculate_vorp_dropoff(self, pos_data: pd.DataFrame) -> Dict[str, float]:
        """Calculate VORP dropoff patterns for a position"""
        if len(pos_data) < 5:
            return {}
        
        # Calculate dropoff from tier to tier
        dropoffs = {}
        for i in range(1, min(6, len(pos_data))):  # First 5 players
            dropoffs[f'rank_{i}_to_{i+1}'] = pos_data.iloc[i-1]['vorp_score'] - pos_data.iloc[i]['vorp_score']
        
        return dropoffs
    
    def _find_most_scarce_position(self, df: pd.DataFrame) -> str:
        """Find the position with the most scarcity based on VORP distribution"""
        position_scarcity = {}
        
        for position in ['QB', 'RB', 'WR', 'TE']:
            pos_data = df[df['position'] == position]
            if len(pos_data) == 0:
                continue
                
            # Calculate scarcity as ratio of elite players to total starters needed
            elite_players = len(pos_data[pos_data['vorp_tier'].isin(['Elite VORP', 'High VORP'])])
            starters_needed = self.starting_lineup[position] * self.num_teams
            
            position_scarcity[position] = elite_players / starters_needed if starters_needed > 0 else 0
        
        # Return position with lowest ratio (most scarce)
        return min(position_scarcity, key=position_scarcity.get) if position_scarcity else 'RB'
    
    def calculate_adp_vorp_value(self, df: pd.DataFrame, adp_column: str = 'consensus_adp') -> pd.DataFrame:
        """
        Calculate value based on ADP vs VORP comparison
        
        Args:
            df: DataFrame with VORP scores and ADP data
            adp_column: Name of the ADP column to use
            
        Returns:
            DataFrame with ADP-VORP value metrics added
        """
        result_df = df.copy()
        
        if adp_column not in df.columns:
            self.logger.warning(f"ADP column {adp_column} not found")
            return result_df
        
        # Calculate ADP ranks
        result_df['adp_rank'] = result_df[adp_column].rank(method='min')
        
        # Calculate VORP vs ADP value
        result_df['vorp_adp_value'] = result_df['adp_rank'] - result_df['vorp_overall_rank']
        
        # Classify ADP-VORP value
        def classify_adp_vorp_value(value):
            if value >= 50:
                return "Massive VORP Value"
            elif value >= 25:
                return "Great VORP Value"
            elif value >= 10:
                return "Good VORP Value"
            elif value >= -10:
                return "Fair VORP Value"
            elif value >= -25:
                return "Poor VORP Value"
            else:
                return "Terrible VORP Value"
        
        result_df['vorp_adp_tier'] = result_df['vorp_adp_value'].apply(classify_adp_vorp_value)
        
        return result_df
    
    def get_draft_recommendations(self, df: pd.DataFrame, 
                                 current_roster: List[str] = None,
                                 draft_position: int = 6,
                                 current_round: int = 1) -> Dict[str, List[Dict]]:
        """
        Generate draft recommendations based on VORP analysis
        
        Args:
            df: DataFrame with VORP calculations
            current_roster: List of already drafted players
            draft_position: Current draft position
            current_round: Current round number
            
        Returns:
            Dictionary with VORP-based recommendations
        """
        available_players = df.copy()
        
        # Filter out already drafted players
        if current_roster:
            available_players = available_players[~available_players['player_name'].isin(current_roster)]
        
        recommendations = {
            'vorp_targets': [],
            'positional_values': {},
            'round_strategy': {},
            'sleeper_picks': []
        }
        
        # Top VORP targets
        vorp_targets = available_players.nlargest(15, 'vorp_score')
        recommendations['vorp_targets'] = vorp_targets[[
            'player_name', 'position', 'vorp_score', 'vorp_tier', 'projected_points'
        ]].to_dict('records')
        
        # Positional VORP values
        for position in ['QB', 'RB', 'WR', 'TE']:
            pos_players = available_players[available_players['position'] == position]
            if len(pos_players) > 0:
                top_vorp = pos_players.nlargest(5, 'vorp_score')
                recommendations['positional_values'][position] = top_vorp[[
                    'player_name', 'vorp_score', 'vorp_tier', 'projected_points'
                ]].to_dict('records')
        
        # Round-specific strategy
        if current_round <= 3:
            strategy = "Target elite VORP players - focus on RB/WR with highest VORP scores"
        elif current_round <= 6:
            strategy = "Balance VORP with positional needs - consider QB/TE if elite VORP available"
        elif current_round <= 10:
            strategy = "Target remaining positive VORP players - focus on depth and upside"
        else:
            strategy = "Handcuffs and lottery tickets - minimal VORP but high upside potential"
        
        recommendations['round_strategy'][current_round] = strategy
        
        # Sleeper picks (positive VORP but low ADP)
        if 'vorp_adp_value' in available_players.columns:
            sleepers = available_players[
                (available_players['vorp_score'] > 10) & 
                (available_players['vorp_adp_value'] > 15)
            ].nlargest(10, 'vorp_adp_value')
            
            recommendations['sleeper_picks'] = sleepers[[
                'player_name', 'position', 'vorp_score', 'vorp_adp_value', 'projected_points'
            ]].to_dict('records')
        
        return recommendations 
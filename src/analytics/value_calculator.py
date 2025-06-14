"""
Value Calculator
Implements Value Based Drafting (VBD) and advanced value calculations
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple

class ValueCalculator:
    """Calculates fantasy football draft values using VBD methodology"""
    
    def __init__(self):
        """Initialize ValueCalculator with default settings"""
        # Replacement level settings (players drafted as starters)
        self.replacement_levels = {
            'QB': 12,    # QB12 is replacement level (12 team league)
            'RB': 24,    # RB24 is replacement level (top 2 RBs per team)
            'WR': 36,    # WR36 is replacement level (top 3 WRs per team)
            'TE': 12     # TE12 is replacement level
        }
        
        # Position scarcity multipliers
        self.scarcity_multipliers = {
            'QB': 0.5,   # QBs less scarce (only need 1)
            'RB': 1.4,   # RBs most scarce
            'WR': 1.2,   # WRs moderately scarce
            'TE': 1.1    # TEs slightly scarce
        }
        
    def calculate_vbd_scores(self, projections: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate Value Based Drafting scores for all players
        
        Args:
            projections: DataFrame with player projections
            
        Returns:
            DataFrame with VBD scores added
        """
        df = projections.copy()
        
        # Calculate replacement level values for each position
        replacement_values = self._get_replacement_values(df)
        
        # Calculate VBD for each player
        df['vbd_score'] = df.apply(
            lambda row: self._calculate_player_vbd(row, replacement_values), 
            axis=1
        )
        
        # Calculate position-adjusted value (considering scarcity)
        df['adjusted_value'] = df.apply(
            lambda row: row['vbd_score'] * self.scarcity_multipliers.get(row['position'], 1.0),
            axis=1
        )
        
        # Calculate draft value (combination of projection and VBD)
        df['draft_value'] = self._calculate_draft_value(df)
        
        # Add value tier classification
        df['value_tier'] = self._classify_value_tiers(df['draft_value'])
        
        return df
    
    def _get_replacement_values(self, df: pd.DataFrame) -> Dict[str, float]:
        """Get replacement level fantasy points for each position"""
        replacement_values = {}
        
        for position in ['QB', 'RB', 'WR', 'TE']:
            pos_players = df[df['position'] == position].sort_values(
                'projected_points', ascending=False
            )
            
            replacement_rank = self.replacement_levels[position]
            if len(pos_players) >= replacement_rank:
                replacement_values[position] = pos_players.iloc[replacement_rank - 1]['projected_points']
            else:
                # If not enough players, use last available
                replacement_values[position] = pos_players.iloc[-1]['projected_points']
                
        return replacement_values
    
    def _calculate_player_vbd(self, player: pd.Series, replacement_values: Dict[str, float]) -> float:
        """Calculate VBD score for a single player"""
        position = player['position']
        projected_points = player['projected_points']
        replacement_value = replacement_values.get(position, 0)
        
        return max(0, projected_points - replacement_value)
    
    def _calculate_draft_value(self, df: pd.DataFrame) -> pd.Series:
        """
        Calculate comprehensive draft value score
        
        Combines projected points, VBD score, and position scarcity
        """
        # Normalize components to 0-100 scale
        max_points = df['projected_points'].max()
        max_vbd = df['vbd_score'].max()
        max_adjusted = df['adjusted_value'].max()
        
        normalized_points = (df['projected_points'] / max_points) * 40  # 40% weight
        normalized_vbd = (df['vbd_score'] / max_vbd) * 40 if max_vbd > 0 else 0  # 40% weight
        normalized_adjusted = (df['adjusted_value'] / max_adjusted) * 20 if max_adjusted > 0 else 0  # 20% weight
        
        return normalized_points + normalized_vbd + normalized_adjusted
    
    def _classify_value_tiers(self, draft_values: pd.Series) -> pd.Series:
        """Classify players into value tiers"""
        def get_value_tier(value):
            if value >= 80:
                return "Elite Value"
            elif value >= 60:
                return "Strong Value"
            elif value >= 40:
                return "Fair Value"
            elif value >= 20:
                return "Questionable Value"
            else:
                return "Poor Value"
        
        return draft_values.apply(get_value_tier)
    
    def calculate_opportunity_score(self, player_data: Dict) -> float:
        """
        Calculate opportunity score based on team context and role
        
        Args:
            player_data: Dictionary with player information
            
        Returns:
            Opportunity score (0-100)
        """
        base_score = 50  # Start with neutral score
        
        # Adjust based on starting probability
        starter_prob = player_data.get('starter_probability', 0.5)
        base_score += (starter_prob - 0.5) * 30  # -15 to +15 adjustment
        
        # Adjust based on age (younger players have more opportunity)
        age = player_data.get('age', 28)
        if age < 25:
            base_score += 10
        elif age > 30:
            base_score -= 10
            
        # Adjust based on confidence level
        confidence = player_data.get('confidence', 'Medium')
        if confidence == 'High':
            base_score += 5
        elif confidence == 'Low':
            base_score -= 5
            
        return max(0, min(100, base_score))
    
    def calculate_sleeper_score(self, player_data: Dict, adp_rank: int = None) -> float:
        """
        Calculate comprehensive sleeper score
        
        Args:
            player_data: Dictionary with player information
            adp_rank: Player's ADP rank (if available)
            
        Returns:
            Sleeper score (0-100, higher = better sleeper)
        """
        projection_rank = player_data.get('overall_rank', 999)
        vbd_score = player_data.get('vbd_score', 0)
        opportunity_score = self.calculate_opportunity_score(player_data)
        
        # Base sleeper score from opportunity
        sleeper_score = opportunity_score * 0.4
        
        # Add VBD component (normalized)
        if vbd_score > 0:
            sleeper_score += min(30, vbd_score * 2)  # Cap VBD contribution at 30
        
        # Add ADP vs projection differential
        if adp_rank and projection_rank:
            adp_advantage = max(0, adp_rank - projection_rank)  # Higher ADP = later pick
            sleeper_score += min(30, adp_advantage * 0.5)  # Cap ADP advantage at 30
        
        return max(0, min(100, sleeper_score))
    
    def calculate_positional_scarcity(self, projections: pd.DataFrame) -> Dict[str, float]:
        """
        Calculate position scarcity metrics
        
        Args:
            projections: DataFrame with all player projections
            
        Returns:
            Dictionary with scarcity scores by position
        """
        scarcity_scores = {}
        
        for position in ['QB', 'RB', 'WR', 'TE']:
            pos_players = projections[projections['position'] == position]
            
            if len(pos_players) == 0:
                scarcity_scores[position] = 0
                continue
                
            # Calculate dropoff from top players
            top_player_points = pos_players['projected_points'].max()
            replacement_level = self.replacement_levels[position]
            
            if len(pos_players) >= replacement_level:
                replacement_points = pos_players.iloc[replacement_level - 1]['projected_points']
                dropoff = top_player_points - replacement_points
                
                # Normalize scarcity (higher dropoff = more scarce)
                scarcity_scores[position] = min(100, dropoff / 2)
            else:
                scarcity_scores[position] = 100  # Maximum scarcity if few players
        
        return scarcity_scores
    
    def get_value_recommendations(self, projections: pd.DataFrame, 
                                 current_roster: List[str] = None) -> Dict[str, List[str]]:
        """
        Get value-based draft recommendations
        
        Args:
            projections: DataFrame with projections and VBD scores
            current_roster: List of already drafted player names
            
        Returns:
            Dictionary with recommendations by category
        """
        available_players = projections.copy()
        
        # Remove already drafted players
        if current_roster:
            available_players = available_players[
                ~available_players['player_name'].isin(current_roster)
            ]
        
        recommendations = {
            'best_values': [],
            'sleepers': [],
            'safe_picks': [],
            'high_upside': []
        }
        
        # Best values: High VBD score
        best_values = available_players.nlargest(10, 'vbd_score')
        recommendations['best_values'] = best_values['player_name'].tolist()
        
        # Safe picks: High projected points with high confidence
        safe_picks = available_players[
            (available_players['confidence'] == 'High') & 
            (available_players['projected_points'] > available_players['projected_points'].median())
        ].nlargest(10, 'projected_points')
        recommendations['safe_picks'] = safe_picks['player_name'].tolist()
        
        # High upside: Young players with high opportunity
        young_players = available_players[available_players.get('age', 30) < 26]
        if not young_players.empty:
            high_upside = young_players.nlargest(10, 'projected_points')
            recommendations['high_upside'] = high_upside['player_name'].tolist()
        
        return recommendations 
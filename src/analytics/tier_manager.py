"""
Tier Manager
Handles dynamic tier creation and management based on value gaps
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple

class TierManager:
    """Manages dynamic tier creation and updates based on value differences"""
    
    def __init__(self):
        """Initialize TierManager with default settings"""
        # Tier break thresholds (value gap that creates new tier)
        self.tier_break_thresholds = {
            'QB': 25,    # Points gap to create new QB tier
            'RB': 20,    # Points gap to create new RB tier  
            'WR': 18,    # Points gap to create new WR tier
            'TE': 15     # Points gap to create new TE tier
        }
        
        # Tier labels
        self.tier_labels = {
            1: "Elite",
            2: "Strong", 
            3: "Solid",
            4: "Serviceable",
            5: "Deep",
            6: "Handcuff/Backup"
        }
        
    def assign_dynamic_tiers(self, projections: pd.DataFrame) -> pd.DataFrame:
        """
        Assign dynamic tiers to all players based on value gaps
        
        Args:
            projections: DataFrame with player projections and VBD scores
            
        Returns:
            DataFrame with tier assignments added
        """
        df = projections.copy()
        
        # Assign tiers by position
        for position in ['QB', 'RB', 'WR', 'TE']:
            pos_players = df[df['position'] == position].copy()
            if len(pos_players) == 0:
                continue
                
            # Sort by draft value or VBD score
            value_column = 'draft_value' if 'draft_value' in pos_players.columns else 'vbd_score'
            pos_players = pos_players.sort_values(value_column, ascending=False)
            
            # Create tiers for this position
            tiers = self._create_position_tiers(pos_players, position, value_column)
            
            # Update main dataframe
            for idx, tier in zip(pos_players.index, tiers):
                df.loc[idx, 'tier'] = tier
                df.loc[idx, 'tier_label'] = f"{self.tier_labels.get(tier, 'Deep')} {position}{tier}"
        
        return df
    
    def _create_position_tiers(self, pos_players: pd.DataFrame, position: str, 
                              value_column: str) -> List[int]:
        """
        Create tiers for a specific position based on value gaps
        
        Args:
            pos_players: DataFrame with players from one position (sorted by value)
            position: Position abbreviation (QB, RB, WR, TE)
            value_column: Column name to use for tier calculation
            
        Returns:
            List of tier numbers for each player
        """
        if len(pos_players) == 0:
            return []
            
        values = pos_players[value_column].values
        threshold = self.tier_break_thresholds.get(position, 20)
        
        tiers = [1]  # First player is always tier 1
        current_tier = 1
        
        for i in range(1, len(values)):
            # Calculate gap from previous player
            gap = values[i-1] - values[i]
            
            # If gap is large enough, create new tier
            if gap >= threshold:
                current_tier += 1
                
            tiers.append(min(current_tier, 6))  # Cap at tier 6
            
        return tiers
    
    def update_tiers_post_pick(self, projections: pd.DataFrame, 
                              drafted_players: List[str]) -> pd.DataFrame:
        """
        Recalculate tiers after players have been drafted
        
        Args:
            projections: DataFrame with all projections
            drafted_players: List of player names that have been drafted
            
        Returns:
            DataFrame with updated tiers for remaining players
        """
        # Filter out drafted players
        available_players = projections[~projections['player_name'].isin(drafted_players)].copy()
        
        # Recalculate tiers for remaining players
        updated_projections = self.assign_dynamic_tiers(available_players)
        
        return updated_projections
    
    def get_tier_recommendations(self, projections: pd.DataFrame, 
                                current_roster: List[str],
                                position_needs: Dict[str, int] = None) -> Dict[str, List[str]]:
        """
        Get tier-based draft recommendations
        
        Args:
            projections: DataFrame with projections and tiers
            current_roster: List of already drafted player names
            position_needs: Dictionary of position needs (e.g., {'RB': 2, 'WR': 3})
            
        Returns:
            Dictionary with tier-based recommendations
        """
        available_players = projections[~projections['player_name'].isin(current_roster)].copy()
        
        recommendations = {
            'tier_1_targets': [],
            'tier_2_values': [],
            'position_runs': {},
            'tier_breaks': {}
        }
        
        # Get tier 1 and 2 targets
        tier_1_players = available_players[available_players['tier'] == 1]
        tier_2_players = available_players[available_players['tier'] == 2]
        
        recommendations['tier_1_targets'] = tier_1_players['player_name'].tolist()
        recommendations['tier_2_values'] = tier_2_players['player_name'].tolist()
        
        # Identify position runs (many players in same tier)
        for position in ['QB', 'RB', 'WR', 'TE']:
            pos_players = available_players[available_players['position'] == position]
            tier_counts = pos_players['tier'].value_counts()
            
            # Find tiers with many players (potential runs)
            run_tiers = tier_counts[tier_counts >= 3].index.tolist()
            if run_tiers:
                recommendations['position_runs'][position] = run_tiers
        
        # Identify tier breaks (where value drops significantly)
        for position in ['QB', 'RB', 'WR', 'TE']:
            pos_players = available_players[available_players['position'] == position]
            if len(pos_players) > 1:
                breaks = self._find_tier_breaks(pos_players)
                if breaks:
                    recommendations['tier_breaks'][position] = breaks
        
        return recommendations
    
    def _find_tier_breaks(self, pos_players: pd.DataFrame) -> List[Dict]:
        """
        Find significant tier breaks in position group
        
        Args:
            pos_players: DataFrame with players from one position
            
        Returns:
            List of dictionaries describing tier breaks
        """
        if len(pos_players) < 2:
            return []
            
        pos_players = pos_players.sort_values('draft_value', ascending=False)
        breaks = []
        
        for i in range(len(pos_players) - 1):
            current_player = pos_players.iloc[i]
            next_player = pos_players.iloc[i + 1]
            
            # Check for tier change with significant value gap
            if (current_player['tier'] != next_player['tier'] and 
                current_player['draft_value'] - next_player['draft_value'] > 15):
                
                breaks.append({
                    'after_player': current_player['player_name'],
                    'tier_from': current_player['tier'],
                    'tier_to': next_player['tier'],
                    'value_gap': current_player['draft_value'] - next_player['draft_value']
                })
        
        return breaks
    
    def get_tier_summary(self, projections: pd.DataFrame) -> Dict[str, Dict]:
        """
        Get summary of tier distributions by position
        
        Args:
            projections: DataFrame with projections and tiers
            
        Returns:
            Dictionary with tier summary by position
        """
        summary = {}
        
        for position in ['QB', 'RB', 'WR', 'TE']:
            pos_players = projections[projections['position'] == position]
            
            if len(pos_players) == 0:
                summary[position] = {'total': 0, 'tiers': {}}
                continue
                
            tier_counts = pos_players['tier'].value_counts().sort_index()
            tier_info = {}
            
            for tier, count in tier_counts.items():
                tier_players = pos_players[pos_players['tier'] == tier]
                tier_info[tier] = {
                    'count': count,
                    'label': self.tier_labels.get(tier, 'Deep'),
                    'avg_points': tier_players['projected_points'].mean(),
                    'top_player': tier_players.iloc[0]['player_name'] if len(tier_players) > 0 else None
                }
            
            summary[position] = {
                'total': len(pos_players),
                'tiers': tier_info
            }
        
        return summary
    
    def suggest_tier_targets(self, projections: pd.DataFrame, 
                           current_roster: List[str],
                           draft_position: int,
                           round_number: int) -> List[Dict]:
        """
        Suggest specific tier targets based on draft context
        
        Args:
            projections: DataFrame with projections and tiers
            current_roster: List of already drafted player names
            draft_position: Current draft position
            round_number: Current round number
            
        Returns:
            List of dictionaries with tier-based suggestions
        """
        available_players = projections[~projections['player_name'].isin(current_roster)].copy()
        suggestions = []
        
        # Early rounds: focus on tier 1-2
        if round_number <= 4:
            targets = available_players[available_players['tier'] <= 2]
            suggestion_text = "Target elite/strong tier players"
        
        # Mid rounds: focus on tier 2-3
        elif round_number <= 8:
            targets = available_players[available_players['tier'] <= 3]
            suggestion_text = "Target strong/solid tier players"
        
        # Late rounds: focus on tier 3-4 and upside
        else:
            targets = available_players[available_players['tier'] <= 4]
            suggestion_text = "Target solid players and upside picks"
        
        # Group by position and tier
        for position in ['QB', 'RB', 'WR', 'TE']:
            pos_targets = targets[targets['position'] == position]
            
            if len(pos_targets) > 0:
                best_tier = pos_targets['tier'].min()
                tier_players = pos_targets[pos_targets['tier'] == best_tier]
                
                suggestions.append({
                    'position': position,
                    'tier': best_tier,
                    'tier_label': self.tier_labels.get(best_tier, 'Deep'),
                    'players': tier_players['player_name'].tolist()[:5],  # Top 5 in tier
                    'suggestion': suggestion_text
                })
        
        return suggestions 
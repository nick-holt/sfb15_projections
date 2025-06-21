"""
Dynamic VORP Calculator
Extends the base VORP calculator to handle real-time draft state changes
Calculates dynamic replacement levels that shift as players are drafted
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
import logging
from dataclasses import dataclass

try:
    from .vorp_calculator import VORPCalculator
    from ..draft.draft_state import DraftState, DraftPick, TeamRoster
except ImportError:
    # Fallback for direct script execution
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from analytics.vorp_calculator import VORPCalculator
    from draft.draft_state import DraftState, DraftPick, TeamRoster

@dataclass
class DynamicVORPMetrics:
    """Container for dynamic VORP calculations"""
    # Static VORP (pre-draft baseline)
    static_vorp: float
    static_replacement_level: float
    
    # Dynamic VORP (real-time adjusted)
    dynamic_vorp: float
    dynamic_replacement_level: float
    
    # Market context
    position_scarcity_multiplier: float
    tier_depletion_factor: float
    round_strategy_adjustment: float
    
    # Change indicators
    vorp_change: float  # dynamic - static
    replacement_level_shift: float
    scarcity_increase: float

class DynamicVORPCalculator(VORPCalculator):
    """Calculates dynamic VORP that adjusts in real-time during drafts"""
    
    def __init__(self, num_teams: int = 12):
        """
        Initialize Dynamic VORP Calculator
        
        Args:
            num_teams: Number of teams in the league
        """
        super().__init__(num_teams)
        self.logger = logging.getLogger(__name__)
        
        # Cache for performance
        self._static_replacement_levels = {}
        self._last_draft_state_hash = None
        self._cached_dynamic_metrics = {}
        
    def calculate_dynamic_vorp(self, 
                             projections: pd.DataFrame,
                             draft_state: Optional[DraftState] = None) -> pd.DataFrame:
        """
        Calculate both static and dynamic VORP scores
        
        Args:
            projections: DataFrame with player projections
            draft_state: Current draft state (None for pre-draft static VORP)
            
        Returns:
            DataFrame with both static and dynamic VORP metrics
        """
        try:
            df = projections.copy()
            
            # First calculate static VORP (baseline)
            df = self.calculate_vorp_scores(df)
            
            # Store static values
            df['static_vorp'] = df['vorp_score'].copy()
            df['static_replacement_level'] = df['replacement_points'].copy()
            
            # If no draft state, return static VORP only
            if draft_state is None:
                df['dynamic_vorp'] = df['static_vorp']
                df['dynamic_replacement_level'] = df['static_replacement_level']
                df['vorp_change'] = 0.0
                df['replacement_level_shift'] = 0.0
                df['position_scarcity_multiplier'] = 1.0
                df['tier_depletion_factor'] = 1.0
                df['round_strategy_adjustment'] = 1.0
                return df
            
            # Calculate dynamic replacement levels based on current draft state
            dynamic_replacement_levels = self._calculate_dynamic_replacement_levels(df, draft_state)
            
            # Update dynamic VORP calculations
            df['dynamic_replacement_level'] = df['position'].map(dynamic_replacement_levels)
            df['dynamic_vorp'] = df['projected_points'] - df['dynamic_replacement_level']
            df['dynamic_vorp'] = df['dynamic_vorp'].clip(lower=0)
            
            # Calculate change metrics
            df['vorp_change'] = df['dynamic_vorp'] - df['static_vorp']
            df['replacement_level_shift'] = df['dynamic_replacement_level'] - df['static_replacement_level']
            
            # Apply dynamic adjustments
            df = self._apply_position_scarcity_adjustments(df, draft_state)
            df = self._apply_tier_depletion_adjustments(df, draft_state)
            df = self._apply_round_strategy_adjustments(df, draft_state)
            
            # Feature 3: Apply roster construction adjustments
            df = self._apply_roster_construction_adjustments(df, draft_state)
            
            # Feature 4: Apply market inefficiency adjustments
            df = self._apply_market_inefficiency_adjustments(df, draft_state)
            
            # Recalculate final dynamic VORP with all adjustments
            df['dynamic_vorp_final'] = (df['dynamic_vorp'] * 
                                      df['position_scarcity_multiplier'] * 
                                      df['tier_depletion_factor'] * 
                                      df['round_strategy_adjustment'] *
                                      df['roster_construction_multiplier'] *
                                      df['positional_scarcity_boost'] *
                                      df['market_inefficiency_multiplier'])
            
            # Update rankings
            df['dynamic_vorp_position_rank'] = df.groupby('position')['dynamic_vorp_final'].rank(
                method='min', ascending=False
            )
            df['dynamic_vorp_overall_rank'] = df['dynamic_vorp_final'].rank(method='min', ascending=False)
            
            self.logger.info(f"Calculated dynamic VORP for {len(df)} players with {len(draft_state.picks)} picks made")
            return df
            
        except Exception as e:
            self.logger.error(f"Error calculating dynamic VORP: {str(e)}")
            # Return static VORP on error
            return self.calculate_vorp_scores(projections)
    
    def _calculate_dynamic_replacement_levels(self, 
                                            df: pd.DataFrame, 
                                            draft_state: DraftState) -> Dict[str, float]:
        """
        Calculate replacement levels that shift based on players already drafted
        
        Args:
            df: DataFrame with projections
            draft_state: Current draft state
            
        Returns:
            Dictionary with dynamic replacement levels by position
        """
        replacement_levels = {}
        drafted_players = {pick.player_id for pick in draft_state.picks}
        
        for position in ['QB', 'RB', 'WR', 'TE']:
            # Get available players at this position (not yet drafted)
            pos_players = df[
                (df['position'] == position) & 
                (~df['player_id'].isin(drafted_players))
            ].copy()
            
            if len(pos_players) == 0:
                replacement_levels[position] = 0
                continue
            
            # Sort by projected points
            pos_players = pos_players.sort_values('projected_points', ascending=False)
            
            # Calculate how many players at this position are still needed
            remaining_needs = self._calculate_remaining_positional_needs(position, draft_state)
            
            # Adjust replacement level based on remaining needs vs available players
            if remaining_needs > 0 and len(pos_players) >= remaining_needs:
                # Replacement level is the player at the cutoff for remaining starters
                replacement_points = pos_players.iloc[remaining_needs - 1]['projected_points']
            elif len(pos_players) > 0:
                # Use median of remaining players if needs calculation is unclear
                replacement_points = pos_players['projected_points'].median()
            else:
                replacement_points = 0
            
            # Apply scarcity adjustment - if fewer players available, raise replacement level
            scarcity_factor = self._calculate_position_scarcity_factor(position, draft_state, pos_players)
            replacement_points *= scarcity_factor
            
            replacement_levels[position] = replacement_points
            
            self.logger.debug(f"{position}: {len(pos_players)} available, "
                            f"{remaining_needs} still needed, "
                            f"replacement level: {replacement_points:.1f}")
        
        return replacement_levels
    
    def _calculate_remaining_positional_needs(self, position: str, draft_state: DraftState) -> int:
        """
        Calculate how many more players are needed at a position across all teams
        
        Args:
            position: Position to analyze
            draft_state: Current draft state
            
        Returns:
            Number of players still needed at this position
        """
        # Count players already drafted at this position
        drafted_at_position = sum(1 for pick in draft_state.picks if pick.position == position)
        
        # Calculate total needs for this position
        starters_per_team = self.starting_lineup.get(position, 0)
        total_starters_needed = starters_per_team * draft_state.settings.total_teams
        
        # Add bench depth (assume 1 backup per starting position for skill positions)
        if position in ['RB', 'WR']:
            bench_depth = draft_state.settings.total_teams  # 1 backup per team
        elif position in ['QB', 'TE']:
            bench_depth = draft_state.settings.total_teams // 2  # 0.5 backups per team
        else:
            bench_depth = 0
        
        total_needed = total_starters_needed + bench_depth
        remaining_needs = max(0, total_needed - drafted_at_position)
        
        return remaining_needs
    
    def _calculate_position_scarcity_factor(self, 
                                          position: str, 
                                          draft_state: DraftState,
                                          available_players: pd.DataFrame) -> float:
        """
        Calculate scarcity multiplier based on supply/demand at position
        
        Args:
            position: Position to analyze
            draft_state: Current draft state
            available_players: Available players at this position
            
        Returns:
            Scarcity factor (>1.0 means more scarce, <1.0 means less scarce)
        """
        if len(available_players) == 0:
            return 1.5  # High scarcity if no players available
        
        remaining_needs = self._calculate_remaining_positional_needs(position, draft_state)
        
        if remaining_needs <= 0:
            return 0.8  # Less valuable if no more needed
        
        # Calculate supply/demand ratio
        supply_demand_ratio = len(available_players) / remaining_needs
        
        # Convert to scarcity factor (inverse relationship)
        if supply_demand_ratio >= 2.0:
            return 0.9  # Plenty of supply, lower replacement level
        elif supply_demand_ratio >= 1.5:
            return 1.0  # Balanced
        elif supply_demand_ratio >= 1.0:
            return 1.1  # Getting scarce
        elif supply_demand_ratio >= 0.5:
            return 1.3  # Very scarce
        else:
            return 1.5  # Extremely scarce
    
    def _apply_position_scarcity_adjustments(self, df: pd.DataFrame, draft_state: DraftState) -> pd.DataFrame:
        """
        Apply position scarcity multipliers based on draft state
        
        Args:
            df: DataFrame with VORP calculations
            draft_state: Current draft state
            
        Returns:
            DataFrame with scarcity adjustments applied
        """
        def get_scarcity_multiplier(row):
            position = row['position']
            available_at_pos = df[
                (df['position'] == position) & 
                (~df['player_id'].isin({pick.player_id for pick in draft_state.picks}))
            ]
            return self._calculate_position_scarcity_factor(position, draft_state, available_at_pos)
        
        df['position_scarcity_multiplier'] = df.apply(get_scarcity_multiplier, axis=1)
        return df
    
    def _apply_tier_depletion_adjustments(self, df: pd.DataFrame, draft_state: DraftState) -> pd.DataFrame:
        """
        Apply adjustments based on tier depletion at each position
        
        Args:
            df: DataFrame with VORP calculations
            draft_state: Current draft state
            
        Returns:
            DataFrame with tier depletion adjustments applied
        """
        # For now, implement basic tier depletion
        # TODO: Implement full tier analysis in next feature
        df['tier_depletion_factor'] = 1.0
        
        return df
    
    def _apply_round_strategy_adjustments(self, df: pd.DataFrame, draft_state: DraftState) -> pd.DataFrame:
        """
        Apply round-specific strategy adjustments with enhanced context awareness
        
        Args:
            df: DataFrame with VORP calculations
            draft_state: Current draft state
            
        Returns:
            DataFrame with round strategy adjustments applied
        """
        picks_made = len(draft_state.picks)
        total_picks = draft_state.settings.total_teams * draft_state.settings.roster_positions.get('total', 16)
        current_round = (picks_made // draft_state.settings.total_teams) + 1
        
        # Count drafted players by position
        position_drafted_count = {}
        for pick in draft_state.picks:
            # Find position from df
            player_row = df[df['player_id'] == pick.player_id]
            if not player_row.empty:
                pos = player_row.iloc[0]['position']
                position_drafted_count[pos] = position_drafted_count.get(pos, 0) + 1
        
        # Apply enhanced context-aware adjustments
        def calculate_context_adjustment(row):
            position = row['position']
            projected_points = row['projected_points']
            position_rank = row.get('position_rank', 999)
            
            # Start with base adjustment
            context_adjustment = 1.0
            
            # Round strategy adjustment
            round_adj = self._calculate_round_strategy_adjustment(
                projected_points=projected_points,
                position=position,
                current_round=current_round,
                draft_position=1,  # Simplified - would need actual team context
                total_teams=draft_state.settings.total_teams,
                draft_type='snake'
            )
            context_adjustment *= round_adj
            
            # Draft timing adjustment
            timing_adj = self._calculate_draft_timing_adjustment(
                position=position,
                current_round=current_round,
                picks_made=picks_made,
                total_picks=total_picks,
                position_drafted_count=position_drafted_count
            )
            context_adjustment *= timing_adj
            
            # Positional value curve adjustment
            value_curve_adj = self._calculate_positional_value_curve(
                position=position,
                position_rank=position_rank,
                current_round=current_round
            )
            context_adjustment *= value_curve_adj
            
            return context_adjustment
        
        df['round_strategy_adjustment'] = df.apply(calculate_context_adjustment, axis=1)
        
        # Add context information for insights
        df['current_round'] = current_round
        df['draft_progress'] = picks_made / total_picks if total_picks > 0 else 0
        
        return df
    
    def get_dynamic_vorp_insights(self, df: pd.DataFrame, draft_state: DraftState) -> Dict[str, Any]:
        """
        Generate insights about how VORP has changed during the draft
        
        Args:
            df: DataFrame with dynamic VORP calculations
            draft_state: Current draft state
            
        Returns:
            Dictionary with insights and recommendations
        """
        insights = {
            'draft_progress': {
                'picks_made': len(draft_state.picks),
                'current_round': draft_state.current_round,
                'completion_percentage': (len(draft_state.picks) / 
                                        (draft_state.settings.total_teams * draft_state.settings.total_rounds)) * 100
            },
            'replacement_level_shifts': {},
            'position_scarcity': {},
            'biggest_vorp_changes': [],
            'recommendations': []
        }
        
        # Analyze replacement level shifts
        for position in ['QB', 'RB', 'WR', 'TE']:
            pos_data = df[df['position'] == position]
            if len(pos_data) > 0:
                avg_shift = pos_data['replacement_level_shift'].mean()
                insights['replacement_level_shifts'][position] = {
                    'average_shift': avg_shift,
                    'direction': 'increased' if avg_shift > 0 else 'decreased' if avg_shift < 0 else 'stable'
                }
        
        # Analyze position scarcity
        for position in ['QB', 'RB', 'WR', 'TE']:
            pos_data = df[df['position'] == position]
            if len(pos_data) > 0:
                avg_scarcity = pos_data['position_scarcity_multiplier'].mean()
                insights['position_scarcity'][position] = {
                    'scarcity_multiplier': avg_scarcity,
                    'scarcity_level': 'High' if avg_scarcity > 1.2 else 'Medium' if avg_scarcity > 1.0 else 'Low'
                }
        
        # Find biggest VORP changes
        biggest_changes = df.nlargest(5, 'vorp_change')[['player_name', 'position', 'vorp_change', 'dynamic_vorp_final']]
        insights['biggest_vorp_changes'] = biggest_changes.to_dict('records')
        
        # Feature 3: Roster construction insights
        if 'roster_construction_multiplier' in df.columns:
            current_roster = self._get_current_team_roster(draft_state)
            drafted_by_position = self._get_drafted_by_position(draft_state)
            
            insights['roster_construction'] = {
                'current_roster': current_roster,
                'roster_balance_score': self._calculate_roster_balance_score(current_roster),
                'positional_needs': self._analyze_positional_needs(current_roster),
                'league_drafting_pace': drafted_by_position,
                'roster_recommendations': self._generate_roster_recommendations(current_roster, df)
            }
        
        # Feature 4: Market inefficiency insights
        if 'market_inefficiency_multiplier' in df.columns:
            position_runs = self._detect_position_runs(draft_state)
            contrarian_opportunities = self._identify_contrarian_opportunities(df, draft_state)
            draft_flow = self._calculate_draft_flow_prediction(draft_state)
            
            insights['market_inefficiency'] = {
                'position_runs': position_runs,
                'contrarian_opportunities': contrarian_opportunities[:5],  # Top 5
                'draft_flow_predictions': draft_flow,
                'market_efficiency_score': self._calculate_market_efficiency_score(df)
            }
        
        return insights 

    def _calculate_round_strategy_adjustment(self, 
                                           projected_points: float, 
                                           position: str, 
                                           current_round: int,
                                           draft_position: int,
                                           total_teams: int,
                                           draft_type: str = 'snake') -> float:
        """
        Calculate round-specific strategy adjustments
        
        Args:
            projected_points: Player's projected points
            position: Player position
            current_round: Current draft round
            draft_position: Team's draft position (1-based)
            total_teams: Total number of teams
            draft_type: Type of draft (snake, linear)
            
        Returns:
            Strategy adjustment multiplier
        """
        base_adjustment = 1.0
        
        # Early rounds (1-3): Favor ceiling and proven production
        if current_round <= 3:
            # Favor RB/WR in early rounds due to positional scarcity
            if position in ['RB', 'WR']:
                base_adjustment *= 1.1
            # Slight penalty for QB/TE in very early rounds
            elif position in ['QB', 'TE'] and current_round <= 2:
                base_adjustment *= 0.95
                
        # Middle rounds (4-8): Balanced approach with positional needs
        elif current_round <= 8:
            # Favor TE if elite options available
            if position == 'TE' and projected_points >= 220:
                base_adjustment *= 1.15
            # Favor QB if top tier available
            elif position == 'QB' and projected_points >= 350:
                base_adjustment *= 1.1
                
        # Late rounds (9+): Favor upside and depth
        else:
            # Favor high-upside players in late rounds
            if position in ['RB', 'WR']:
                base_adjustment *= 1.05
            # Penalty for low-upside veterans
            base_adjustment *= 0.98
            
        # Snake draft position adjustments
        if draft_type == 'snake':
            picks_until_next = self._calculate_picks_until_next_turn(
                current_round, draft_position, total_teams
            )
            
            # If long wait until next pick, favor players less likely to be available
            if picks_until_next >= total_teams * 1.5:  # More than 1.5 rounds
                # Boost scarce positions
                if position in ['RB', 'TE']:
                    base_adjustment *= 1.1
                # Boost high-value players
                if projected_points >= 300:
                    base_adjustment *= 1.05
                    
            # If short wait, can afford to wait on certain positions
            elif picks_until_next <= 6:
                # Can wait on QB in most cases
                if position == 'QB' and current_round <= 10:
                    base_adjustment *= 0.95
                    
        return base_adjustment
    
    def _calculate_picks_until_next_turn(self, 
                                       current_round: int, 
                                       draft_position: int, 
                                       total_teams: int) -> int:
        """
        Calculate how many picks until this team picks again in snake draft
        
        Args:
            current_round: Current round
            draft_position: Team's draft position (1-based)
            total_teams: Total number of teams
            
        Returns:
            Number of picks until next turn
        """
        if current_round % 2 == 1:  # Odd round (1, 3, 5...)
            # Normal order: 1, 2, 3, ..., total_teams
            picks_left_this_round = total_teams - draft_position
            picks_next_round = total_teams - draft_position + 1
        else:  # Even round (2, 4, 6...)
            # Reverse order: total_teams, ..., 3, 2, 1
            reverse_position = total_teams - draft_position + 1
            picks_left_this_round = reverse_position - 1
            picks_next_round = draft_position
            
        return picks_left_this_round + picks_next_round
    
    def _calculate_draft_timing_adjustment(self, 
                                         position: str,
                                         current_round: int,
                                         picks_made: int,
                                         total_picks: int,
                                         position_drafted_count: Dict[str, int]) -> float:
        """
        Calculate adjustments based on draft timing and positional runs
        
        Args:
            position: Player position
            current_round: Current round
            picks_made: Total picks made so far
            total_picks: Total picks in draft
            position_drafted_count: Count of players drafted by position
            
        Returns:
            Timing adjustment multiplier
        """
        adjustment = 1.0
        draft_progress = picks_made / total_picks
        
        # Position run detection and response
        recent_picks = 5  # Look at last 5 picks
        if picks_made >= recent_picks:
            # This would need access to recent picks - simplified for now
            # In real implementation, would analyze if position is being overdrafted
            pass
        
        # Positional scarcity timing
        expected_drafted = {
            'QB': int(picks_made * 0.08),  # ~8% of picks should be QB
            'RB': int(picks_made * 0.35),  # ~35% should be RB
            'WR': int(picks_made * 0.35),  # ~35% should be WR
            'TE': int(picks_made * 0.08),  # ~8% should be TE
        }
        
        actual_drafted = position_drafted_count.get(position, 0)
        expected = expected_drafted.get(position, 0)
        
        if actual_drafted < expected and expected > 0:
            # Position being underdrafted - slight boost
            shortage_ratio = (expected - actual_drafted) / expected
            adjustment *= (1.0 + shortage_ratio * 0.1)  # Up to 10% boost
        elif actual_drafted > expected and expected > 0:
            # Position being overdrafted - slight penalty
            excess_ratio = (actual_drafted - expected) / expected
            adjustment *= (1.0 - excess_ratio * 0.05)  # Up to 5% penalty
            
        # Late draft urgency for key positions
        if draft_progress > 0.6:  # After 60% of draft
            if position in ['QB', 'TE'] and position_drafted_count.get(position, 0) == 0:
                # Haven't drafted position yet - urgency boost
                adjustment *= 1.2
                
        return adjustment
    
    def _calculate_positional_value_curve(self, 
                                        position: str,
                                        position_rank: int,
                                        current_round: int) -> float:
        """
        Calculate value adjustments based on positional value curves
        
        Args:
            position: Player position
            position_rank: Rank within position
            current_round: Current draft round
            
        Returns:
            Value curve adjustment multiplier
        """
        adjustment = 1.0
        
        # Position-specific value curves
        if position == 'RB':
            # RB has steep dropoff after elite tier
            if position_rank <= 6:  # Elite RBs
                adjustment *= 1.15
            elif position_rank <= 15:  # Solid RB1s
                adjustment *= 1.05
            elif position_rank <= 24:  # RB2s
                adjustment *= 1.0
            else:  # Handcuffs and lottery tickets
                adjustment *= 0.9
                
        elif position == 'WR':
            # WR has more consistent value throughout
            if position_rank <= 8:  # Elite WRs
                adjustment *= 1.1
            elif position_rank <= 20:  # WR1s
                adjustment *= 1.02
            elif position_rank <= 36:  # WR2s
                adjustment *= 1.0
            else:  # WR3+ and fliers
                adjustment *= 0.95
                
        elif position == 'QB':
            # QB value is more consistent but with clear tiers
            if position_rank <= 3:  # Elite QBs
                adjustment *= 1.1
            elif position_rank <= 8:  # QB1s
                adjustment *= 1.0
            elif position_rank <= 16:  # Streaming options
                adjustment *= 0.9
            else:  # Deep backups
                adjustment *= 0.8
                
        elif position == 'TE':
            # TE has extreme scarcity at top
            if position_rank <= 2:  # Elite TEs
                adjustment *= 1.3
            elif position_rank <= 5:  # Solid TE1s
                adjustment *= 1.1
            elif position_rank <= 12:  # Streaming TEs
                adjustment *= 0.95
            else:  # Deep options
                adjustment *= 0.85
                
        # Round-based adjustments to value curves
        if current_round <= 3:
            # Early rounds - emphasize elite players more
            if position_rank <= 5:
                adjustment *= 1.05
        elif current_round >= 10:
            # Late rounds - flatten value differences
            adjustment = 1.0 + (adjustment - 1.0) * 0.7
            
        return adjustment
    
    def _calculate_roster_construction_adjustment(self, 
                                                projected_points: float, 
                                                position: str, 
                                                current_roster: Dict[str, int],
                                                total_roster_spots: int = 16,
                                                bye_week: int = None) -> float:
        """
        Calculate roster construction adjustments based on team needs
        
        Args:
            projected_points: Player's projected points
            position: Player position
            current_roster: Current roster composition by position
            total_roster_spots: Total roster spots available
            bye_week: Player's bye week
            
        Returns:
            Roster construction multiplier
        """
        # Standard roster construction targets (12-team league)
        roster_targets = {
            'QB': {'min': 1, 'max': 2, 'optimal': 1},
            'RB': {'min': 2, 'max': 6, 'optimal': 4},
            'WR': {'min': 2, 'max': 6, 'optimal': 5},
            'TE': {'min': 1, 'max': 3, 'optimal': 2},
            'K': {'min': 1, 'max': 2, 'optimal': 1},
            'DEF': {'min': 1, 'max': 2, 'optimal': 1}
        }
        
        current_count = current_roster.get(position, 0)
        targets = roster_targets.get(position, {'min': 0, 'max': 3, 'optimal': 2})
        
        # Base multiplier
        multiplier = 1.0
        
        # Positional need adjustment
        if current_count < targets['min']:
            # Critical need - significant boost
            multiplier *= 1.25
        elif current_count < targets['optimal']:
            # Moderate need - small boost
            multiplier *= 1.1
        elif current_count >= targets['max']:
            # Oversupplied - penalty
            multiplier *= 0.8
        elif current_count > targets['optimal']:
            # Slightly oversupplied - small penalty
            multiplier *= 0.95
            
        # High-value player adjustment (overcome positional penalties for elite players)
        if projected_points > self._get_position_elite_threshold(position):
            if current_count > targets['optimal']:
                # Reduce penalty for elite players
                multiplier = min(multiplier * 1.15, 1.0)
        
        # Bye week stacking penalty (if we have multiple players with same bye)
        if bye_week and self._has_bye_week_conflict(current_roster, bye_week, position):
            multiplier *= 0.92
            
        return multiplier
    
    def _get_position_elite_threshold(self, position: str) -> float:
        """Get the elite threshold for a position"""
        thresholds = {
            'QB': 350,  # Elite QB threshold
            'RB': 280,  # Elite RB threshold
            'WR': 270,  # Elite WR threshold
            'TE': 220,  # Elite TE threshold
            'K': 140,   # Elite K threshold
            'DEF': 160  # Elite DEF threshold
        }
        return thresholds.get(position, 250)
    
    def _has_bye_week_conflict(self, current_roster: Dict[str, int], bye_week: int, position: str) -> bool:
        """Check if adding this player creates bye week conflicts"""
        # Simplified check - in real implementation, would check actual roster
        # For now, assume conflict if we already have 3+ players at same position
        return current_roster.get(position, 0) >= 3
    
    def _calculate_positional_scarcity_boost(self, 
                                           position: str, 
                                           projected_points: float,
                                           drafted_by_position: Dict[str, int],
                                           total_teams: int = 12) -> float:
        """
        Calculate boost based on positional scarcity in draft
        
        Args:
            position: Player position
            projected_points: Player's projected points
            drafted_by_position: Number of players drafted by position
            total_teams: Number of teams in league
            
        Returns:
            Scarcity boost multiplier
        """
        # Expected drafting pace by position (players per round)
        expected_pace = {
            'QB': 0.5,   # ~6 QBs per round
            'RB': 3.0,   # ~36 RBs per round  
            'WR': 3.5,   # ~42 WRs per round
            'TE': 0.8,   # ~10 TEs per round
            'K': 0.1,    # ~1 K per round
            'DEF': 0.1   # ~1 DEF per round
        }
        
        drafted_count = drafted_by_position.get(position, 0)
        expected_count = expected_pace.get(position, 1.0) * (drafted_count // total_teams + 1)
        
        # Calculate scarcity ratio
        if expected_count > 0:
            scarcity_ratio = drafted_count / expected_count
        else:
            scarcity_ratio = 1.0
            
        # Apply scarcity boost
        if scarcity_ratio > 1.2:
            # Position being overdrafted - slight penalty
            return 0.95
        elif scarcity_ratio < 0.8:
            # Position being underdrafted - boost
            return 1.08
        else:
            # Normal pace
            return 1.0
    
    def _calculate_roster_balance_score(self, current_roster: Dict[str, int]) -> float:
        """
        Calculate how balanced the current roster is
        
        Args:
            current_roster: Current roster composition
            
        Returns:
            Balance score (0.0 to 1.0, higher is better)
        """
        # Ideal roster distribution (percentages)
        ideal_distribution = {
            'QB': 0.08,   # ~1-2 QBs
            'RB': 0.31,   # ~5 RBs  
            'WR': 0.38,   # ~6 WRs
            'TE': 0.15,   # ~2-3 TEs
            'K': 0.04,    # ~1 K
            'DEF': 0.04   # ~1 DEF
        }
        
        total_players = sum(current_roster.values())
        if total_players == 0:
            return 1.0
            
        # Calculate actual distribution
        actual_distribution = {
            pos: count / total_players 
            for pos, count in current_roster.items()
        }
        
        # Calculate balance score (inverse of deviation from ideal)
        total_deviation = 0
        for pos, ideal_pct in ideal_distribution.items():
            actual_pct = actual_distribution.get(pos, 0)
            total_deviation += abs(ideal_pct - actual_pct)
            
        # Convert to score (0-1, higher is better)
        balance_score = max(0, 1 - (total_deviation / 2))
        return balance_score
    
    def _get_current_team_roster(self, draft_state: DraftState) -> Dict[str, int]:
        """
        Get current roster composition for the team that's drafting
        
        Args:
            draft_state: Current draft state
            
        Returns:
            Dictionary with position counts for current team
        """
        if not draft_state.picks:
            return {}
            
        # Find current drafting team
        current_team_index = (draft_state.current_pick - 1) % draft_state.settings.num_teams
        
        # Count positions for this team
        roster = {}
        for i, pick in enumerate(draft_state.picks):
            team_index = i % draft_state.settings.num_teams
            if team_index == current_team_index:
                position = pick.position
                roster[position] = roster.get(position, 0) + 1
                
        return roster
    
    def _get_drafted_by_position(self, draft_state: DraftState) -> Dict[str, int]:
        """
        Get count of players drafted by position across all teams
        
        Args:
            draft_state: Current draft state
            
        Returns:
            Dictionary with total draft counts by position
        """
        drafted_counts = {}
        for pick in draft_state.picks:
            position = pick.position
            drafted_counts[position] = drafted_counts.get(position, 0) + 1
            
        return drafted_counts
    
    def _apply_roster_construction_adjustments(self, df: pd.DataFrame, draft_state: DraftState) -> pd.DataFrame:
        """
        Apply Feature 3: Team Roster Construction adjustments
        
        Args:
            df: DataFrame with VORP calculations
            draft_state: Current draft state
            
        Returns:
            DataFrame with roster construction adjustments applied
        """
        # Get current team roster and league-wide position counts
        current_roster = self._get_current_team_roster(draft_state)
        drafted_by_position = self._get_drafted_by_position(draft_state)
        
        # Apply roster construction adjustment for current team needs
        df['roster_construction_multiplier'] = df.apply(
            lambda row: self._calculate_roster_construction_adjustment(
                row['projected_points'],
                row['position'],
                current_roster
            ), axis=1
        )
        
        # Apply positional scarcity boost based on league-wide drafting patterns
        df['positional_scarcity_boost'] = df.apply(
            lambda row: self._calculate_positional_scarcity_boost(
                row['position'],
                row['projected_points'],
                drafted_by_position,
                draft_state.settings.num_teams
            ), axis=1
        )
        
        # Calculate roster balance score for insights
        balance_score = self._calculate_roster_balance_score(current_roster)
        df['roster_balance_context'] = balance_score
        
        return df
    
    def _analyze_positional_needs(self, current_roster: Dict[str, int]) -> Dict[str, str]:
        """
        Analyze current positional needs for the team
        
        Args:
            current_roster: Current roster composition
            
        Returns:
            Dictionary with need level by position
        """
        roster_targets = {
            'QB': {'min': 1, 'optimal': 1},
            'RB': {'min': 2, 'optimal': 4},
            'WR': {'min': 2, 'optimal': 5},
            'TE': {'min': 1, 'optimal': 2},
            'K': {'min': 1, 'optimal': 1},
            'DEF': {'min': 1, 'optimal': 1}
        }
        
        needs = {}
        for position, targets in roster_targets.items():
            current_count = current_roster.get(position, 0)
            
            if current_count < targets['min']:
                needs[position] = 'Critical'
            elif current_count < targets['optimal']:
                needs[position] = 'Moderate'
            elif current_count == targets['optimal']:
                needs[position] = 'Satisfied'
            else:
                needs[position] = 'Oversupplied'
                
        return needs
    
    def _generate_roster_recommendations(self, current_roster: Dict[str, int], df: pd.DataFrame) -> List[str]:
        """
        Generate roster construction recommendations
        
        Args:
            current_roster: Current roster composition
            df: DataFrame with player data
            
        Returns:
            List of recommendation strings
        """
        recommendations = []
        needs = self._analyze_positional_needs(current_roster)
        
        # Critical needs
        critical_needs = [pos for pos, need in needs.items() if need == 'Critical']
        if critical_needs:
            recommendations.append(f"🚨 Critical needs: {', '.join(critical_needs)} - prioritize these positions")
        
        # Moderate needs
        moderate_needs = [pos for pos, need in needs.items() if need == 'Moderate']
        if moderate_needs:
            recommendations.append(f"⚠️ Moderate needs: {', '.join(moderate_needs)} - consider filling soon")
        
        # Oversupplied positions
        oversupplied = [pos for pos, need in needs.items() if need == 'Oversupplied']
        if oversupplied:
            recommendations.append(f"📈 Oversupplied: {', '.join(oversupplied)} - avoid unless exceptional value")
        
        # Balance recommendations
        balance_score = self._calculate_roster_balance_score(current_roster)
        if balance_score < 0.7:
            recommendations.append("⚖️ Roster balance needs improvement - diversify positions")
        elif balance_score > 0.9:
            recommendations.append("✅ Well-balanced roster - focus on best available talent")
        
        return recommendations
    
    def _calculate_market_inefficiency_adjustment(self, 
                                                projected_points: float, 
                                                position: str, 
                                                adp_rank: float = None,
                                                vorp_rank: float = None,
                                                draft_state: DraftState = None) -> float:
        """
        Calculate market inefficiency adjustments based on ADP vs VORP gaps
        
        Args:
            projected_points: Player's projected points
            position: Player position
            adp_rank: Player's ADP ranking
            vorp_rank: Player's VORP ranking
            draft_state: Current draft state
            
        Returns:
            Market inefficiency multiplier
        """
        if not adp_rank or not vorp_rank:
            return 1.0
            
        # Calculate rank differential (positive = undervalued by market)
        rank_diff = adp_rank - vorp_rank
        
        # Base inefficiency multiplier
        if rank_diff > 50:  # Severely undervalued
            multiplier = 1.3
        elif rank_diff > 25:  # Moderately undervalued
            multiplier = 1.15
        elif rank_diff > 10:  # Slightly undervalued
            multiplier = 1.05
        elif rank_diff < -50:  # Severely overvalued
            multiplier = 0.7
        elif rank_diff < -25:  # Moderately overvalued
            multiplier = 0.85
        elif rank_diff < -10:  # Slightly overvalued
            multiplier = 0.95
        else:  # Fair value
            multiplier = 1.0
            
        # Position-specific adjustments
        if position in ['RB', 'WR'] and rank_diff > 20:
            multiplier *= 1.1  # Skill position value
        elif position == 'TE' and rank_diff > 15:
            multiplier *= 1.15  # TE scarcity premium
        elif position == 'QB' and rank_diff < -20:
            multiplier *= 0.9  # QB overvaluation penalty
            
        return multiplier
    
    def _detect_position_runs(self, draft_state: DraftState) -> Dict[str, Dict]:
        """
        Detect position runs in recent picks
        
        Args:
            draft_state: Current draft state
            
        Returns:
            Dictionary with position run information
        """
        if not draft_state.picks or len(draft_state.picks) < 3:
            return {}
            
        # Look at last 5 picks
        recent_picks = draft_state.picks[-5:]
        position_counts = {}
        
        for pick in recent_picks:
            pos = pick.position
            position_counts[pos] = position_counts.get(pos, 0) + 1
            
        # Detect runs (3+ of same position in recent picks)
        runs = {}
        for position, count in position_counts.items():
            if count >= 3:
                runs[position] = {
                    'count': count,
                    'severity': 'High' if count >= 4 else 'Medium',
                    'impact': 'Scarcity premium activated' if count >= 3 else 'Monitor closely'
                }
                
        return runs
    
    def _identify_contrarian_opportunities(self, 
                                        df: pd.DataFrame, 
                                        draft_state: DraftState) -> List[Dict]:
        """
        Identify contrarian draft opportunities
        
        Args:
            df: DataFrame with VORP calculations
            draft_state: Current draft state
            
        Returns:
            List of contrarian opportunity dictionaries
        """
        opportunities = []
        
        if 'adp_rank' not in df.columns or 'dynamic_vorp_final' not in df.columns:
            return opportunities
            
        # Find players with large ADP vs VORP gaps
        df_available = df[~df['player_name'].isin([p.player_name for p in draft_state.picks])].copy()
        
        if df_available.empty:
            return opportunities
            
        # Calculate VORP rank
        df_available = df_available.sort_values('dynamic_vorp_final', ascending=False).reset_index(drop=True)
        df_available['vorp_rank'] = df_available.index + 1
        
        # Find undervalued players (ADP rank > VORP rank by significant margin)
        df_available['rank_diff'] = df_available['adp_rank'] - df_available['vorp_rank']
        
        # Contrarian opportunities
        contrarian_candidates = df_available[
            (df_available['rank_diff'] > 25) &  # Significantly undervalued
            (df_available['vorp_rank'] <= 100)  # Still valuable
        ].nlargest(10, 'rank_diff')
        
        for _, player in contrarian_candidates.iterrows():
            opportunities.append({
                'player_name': player['player_name'],
                'position': player['position'],
                'adp_rank': player['adp_rank'],
                'vorp_rank': player['vorp_rank'],
                'rank_diff': player['rank_diff'],
                'dynamic_vorp': player['dynamic_vorp_final'],
                'opportunity_type': 'Undervalued by Market',
                'confidence': 'High' if player['rank_diff'] > 50 else 'Medium'
            })
            
        return opportunities
    
    def _calculate_draft_flow_prediction(self, draft_state: DraftState) -> Dict[str, any]:
        """
        Predict draft flow and position availability
        
        Args:
            draft_state: Current draft state
            
        Returns:
            Dictionary with draft flow predictions
        """
        predictions = {
            'next_round_positions': {},
            'scarcity_alerts': [],
            'value_windows': {}
        }
        
        if not draft_state.picks:
            return predictions
            
        # Analyze recent drafting patterns
        recent_picks = draft_state.picks[-12:] if len(draft_state.picks) >= 12 else draft_state.picks
        position_frequency = {}
        
        for pick in recent_picks:
            pos = pick.position
            position_frequency[pos] = position_frequency.get(pos, 0) + 1
            
        total_recent = len(recent_picks)
        
        # Predict next round position likelihood
        for position in ['QB', 'RB', 'WR', 'TE', 'K', 'DEF']:
            recent_rate = position_frequency.get(position, 0) / total_recent if total_recent > 0 else 0
            
            # Adjust based on typical draft patterns
            typical_rates = {'QB': 0.08, 'RB': 0.30, 'WR': 0.35, 'TE': 0.12, 'K': 0.05, 'DEF': 0.10}
            expected_rate = typical_rates.get(position, 0.10)
            
            # Predict likelihood
            if recent_rate > expected_rate * 1.5:
                likelihood = 'High - Position Run Active'
            elif recent_rate > expected_rate:
                likelihood = 'Above Average'
            elif recent_rate < expected_rate * 0.5:
                likelihood = 'Below Average - Value Window'
            else:
                likelihood = 'Average'
                
            predictions['next_round_positions'][position] = {
                'likelihood': likelihood,
                'recent_rate': f"{recent_rate:.1%}",
                'expected_rate': f"{expected_rate:.1%}"
            }
            
        return predictions
    
    def _apply_market_inefficiency_adjustments(self, df: pd.DataFrame, draft_state: DraftState) -> pd.DataFrame:
        """
        Apply Feature 4: Market Inefficiency Detection adjustments
        
        Args:
            df: DataFrame with VORP calculations
            draft_state: Current draft state
            
        Returns:
            DataFrame with market inefficiency adjustments applied
        """
        # Check if we have ADP data available
        has_adp = 'adp_rank' in df.columns
        
        if has_adp:
            # Calculate VORP rank for comparison
            df_sorted = df.sort_values('dynamic_vorp', ascending=False).reset_index(drop=True)
            df_sorted['vorp_rank'] = df_sorted.index + 1
            
            # Merge back to original dataframe
            df = df.merge(df_sorted[['player_id', 'vorp_rank']], on='player_id', how='left')
            
            # Apply market inefficiency adjustment
            df['market_inefficiency_multiplier'] = df.apply(
                lambda row: self._calculate_market_inefficiency_adjustment(
                    row['projected_points'],
                    row['position'],
                    row.get('adp_rank'),
                    row.get('vorp_rank'),
                    draft_state
                ), axis=1
            )
        else:
            # No ADP data available, use neutral multiplier
            df['market_inefficiency_multiplier'] = 1.0
            
        return df
    
    def _calculate_market_efficiency_score(self, df: pd.DataFrame) -> Dict[str, any]:
        """
        Calculate overall market efficiency score based on ADP vs VORP alignment
        
        Args:
            df: DataFrame with VORP and ADP data
            
        Returns:
            Dictionary with market efficiency metrics
        """
        if 'adp_rank' not in df.columns or 'vorp_rank' not in df.columns:
            return {
                'score': 'N/A',
                'description': 'ADP data not available',
                'correlation': None
            }
        
        # Filter to players with both ADP and VORP rankings
        df_ranked = df.dropna(subset=['adp_rank', 'vorp_rank']).copy()
        
        if len(df_ranked) < 20:  # Need sufficient data
            return {
                'score': 'Insufficient Data',
                'description': 'Not enough players with both ADP and VORP rankings',
                'correlation': None
            }
        
        # Calculate correlation between ADP rank and VORP rank
        # (Note: both are ranks, so perfect correlation would be 1.0)
        correlation = df_ranked['adp_rank'].corr(df_ranked['vorp_rank'])
        
        # Calculate efficiency score (0-100%)
        if correlation >= 0.8:
            score = 90 + (correlation - 0.8) * 50  # 90-100%
            description = "Highly Efficient Market"
        elif correlation >= 0.6:
            score = 70 + (correlation - 0.6) * 100  # 70-90%
            description = "Moderately Efficient Market"
        elif correlation >= 0.4:
            score = 50 + (correlation - 0.4) * 100  # 50-70%
            description = "Somewhat Inefficient Market"
        elif correlation >= 0.2:
            score = 30 + (correlation - 0.2) * 100  # 30-50%
            description = "Inefficient Market"
        else:
            score = max(0, correlation * 150)  # 0-30%
            description = "Highly Inefficient Market"
        
        # Count significant mispricings
        df_ranked['rank_diff'] = abs(df_ranked['adp_rank'] - df_ranked['vorp_rank'])
        significant_mispricings = len(df_ranked[df_ranked['rank_diff'] > 25])
        
        return {
            'score': f"{score:.1f}%",
            'description': description,
            'correlation': f"{correlation:.3f}",
            'significant_mispricings': significant_mispricings,
            'total_players_analyzed': len(df_ranked)
        } 
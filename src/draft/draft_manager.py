"""
Draft Manager

This module coordinates live draft tracking by combining Sleeper API data
with our internal draft state management and player projections.
"""

import logging
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
import threading
import time

from .draft_state import DraftState, DraftSettings, DraftPick, TeamRoster
from .sleeper_client import SleeperClient, SleeperDraftMonitor, SleeperPlayerCache, SleeperAPIError
from ..utils.name_normalizer import name_normalizer
try:
    from ..analytics.dynamic_vorp_calculator import DynamicVORPCalculator
except ImportError:
    from analytics.dynamic_vorp_calculator import DynamicVORPCalculator

logger = logging.getLogger(__name__)

class DraftManager:
    """Main class for managing live draft tracking"""
    
    def __init__(self, 
                 draft_id: str,
                 sleeper_client: Optional[SleeperClient] = None,
                 projections_data: Optional[Dict[str, Any]] = None):
        """
        Initialize draft manager
        
        Args:
            draft_id: Sleeper draft_id to track
            sleeper_client: Optional SleeperClient instance
            projections_data: Optional projections data for VORP calculations
        """
        self.draft_id = draft_id
        self.client = sleeper_client or SleeperClient()
        self.monitor = SleeperDraftMonitor(draft_id, self.client)
        self.player_cache = SleeperPlayerCache(self.client)
        self.projections_data = projections_data or {}
        
        # Draft state
        self.draft_state: Optional[DraftState] = None
        self.is_monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None
        
        # Dynamic VORP calculator
        self.dynamic_vorp_calc: Optional[DynamicVORPCalculator] = None
        
        # Callbacks for real-time updates
        self._pick_callbacks: List[Callable[[DraftPick], None]] = []
        self._state_callbacks: List[Callable[[DraftState], None]] = []
        
        # UI callback for Streamlit auto-refresh
        self._ui_refresh_callback: Optional[Callable[[], None]] = None
        
        # Player name mapping for projections integration
        self._player_name_map: Dict[str, str] = {}  # sleeper_name -> projection_name
        
    def initialize_draft(self) -> DraftState:
        """
        Initialize draft state from Sleeper API
        
        Returns:
            Initialized DraftState object
            
        Raises:
            SleeperAPIError: If unable to fetch draft data
        """
        try:
            # Get draft information
            draft_info = self.monitor.get_draft_info()
            league_id = draft_info.get('league_id')
            
            # Try to get league information (may fail for mock drafts)
            league_info = {}
            league_users = []
            league_rosters = []
            
            if league_id:
                try:
                    league_info = self.client.get_league(league_id)
                    league_users = self.client.get_league_users(league_id)
                    league_rosters = self.client.get_league_rosters(league_id)
                    logger.info(f"Successfully loaded league data for draft {self.draft_id}")
                except Exception as e:
                    logger.warning(f"Could not load league data for draft {self.draft_id}: {e}")
                    logger.info("Proceeding with draft-only data (likely a mock draft)")
            else:
                logger.info(f"No league_id found for draft {self.draft_id} (likely a mock draft)")
            
            # Create draft settings with fallback values for mock drafts
            draft_settings = draft_info.get('settings', {})
            settings = DraftSettings(
                league_id=league_id or 'mock_draft',
                draft_id=self.draft_id,
                league_name=league_info.get('name') or draft_info.get('metadata', {}).get('name', 'Mock Draft'),
                total_teams=draft_settings.get('teams', 12),
                total_rounds=draft_settings.get('rounds', 15),
                pick_timer=draft_settings.get('pick_timer', 120),
                draft_type=draft_info.get('type', 'snake'),
                scoring_type=league_info.get('scoring_settings', {}).get('rec', 0) and 'ppr' or 'standard',
                roster_positions=league_info.get('roster_positions', [
                    'QB', 'RB', 'RB', 'WR', 'WR', 'TE', 'FLEX', 'K', 'DEF', 'BN', 'BN', 'BN', 'BN', 'BN', 'BN'
                ]),  # Default roster for mock drafts
                draft_order=draft_info.get('draft_order', {}),
                slot_to_roster=draft_info.get('slot_to_roster_id', {})
            )
            
            # Convert string keys to integers for slot_to_roster
            if settings.slot_to_roster:
                settings.slot_to_roster = {
                    int(k): int(v) for k, v in settings.slot_to_roster.items()
                }
            
            # Create draft state
            self.draft_state = DraftState(
                settings=settings,
                status=draft_info.get('status', 'unknown')
            )
            
            # Populate team rosters with owner information (if available)
            if league_users and league_rosters:
                user_map = {user['user_id']: user for user in league_users}
                for roster in league_rosters:
                    roster_id = roster['roster_id']
                    owner_id = roster.get('owner_id', '')
                    owner_info = user_map.get(owner_id, {})
                    
                    if roster_id in self.draft_state.rosters:
                        team_roster = self.draft_state.rosters[roster_id]
                        team_roster.owner_id = owner_id
                        team_roster.owner_name = owner_info.get('display_name', owner_info.get('username', 'Unknown'))
                        team_roster.team_name = owner_info.get('metadata', {}).get('team_name')
            else:
                # For mock drafts, create generic team names
                for roster_id in self.draft_state.rosters:
                    team_roster = self.draft_state.rosters[roster_id]
                    team_roster.owner_name = f"Team {roster_id}"
                    team_roster.team_name = f"Team {roster_id}"
            
            # Load existing picks
            existing_picks = self.monitor.get_all_picks()
            self._process_picks(existing_picks)
            
            # Initialize player name mapping for projections
            self._build_player_name_map()
            
            # Initialize dynamic VORP calculator if we have projections
            if self.projections_data:
                num_teams = self.draft_state.settings.total_teams
                self.dynamic_vorp_calc = DynamicVORPCalculator(num_teams=num_teams)
            
            draft_type = "league draft" if league_id and league_info else "mock draft"
            logger.info(f"Initialized {draft_type} {self.draft_id} with {len(existing_picks)} existing picks")
            return self.draft_state
            
        except Exception as e:
            logger.error(f"Failed to initialize draft {self.draft_id}: {e}")
            raise SleeperAPIError(f"Could not initialize draft: {e}")
    
    def start_monitoring(self, poll_interval: int = 10):
        """
        Start monitoring the draft for live updates
        
        Args:
            poll_interval: Seconds between API polls
        """
        if self.is_monitoring:
            logger.warning("Draft monitoring already active")
            return
        
        if self.draft_state is None:
            raise ValueError("Draft must be initialized before monitoring")
        
        self.is_monitoring = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(poll_interval,),
            daemon=True
        )
        self.monitor_thread.start()
        logger.info(f"Started monitoring draft {self.draft_id}")
    
    def stop_monitoring(self):
        """Stop monitoring the draft"""
        self.is_monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info(f"Stopped monitoring draft {self.draft_id}")
    
    def _monitor_loop(self, poll_interval: int):
        """Main monitoring loop (runs in separate thread)"""
        while self.is_monitoring:
            try:
                # Check for new picks
                new_picks = self.monitor.get_new_picks()
                if new_picks:
                    self._process_picks(new_picks)
                    
                    # Trigger callbacks
                    for callback in self._state_callbacks:
                        try:
                            callback(self.draft_state)
                        except Exception as e:
                            logger.error(f"Error in state callback: {e}")
                    
                    # CRITICAL FIX: Trigger UI refresh when picks detected
                    if self._ui_refresh_callback:
                        try:
                            logger.info(f"Triggering UI refresh for {len(new_picks)} new picks")
                            self._ui_refresh_callback()
                        except Exception as e:
                            logger.error(f"Error in UI refresh callback: {e}")
                
                # Check if draft is complete
                if self.draft_state.is_draft_complete():
                    logger.info(f"Draft {self.draft_id} is complete")
                    self.is_monitoring = False
                    break
                
                time.sleep(poll_interval)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(poll_interval)
    
    def _process_picks(self, picks_data: List[Dict[str, Any]]):
        """Process new picks from Sleeper API"""
        for pick_data in picks_data:
            # Get player information
            player_id = pick_data.get('player_id', '')
            sleeper_player = self.player_cache.get_player(player_id)
            
            if sleeper_player:
                player_name = f"{sleeper_player.get('first_name', '')} {sleeper_player.get('last_name', '')}".strip()
                position = sleeper_player.get('position', 'UNK')
                team = sleeper_player.get('team', 'UNK')
            else:
                # Fallback to metadata if player not found in cache
                metadata = pick_data.get('metadata', {})
                player_name = f"{metadata.get('first_name', '')} {metadata.get('last_name', '')}".strip()
                position = metadata.get('position', 'UNK')
                team = metadata.get('team', 'UNK')
            
            # Create draft pick
            draft_pick = DraftPick(
                pick_number=pick_data.get('pick_no', 0),
                round=pick_data.get('round', 1),
                draft_slot=pick_data.get('draft_slot', 1),
                player_id=player_id,
                player_name=player_name,
                position=position,
                team=team,
                roster_id=pick_data.get('roster_id', 0),
                picked_by=pick_data.get('picked_by', ''),
                timestamp=datetime.now(),
                metadata=pick_data.get('metadata', {})
            )
            
            # Add to draft state
            self.draft_state.add_pick(draft_pick)
            
            # Trigger pick callbacks
            for callback in self._pick_callbacks:
                try:
                    callback(draft_pick)
                except Exception as e:
                    logger.error(f"Error in pick callback: {e}")
    
    def _build_player_name_map(self):
        """Build mapping between Sleeper player names and projection names"""
        if not self.projections_data:
            return
        
        players = self.player_cache.get_players()
        projection_names = set()
        
        # Get all projection player names
        if 'player_name' in self.projections_data:
            if hasattr(self.projections_data['player_name'], 'tolist'):
                projection_names = set(self.projections_data['player_name'].tolist())
            else:
                projection_names = set(self.projections_data['player_name'])
        
        # Create mapping
        for player_id, player_data in players.items():
            sleeper_name = f"{player_data.get('first_name', '')} {player_data.get('last_name', '')}".strip()
            normalized_sleeper = name_normalizer.normalize_name(sleeper_name)
            
            # Find best match in projections
            best_match = None
            for proj_name in projection_names:
                normalized_proj = name_normalizer.normalize_name(proj_name)
                if normalized_sleeper == normalized_proj:
                    best_match = proj_name
                    break
            
            if best_match:
                self._player_name_map[sleeper_name] = best_match
    
    def get_player_projection(self, sleeper_player_name: str) -> Optional[Dict[str, Any]]:
        """
        Get projection data for a Sleeper player
        
        Args:
            sleeper_player_name: Player name from Sleeper
            
        Returns:
            Projection data dictionary or None
        """
        if not self.projections_data:
            return None
        
        # Try direct mapping first
        projection_name = self._player_name_map.get(sleeper_player_name)
        if not projection_name:
            # Try normalized name matching
            normalized_sleeper = name_normalizer.normalize_name(sleeper_player_name)
            for proj_name in self.projections_data.get('player_name', []):
                if name_normalizer.normalize_name(proj_name) == normalized_sleeper:
                    projection_name = proj_name
                    break
        
        if projection_name and hasattr(self.projections_data, 'query'):
            # Pandas DataFrame
            matches = self.projections_data.query(f"player_name == '{projection_name}'")
            if not matches.empty:
                return matches.iloc[0].to_dict()
        elif projection_name:
            # Dictionary format
            for i, name in enumerate(self.projections_data.get('player_name', [])):
                if name == projection_name:
                    return {key: values[i] for key, values in self.projections_data.items()}
        
        return None
    
    def add_pick_callback(self, callback: Callable[[DraftPick], None]):
        """Add callback for new picks"""
        self._pick_callbacks.append(callback)
    
    def add_state_callback(self, callback: Callable[[DraftState], None]):
        """Add callback for draft state changes"""
        self._state_callbacks.append(callback)
    
    def set_ui_refresh_callback(self, callback: Callable[[], None]):
        """
        Set UI refresh callback for Streamlit integration
        
        Args:
            callback: Function to call when UI refresh is needed (e.g., st.experimental_rerun)
        """
        self._ui_refresh_callback = callback
        logger.info("UI refresh callback registered")
    
    def trigger_ui_refresh(self):
        """Manually trigger UI refresh if callback is set"""
        if self._ui_refresh_callback:
            try:
                logger.info("Manually triggering UI refresh")
                self._ui_refresh_callback()
            except Exception as e:
                logger.error(f"Error in manual UI refresh: {e}")
        else:
            logger.warning("No UI refresh callback set")
    
    def get_draft_board(self) -> List[List[Optional[DraftPick]]]:
        """
        Get draft board as 2D array [round][team]
        
        Returns:
            2D list representing the draft board
        """
        if not self.draft_state:
            return []
        
        settings = self.draft_state.settings
        board = []
        
        for round_num in range(1, settings.total_rounds + 1):
            round_picks = [None] * settings.total_teams
            
            for pick in self.draft_state.picks:
                if pick.round == round_num:
                    # Convert draft slot to 0-based index
                    slot_index = pick.draft_slot - 1
                    if 0 <= slot_index < settings.total_teams:
                        round_picks[slot_index] = pick
            
            board.append(round_picks)
        
        return board
    
    def get_team_needs_analysis(self, roster_id: int) -> Dict[str, Any]:
        """
        Get detailed needs analysis for a specific team
        
        Args:
            roster_id: Team roster ID
            
        Returns:
            Dictionary with team needs analysis
        """
        if not self.draft_state or roster_id not in self.draft_state.rosters:
            return {}
        
        roster = self.draft_state.rosters[roster_id]
        picks = self.draft_state.get_picks_by_team(roster_id)
        
        return {
            'roster_id': roster_id,
            'owner_name': roster.owner_name,
            'team_name': roster.team_name,
            'total_picks': len(picks),
            'positional_counts': {
                'QB': len(roster.qb),
                'RB': len(roster.rb),
                'WR': len(roster.wr),
                'TE': len(roster.te),
                'K': len(roster.k),
                'DEF': len(roster.def_),
                'BENCH': len(roster.bench)
            },
            'positional_needs': {
                'QB': roster.needs_qb,
                'RB': roster.needs_rb,
                'WR': roster.needs_wr,
                'TE': roster.needs_te,
                'K': roster.needs_k,
                'DEF': roster.needs_def,
                'FLEX': roster.needs_flex,
                'BENCH': roster.needs_bench
            },
            'recent_picks': [
                {
                    'player_name': pick.player_name,
                    'position': pick.position,
                    'round': pick.round,
                    'pick_no': pick.pick_number
                }
                for pick in picks[-3:]  # Last 3 picks
            ]
        }
    
    def export_draft_summary(self) -> Dict[str, Any]:
        """Export complete draft summary"""
        if not self.draft_state:
            return {}
        
        return {
            'draft_info': {
                'draft_id': self.draft_id,
                'league_name': self.draft_state.settings.league_name,
                'status': self.draft_state.status,
                'current_pick': self.draft_state.current_pick,
                'current_round': self.draft_state.current_round,
                'total_picks': len(self.draft_state.picks),
                'is_complete': self.draft_state.is_draft_complete()
            },
            'teams': [
                self.get_team_needs_analysis(roster_id)
                for roster_id in self.draft_state.rosters.keys()
            ],
            'recent_picks': [
                {
                    'pick_no': pick.pick_number,
                    'round': pick.round,
                    'player_name': pick.player_name,
                    'position': pick.position,
                    'team': pick.team,
                    'drafted_by': getattr(self.draft_state.rosters.get(pick.roster_id), 'owner_name', 'Unknown') or 'Unknown'
                }
                for pick in self.draft_state.picks[-10:]  # Last 10 picks
            ]
        }
    
    def get_dynamic_vorp_recommendations(self, 
                                       projections_df,
                                       top_n: int = 20) -> Dict[str, Any]:
        """
        Get dynamic VORP-based recommendations for the current draft state
        
        Args:
            projections_df: DataFrame with player projections
            top_n: Number of top recommendations to return
            
        Returns:
            Dictionary with dynamic VORP recommendations and insights
        """
        if not self.dynamic_vorp_calc or not self.draft_state:
            # Fallback to static VORP if dynamic not available
            from ..analytics.vorp_calculator import VORPCalculator
            static_calc = VORPCalculator(num_teams=12)
            df_with_vorp = static_calc.calculate_vorp_scores(projections_df.copy())
            
            return {
                'recommendations': df_with_vorp.nlargest(top_n, 'vorp_score')[
                    ['player_name', 'position', 'team', 'projected_points', 'vorp_score']
                ].to_dict('records'),
                'is_dynamic': False,
                'message': 'Static VORP recommendations (no draft state available)'
            }
        
        try:
            # Calculate dynamic VORP with current draft state
            df_with_dynamic_vorp = self.dynamic_vorp_calc.calculate_dynamic_vorp(
                projections_df.copy(), 
                self.draft_state
            )
            
            # Filter out already drafted players
            drafted_players = {pick.player_id for pick in self.draft_state.picks}
            available_players = df_with_dynamic_vorp[
                ~df_with_dynamic_vorp['player_id'].isin(drafted_players)
            ]
            
            # Get top recommendations by dynamic VORP
            top_recommendations = available_players.nlargest(top_n, 'dynamic_vorp_final')
            
            # Get current team on the clock for targeted recommendations
            current_team = self.draft_state.get_current_team()
            current_team_needs = {}
            if current_team:
                current_team_needs = {
                    'QB': current_team.needs_qb,
                    'RB': current_team.needs_rb,
                    'WR': current_team.needs_wr,
                    'TE': current_team.needs_te,
                }
            
            # Get position-specific recommendations for current team
            position_recs = {}
            for pos, need in current_team_needs.items():
                if need > 0:  # Only if team needs this position
                    pos_players = available_players[available_players['position'] == pos]
                    if not pos_players.empty:
                        position_recs[pos] = pos_players.nlargest(5, 'dynamic_vorp_final')[
                            ['player_name', 'position', 'team', 'projected_points', 
                             'static_vorp', 'dynamic_vorp_final', 'vorp_change']
                        ].to_dict('records')
            
            # Generate insights
            insights = self.dynamic_vorp_calc.get_dynamic_vorp_insights(df_with_dynamic_vorp, self.draft_state)
            
            return {
                'recommendations': top_recommendations[
                    ['player_name', 'position', 'team', 'projected_points', 
                     'static_vorp', 'dynamic_vorp_final', 'vorp_change',
                     'position_scarcity_multiplier', 'dynamic_vorp_overall_rank']
                ].to_dict('records'),
                'current_team_recommendations': position_recs,
                'current_team_info': {
                    'team_name': current_team.team_name if current_team else 'Unknown',
                    'owner_name': current_team.owner_name if current_team else 'Unknown',
                    'needs': current_team_needs
                } if current_team else {},
                'insights': insights,
                'is_dynamic': True,
                'draft_context': {
                    'picks_made': len(self.draft_state.picks),
                    'current_round': self.draft_state.current_round,
                    'current_pick': self.draft_state.current_pick
                }
            }
            
        except Exception as e:
            logger.error(f"Error calculating dynamic VORP recommendations: {e}")
            # Fallback to static recommendations
            return self.get_dynamic_vorp_recommendations(projections_df, top_n)
    
    def get_vorp_comparison_for_player(self, player_id: str, projections_df) -> Dict[str, Any]:
        """
        Get detailed VORP comparison (static vs dynamic) for a specific player
        
        Args:
            player_id: Player ID to analyze
            projections_df: DataFrame with player projections
            
        Returns:
            Dictionary with detailed VORP analysis for the player
        """
        if not self.dynamic_vorp_calc or not self.draft_state:
            return {'error': 'Dynamic VORP not available'}
        
        try:
            # Calculate dynamic VORP
            df_with_dynamic_vorp = self.dynamic_vorp_calc.calculate_dynamic_vorp(
                projections_df.copy(), 
                self.draft_state
            )
            
            # Find the player
            player_data = df_with_dynamic_vorp[df_with_dynamic_vorp['player_id'] == player_id]
            if player_data.empty:
                return {'error': f'Player {player_id} not found'}
            
            player_row = player_data.iloc[0]
            
            return {
                'player_name': player_row['player_name'],
                'position': player_row['position'],
                'team': player_row['team'],
                'projected_points': player_row['projected_points'],
                'static_vorp': player_row['static_vorp'],
                'dynamic_vorp': player_row['dynamic_vorp_final'],
                'vorp_change': player_row['vorp_change'],
                'static_rank': player_row['vorp_overall_rank'],
                'dynamic_rank': player_row['dynamic_vorp_overall_rank'],
                'rank_change': player_row['vorp_overall_rank'] - player_row['dynamic_vorp_overall_rank'],
                'market_factors': {
                    'position_scarcity': player_row['position_scarcity_multiplier'],
                    'tier_depletion': player_row['tier_depletion_factor'],
                    'round_strategy': player_row['round_strategy_adjustment']
                },
                'context': {
                    'replacement_level_shift': player_row['replacement_level_shift'],
                    'current_round': self.draft_state.current_round,
                    'picks_made': len(self.draft_state.picks)
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting VORP comparison for player {player_id}: {e}")
            return {'error': str(e)}

class DraftDiscovery:
    """Helper class for discovering drafts from league or user information"""
    
    def __init__(self, client: Optional[SleeperClient] = None):
        """Initialize draft discovery"""
        self.client = client or SleeperClient()
    
    def find_drafts_by_username(self, username: str, season: str = "2025") -> List[Dict[str, Any]]:
        """
        Find all drafts for a user by username
        
        Args:
            username: Sleeper username
            season: Season year
            
        Returns:
            List of draft information dictionaries
        """
        try:
            # Get user info
            user_info = self.client.get_user(username)
            user_id = user_info['user_id']
            
            # Get user's leagues
            leagues = self.client.get_user_leagues(user_id, season=season)
            
            drafts = []
            for league in leagues:
                league_id = league['league_id']
                league_drafts = self.client.get_league_drafts(league_id)
                
                for draft in league_drafts:
                    draft['league_name'] = league.get('name', 'Unknown')
                    draft['league_status'] = league.get('status', 'unknown')
                    drafts.append(draft)
            
            return drafts
            
        except SleeperAPIError as e:
            logger.error(f"Error finding drafts for user {username}: {e}")
            return []
    
    def find_active_drafts_by_username(self, username: str, season: str = "2025") -> List[Dict[str, Any]]:
        """Find only active/drafting drafts for a user"""
        all_drafts = self.find_drafts_by_username(username, season)
        return [draft for draft in all_drafts if draft.get('status') == 'drafting']
    
    def get_draft_by_league_id(self, league_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the most recent draft for a league
        
        Args:
            league_id: Sleeper league_id
            
        Returns:
            Draft information or None
        """
        try:
            drafts = self.client.get_league_drafts(league_id)
            if drafts:
                # Return most recent draft (they're sorted by most recent first)
                return drafts[0]
            return None
        except SleeperAPIError as e:
            logger.error(f"Error getting draft for league {league_id}: {e}")
            return None 
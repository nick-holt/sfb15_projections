"""
Live Draft Dashboard View

This module provides the Streamlit interface for live draft tracking,
showing real-time draft progress, team needs, and VORP-based recommendations.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import Dict, List, Optional, Any
import logging
from datetime import datetime
import time
import threading

from ...draft.draft_manager import DraftManager, DraftDiscovery
from ...draft.draft_state import DraftState, DraftPick
from ...draft.sleeper_client import SleeperAPIError

logger = logging.getLogger(__name__)

# Compatibility functions for older Streamlit versions
def create_tab_interface(tab_names: List[str], key_prefix: str = "tab"):
    """Create a simple selectbox interface for Streamlit 1.12.0 compatibility"""
    
    # Initialize session state for selected tab if not exists
    tab_key = f"{key_prefix}_selected"
    if tab_key not in st.session_state:
        st.session_state[tab_key] = 0
    
    # Use selectbox for reliable compatibility
    selected_tab_name = st.selectbox(
        "Choose section:",
        tab_names,
        index=st.session_state[tab_key],
        key=f"{key_prefix}_selectbox"
    )
    
    # Update session state
    selected_index = tab_names.index(selected_tab_name)
    st.session_state[tab_key] = selected_index
    
    return selected_index

class LiveDraftView:
    """Streamlit component for live draft tracking"""
    
    def __init__(self, projections_data: Optional[pd.DataFrame] = None):
        """
        Initialize live draft view
        
        Args:
            projections_data: Player projections DataFrame
        """
        self.projections_data = projections_data
        self.draft_manager: Optional[DraftManager] = None
        
        # Initialize session state
        if 'draft_state' not in st.session_state:
            st.session_state.draft_state = None
        if 'draft_manager' not in st.session_state:
            st.session_state.draft_manager = None
        if 'live_picks' not in st.session_state:
            st.session_state.live_picks = []
        if 'last_refresh' not in st.session_state:
            st.session_state.last_refresh = time.time()
    
    def render(self):
        """Render the complete live draft interface"""
        st.title("🏈 Live Draft Tracker")
        
        # Draft connection section
        with st.container():
            self._render_draft_connection()
        
        # If we have an active draft, show the main interface
        if st.session_state.draft_manager and st.session_state.draft_state:
            st.markdown("---")  # Horizontal line instead of st.divider()
            self._render_draft_dashboard()
        else:
            self._render_getting_started()
    
    def _render_draft_connection(self):
        """Render draft connection/discovery interface"""
        st.subheader("Connect to Live Draft")
        
        # Connection method tabs - using button interface for older Streamlit
        method_tab_names = ["By Username", "By Draft ID", "By League ID"]
        selected_method_index = create_tab_interface(method_tab_names, "connection_method")
        
        if selected_method_index == 0:  # By Username
            col1, col2 = st.columns([3, 1])
            with col1:
                username = st.text_input(
                    "Sleeper Username",
                    help="Enter your Sleeper username to find your drafts"
                )
            with col2:
                season = st.selectbox("Season", ["2025", "2024"], index=0)
            
            if st.button("Find Drafts", key="find_by_username"):
                if username:
                    self._find_drafts_by_username(username, season)
                else:
                    st.error("Please enter a username")
        
        elif selected_method_index == 1:  # By Draft ID
            draft_id = st.text_input(
                "Draft ID",
                help="Enter the Sleeper draft ID directly"
            )
            
            if st.button("Connect to Draft", key="connect_by_draft_id"):
                if draft_id:
                    self._connect_to_draft(draft_id)
                else:
                    st.error("Please enter a draft ID")
        
        elif selected_method_index == 2:  # By League ID
            league_id = st.text_input(
                "League ID", 
                help="Enter the Sleeper league ID to find its draft"
            )
            
            if st.button("Find League Draft", key="find_by_league_id"):
                if league_id:
                    self._find_draft_by_league(league_id)
                else:
                    st.error("Please enter a league ID")
        
        # Show current connection status
        if st.session_state.draft_manager:
            draft_state = st.session_state.draft_state
            st.success(f"✅ Connected to: **{draft_state.settings.league_name}**")
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Status", draft_state.status.title())
            with col2:
                st.metric("Current Pick", f"{draft_state.current_pick}")
            with col3:
                st.metric("Round", f"{draft_state.current_round}")
            with col4:
                total_picks = len(draft_state.picks)
                max_picks = draft_state.settings.total_teams * draft_state.settings.total_rounds
                st.metric("Progress", f"{total_picks}/{max_picks}")
    
    def _render_draft_dashboard(self):
        """Render the main draft dashboard"""
        draft_state = st.session_state.draft_state
        
        # Main dashboard tabs - using button interface for older Streamlit
        dashboard_tab_names = ["📊 Draft Board", "🎯 Team Analysis", "⚡ Live Recommendations", "📈 Draft Insights"]
        selected_dashboard_index = create_tab_interface(dashboard_tab_names, "dashboard")
        
        if selected_dashboard_index == 0:  # Draft Board
            self._render_draft_board(draft_state)
        elif selected_dashboard_index == 1:  # Team Analysis
            self._render_team_analysis(draft_state)
        elif selected_dashboard_index == 2:  # Live Recommendations
            self._render_live_recommendations(draft_state)
        elif selected_dashboard_index == 3:  # Draft Insights
            self._render_draft_insights(draft_state)
    
    def _render_draft_board(self, draft_state: DraftState):
        """Render visual draft board"""
        st.subheader("Draft Board")
        
        # Get draft board data
        draft_manager = st.session_state.draft_manager
        board = draft_manager.get_draft_board()
        
        if not board:
            st.info("No picks yet")
            return
        
        # Create draft board visualization
        board_data = []
        for round_num, round_picks in enumerate(board, 1):
            for slot_num, pick in enumerate(round_picks, 1):
                if pick:
                    board_data.append({
                        'Round': round_num,
                        'Pick': slot_num,
                        'Player': pick.player_name,
                        'Position': pick.position,
                        'Team': pick.team,
                        'Owner': draft_state.rosters.get(pick.roster_id, {}).owner_name or 'Unknown'
                    })
        
        if board_data:
            board_df = pd.DataFrame(board_data)
            
            # Create interactive heatmap-style board
            fig = px.scatter(
                board_df,
                x='Pick',
                y='Round',
                color='Position',
                hover_data=['Player', 'Team', 'Owner'],
                title="Draft Board Overview"
            )
            
            fig.update_layout(
                yaxis=dict(autorange="reversed"),  # Reverse y-axis so Round 1 is at top
                height=600
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Recent picks table
            st.subheader("Recent Picks")
            recent_picks = board_df.tail(10).sort_values('Round', ascending=False)
            st.dataframe(recent_picks, use_container_width=True)
    
    def _render_team_analysis(self, draft_state: DraftState):
        """Render team-by-team analysis"""
        st.subheader("Team Analysis")
        
        draft_manager = st.session_state.draft_manager
        
        # Team selector
        team_options = {
            f"{roster.owner_name} ({roster.team_name or 'No Team Name'})": roster_id
            for roster_id, roster in draft_state.rosters.items()
        }
        
        selected_team_name = st.selectbox("Select Team", list(team_options.keys()))
        selected_roster_id = team_options[selected_team_name]
        
        # Get team analysis
        team_analysis = draft_manager.get_team_needs_analysis(selected_roster_id)
        
        if team_analysis:
            # Team overview
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Picks", team_analysis['total_picks'])
            with col2:
                st.metric("QB", team_analysis['positional_counts']['QB'])
            with col3:
                st.metric("RB", team_analysis['positional_counts']['RB'])
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("WR", team_analysis['positional_counts']['WR'])
            with col2:
                st.metric("TE", team_analysis['positional_counts']['TE'])
            with col3:
                st.metric("Bench", team_analysis['positional_counts']['BENCH'])
            
            # Positional needs
            st.subheader("Remaining Needs")
            needs_data = [
                {'Position': pos, 'Still Need': count}
                for pos, count in team_analysis['positional_needs'].items()
                if count > 0
            ]
            
            if needs_data:
                needs_df = pd.DataFrame(needs_data)
                fig = px.bar(needs_df, x='Position', y='Still Need', 
                           title="Remaining Positional Needs")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.success("✅ All positional needs filled!")
            
            # Recent picks
            if team_analysis['recent_picks']:
                st.subheader("Recent Picks")
                recent_df = pd.DataFrame(team_analysis['recent_picks'])
                st.dataframe(recent_df, use_container_width=True)
    
    def _render_live_recommendations(self, draft_state: DraftState):
        """Render live draft recommendations based on VORP"""
        st.subheader("Live Draft Recommendations")
        
        if self.projections_data is None:
            st.warning("Projections data not available for recommendations")
            return
        
        # Get current team on the clock
        current_team = draft_state.get_current_team()
        if not current_team:
            st.info("Draft complete or no current team")
            return
        
        st.info(f"**{current_team.owner_name}** is on the clock (Pick {draft_state.current_pick})")
        
        # Get available players with projections
        available_players = self._get_available_players_with_projections(draft_state)
        
        if available_players.empty:
            st.warning("No available players with projection data")
            return
        
        # Get team needs
        draft_manager = st.session_state.draft_manager
        team_analysis = draft_manager.get_team_needs_analysis(current_team.roster_id)
        
        # Filter recommendations by need
        recommendations = self._generate_recommendations(available_players, team_analysis)
        
        # Display top recommendations
        st.subheader("Top Recommendations")
        
        if not recommendations.empty:
            # Top 10 recommendations
            top_recs = recommendations.head(10)
            
            for idx, player in top_recs.iterrows():
                with st.container():
                    col1, col2, col3, col4 = st.columns([3, 1, 1, 2])
                    
                    with col1:
                        st.write(f"**{player['player_name']}** ({player['position']} - {player['team']})")
                    
                    with col2:
                        st.metric("VORP", f"{player.get('vorp_score', 0):.1f}")
                    
                    with col3:
                        st.metric("Proj Pts", f"{player.get('projected_points', 0):.1f}")
                    
                    with col4:
                        need_level = self._assess_positional_need(player['position'], team_analysis)
                        st.write(f"Need: {need_level}")
        else:
            st.info("No specific recommendations available")
    
    def _render_draft_insights(self, draft_state: DraftState):
        """Render draft insights and analytics"""
        st.subheader("Draft Insights")
        
        if not draft_state.picks:
            st.info("No picks to analyze yet")
            return
        
        # Position distribution
        picks_df = pd.DataFrame([
            {
                'pick_number': pick.pick_number,
                'round': pick.round,
                'position': pick.position,
                'player_name': pick.player_name,
                'team': pick.team
            }
            for pick in draft_state.picks
        ])
        
        # Position distribution by round
        pos_by_round = picks_df.groupby(['round', 'position']).size().reset_index(name='count')
        
        fig = px.bar(
            pos_by_round,
            x='round',
            y='count',
            color='position',
            title="Position Distribution by Round"
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Team drafting patterns
        team_picks = []
        for pick in draft_state.picks:
            roster = draft_state.rosters.get(pick.roster_id)
            if roster:
                team_picks.append({
                    'owner': roster.owner_name,
                    'position': pick.position,
                    'round': pick.round
                })
        
        if team_picks:
            team_df = pd.DataFrame(team_picks)
            team_pos_counts = team_df.groupby(['owner', 'position']).size().reset_index(name='count')
            
            fig = px.bar(
                team_pos_counts,
                x='owner',
                y='count',
                color='position',
                title="Positional Picks by Team"
            )
            fig.update_xaxes(tickangle=45)
            st.plotly_chart(fig, use_container_width=True)
    
    def _render_getting_started(self):
        """Render getting started guide"""
        st.subheader("Getting Started")
        
        st.markdown("""
        ### How to Connect to Your Live Draft
        
        **Works with both League Drafts and Mock Drafts!**
        
        1. **By Username**: Enter your Sleeper username to see all your drafts (league drafts only)
        2. **By Draft ID**: If you have the draft ID, enter it directly (works for both league and mock drafts)
        3. **By League ID**: Enter your league ID to find the draft (league drafts only)
        
        ### What You'll See
        
        - **Real-time draft board** with all picks as they happen
        - **Team analysis** showing positional needs and roster composition
        - **VORP-based recommendations** for the team currently on the clock
        - **Draft insights** and analytics on drafting patterns
        
        ### Finding Your IDs
        
        - **Username**: Your Sleeper username (not display name)
        - **Draft ID**: Found in the Sleeper app URL during draft (works for mock drafts too!)
        - **League ID**: Found in league settings or URL (league drafts only)
        
        ### Mock Draft Support
        
        For mock drafts, use the **Draft ID** option. Mock drafts will show as "Mock Draft" 
        with generic team names since they don't have league information.
        """)
    
    def _find_drafts_by_username(self, username: str, season: str):
        """Find drafts for a username"""
        try:
            with st.spinner("Finding drafts..."):
                discovery = DraftDiscovery()
                drafts = discovery.find_drafts_by_username(username, season)
                
                if not drafts:
                    st.error(f"No drafts found for username: {username}")
                    return
                
                # Show draft selection
                st.subheader("Select Draft")
                
                draft_options = {}
                for draft in drafts:
                    status = draft.get('status', 'unknown')
                    league_name = draft.get('league_name', 'Unknown League')
                    draft_name = f"{league_name} - {status.title()}"
                    draft_options[draft_name] = draft['draft_id']
                
                selected_draft_name = st.selectbox("Available Drafts", list(draft_options.keys()))
                selected_draft_id = draft_options[selected_draft_name]
                
                if st.button("Connect to Selected Draft"):
                    self._connect_to_draft(selected_draft_id)
                    
        except SleeperAPIError as e:
            st.error(f"Error finding drafts: {e}")
    
    def _find_draft_by_league(self, league_id: str):
        """Find draft by league ID"""
        try:
            with st.spinner("Finding league draft..."):
                discovery = DraftDiscovery()
                draft = discovery.get_draft_by_league_id(league_id)
                
                if not draft:
                    st.error(f"No draft found for league: {league_id}")
                    return
                
                draft_id = draft['draft_id']
                self._connect_to_draft(draft_id)
                
        except SleeperAPIError as e:
            st.error(f"Error finding league draft: {e}")
    
    def _connect_to_draft(self, draft_id: str):
        """Connect to a specific draft"""
        try:
            with st.spinner("Connecting to draft..."):
                # Create draft manager
                projections_dict = self.projections_data.to_dict('list') if self.projections_data is not None else None
                draft_manager = DraftManager(draft_id, projections_data=projections_dict)
                
                # Initialize draft state
                draft_state = draft_manager.initialize_draft()
                
                # Store in session state
                st.session_state.draft_manager = draft_manager
                st.session_state.draft_state = draft_state
                
                st.success(f"✅ Connected to draft: {draft_state.settings.league_name}")
                st.experimental_rerun()
                
        except SleeperAPIError as e:
            st.error(f"Error connecting to draft: {e}")
        except Exception as e:
            st.error(f"Unexpected error: {e}")
            logger.error(f"Error connecting to draft {draft_id}: {e}")
    
    def _get_available_players_with_projections(self, draft_state: DraftState) -> pd.DataFrame:
        """Get available players merged with projection data"""
        if self.projections_data is None:
            return pd.DataFrame()
        
        # Get drafted player names
        drafted_players = {pick.player_name for pick in draft_state.picks}
        
        # Filter projections to only available players
        available_projections = self.projections_data[
            ~self.projections_data['player_name'].isin(drafted_players)
        ].copy()
        
        return available_projections
    
    def _generate_recommendations(self, available_players: pd.DataFrame, team_analysis: Dict[str, Any]) -> pd.DataFrame:
        """Generate position-based recommendations"""
        if available_players.empty:
            return pd.DataFrame()
        
        # Add need score based on positional needs
        def calculate_need_score(position: str) -> float:
            needs = team_analysis.get('positional_needs', {})
            
            # Base need scores
            need_score = 0
            if position in ['QB', 'RB', 'WR', 'TE', 'K', 'DEF']:
                need_score = needs.get(position, 0) * 10
            
            # Flex eligibility bonus
            if position in ['RB', 'WR', 'TE']:
                need_score += needs.get('FLEX', 0) * 5
            
            # Bench need
            need_score += needs.get('BENCH', 0) * 2
            
            return need_score
        
        recommendations = available_players.copy()
        recommendations['need_score'] = recommendations['position'].apply(calculate_need_score)
        
        # Calculate total recommendation score
        vorp_score = recommendations.get('vorp_score', 0)
        recommendations['recommendation_score'] = (
            vorp_score + recommendations['need_score']
        )
        
        # Sort by recommendation score
        recommendations = recommendations.sort_values(
            'recommendation_score', ascending=False
        )
        
        return recommendations
    
    def _assess_positional_need(self, position: str, team_analysis: Dict[str, Any]) -> str:
        """Assess positional need level"""
        needs = team_analysis.get('positional_needs', {})
        
        direct_need = needs.get(position, 0)
        flex_need = needs.get('FLEX', 0) if position in ['RB', 'WR', 'TE'] else 0
        bench_need = needs.get('BENCH', 0)
        
        total_need = direct_need + (flex_need * 0.5) + (bench_need * 0.2)
        
        if total_need >= 2:
            return "🔴 High"
        elif total_need >= 1:
            return "🟡 Medium"
        elif total_need > 0:
            return "🟢 Low"
        else:
            return "⚪ None" 
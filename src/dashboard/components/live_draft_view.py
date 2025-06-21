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
        """Render live draft recommendations with dynamic VORP"""
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
        
        # Get dynamic VORP recommendations
        draft_manager = st.session_state.draft_manager
        if hasattr(draft_manager, 'get_dynamic_vorp_recommendations'):
            try:
                vorp_recs = draft_manager.get_dynamic_vorp_recommendations(self.projections_data, top_n=15)
                
                # Show dynamic vs static toggle
                show_dynamic = st.checkbox("Show Dynamic VORP (real-time adjusted)", value=True)
                
                if vorp_recs['is_dynamic'] and show_dynamic:
                    st.subheader("🔥 Dynamic VORP Recommendations")
                    st.caption("Values adjusted for current draft state and position scarcity")
                    
                    # Show insights first
                    insights = vorp_recs.get('insights', {})
                    recommendations = vorp_recs.get('recommendations', [])
                    
                    if insights or recommendations:
                        with st.expander("📈 Market Insights & Draft Context", expanded=False):
                            # Show current draft context if available
                            if recommendations:
                                rec_df = pd.DataFrame(recommendations)
                                if 'current_round' in rec_df.columns and 'draft_progress' in rec_df.columns:
                                    current_round = rec_df['current_round'].iloc[0] if not rec_df.empty else 1
                                    draft_progress = rec_df['draft_progress'].iloc[0] if not rec_df.empty else 0
                                    
                                    st.markdown("**🎯 Draft Context:**")
                                    context_col1, context_col2, context_col3 = st.columns(3)
                                    with context_col1:
                                        st.metric("Current Round", f"Round {current_round}")
                                    with context_col2:
                                        st.metric("Draft Progress", f"{draft_progress:.1%}")
                                    with context_col3:
                                        draft_stage = "Early" if current_round <= 3 else "Middle" if current_round <= 8 else "Late"
                                        st.metric("Draft Stage", draft_stage)
                                    
                                    st.markdown("---")
                            
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.write("**Position Scarcity:**")
                                if insights and 'position_scarcity' in insights:
                                    scarcity = insights.get('position_scarcity', {})
                                    for pos, data in scarcity.items():
                                        level = data.get('scarcity_level', 'Unknown')
                                        multiplier = data.get('scarcity_multiplier', 1.0)
                                        color = "🔴" if level == "High" else "🟡" if level == "Medium" else "🟢"
                                        st.write(f"{color} {pos}: {level} ({multiplier:.2f}x)")
                                elif recommendations:
                                    # Calculate from recommendations data
                                    rec_df = pd.DataFrame(recommendations)
                                    for position in ['QB', 'RB', 'WR', 'TE']:
                                        pos_data = rec_df[rec_df['position'] == position]
                                        if not pos_data.empty:
                                            avg_scarcity = pos_data.get('position_scarcity_multiplier', pd.Series([1.0])).mean()
                                            if avg_scarcity > 1.2:
                                                level = "🔴 High"
                                            elif avg_scarcity > 1.0:
                                                level = "🟡 Medium"
                                            else:
                                                level = "🟢 Low"
                                            st.write(f"{position}: {level} ({avg_scarcity:.2f}x)")
                            
                            with col2:
                                st.write("**Context Adjustments:**")
                                if recommendations:
                                    rec_df = pd.DataFrame(recommendations)
                                    if 'round_strategy_adjustment' in rec_df.columns:
                                        for position in ['QB', 'RB', 'WR', 'TE']:
                                            pos_data = rec_df[rec_df['position'] == position]
                                            if not pos_data.empty:
                                                avg_context = pos_data['round_strategy_adjustment'].mean()
                                                trend = "📈" if avg_context > 1.05 else "📉" if avg_context < 0.95 else "➡️"
                                                st.write(f"{position}: {trend} {avg_context:.3f}")
                                    else:
                                        st.write("Context data not available")
                                else:
                                    st.write("**Replacement Level Shifts:**")
                                    shifts = insights.get('replacement_level_shifts', {})
                                    for pos, data in shifts.items():
                                        direction = data.get('direction', 'stable')
                                        avg_shift = data.get('average_shift', 0)
                                        arrow = "⬆️" if direction == "increased" else "⬇️" if direction == "decreased" else "➡️"
                                        st.write(f"{arrow} {pos}: {direction} ({avg_shift:+.1f})")
                            
                            # Show Feature 2 context awareness info
                            if recommendations:
                                rec_df = pd.DataFrame(recommendations)
                                if 'round_strategy_adjustment' in rec_df.columns:
                                    st.markdown("---")
                                    st.markdown("**🧠 Context Awareness Features:**")
                                    st.write("✓ Round-specific strategy adjustments")
                                    st.write("✓ Snake draft position optimization")
                                    st.write("✓ Draft timing considerations")
                                    st.write("✓ Positional value curve adjustments")
                                    
                                # Feature 3: Roster Construction Analysis
                                if 'roster_construction_multiplier' in rec_df.columns:
                                    st.markdown("---")
                                    st.markdown("**🏗️ Roster Construction Analysis:**")
                                    
                                    # Show current team roster composition
                                    if insights and 'roster_construction' in insights:
                                        roster_info = insights['roster_construction']
                                        
                                        col1, col2 = st.columns(2)
                                        with col1:
                                            st.write("**Current Roster:**")
                                            current_roster = roster_info.get('current_roster', {})
                                            if current_roster:
                                                for pos, count in current_roster.items():
                                                    st.write(f"• {pos}: {count}")
                                            else:
                                                st.write("• No picks yet")
                                            
                                            balance_score = roster_info.get('roster_balance_score', 0)
                                            balance_emoji = "🟢" if balance_score > 0.8 else "🟡" if balance_score > 0.6 else "🔴"
                                            st.write(f"**Balance Score:** {balance_emoji} {balance_score:.1%}")
                                        
                                        with col2:
                                            st.write("**Positional Needs:**")
                                            needs = roster_info.get('positional_needs', {})
                                            for pos, need in needs.items():
                                                emoji = "🚨" if need == "Critical" else "⚠️" if need == "Moderate" else "✅" if need == "Satisfied" else "📈"
                                                st.write(f"{emoji} {pos}: {need}")
                                        
                                        # Show roster recommendations
                                        recommendations_list = roster_info.get('roster_recommendations', [])
                                        if recommendations_list:
                                            st.write("**Recommendations:**")
                                            for rec in recommendations_list:
                                                st.write(f"• {rec}")
                                    
                                    st.write("✓ Team positional need analysis")
                                    st.write("✓ Roster balance optimization")
                                    st.write("✓ League-wide position scarcity tracking")
                                    st.write("✓ Bye week conflict avoidance")
                                
                                # Feature 4: Market Inefficiency Detection
                                if 'market_inefficiency_multiplier' in rec_df.columns:
                                    st.markdown("---")
                                    st.markdown("**📊 Market Inefficiency Detection:**")
                                    
                                    # Show market inefficiency insights
                                    if insights and 'market_inefficiency' in insights:
                                        market_info = insights['market_inefficiency']
                                        
                                        col1, col2 = st.columns(2)
                                        with col1:
                                            # Market efficiency score
                                            efficiency = market_info.get('market_efficiency_score', {})
                                            if efficiency and efficiency.get('score') != 'N/A':
                                                score = efficiency.get('score', 'N/A')
                                                description = efficiency.get('description', '')
                                                correlation = efficiency.get('correlation', 'N/A')
                                                st.write(f"**Market Efficiency:** {score}")
                                                st.write(f"*{description}*")
                                                st.write(f"ADP-VORP Correlation: {correlation}")
                                            
                                            # Position runs
                                            position_runs = market_info.get('position_runs', {})
                                            if position_runs:
                                                st.write("**🏃 Active Position Runs:**")
                                                for pos, run_data in position_runs.items():
                                                    severity = run_data.get('severity', 'Medium')
                                                    count = run_data.get('count', 0)
                                                    emoji = "🚨" if severity == "High" else "⚠️"
                                                    st.write(f"{emoji} {pos}: {count} in last 5 picks")
                                        
                                        with col2:
                                            # Contrarian opportunities
                                            opportunities = market_info.get('contrarian_opportunities', [])
                                            if opportunities:
                                                st.write("**💎 Contrarian Opportunities:**")
                                                for opp in opportunities[:3]:  # Top 3
                                                    player = opp.get('player_name', 'Unknown')
                                                    rank_diff = opp.get('rank_diff', 0)
                                                    confidence = opp.get('confidence', 'Medium')
                                                    emoji = "⭐" if confidence == "High" else "💡"
                                                    st.write(f"{emoji} {player} (+{rank_diff:.0f} value gap)")
                                            
                                            # Draft flow predictions
                                            flow = market_info.get('draft_flow_predictions', {})
                                            next_round = flow.get('next_round_positions', {})
                                            if next_round:
                                                st.write("**🔮 Next Round Predictions:**")
                                                for pos, pred in next_round.items():
                                                    likelihood = pred.get('likelihood', 'Average')
                                                    if likelihood != 'Average':
                                                        emoji = "📈" if "High" in likelihood or "Above" in likelihood else "📉"
                                                        st.write(f"{emoji} {pos}: {likelihood}")
                                    
                                    st.write("✓ ADP vs VORP gap analysis")
                                    st.write("✓ Position run detection")
                                    st.write("✓ Contrarian opportunity identification")
                                    st.write("✓ Draft flow predictions")
                    
                    # Current team specific recommendations
                    team_recs = vorp_recs.get('current_team_recommendations', {})
                    if team_recs:
                        st.write("**🎯 Position-Specific for Current Team:**")
                        for pos, players in team_recs.items():
                            if players:
                                with st.expander(f"{pos} Recommendations ({len(players)} players)", expanded=True):
                                    for player in players[:3]:  # Top 3 per position
                                        col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                                        with col1:
                                            st.write(f"**{player['player_name']}** ({player['team']})")
                                        with col2:
                                            static_vorp = player.get('static_vorp', 0)
                                            st.metric("Static VORP", f"{static_vorp:.1f}")
                                        with col3:
                                            dynamic_vorp = player.get('dynamic_vorp_final', 0)
                                            st.metric("Dynamic VORP", f"{dynamic_vorp:.1f}")
                                        with col4:
                                            change = player.get('vorp_change', 0)
                                            delta_color = "normal" if abs(change) < 1 else "inverse" if change < 0 else "normal"
                                            st.metric("Change", f"{change:+.1f}", delta_color=delta_color)
                    
                    # Top overall recommendations
                    st.write("**🏆 Top Overall Available Players:**")
                    top_recs = vorp_recs['recommendations'][:10]
                    
                    for i, player in enumerate(top_recs):
                        with st.container():
                            col1, col2, col3, col4, col5 = st.columns([3, 1, 1, 1, 1])
                            
                            with col1:
                                rank_change = ""
                                if 'dynamic_vorp_overall_rank' in player:
                                    rank = int(player['dynamic_vorp_overall_rank'])
                                    rank_change = f" (#{rank})"
                                st.write(f"**{i+1}.** {player['player_name']} ({player['position']} - {player['team']}){rank_change}")
                            
                            with col2:
                                static_vorp = player.get('static_vorp', 0)
                                st.metric("Static", f"{static_vorp:.1f}")
                            
                            with col3:
                                dynamic_vorp = player.get('dynamic_vorp_final', 0)
                                st.metric("Dynamic", f"{dynamic_vorp:.1f}")
                            
                            with col4:
                                change = player.get('vorp_change', 0)
                                delta_color = "normal" if abs(change) < 1 else "inverse" if change < 0 else "normal"
                                st.metric("Change", f"{change:+.1f}", delta_color=delta_color)
                            
                            with col5:
                                scarcity = player.get('position_scarcity_multiplier', 1.0)
                                scarcity_color = "🔴" if scarcity > 1.2 else "🟡" if scarcity > 1.0 else "🟢"
                                st.write(f"{scarcity_color} {scarcity:.2f}x")
                
                else:
                    # Fallback to static VORP
                    st.subheader("📊 Static VORP Recommendations")
                    if not vorp_recs['is_dynamic']:
                        st.caption(vorp_recs.get('message', 'Pre-draft baseline values'))
                    
                    static_recs = vorp_recs['recommendations'][:10]
                    for i, player in enumerate(static_recs):
                        with st.container():
                            col1, col2, col3, col4 = st.columns([3, 1, 1, 2])
                            
                            with col1:
                                st.write(f"**{i+1}.** {player['player_name']} ({player['position']} - {player['team']})")
                            
                            with col2:
                                vorp = player.get('vorp_score', player.get('static_vorp', 0))
                                st.metric("VORP", f"{vorp:.1f}")
                            
                            with col3:
                                st.metric("Proj Pts", f"{player.get('projected_points', 0):.1f}")
                            
                            with col4:
                                team_analysis = draft_manager.get_team_needs_analysis(current_team.roster_id)
                                need_level = self._assess_positional_need(player['position'], team_analysis)
                                st.write(f"Need: {need_level}")
                
            except Exception as e:
                st.error(f"Error getting dynamic VORP recommendations: {e}")
                # Fallback to basic recommendations
                self._render_basic_recommendations(draft_state)
        else:
            # Fallback to basic recommendations
            self._render_basic_recommendations(draft_state)
    
    def _render_basic_recommendations(self, draft_state: DraftState):
        """Render basic recommendations when dynamic VORP is not available"""
        current_team = draft_state.get_current_team()
        draft_manager = st.session_state.draft_manager
        
        # Get available players with projections
        available_players = self._get_available_players_with_projections(draft_state)
        
        if available_players.empty:
            st.warning("No available players with projection data")
            return
        
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
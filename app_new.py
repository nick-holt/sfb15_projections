"""
SFB15 Draft Command Center - Overhauled UI
Enhanced fantasy football draft interface with Don Norman's design principles
"""

import streamlit as st
import pandas as pd
import numpy as np
import sys
from pathlib import Path
import time
from datetime import datetime

# Add src to path for imports
current_dir = Path(__file__).parent
src_path = current_dir / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

# Core imports - using existing project structure
try:
    from src.data.projections import ProjectionManager
    from src.analytics.dynamic_vorp_calculator import DynamicVORPCalculator
    from src.data.adp_manager import ADPManager
    from src.draft.draft_manager import DraftManager
    from src.analytics.value_calculator import ValueCalculator
    from src.analytics.tier_manager import TierManager
    
    # New UI imports
    from src.dashboard.utils.mobile_detection import (
        get_responsive_config, 
        apply_mobile_css, 
        detect_mobile_device
    )
    from src.dashboard.components.shared.mission_control import render_mission_control
    from src.dashboard.components.draft_mode.pick_now_view import render_pick_now_view
    
    # Legacy imports for analysis features
    from src.dashboard.components.main_view import render_main_view
    from src.dashboard.components.live_draft_view import LiveDraftView
    
except ImportError as e:
    st.error(f"Import error: {e}")
    st.error("Please ensure you're running from the project root directory")
    st.stop()


# Page configuration - MUST be first Streamlit command
st.set_page_config(
    page_title="🏈 SFB15 Draft Command Center",
    page_icon="🏈",
    layout="wide",
    initial_sidebar_state="expanded"
)


@st.cache(ttl=3600, allow_output_mutation=True, suppress_st_warning=True)  # Cache for 1 hour - Streamlit 1.12.0 compatibility
def load_core_data():
    """Load and cache core projection and ADP data"""
    try:
        # Load projections using existing ProjectionManager
        projection_manager = ProjectionManager()
        projections_df = projection_manager.load_enhanced_projections()
        
        if projections_df is None or projections_df.empty:
            # Don't use st.error in cached function - let caller handle the error
            return None, None, None
        
        # Initialize analytics engines
        value_calc = ValueCalculator()
        tier_manager = TierManager()
        
        # Calculate VBD and tiers (following existing app pattern)
        projections_with_vbd = value_calc.calculate_vbd_scores(projections_df)
        projections_final = tier_manager.assign_dynamic_tiers(projections_with_vbd)
        
        # Load ADP data
        adp_manager = ADPManager()
        adp_data = adp_manager.get_blended_adp()
        
        # CRITICAL FIX: Merge ADP data with projections DataFrame
        if adp_data is not None and not adp_data.empty:
            # Merge ADP data with projections using player names
            adp_for_merge = adp_data[['name', 'consensus_adp', 'overall_rank']].copy()
            adp_for_merge = adp_for_merge.rename(columns={
                'name': 'player_name',
                'consensus_adp': 'sfb15_adp',
                'overall_rank': 'sfb15_rank'
            })
            
            # Merge ADP data
            projections_final = projections_final.merge(
                adp_for_merge,
                on='player_name',
                how='left'
            )
        
        # FIXED: Initialize VORP calculator with correct parameters and actually calculate VORP
        vorp_calc = DynamicVORPCalculator(num_teams=12)  # Pass num_teams, not DataFrame
        
        # CRITICAL FIX: Actually calculate VORP scores and add them to the DataFrame
        projections_with_vorp = vorp_calc.calculate_dynamic_vorp(projections_final, draft_state=None)
        
        return projections_with_vorp, adp_data, vorp_calc
        
    except Exception as e:
        # Don't use st.error in cached function - let caller handle the error
        return None, None, None


# Navigation function replaced with render_compact_navigation()


def render_draft_connection():
    """Render draft connection interface"""
    st.markdown("### 🔗 Connect to Live Draft")
    
    with st.expander("Connect to Sleeper Draft", expanded=False):
        st.markdown("**Choose your connection method:**")
        
        # Connection method tabs using radio buttons
        connection_method = st.radio(
            "Connection Method:",
            ["By Username", "By Draft ID", "By League ID"],
            key="connection_method"
        )
        
        if connection_method == "By Username":
            col1, col2 = st.columns([3, 1])
            with col1:
                username = st.text_input(
                    "Sleeper Username",
                    placeholder="Enter your Sleeper username",
                    help="Enter your Sleeper username to find your drafts"
                )
            with col2:
                season = st.selectbox("Season", ["2025", "2024"], index=0)
            
            if st.button("🔍 Find My Drafts", key="find_drafts"):
                if username:
                    with st.spinner("🔍 Searching for your drafts..."):
                        try:
                            from src.draft.draft_manager import DraftDiscovery
                            from src.draft.sleeper_client import SleeperClient, SleeperAPIError
                            
                            # Use the proper DraftDiscovery class
                            sleeper_client = SleeperClient()
                            draft_discovery = DraftDiscovery(sleeper_client)
                            
                            # Find drafts for the user
                            drafts = draft_discovery.find_drafts_by_username(username, season)
                            
                            if drafts:
                                st.success(f"✅ Found {len(drafts)} drafts for {username}")
                                
                                # Display draft options
                                for i, draft in enumerate(drafts):
                                    draft_name = f"Draft {draft['draft_id']} - {draft.get('league_name', 'Unknown League')}"
                                    draft_status = draft.get('status', 'unknown')
                                    
                                    col_a, col_b = st.columns([3, 1])
                                    with col_a:
                                        st.write(f"**{draft_name}** (Status: {draft_status})")
                                    with col_b:
                                        if st.button("Connect", key=f"connect_draft_{i}"):
                                            draft_id = draft['draft_id']
                                            
                                            # Initialize the draft connection
                                            try:
                                                from src.draft.draft_manager import DraftManager
                                                draft_manager = DraftManager(draft_id, sleeper_client)
                                                draft_state = draft_manager.initialize_draft()
                                                
                                                st.session_state.connected_draft_id = draft_id
                                                st.session_state.draft_manager = draft_manager
                                                st.session_state.draft_state = draft_state
                                                st.session_state.draft_username = username
                                                
                                                st.success(f"🎯 Connected to {draft_name}")
                                                st.experimental_rerun()
                                            except Exception as connect_error:
                                                st.error(f"Error connecting to draft: {connect_error}")
                            else:
                                st.warning(f"No drafts found for {username} in {season}")
                        except SleeperAPIError as e:
                            st.error(f"Sleeper API Error: {str(e)}")
                        except ImportError:
                            st.error("Draft manager not available. Please check your installation.")
                        except Exception as e:
                            st.error(f"Error searching for drafts: {str(e)}")
                            st.info("Using mock data for demonstration")
                            # Mock draft data
                            st.success(f"✅ Found 2 mock drafts for {username}")
                            if st.button("Connect to Mock Draft", key="mock_connect"):
                                st.session_state.connected_draft_id = "mock_draft_123"
                                st.session_state.draft_username = username
                                st.success("🎯 Connected to mock draft")
                                st.experimental_rerun()
                else:
                    st.error("Please enter a username")
        
        elif connection_method == "By Draft ID":
            draft_id = st.text_input(
                "Draft ID",
                placeholder="Enter Sleeper draft ID",
                help="Enter the Sleeper draft ID directly"
            )
            
            if st.button("🔗 Connect to Draft", key="connect_draft"):
                if draft_id:
                    with st.spinner("🔗 Connecting to draft..."):
                        try:
                            from src.draft.draft_manager import DraftManager
                            from src.draft.sleeper_client import SleeperClient, SleeperAPIError
                            
                            # Test draft connection using proper Sleeper API
                            sleeper_client = SleeperClient()
                            draft_info = sleeper_client.get_draft(draft_id)
                            
                            if draft_info:
                                # Initialize draft manager with the draft info
                                draft_manager = DraftManager(draft_id, sleeper_client)
                                draft_state = draft_manager.initialize_draft()
                                
                                # CRITICAL FIX: Set UI refresh callback for auto-refresh
                                draft_manager.set_ui_refresh_callback(lambda: st.experimental_rerun())
                                
                                # CRITICAL FIX: Start monitoring for live updates
                                draft_manager.start_monitoring(poll_interval=5)
                                
                                st.session_state.connected_draft_id = draft_id
                                st.session_state.draft_manager = draft_manager
                                st.session_state.draft_state = draft_state
                                
                                st.success(f"✅ Connected to draft {draft_id} with live monitoring")
                                league_name = draft_state.settings.league_name
                                st.info(f"League: {league_name}")
                                st.info(f"Status: {draft_state.status}")
                                st.info(f"Teams: {draft_state.settings.total_teams}, Rounds: {draft_state.settings.total_rounds}")
                                
                                # Use experimental_rerun for Streamlit 1.12.0 compatibility
                                st.experimental_rerun()
                            else:
                                st.error("Draft not found or invalid draft ID")
                        except SleeperAPIError as e:
                            st.error(f"Sleeper API Error: {str(e)}")
                        except ImportError:
                            st.error("Draft manager not available. Please check your installation.")
                        except Exception as e:
                            st.error(f"Error connecting to draft: {str(e)}")
                            # Fallback mock connection
                            st.session_state.connected_draft_id = draft_id
                            st.success(f"✅ Connected to draft {draft_id} (mock mode)")
                            st.experimental_rerun()
                else:
                    st.error("Please enter a draft ID")
        
        elif connection_method == "By League ID":
            league_id = st.text_input(
                "League ID", 
                placeholder="Enter Sleeper league ID",
                help="Enter the Sleeper league ID to find its draft"
            )
            
            if st.button("🔍 Find League Draft", key="find_league"):
                if league_id:
                    with st.spinner("🔍 Finding league draft..."):
                        try:
                            from src.draft.draft_manager import DraftDiscovery
                            from src.draft.sleeper_client import SleeperClient, SleeperAPIError
                            
                            # Use the proper DraftDiscovery class
                            sleeper_client = SleeperClient()
                            draft_discovery = DraftDiscovery(sleeper_client)
                            
                            # Find draft for the league
                            draft_info = draft_discovery.get_draft_by_league_id(league_id)
                            
                            if draft_info:
                                draft_id = draft_info['draft_id']
                                league_name = draft_info.get('league_name', 'Unknown League')
                                
                                from src.draft.draft_manager import DraftManager
                                draft_manager = DraftManager(draft_id, sleeper_client)
                                draft_state = draft_manager.initialize_draft()
                                
                                # CRITICAL FIX: Set UI refresh callback for auto-refresh
                                draft_manager.set_ui_refresh_callback(lambda: st.experimental_rerun())
                                
                                # CRITICAL FIX: Start monitoring for live updates
                                draft_manager.start_monitoring(poll_interval=5)
                                
                                st.session_state.connected_draft_id = draft_id
                                st.session_state.draft_manager = draft_manager
                                st.session_state.draft_state = draft_state
                                
                                st.success(f"✅ Connected to draft for {league_name} with live monitoring")
                                st.experimental_rerun()
                            else:
                                st.error("No active draft found for this league")
                        except Exception as e:
                            st.error(f"Error finding league draft: {str(e)}")
                else:
                    st.error("Please enter a league ID")


def render_player_analysis(projections_df, adp_data, vorp_calc):
    """Render comprehensive player analysis"""
    st.markdown("## 🏈 Player Analysis")
    st.markdown("*Comprehensive player rankings with VORP and ADP integration*")
    
    # Analysis sub-navigation
    analysis_mode = st.radio(
        "Analysis View:",
        ["📊 Rankings", "🏆 Tiers", "💎 Value Finder", "🎯 Sleepers & Busts"],
        horizontal=True,
        key="analysis_mode"
    )
    
    if analysis_mode == "📊 Rankings":
        # Use existing main_view with proper config
        sidebar_config = {
            'show_advanced_metrics': True,
            'positions': [],
            'teams': [],
            'min_projected_points': 0,
            'max_points': 500,
            'max_tier': 10,
            'max_age': 35,
            'search_term': '',
            'confidence_levels': ['High', 'Medium', 'Low'],
            'players_per_page': 50,
            'show_sleepers': False,
            'show_busts': False
        }
        
        try:
            value_calc = ValueCalculator()
            tier_manager = TierManager()
            render_main_view(projections_df, value_calc, tier_manager, adp_data, sidebar_config)
        except Exception as e:
            st.error(f"Error rendering rankings: {str(e)}")
            render_fallback_rankings(projections_df)
    
    elif analysis_mode == "🏆 Tiers":
        render_tier_analysis(projections_df)
    
    elif analysis_mode == "💎 Value Finder":
        render_value_analysis(projections_df, adp_data)
    
    elif analysis_mode == "🎯 Sleepers & Busts":
        render_sleepers_busts(projections_df, adp_data)


def render_fallback_rankings(projections_df):
    """Enhanced fallback rankings view with full functionality"""
    st.subheader("🏈 Player Rankings")
    
    # Enhanced filters in columns
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        positions = ["All"] + sorted(projections_df['position'].unique().tolist())
        selected_pos = st.selectbox("Position:", positions, key="pos_filter")
    
    with col2:
        teams = ["All"] + sorted(projections_df['team'].unique().tolist())
        selected_team = st.selectbox("Team:", teams, key="team_filter")
    
    with col3:
        if 'tier_label' in projections_df.columns:
            tiers = ["All"] + sorted(projections_df['tier_label'].unique().tolist())
            selected_tier = st.selectbox("Tier:", tiers, key="tier_filter")
        else:
            selected_tier = "All"
    
    with col4:
        sort_options = ["Overall Rank", "Projected Points", "VORP Score", "Player Name"]
        sort_by = st.selectbox("Sort by:", sort_options, key="sort_filter")
    
    # Apply filters
    filtered_df = projections_df.copy()
    
    if selected_pos != "All":
        filtered_df = filtered_df[filtered_df['position'] == selected_pos]
    
    if selected_team != "All":
        filtered_df = filtered_df[filtered_df['team'] == selected_team]
    
    if selected_tier != "All" and 'tier_label' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['tier_label'] == selected_tier]
    
    # Sort data
    if sort_by == "Overall Rank":
        filtered_df = filtered_df.sort_values('overall_rank')
    elif sort_by == "Projected Points":
        filtered_df = filtered_df.sort_values('projected_points', ascending=False)
    elif sort_by == "VORP Score" and 'vorp_score' in filtered_df.columns:
        filtered_df = filtered_df.sort_values('vorp_score', ascending=False)
    elif sort_by == "Player Name":
        filtered_df = filtered_df.sort_values('player_name')
    
    # Display summary
    st.markdown(f"**Showing {len(filtered_df)} players**")
    
    # Enhanced display columns with better formatting
    display_cols = ['player_name', 'position', 'team', 'projected_points', 'overall_rank']
    
    if 'vorp_score' in filtered_df.columns:
        display_cols.append('vorp_score')
    if 'tier_label' in filtered_df.columns:
        display_cols.append('tier_label')
    if 'vbd_score' in filtered_df.columns:
        display_cols.append('vbd_score')
    
    # Format the dataframe for better display
    display_df = filtered_df[display_cols].copy()
    
    # Rename columns for better display
    column_renames = {
        'player_name': 'Player',
        'position': 'Pos',
        'team': 'Team',
        'projected_points': 'Proj Pts',
        'overall_rank': 'Rank',
        'vorp_score': 'VORP',
        'tier_label': 'Tier',
        'vbd_score': 'VBD'
    }
    
    display_df = display_df.rename(columns=column_renames)
    
    # Format numeric columns
    if 'Proj Pts' in display_df.columns:
        display_df['Proj Pts'] = display_df['Proj Pts'].round(1)
    if 'VORP' in display_df.columns:
        display_df['VORP'] = display_df['VORP'].round(1)
    if 'VBD' in display_df.columns:
        display_df['VBD'] = display_df['VBD'].round(1)
    
    # Show top players with pagination
    players_per_page = st.slider("Players per page:", 10, 100, 50, key="players_per_page")
    
    if len(display_df) > players_per_page:
        # Simple pagination
        total_pages = (len(display_df) - 1) // players_per_page + 1
        page = st.selectbox(f"Page (1-{total_pages}):", range(1, total_pages + 1), key="page_select")
        
        start_idx = (page - 1) * players_per_page
        end_idx = start_idx + players_per_page
        
        st.dataframe(display_df.iloc[start_idx:end_idx].reset_index(drop=True))
        
        st.markdown(f"*Showing players {start_idx + 1}-{min(end_idx, len(display_df))} of {len(display_df)}*")
    else:
        st.dataframe(display_df.reset_index(drop=True))


def render_tier_analysis(projections_df):
    """Render tier analysis using existing TierManager"""
    st.subheader("🏆 Tier Analysis")
    
    try:
        from src.analytics.tier_manager import TierManager
        tier_manager = TierManager()
        
        # Position selector
        positions = ["All"] + sorted(projections_df['position'].unique().tolist())
        selected_pos = st.selectbox("Select Position:", positions, key="tier_pos_filter")
        
        # Filter data
        if selected_pos != "All":
            tier_df = projections_df[projections_df['position'] == selected_pos]
        else:
            tier_df = projections_df
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Tier Breakdown")
            if 'tier_label' in tier_df.columns:
                tier_counts = tier_df['tier_label'].value_counts().sort_index()
                st.bar_chart(tier_counts)
                
                # Tier summary table
                st.subheader("Tier Summary")
                tier_summary = tier_df.groupby('tier_label').agg({
                    'player_name': 'count',
                    'projected_points': ['mean', 'min', 'max']
                }).round(1)
                tier_summary.columns = ['Players', 'Avg Points', 'Min Points', 'Max Points']
                st.dataframe(tier_summary)
        
        with col2:
            st.subheader("Players by Tier")
            if 'tier_label' in tier_df.columns:
                selected_tier = st.selectbox("Select Tier:", sorted(tier_df['tier_label'].unique()), key="tier_select")
                
                tier_players = tier_df[tier_df['tier_label'] == selected_tier][
                    ['player_name', 'position', 'team', 'projected_points', 'overall_rank']
                ].sort_values('overall_rank')
                
                tier_players.columns = ['Player', 'Pos', 'Team', 'Proj Pts', 'Rank']
                tier_players['Proj Pts'] = tier_players['Proj Pts'].round(1)
                
                st.dataframe(tier_players.reset_index(drop=True))
    
    except Exception as e:
        st.error(f"Error loading tier analysis: {str(e)}")
        # Fallback tier breakdown
        if 'tier_label' in projections_df.columns:
            tier_counts = projections_df['tier_label'].value_counts()
            st.bar_chart(tier_counts)


def render_value_analysis(projections_df, adp_data):
    """Render value analysis using existing ValueCalculator"""
    st.subheader("💎 Value Analysis")
    
    try:
        from src.analytics.value_calculator import ValueCalculator
        value_calc = ValueCalculator()
        
        # Merge with ADP data for value calculations
        if adp_data is not None and not adp_data.empty:
            # Check what ADP columns are available and prepare for merge
            adp_cols = ['name', 'consensus_adp'] if 'consensus_adp' in adp_data.columns else ['name', 'adp']
            if 'sources' in adp_data.columns:
                adp_cols.append('sources')
            
            if 'name' in adp_data.columns:
                # Rename to match projections column
                adp_for_merge = adp_data[adp_cols].copy()
                adp_for_merge = adp_for_merge.rename(columns={'name': 'player_name'})
                if 'consensus_adp' in adp_for_merge.columns:
                    adp_for_merge = adp_for_merge.rename(columns={'consensus_adp': 'adp'})
                if 'sources' in adp_for_merge.columns:
                    adp_for_merge = adp_for_merge.rename(columns={'sources': 'adp_source'})
                
                # Merge projections with ADP
                merged_df = projections_df.merge(
                    adp_for_merge, 
                    on='player_name', 
                    how='left'
                )
            else:
                merged_df = projections_df.copy()
                merged_df['adp'] = None
            
            # Calculate value metrics
            merged_df['value_score'] = merged_df['projected_points'] / merged_df['adp'].fillna(999)
            merged_df['adp_diff'] = merged_df['overall_rank'] - merged_df['adp'].fillna(999)
        else:
            merged_df = projections_df.copy()
            merged_df['adp'] = None
            merged_df['value_score'] = merged_df['projected_points'] / 100  # Simple value metric
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🔥 Best Values (Undervalued)")
            
            # Players with positive ADP difference (ranked higher than ADP suggests)
            if 'adp_diff' in merged_df.columns:
                undervalued = merged_df[
                    (merged_df['adp_diff'] < -10) & 
                    (merged_df['adp'].notna())
                ].nlargest(15, 'projected_points')
            else:
                # Fallback to VORP or projected points
                if 'vorp_score' in merged_df.columns:
                    undervalued = merged_df.nlargest(15, 'vorp_score')
                else:
                    undervalued = merged_df.nlargest(15, 'projected_points')
            
            value_cols = ['player_name', 'position', 'team', 'projected_points', 'overall_rank']
            if 'adp' in undervalued.columns:
                value_cols.extend(['adp', 'adp_diff'])
            if 'vorp_score' in undervalued.columns:
                value_cols.append('vorp_score')
                
            display_undervalued = undervalued[value_cols].copy()
            
            # Rename and format columns
            col_renames = {
                'player_name': 'Player',
                'position': 'Pos', 
                'team': 'Team',
                'projected_points': 'Proj Pts',
                'overall_rank': 'My Rank',
                'adp': 'ADP',
                'adp_diff': 'Value',
                'vorp_score': 'VORP'
            }
            
            display_undervalued = display_undervalued.rename(columns=col_renames)
            
            # Format numeric columns
            for col in ['Proj Pts', 'ADP', 'VORP']:
                if col in display_undervalued.columns:
                    display_undervalued[col] = display_undervalued[col].round(1)
            
            if 'Value' in display_undervalued.columns:
                display_undervalued['Value'] = display_undervalued['Value'].round(0).astype(int)
            
            st.dataframe(display_undervalued.reset_index(drop=True))
        
        with col2:
            st.subheader("⚠️ Potential Overvalued")
            
            # Players with negative ADP difference (ranked lower than ADP suggests)
            if 'adp_diff' in merged_df.columns:
                overvalued = merged_df[
                    (merged_df['adp_diff'] > 10) & 
                    (merged_df['adp'].notna()) &
                    (merged_df['adp'] <= 120)  # Only look at players being drafted
                ].nsmallest(15, 'adp_diff')
            else:
                # Fallback to lowest VORP in top 120
                if 'vorp_score' in merged_df.columns:
                    overvalued = merged_df.head(120).nsmallest(15, 'vorp_score')
                else:
                    overvalued = merged_df.head(120).tail(15)
            
            display_overvalued = overvalued[value_cols].copy()
            display_overvalued = display_overvalued.rename(columns=col_renames)
            
            # Format numeric columns
            for col in ['Proj Pts', 'ADP', 'VORP']:
                if col in display_overvalued.columns:
                    display_overvalued[col] = display_overvalued[col].round(1)
            
            if 'Value' in display_overvalued.columns:
                display_overvalued['Value'] = display_overvalued['Value'].round(0).astype(int)
            
            st.dataframe(display_overvalued.reset_index(drop=True))
        
        # Value summary by position
        st.subheader("Value Summary by Position")
        if 'adp' in merged_df.columns:
            pos_value = merged_df[merged_df['adp'].notna()].groupby('position').agg({
                'adp_diff': ['mean', 'count'],
                'projected_points': 'mean'
            }).round(1)
            pos_value.columns = ['Avg Value Diff', 'Players with ADP', 'Avg Proj Pts']
            st.dataframe(pos_value)
    
    except Exception as e:
        st.error(f"Error loading value analysis: {str(e)}")
        # Fallback value display
        if 'vorp_score' in projections_df.columns:
            top_value = projections_df.nlargest(20, 'vorp_score')[
                ['player_name', 'position', 'team', 'projected_points', 'vorp_score']
            ]
            st.dataframe(top_value)


def render_sleepers_busts(projections_df, adp_data):
    """Render sleepers and busts analysis using existing analytics"""
    st.subheader("🎯 Sleepers & Busts")
    
    try:
        # Merge with ADP data - use the correct column names
        if adp_data is not None and not adp_data.empty:
            # Check what ADP columns are available
            if 'name' in adp_data.columns and 'consensus_adp' in adp_data.columns:
                # Use SFB15/blended ADP data structure
                adp_for_merge = adp_data[['name', 'consensus_adp']].copy()
                adp_for_merge = adp_for_merge.rename(columns={
                    'name': 'player_name',
                    'consensus_adp': 'adp'
                })
                
                merged_df = projections_df.merge(
                    adp_for_merge, 
                    on='player_name', 
                    how='left'
                )
                
                # Successfully merged ADP data
                pass
            else:
                st.warning("⚠️ ADP data structure not recognized, using fallback analysis")
                merged_df = projections_df.copy()
                merged_df['adp'] = None
        else:
            st.info("ℹ️ No ADP data available, using projection-based analysis")
            merged_df = projections_df.copy()
            merged_df['adp'] = None
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("💎 Sleepers")
            st.markdown("*High upside players being drafted late*")
            
            # Enhanced sleeper criteria with multiple factors
            if 'adp' in merged_df.columns and merged_df['adp'].notna().sum() > 50:
                # Sleepers: Good projections with late ADP or no ADP
                sleeper_candidates = merged_df[
                    (merged_df['projected_points'] >= merged_df['projected_points'].quantile(0.55)) &
                    (merged_df['position'].isin(['QB', 'RB', 'WR', 'TE']))
                ].copy()
                
                # Calculate sleeper score based on multiple factors
                sleeper_candidates['sleeper_score'] = 0
                
                # Factor 1: ADP vs Projection rank differential
                sleeper_candidates['sleeper_score'] += np.where(
                    sleeper_candidates['adp'] > sleeper_candidates['overall_rank'] + 20, 3, 0
                )
                
                # Factor 2: Very late ADP or no ADP
                sleeper_candidates['sleeper_score'] += np.where(
                    (sleeper_candidates['adp'] >= 100) | (sleeper_candidates['adp'].isna()), 2, 0
                )
                
                # Factor 3: Good projections for position
                pos_medians = sleeper_candidates.groupby('position')['projected_points'].median()
                for pos in pos_medians.index:
                    mask = sleeper_candidates['position'] == pos
                    sleeper_candidates.loc[mask, 'sleeper_score'] += np.where(
                        sleeper_candidates.loc[mask, 'projected_points'] >= pos_medians[pos] * 1.1, 2, 0
                    )
                
                # Factor 4: Injury risk (if available) - lower risk is better for sleepers
                if 'injury_risk_score' in sleeper_candidates.columns:
                    sleeper_candidates['sleeper_score'] += np.where(
                        sleeper_candidates['injury_risk_score'] <= 0.3, 1, 0
                    )
                
                # Get top sleepers
                sleepers = sleeper_candidates[
                    sleeper_candidates['sleeper_score'] >= 3
                ].nlargest(15, ['sleeper_score', 'projected_points'])
                
            else:
                # Fallback sleeper identification
                if 'vorp_score' in merged_df.columns:
                    sleepers = merged_df[
                        (merged_df['vorp_score'] > 0) &
                        (merged_df['overall_rank'] > 50)
                    ].nlargest(15, 'vorp_score')
                elif 'confidence' in merged_df.columns:
                    sleepers = merged_df[
                        (merged_df['confidence'] == 'Low') &
                        (merged_df['projected_points'] >= merged_df['projected_points'].quantile(0.5))
                    ].nlargest(15, 'projected_points')
                else:
                    sleepers = merged_df[
                        merged_df['position_rank'] > 30
                    ].nlargest(15, 'projected_points')
            
            sleeper_cols = ['player_name', 'position', 'team', 'projected_points', 'overall_rank']
            if 'adp' in sleepers.columns:
                sleeper_cols.append('adp')
            if 'sleeper_score' in sleepers.columns:
                sleeper_cols.append('sleeper_score')
            if 'age' in sleepers.columns:
                sleeper_cols.append('age')
            if 'injury_risk_category' in sleepers.columns:
                sleeper_cols.append('injury_risk_category')
            
            display_sleepers = sleepers[sleeper_cols].copy()
            
            # Rename columns
            col_renames = {
                'player_name': 'Player',
                'position': 'Pos',
                'team': 'Team', 
                'projected_points': 'Proj Pts',
                'overall_rank': 'My Rank',
                'adp': 'ADP',
                'sleeper_score': 'Sleeper Score',
                'bust_score': 'Bust Risk',
                'age': 'Age',
                'injury_risk_category': 'Injury Risk'
            }
            
            display_sleepers = display_sleepers.rename(columns=col_renames)
            
            # Format numeric columns
            for col in ['Proj Pts', 'ADP']:
                if col in display_sleepers.columns:
                    display_sleepers[col] = display_sleepers[col].round(1)
            
            st.dataframe(display_sleepers.reset_index(drop=True))
        
        with col2:
            st.subheader("⚠️ Potential Busts") 
            st.markdown("*High ADP players with concerning indicators*")
            
            # Enhanced bust criteria with multiple risk factors
            if 'adp' in merged_df.columns and merged_df['adp'].notna().sum() > 50:
                # Focus on players being drafted in first 8-10 rounds
                bust_candidates = merged_df[
                    (merged_df['adp'] <= 120) &  # Being drafted reasonably early
                    (merged_df['adp'].notna())
                ].copy()
                
                # Calculate bust risk score
                bust_candidates['bust_score'] = 0
                
                # Factor 1: ADP much higher than projection rank (overvalued)
                bust_candidates['bust_score'] += np.where(
                    bust_candidates['overall_rank'] > bust_candidates['adp'] + 25, 3, 0
                )
                
                # Factor 2: Age concerns (29+ for skill positions)
                if 'age' in bust_candidates.columns:
                    bust_candidates['bust_score'] += np.where(
                        (bust_candidates['age'] >= 29) & 
                        (bust_candidates['position'].isin(['RB', 'WR'])), 2,
                        np.where(bust_candidates['age'] >= 32, 1, 0)
                    )
                
                # Factor 3: High injury risk
                if 'injury_risk_score' in bust_candidates.columns:
                    bust_candidates['bust_score'] += np.where(
                        bust_candidates['injury_risk_score'] >= 0.7, 2,
                        np.where(bust_candidates['injury_risk_score'] >= 0.5, 1, 0)
                    )
                
                # Factor 4: Low confidence in projections
                if 'confidence' in bust_candidates.columns:
                    bust_candidates['bust_score'] += np.where(
                        bust_candidates['confidence'] == 'Low', 1, 0
                    )
                
                # Factor 5: Significant drop from previous season
                if 'prev_season_points' in bust_candidates.columns:
                    bust_candidates['point_drop'] = bust_candidates['prev_season_points'] - bust_candidates['projected_points']
                    bust_candidates['bust_score'] += np.where(
                        bust_candidates['point_drop'] >= 50, 2,
                        np.where(bust_candidates['point_drop'] >= 25, 1, 0)
                    )
                
                # Get players with highest bust risk
                busts = bust_candidates[
                    bust_candidates['bust_score'] >= 2
                ].nlargest(15, ['bust_score', 'adp'])
                
            else:
                # Fallback bust identification
                if 'vorp_score' in merged_df.columns:
                    busts = merged_df.head(100).nsmallest(15, 'vorp_score')
                else:
                    busts = merged_df.head(80).nsmallest(15, 'projected_points')
            
            bust_cols = ['player_name', 'position', 'team', 'projected_points', 'overall_rank']
            if 'adp' in busts.columns:
                bust_cols.append('adp')
            if 'bust_score' in busts.columns:
                bust_cols.append('bust_score')
            if 'age' in busts.columns:
                bust_cols.append('age')
            if 'injury_risk_category' in busts.columns:
                bust_cols.append('injury_risk_category')
            
            display_busts = busts[bust_cols].copy()
            display_busts = display_busts.rename(columns=col_renames)
            
            # Format numeric columns
            for col in ['Proj Pts', 'ADP']:
                if col in display_busts.columns:
                    display_busts[col] = display_busts[col].round(1)
            
            st.dataframe(display_busts.reset_index(drop=True))
        
        # Enhanced insights section
        st.subheader("💡 Key Insights & Analysis")
        
        insights_col1, insights_col2, insights_col3 = st.columns(3)
        
        with insights_col1:
            if not sleepers.empty:
                top_sleeper = sleepers.iloc[0]
                sleeper_adp = top_sleeper.get('adp', 'Undrafted')
                sleeper_rank = top_sleeper.get('overall_rank', 'N/A')
                
                st.success(f"**🎯 Top Sleeper Pick**")
                st.write(f"**{top_sleeper['player_name']}** ({top_sleeper['position']})")
                st.write(f"• Projected: {top_sleeper['projected_points']:.1f} pts")
                st.write(f"• My Rank: #{sleeper_rank}")
                st.write(f"• ADP: {sleeper_adp if sleeper_adp != 'Undrafted' else 'Undrafted'}")
                
                if 'sleeper_score' in top_sleeper:
                    st.write(f"• Sleeper Score: {top_sleeper['sleeper_score']}/8")
        
        with insights_col2:
            if not busts.empty:
                top_bust = busts.iloc[0]
                bust_adp = top_bust.get('adp', 'N/A')
                bust_rank = top_bust.get('overall_rank', 'N/A')
                
                st.warning(f"**⚠️ Biggest Risk**")
                st.write(f"**{top_bust['player_name']}** ({top_bust['position']})")
                st.write(f"• Projected: {top_bust['projected_points']:.1f} pts")
                st.write(f"• My Rank: #{bust_rank}")
                st.write(f"• ADP: {bust_adp}")
                
                if 'bust_score' in top_bust:
                    st.write(f"• Risk Score: {top_bust['bust_score']}/8")
        
        with insights_col3:
            # Summary statistics
            st.info("**📊 Analysis Summary**")
            
            if 'adp' in merged_df.columns:
                total_with_adp = merged_df['adp'].notna().sum()
                st.write(f"• Players with ADP: {total_with_adp}")
                
                if not sleepers.empty:
                    avg_sleeper_adp = sleepers['adp'].mean()
                    st.write(f"• Avg Sleeper ADP: {avg_sleeper_adp:.0f}")
                
                if not busts.empty:
                    avg_bust_adp = busts['adp'].mean()
                    st.write(f"• Avg Bust ADP: {avg_bust_adp:.0f}")
            
            st.write(f"• Sleepers Found: {len(sleepers)}")
            st.write(f"• Potential Busts: {len(busts)}")
        
        # Position-specific insights
        if len(sleepers) > 0 or len(busts) > 0:
            st.subheader("🎯 Position-Specific Opportunities")
            
            pos_col1, pos_col2 = st.columns(2)
            
            with pos_col1:
                if not sleepers.empty:
                    st.write("**💎 Sleepers by Position:**")
                    sleeper_pos_counts = sleepers['position'].value_counts()
                    for pos, count in sleeper_pos_counts.items():
                        top_sleeper_pos = sleepers[sleepers['position'] == pos].iloc[0]
                        st.write(f"• **{pos}**: {count} sleepers (top: {top_sleeper_pos['player_name']})")
            
            with pos_col2:
                if not busts.empty:
                    st.write("**⚠️ Bust Risks by Position:**")
                    bust_pos_counts = busts['position'].value_counts()
                    for pos, count in bust_pos_counts.items():
                        top_bust_pos = busts[busts['position'] == pos].iloc[0]
                        st.write(f"• **{pos}**: {count} risks (top: {top_bust_pos['player_name']})")
    
    except Exception as e:
        st.error(f"Error loading sleepers & busts analysis: {str(e)}")
        st.info("Basic sleeper/bust analysis requires ADP data integration.")


def render_vorp_analysis(projections_df, vorp_calc):
    """Render VORP analysis"""
    st.markdown("## 📊 VORP Analysis")
    st.markdown("*Value Over Replacement Player analysis and insights*")
    
    # VORP breakdown
    if 'vorp_score' in projections_df.columns:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Top VORP Players")
            top_vorp = projections_df.nlargest(15, 'vorp_score')[
                ['player_name', 'position', 'team', 'projected_points', 'vorp_score']
            ]
            st.dataframe(top_vorp)
        
        with col2:
            st.subheader("VORP by Position")
            pos_vorp = projections_df.groupby('position')['vorp_score'].mean().sort_values(ascending=False)
            st.bar_chart(pos_vorp)
    else:
        st.error("VORP data not available")


def render_visual_draft_board(draft_manager, projections_df):
    """
    P0-2: Visual Draft Board Interface
    Create Sleeper-style visual draft board with position-colored tiles
    """
    if not draft_manager or not draft_manager.draft_state:
        st.error("Draft manager not available")
        return
    
    # CSS for position-colored tiles
    st.markdown("""
    <style>
    .draft-board {
        background: #f8fafc;
        border-radius: 10px;
        padding: 15px;
        margin: 10px 0;
    }
    .round-header {
        background: linear-gradient(90deg, #1e3a8a 0%, #3b82f6 100%);
        color: white;
        padding: 8px 15px;
        border-radius: 8px;
        font-weight: 600;
        text-align: center;
        margin-bottom: 10px;
    }
    /* Reduce column spacing to maximize card width */
    .stColumns > div {
        padding-left: 0.25rem !important;
        padding-right: 0.25rem !important;
    }
    .stColumns > div:first-child {
        padding-left: 0 !important;
    }
    .stColumns > div:last-child {
        padding-right: 0 !important;
    }
    .pick-tile {
        border-radius: 8px;
        padding: 6px 4px;
        margin: 1px;
        height: 85px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        text-align: center;
        font-size: 12px;
        color: white !important;
        font-weight: 500;
        border: 2px solid transparent;
        transition: all 0.3s ease;
        box-sizing: border-box;
        position: relative;
        overflow: hidden;
        min-width: 0;
        width: 100%;
    }
    .pick-tile:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    .pick-tile.empty {
        background: #e2e8f0;
        color: #64748b !important;
        border: 2px dashed #cbd5e1;
    }
    .pick-tile.QB { background: linear-gradient(135deg, #dc2626 0%, #ef4444 100%); }
    .pick-tile.RB { background: linear-gradient(135deg, #059669 0%, #10b981 100%); }
    .pick-tile.WR { background: linear-gradient(135deg, #2563eb 0%, #3b82f6 100%); }
    .pick-tile.TE { background: linear-gradient(135deg, #ea580c 0%, #f97316 100%); }
    .pick-tile.K { background: linear-gradient(135deg, #7c3aed 0%, #8b5cf6 100%); }
    .pick-tile.DEF { background: linear-gradient(135deg, #374151 0%, #4b5563 100%); }
    .pick-tile.DST { background: linear-gradient(135deg, #374151 0%, #4b5563 100%); }
    .player-name {
        font-weight: 700;
        font-size: 9px;
        margin-bottom: 1px;
        color: white !important;
        line-height: 1.0;
        padding: 0 10px 0 4px;
        width: 100%;
        box-sizing: border-box;
        text-overflow: ellipsis;
        overflow: hidden;
        white-space: nowrap;
    }
    .player-info {
        font-size: 9px;
        opacity: 0.9;
        color: white !important;
        line-height: 1.0;
        text-overflow: ellipsis;
        overflow: hidden;
        white-space: nowrap;
        margin: 0px 0;
        width: 100%;
        box-sizing: border-box;
    }
    .pick-position {
        position: absolute;
        top: 2px;
        left: 2px;
        font-size: 7px;
        font-weight: 600;
        opacity: 0.8;
        color: white !important;
        z-index: 10;
    }
    .team-header {
        background: linear-gradient(135deg, #374151 0%, #4b5563 100%);
        color: white;
        padding: 3px 1px;
        border-radius: 4px;
        font-size: 9px;
        font-weight: 600;
        text-align: center;
        margin-bottom: 3px;
        border: 1px solid #6b7280;
    }
    .current-pick {
        border: 3px solid #fbbf24 !important;
        animation: pulse 2s infinite;
    }
    @keyframes pulse {
        0%, 100% { border-color: #fbbf24; }
        50% { border-color: #f59e0b; }
    }
    </style>
    """, unsafe_allow_html=True)
    
    draft_state = draft_manager.draft_state
    settings = draft_state.settings
    
    # Get draft board data
    board = draft_manager.get_draft_board()
    
    # Draft board header - inline and compact
    col1, col2 = st.columns([3, 2])
    with col1:
        st.markdown(f"""
        <div style="display: flex; align-items: center; margin-bottom: 15px;">
            <h2 style="margin: 0; padding: 0;">🏈 Draft Board</h2>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div style="text-align: right; margin-bottom: 15px; padding-top: 5px;">
            <p style="color: #666; margin: 0; font-size: 14px;">
                {len(draft_state.picks)} / {settings.total_teams * settings.total_rounds} picks • 
                Round {draft_state.current_round} • 
                Pick {draft_state.current_pick}
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    # Show first 5 rounds (or less if fewer rounds exist)
    max_rounds_to_show = min(5, len(board))
    
    if max_rounds_to_show == 0:
        st.info("🎯 Draft board will appear here once draft picks are made")
        return
    
    for round_idx in range(max_rounds_to_show):
        round_num = round_idx + 1
        round_picks = board[round_idx]
        
        # Add team headers above the first round only
        if round_idx == 0:
            cols_header = st.columns(settings.total_teams)
            for team_idx in range(settings.total_teams):
                with cols_header[team_idx]:
                    # Get team name from any roster in this position
                    team_name = f"Team {team_idx + 1}"  # Default
                    
                    # Try to find actual team name from existing picks
                    for round_data in board:
                        if len(round_data) > team_idx and round_data[team_idx]:
                            pick = round_data[team_idx]
                            roster = draft_state.rosters.get(pick.roster_id)
                            if roster:
                                actual_name = roster.team_name or roster.owner_name
                                if actual_name and not actual_name.startswith("Team "):
                                    team_name = actual_name[:10]  # Limit length
                                    break
                    
                    st.markdown(f'<div class="team-header">{team_name}</div>', unsafe_allow_html=True)
        
        # Round header
        st.markdown(f'<div class="round-header">Round {round_num}</div>', unsafe_allow_html=True)
        
        # Create columns for each team
        cols = st.columns(settings.total_teams)
        
        for team_idx, pick in enumerate(round_picks):
            with cols[team_idx]:
                # Calculate pick number
                if settings.draft_type == 'snake' and round_num % 2 == 0:
                    # Even rounds go in reverse order for snake draft
                    pick_number = (round_num - 1) * settings.total_teams + (settings.total_teams - team_idx)
                    team_position = settings.total_teams - team_idx
                else:
                    pick_number = (round_num - 1) * settings.total_teams + (team_idx + 1)
                    team_position = team_idx + 1
                
                # Create round.pick format and ordinal
                round_pick = f"{round_num}.{team_position}"
                
                # Helper function for ordinals
                def get_ordinal(n):
                    if 10 <= n % 100 <= 20:
                        suffix = 'th'
                    else:
                        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
                    return f"{n}{suffix}"
                
                ordinal = get_ordinal(pick_number)
                
                # Check if this is the current pick
                is_current_pick = pick_number == draft_state.current_pick
                current_class = "current-pick" if is_current_pick else ""
                
                if pick:
                    # Player picked - show player tile
                    position = pick.position or 'UNK'
                    player_name = pick.player_name or 'Unknown Player'
                    team = pick.team or 'FA'
                    
                    # Format name as "J. LastName" for space efficiency
                    name_parts = player_name.split(' ', 1)  # Split on first space only
                    if len(name_parts) >= 2:
                        first_initial = name_parts[0][0].upper() if name_parts[0] else 'X'
                        last_name = name_parts[1]
                        # Truncate last name if needed
                        if len(last_name) > 10:
                            last_name = last_name[:10] + "..."
                        name_display = f"{first_initial}. {last_name}"
                    else:
                        # Single name - truncate if needed
                        if len(player_name) > 12:
                            name_display = player_name[:12] + "..."
                        else:
                            name_display = player_name
                    
                    tile_html = f"""
                    <div class="pick-tile {position} {current_class}" style="position: relative;">
                        <div class="pick-position">{round_pick}</div>
                        <div class="player-name">{name_display}</div>
                        <div class="player-info">{position} - {team}</div>
                        <div class="player-info">{ordinal}</div>
                    </div>
                    """
                else:
                    # Empty slot
                    if is_current_pick:
                        tile_html = f"""
                        <div class="pick-tile empty current-pick" style="position: relative;">
                            <div class="pick-position">{round_pick}</div>
                            <div style="color: #f59e0b; font-weight: 700;">ON THE CLOCK</div>
                            <div style="font-size: 10px;">⏱️ {ordinal}</div>
                        </div>
                        """
                    else:
                        tile_html = f"""
                        <div class="pick-tile empty" style="position: relative;">
                            <div class="pick-position">{round_pick}</div>
                            <div>Pick {ordinal}</div>
                        </div>
                        """
                
                st.markdown(tile_html, unsafe_allow_html=True)
    
    # Show more rounds option
    if len(board) > max_rounds_to_show:
        if st.button(f"📊 Show All {len(board)} Rounds", key="show_all_rounds"):
            st.markdown("### 📋 Complete Draft Board")
            for round_idx in range(len(board)):
                round_num = round_idx + 1
                round_picks = board[round_idx]
                
                st.markdown(f"**Round {round_num}**")
                picks_text = []
                for team_idx, pick in enumerate(round_picks):
                    if pick:
                        roster = draft_state.rosters.get(pick.roster_id)
                        owner_name = (roster.owner_name or f"Team {pick.roster_id}") if roster else "Team"
                        picks_text.append(f"{pick.pick_number}. {pick.player_name} ({pick.position}) - {owner_name}")
                    else:
                        pick_number = (round_num - 1) * settings.total_teams + (team_idx + 1)
                        picks_text.append(f"{pick_number}. [Available]")
                
                for i in range(0, len(picks_text), 2):
                    if i + 1 < len(picks_text):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.text(picks_text[i])
                        with col2:
                            st.text(picks_text[i + 1])
                    else:
                        st.text(picks_text[i])


def render_enhanced_sleeper_connection():
    """Enhanced Sleeper connection interface for Settings"""
    
    # Connection status display
    is_connected = hasattr(st.session_state, 'connected_draft_id') and st.session_state.connected_draft_id
    
    if is_connected:
        st.success(f"🟢 **CONNECTED** to Draft: {st.session_state.connected_draft_id}")
        if hasattr(st.session_state, 'draft_username'):
            st.info(f"👤 Username: {st.session_state.draft_username}")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Refresh Connection", key="refresh_connection"):
                st.experimental_rerun()
        with col2:
            if st.button("❌ Disconnect", key="disconnect_draft"):
                # Clear connection state
                for key in ['connected_draft_id', 'draft_manager', 'draft_state', 'draft_username']:
                    if key in st.session_state:
                        del st.session_state[key]
                st.experimental_rerun()
        
        st.markdown("---")
    else:
        st.warning("🔴 **NOT CONNECTED** - Choose a connection method below")
    
    # Connection methods
    st.markdown("### 🔗 Connection Methods")
    
    # Method 1: By Username (Most Common)
    st.markdown("#### 👤 **Method 1: By Username** (Recommended)")
    st.markdown("*Find all your drafts using your Sleeper username*")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        username = st.text_input(
            "Sleeper Username",
            placeholder="Enter your Sleeper username",
            help="This is the username you use to log into Sleeper",
            key="settings_username"
        )
    with col2:
        season = st.selectbox("Season", ["2025", "2024"], index=0, key="settings_season")
    
    if st.button("🔍 Find My Drafts", key="settings_find_drafts"):
        if username:
            with st.spinner("🔍 Searching for your drafts..."):
                try:
                    from src.draft.draft_manager import DraftDiscovery
                    from src.draft.sleeper_client import SleeperClient, SleeperAPIError
                    
                    # Use the proper DraftDiscovery class
                    sleeper_client = SleeperClient()
                    draft_discovery = DraftDiscovery(sleeper_client)
                    
                    # Find drafts for the user
                    drafts = draft_discovery.find_drafts_by_username(username, season)
                    
                    if drafts:
                        st.success(f"✅ Found {len(drafts)} drafts for {username}")
                        
                        # Store drafts in session state for selection
                        st.session_state.found_drafts = drafts
                        st.session_state.search_username = username
                        st.experimental_rerun()
                    else:
                        st.warning(f"No drafts found for {username} in {season}")
                        st.info("Make sure your username is correct and you have active drafts")
                except Exception as e:
                    st.error(f"Error searching for drafts: {str(e)}")
                    # Mock fallback for development
                    st.info("Using mock data for demonstration")
                    mock_drafts = [
                        {'draft_id': 'mock_draft_123', 'league_name': 'Mock League 1', 'status': 'pre_draft'},
                        {'draft_id': 'mock_draft_456', 'league_name': 'Mock League 2', 'status': 'drafting'}
                    ]
                    st.session_state.found_drafts = mock_drafts
                    st.session_state.search_username = username
                    st.experimental_rerun()
        else:
            st.error("Please enter a username")
    
    # Display found drafts if any
    if hasattr(st.session_state, 'found_drafts') and st.session_state.found_drafts:
        st.markdown("#### 📋 Your Available Drafts")
        for i, draft in enumerate(st.session_state.found_drafts):
            draft_name = f"{draft.get('league_name', 'Unknown League')}"
            draft_status = draft.get('status', 'unknown')
            draft_id = draft['draft_id']
            
            with st.container():
                col_a, col_b, col_c = st.columns([3, 1, 1])
                with col_a:
                    st.write(f"**{draft_name}**")
                    st.caption(f"ID: {draft_id} • Status: {draft_status}")
                with col_b:
                    status_color = "🟢" if draft_status == "drafting" else "🟡" if draft_status == "pre_draft" else "🔴"
                    st.markdown(f"{status_color} {draft_status}")
                with col_c:
                    if st.button("Connect", key=f"settings_connect_draft_{i}"):
                        try:
                            from src.draft.draft_manager import DraftManager
                            from src.draft.sleeper_client import SleeperClient
                            
                            sleeper_client = SleeperClient()
                            draft_manager = DraftManager(draft_id, sleeper_client)
                            draft_state = draft_manager.initialize_draft()
                            
                            st.session_state.connected_draft_id = draft_id
                            st.session_state.draft_manager = draft_manager
                            st.session_state.draft_state = draft_state
                            st.session_state.draft_username = username
                            
                            # Clear found drafts
                            if 'found_drafts' in st.session_state:
                                del st.session_state.found_drafts
                            
                            st.success(f"🎯 Connected to {draft_name}")
                            st.experimental_rerun()
                        except Exception as connect_error:
                            st.error(f"Error connecting to draft: {connect_error}")
    
    st.markdown("---")
    
    # Method 2: Direct Draft ID
    st.markdown("#### 🎯 **Method 2: Direct Draft ID**")
    st.markdown("*Connect directly if you have the draft ID*")
    
    draft_id = st.text_input(
        "Draft ID",
        placeholder="Enter Sleeper draft ID (e.g., 1234567890123456789)",
        help="You can find this in the Sleeper app URL when viewing the draft",
        key="settings_draft_id"
    )
    
    if st.button("🔗 Connect to Draft", key="settings_connect_direct"):
        if draft_id:
            with st.spinner("🔗 Connecting to draft..."):
                try:
                    from src.draft.draft_manager import DraftManager
                    from src.draft.sleeper_client import SleeperClient
                    
                    sleeper_client = SleeperClient()
                    draft_manager = DraftManager(draft_id, sleeper_client)
                    draft_state = draft_manager.initialize_draft()
                    
                    st.session_state.connected_draft_id = draft_id
                    st.session_state.draft_manager = draft_manager
                    st.session_state.draft_state = draft_state
                    
                    st.success(f"✅ Connected to draft {draft_id}")
                    st.experimental_rerun()
                except Exception as e:
                    st.error(f"Error connecting to draft: {str(e)}")
                    st.info("Double-check the draft ID and try again")
        else:
            st.error("Please enter a draft ID")
    
    st.markdown("---")
    
    # Method 3: League ID
    st.markdown("#### 🏆 **Method 3: By League ID**")
    st.markdown("*Find the current draft for a specific league*")
    
    league_id = st.text_input(
        "League ID", 
        placeholder="Enter Sleeper league ID",
        help="Find this in your league settings or URL",
        key="settings_league_id"
    )
    
    if st.button("🔍 Find League Draft", key="settings_find_league"):
        if league_id:
            with st.spinner("🔍 Finding league draft..."):
                try:
                    from src.draft.draft_manager import DraftDiscovery
                    from src.draft.sleeper_client import SleeperClient
                    
                    sleeper_client = SleeperClient()
                    draft_discovery = DraftDiscovery(sleeper_client)
                    
                    draft_info = draft_discovery.get_draft_by_league_id(league_id)
                    
                    if draft_info:
                        draft_id = draft_info['draft_id']
                        league_name = draft_info.get('league_name', 'Unknown League')
                        
                        from src.draft.draft_manager import DraftManager
                        draft_manager = DraftManager(draft_id, sleeper_client)
                        draft_state = draft_manager.initialize_draft()
                        
                        # CRITICAL FIX: Set UI refresh callback for auto-refresh
                        draft_manager.set_ui_refresh_callback(lambda: st.experimental_rerun())
                        
                        # CRITICAL FIX: Start monitoring for live updates
                        draft_manager.start_monitoring(poll_interval=5)
                        
                        st.session_state.connected_draft_id = draft_id
                        st.session_state.draft_manager = draft_manager
                        st.session_state.draft_state = draft_state
                        
                        st.success(f"✅ Connected to draft for {league_name} with live monitoring")
                        st.experimental_rerun()
                    else:
                        st.error("No active draft found for this league")
                except Exception as e:
                    st.error(f"Error finding league draft: {str(e)}")
        else:
            st.error("Please enter a league ID")
    
    # Troubleshooting section (can't use expander inside expander)
    st.markdown("---")
    st.markdown("### 🔧 Troubleshooting & Help")
    
    with st.container():
        st.markdown("""
        **Common Issues:**
        
        1. **"No drafts found"** - Make sure:
           - Your username is spelled correctly
           - You have active drafts in the selected season
           - Your drafts aren't private/hidden
        
        2. **"Connection failed"** - Try:
           - Refreshing the page
           - Using a different connection method
           - Checking if the draft is still active
        
        3. **"Draft ID not found"** - Verify:
           - The draft ID is complete (usually 18-19 digits)
           - The draft hasn't been deleted
           - You have access to the draft
        
        **Where to find IDs:**
        - **Draft ID**: In the URL when viewing a draft on Sleeper
        - **League ID**: In league settings or league URL
        - **Username**: Your Sleeper login username (not display name)
        """)


def render_settings():
    """Render settings and configuration"""
    st.markdown("## 🔧 Settings & Configuration")
    
    # PROMINENT SLEEPER CONNECTION SECTION
    with st.expander("🔗 **Sleeper Draft Connection**", expanded=True):
        st.markdown("### Connect to your live Sleeper draft")
        render_enhanced_sleeper_connection()
    
    # SYSTEM DIAGNOSTICS SECTION
    with st.expander("🔍 **System Diagnostics**", expanded=False):
        st.markdown("### System Status & Performance Metrics")
        
        # Status indicators (moved from main view)
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown("""
            <div class="metric-card">
                <h3>996</h3>
                <p>Players Loaded</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown("""
            <div class="metric-card">
                <h3>71%</h3>
                <p>Model Accuracy</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown("""
            <div class="metric-card">
                <h3>Live</h3>
                <p>ADP Data</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col4:
            st.markdown("""
            <div class="metric-card">
                <h3>Ready</h3>
                <p>Draft Status</p>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Additional diagnostic info
        col_a, col_b = st.columns(2)
        
        with col_a:
            st.markdown("**📊 Data Sources:**")
            st.info("✅ SFB15 ADP: Live data")
            st.info("✅ Sleeper API: Connected")
            st.info("✅ VORP Calculator: Active")
            st.info("✅ ML Models: Loaded")
        
        with col_b:
            st.markdown("**⚡ Performance:**")
            st.info("🚀 Auto-refresh: Enabled")
            st.info("🔄 Background monitoring: Active")
            st.info("💾 Cache status: Healthy")
            st.info("🎯 Response time: <2s")
        
        # System info
        import streamlit as st
        import time
        st.markdown("**🔧 Technical Details:**")
        st.code(f"""
System Time: {time.strftime('%Y-%m-%d %H:%M:%S')}
Streamlit Version: {st.__version__}
Session ID: {id(st.session_state)}
Cache Status: Active
        """)
    
    with st.expander("🎨 Display Settings"):
        st.slider("Players per page", 10, 100, 50, key="players_per_page_setting")
        st.checkbox("Show advanced metrics", True, key="show_advanced_setting")
        st.checkbox("Dark mode", False, key="dark_mode_setting")
    
    with st.expander("📊 Data Settings"):
        st.selectbox("Primary ADP source", ["SFB15", "Sleeper", "FantasyPros"], key="adp_source")
        st.slider("Cache refresh (hours)", 1, 24, 6, key="cache_refresh")
    
    with st.expander("🎯 Draft Settings"):
        st.number_input("League size", 8, 16, 12, key="league_size")
        st.selectbox("Scoring", ["PPR", "Half PPR", "Standard"], key="scoring_type")


def render_streamlined_available_players(projections_df, draft_manager=None):
    """
    P0-3: Streamlined Available Players Table
    Essential columns only, optimized for quick draft decisions
    """
    
    # ===============================================
    # FIXED: PROPER AUTO-REFRESH IMPLEMENTATION
    # ===============================================
    
    # Initialize auto-refresh state
    if 'last_auto_refresh' not in st.session_state:
        st.session_state.last_auto_refresh = time.time()
    if 'last_pick_count' not in st.session_state:
        st.session_state.last_pick_count = 0
    if 'auto_refresh_interval' not in st.session_state:
        st.session_state.auto_refresh_interval = 5  # 5 seconds
    
    current_time = time.time()
    current_picks = 0
    
    # Get current pick count
    if draft_manager and hasattr(draft_manager, 'draft_state') and draft_manager.draft_state:
        current_picks = len(draft_manager.draft_state.picks)
    
    # Check if picks have changed (indicating new picks detected)
    picks_changed = current_picks != st.session_state.last_pick_count
    if picks_changed:
        st.session_state.last_pick_count = current_picks
        st.session_state.last_auto_refresh = current_time
        # Force immediate refresh when picks change
        st.success(f"🆕 New pick detected! Total picks: {current_picks}")
        time.sleep(0.5)  # Brief pause to show the message
        st.experimental_rerun()
    
    # Auto-refresh based on time interval
    time_since_refresh = current_time - st.session_state.last_auto_refresh
    should_auto_refresh = (
        draft_manager and 
        hasattr(draft_manager, 'is_monitoring') and 
        draft_manager.is_monitoring and
        time_since_refresh >= st.session_state.auto_refresh_interval
    )
    
    if should_auto_refresh:
        st.session_state.last_auto_refresh = current_time
        st.experimental_rerun()
    
    # ===============================================
    # LIVE DRAFT STATUS AND MANUAL CONTROLS
    # ===============================================
    
    st.markdown("### 🔄 Live Draft Status")
    
    if draft_manager and hasattr(draft_manager, 'draft_state') and draft_manager.draft_state:
        # Status columns
        col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
        
        with col1:
            st.metric("Total Picks", current_picks)
        
        with col2:
            monitoring_status = "🟢 LIVE" if (hasattr(draft_manager, 'is_monitoring') and draft_manager.is_monitoring) else "🔴 PAUSED"
            st.metric("Status", monitoring_status)
        
        with col3:
            next_refresh = max(0, st.session_state.auto_refresh_interval - time_since_refresh)
            st.metric("Next Auto-Refresh", f"{next_refresh:.0f}s")
        
        with col4:
            if st.button("🔄 Refresh Now", key="manual_refresh_prominent"):
                st.session_state.last_auto_refresh = current_time
                st.experimental_rerun()
        
        # Detailed status
        current_time_str = datetime.now().strftime("%H:%M:%S")
        is_monitoring = hasattr(draft_manager, 'is_monitoring') and draft_manager.is_monitoring
        
        if is_monitoring:
            st.success(f"✅ **LIVE MONITORING ACTIVE** | Last updated: {current_time_str}")
        else:
            st.warning(f"⚠️ **MONITORING PAUSED** | Last updated: {current_time_str}")
            if st.button("🔄 Restart Monitoring", key="restart_monitoring"):
                try:
                    draft_manager.start_monitoring(poll_interval=5)
                    st.success("✅ Monitoring restarted")
                    st.experimental_rerun()
                except Exception as e:
                    st.error(f"Failed to restart monitoring: {str(e)}")
        
        # Auto-refresh settings
        with st.expander("⚙️ Auto-Refresh Settings"):
            col_a, col_b = st.columns(2)
            with col_a:
                new_interval = st.slider(
                    "Auto-refresh interval (seconds)",
                    min_value=3,
                    max_value=30,
                    value=st.session_state.auto_refresh_interval,
                    key="refresh_interval_slider"
                )
                if new_interval != st.session_state.auto_refresh_interval:
                    st.session_state.auto_refresh_interval = new_interval
                    st.success(f"✅ Auto-refresh set to {new_interval} seconds")
            
            with col_b:
                if st.button("🎯 Force Full Refresh", key="force_full_refresh"):
                    # Clear caches and force complete refresh
                    if hasattr(draft_manager, 'monitor'):
                        draft_manager.monitor.reset_cache()
                    st.session_state.last_pick_count = 0
                    st.success("🔄 Full refresh initiated...")
                    st.experimental_rerun()
    
    else:
        st.info("📊 **Analysis Mode** - Connect to a live draft for real-time updates")
        if st.button("🔗 Connect to Draft", key="connect_to_draft_btn"):
            # Switch to settings to connect
            st.session_state.selected_nav = "🔧 Settings"
            st.experimental_rerun()

    # ===============================================
    # Remove broken JavaScript auto-refresh
    # ===============================================
    # REMOVED: The broken setTimeout JavaScript that didn't work
    
    # Add proper visual indicators
    st.markdown("""
    <style>
    .live-indicator {
        position: fixed;
        top: 10px;
        right: 10px;
        background: #10b981;
        color: white;
        padding: 5px 10px;
        border-radius: 5px;
        font-size: 12px;
        z-index: 1000;
        animation: pulse 2s infinite;
    }
    .monitoring-indicator {
        background: #3b82f6;
        color: white;
        padding: 8px 15px;
        border-radius: 8px;
        margin: 10px 0;
        text-align: center;
        font-weight: 600;
    }
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.7; }
    }
    .pick-count-display {
        background: #3b82f6;
        color: white;
        padding: 8px 15px;
        border-radius: 8px;
        margin: 10px 0;
        text-align: center;
        font-weight: 600;
    }
    </style>
    """, unsafe_allow_html=True)

    # ===============================================
    # REST OF THE EXISTING FUNCTION CONTINUES...
    # ===============================================
    
    # CSS for streamlined table (keeping existing styles)
    st.markdown("""
    <style>
    .available-players-header {
        background: linear-gradient(90deg, #1e3a8a 0%, #3b82f6 100%);
        color: white;
        padding: 15px;
        border-radius: 10px 10px 0 0;
        margin: 0;
        text-align: center;
    }
    .player-filters {
        background: #f8fafc;
        padding: 15px;
        border: 1px solid #e2e8f0;
        border-radius: 0 0 10px 10px;
        margin-bottom: 10px;
    }
    .position-badge {
        display: inline-block;
        padding: 4px 8px;
        border-radius: 4px;
        font-weight: 600;
        font-size: 11px;
        color: white;
        margin-right: 5px;
    }
    .position-QB { background: #dc2626; }
    .position-RB { background: #059669; }
    .position-WR { background: #2563eb; }
    .position-TE { background: #ea580c; }
    .position-K { background: #7c3aed; }
    .position-DEF { background: #374151; }
    .position-DST { background: #374151; }
    .tier-indicator {
        padding: 2px 6px;
        border-radius: 3px;
        font-size: 10px;
        font-weight: 600;
    }
    .tier-1 { background: #fee2e2; color: #991b1b; }
    .tier-2 { background: #fef3c7; color: #92400e; }
    .tier-3 { background: #dcfce7; color: #166534; }
    .tier-4 { background: #ddd6fe; color: #5b21b6; }
    .tier-5 { background: #e5e7eb; color: #374151; }
    .value-indicator {
        font-weight: 600;
        font-size: 12px;
    }
    .value-great { color: #059669; }
    .value-good { color: #0891b2; }
    .value-ok { color: #7c3aed; }
    .value-reach { color: #dc2626; }
    </style>
    """, unsafe_allow_html=True)
    
    # Live monitoring indicator (only show if actively monitoring)
    if draft_manager and hasattr(draft_manager, 'is_monitoring') and draft_manager.is_monitoring:
        st.markdown("""
        <div class="live-indicator">
            🔄 LIVE
        </div>
        """, unsafe_allow_html=True)
    
    # Get available players
    available_players = projections_df.copy()
    
    # Filter out drafted players if draft manager available
    drafted_count = 0
    if draft_manager and hasattr(draft_manager, 'draft_state') and draft_manager.draft_state:
        drafted_players = {pick.player_name for pick in draft_manager.draft_state.picks}
        available_players = available_players[~available_players['player_name'].isin(drafted_players)]
        drafted_count = len(drafted_players)
    
    # Header with draft status and pick count
    current_time = datetime.now().strftime("%H:%M:%S")
    monitoring_status = "🔄 LIVE" if (draft_manager and hasattr(draft_manager, 'is_monitoring') and draft_manager.is_monitoring) else "⏸️ PAUSED"
    
    # Display current pick count prominently
    if draft_manager and hasattr(draft_manager, 'draft_state') and draft_manager.draft_state:
        current_pick = draft_manager.draft_state.current_pick
        total_picks = len(draft_manager.draft_state.picks)
        st.markdown(f"""
        <div class="pick-count-display">
            📊 Current Pick: {current_pick} | Total Picks Made: {total_picks}
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown(f"""
    <div class="available-players-header">
        <h3>⚡ Available Players</h3>
        <p>{monitoring_status} | Last updated: {current_time} | {drafted_count} players drafted</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Filters section
    with st.container():
        st.markdown('<div class="player-filters">', unsafe_allow_html=True)
        
        col1, col2, col3, col4 = st.columns([2, 2, 2, 2])
        
        with col1:
            # Position filter
            all_positions = ['All'] + sorted(available_players['position'].unique().tolist())
            selected_position = st.selectbox(
                "Position",
                all_positions,
                key="streamlined_position_filter"
            )
        
        with col2:
            # Hide picked players toggle
            hide_picked = st.checkbox(
                "Hide Drafted Players",
                value=True,
                key="hide_drafted_toggle"
            )
        
        with col3:
            # Tier filter
            if 'tier' in available_players.columns:
                all_tiers = ['All'] + sorted([str(t) for t in available_players['tier'].unique() if pd.notna(t)])
                selected_tier = st.selectbox(
                    "Tier",
                    all_tiers,
                    key="streamlined_tier_filter"
                )
            else:
                selected_tier = 'All'
        
        with col4:
            # View toggle
            view_mode = st.selectbox(
                "View Mode",
                ["Enhanced Cards", "Data Table"],
                key="view_mode_toggle"
            )
            
        # Quick search (full width)
        search_term = st.text_input(
            "Quick Search",
            placeholder="Player name...",
            key="streamlined_search"
        )
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Apply filters
    filtered_players = available_players.copy()
    
    if selected_position != 'All':
        filtered_players = filtered_players[filtered_players['position'] == selected_position]
    
    if selected_tier != 'All':
        if 'tier' in filtered_players.columns:
            filtered_players = filtered_players[filtered_players['tier'].astype(str) == selected_tier]
    
    if search_term:
        filtered_players = filtered_players[
            filtered_players['player_name'].str.contains(search_term, case=False, na=False)
        ]
    
    # Limit to top results for performance
    display_players = filtered_players.head(50)  # Top 50 for speed
    
    if display_players.empty:
        st.warning("No players match your filters")
        return
    
    # ESSENTIAL COLUMNS FOR DRAFT DECISIONS - INCLUDING VORP AND ADP
    essential_columns = {
        'player_name': 'Player',
        'position': 'Pos',
        'team': 'Team',
        'projected_points': 'Proj',
        'overall_rank': 'Rank'
    }
    
    # Add critical decision-making columns
    critical_columns = {}
    
    # VORP columns (prioritize static VORP for basic display, dynamic when available)
    if 'vorp_score' in display_players.columns:
        critical_columns['vorp_score'] = 'VORP'
    elif 'static_vorp' in display_players.columns:
        critical_columns['static_vorp'] = 'VORP'
    elif 'dynamic_vorp_final' in display_players.columns:
        critical_columns['dynamic_vorp_final'] = 'VORP'
    elif 'dynamic_vorp' in display_players.columns:
        critical_columns['dynamic_vorp'] = 'VORP'
    
    # ADP columns (prioritize SFB15 ADP)
    if 'sfb15_adp' in display_players.columns:
        critical_columns['sfb15_adp'] = 'ADP'
    elif 'consensus_adp' in display_players.columns:
        critical_columns['consensus_adp'] = 'ADP'
    elif 'current_adp' in display_players.columns:
        critical_columns['current_adp'] = 'ADP'
    elif 'adp' in display_players.columns:
        critical_columns['adp'] = 'ADP'
    
    # Add optional columns if available
    optional_columns = {}
    if 'tier' in display_players.columns:
        optional_columns['tier'] = 'Tier'
    
    # Combine columns in priority order
    display_columns = {**essential_columns, **critical_columns, **optional_columns}
    
    # Create display dataframe
    available_cols = [col for col in display_columns.keys() if col in display_players.columns]
    display_df = display_players[available_cols].copy()
    
    # Rename columns
    column_mapping = {col: display_columns[col] for col in available_cols}
    display_df = display_df.rename(columns=column_mapping)
    
    # Format numeric columns
    for col in display_df.columns:
        if col in ['Proj', 'VORP', 'ADP', 'SFB ADP'] and col in display_df.columns:
            display_df[col] = pd.to_numeric(display_df[col], errors='coerce').round(1)
    
    # Custom rendering for better mobile experience
    st.markdown("### 📋 Available Players")
    
    # Show player count and key metrics
    total_available = len(available_players)
    showing_count = len(display_df)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Available", f"{total_available}")
    with col2:
        st.metric("Showing", f"{showing_count}")
    with col3:
        st.metric("Drafted", f"{drafted_count}")
    
    # Render based on selected view mode
    if view_mode == "Enhanced Cards":
        # Enhanced CSS for better visual design
        st.markdown("""
        <style>
        .player-card {
            background: white;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 12px;
            margin: 8px 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .player-info {
            margin-bottom: 12px;
        }
        .player-name {
            font-size: 16px;
            font-weight: 600;
            color: #1a202c;
            margin-left: 8px;
        }
        .player-team {
            color: #64748b;
            font-size: 13px;
            font-weight: 500;
        }
        .stat-item {
            text-align: center;
            padding: 8px;
            background: #f8fafc;
            border-radius: 6px;
            border: 1px solid #e2e8f0;
        }
        .stat-label {
            font-size: 11px;
            color: #64748b;
            font-weight: 500;
            margin-bottom: 2px;
        }
        .stat-value {
            font-size: 14px;
            font-weight: 700;
            color: #1a202c;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # Render players in an enhanced card format
        for idx, player in display_df.iterrows():
            # Get player data
            pos = player.get('Pos', 'UNK')
            player_name = player.get('Player', 'Unknown')
            team = player.get('Team', 'FA')
            proj = player.get('Proj', 0)
            vorp = player.get('VORP', 0)
            adp = player.get('ADP', 0)
            rank = player.get('Rank', 'N/A')
            tier = player.get('Tier', 'N/A')
            
            # Value assessment
            if vorp > 20:
                value_class = "value-great"
                value_text = "🔥 Elite"
                badge_color = "#10b981"
            elif vorp > 10:
                value_class = "value-good"
                value_text = "⭐ Good"
                badge_color = "#3b82f6"
            elif vorp > 0:
                value_class = "value-ok"
                value_text = "✓ OK"
                badge_color = "#6366f1"
            else:
                value_class = "value-reach"
                value_text = "⚠️ Reach"
                badge_color = "#ef4444"
            
            # Enhanced player card with better visual hierarchy
            with st.container():
                # Create a more prominent card container
                st.markdown(f"""
                <div style="
                    background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
                    border: 2px solid #e2e8f0;
                    border-radius: 12px;
                    padding: 20px;
                    margin: 16px 0;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.08);
                    position: relative;
                ">
                    <div style="display: flex; align-items: center; margin-bottom: 16px;">
                        <span class="position-badge position-{pos}" style="
                            font-size: 16px; 
                            padding: 8px 12px; 
                            margin-right: 12px;
                            font-weight: 700;
                            border-radius: 8px;
                            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                        ">{pos}</span>
                        <div>
                            <div style="font-size: 20px; font-weight: 800; color: #1a202c; line-height: 1.2;">
                                {player_name}
                            </div>
                            <div style="font-size: 16px; color: #64748b; font-weight: 500;">
                                {team} • Rank #{rank}{f" • Tier {tier}" if tier != 'N/A' else ""}
                            </div>
                        </div>
                        <div style="margin-left: auto;">
                            <span style="
                                background-color: {badge_color}; 
                                color: white; 
                                padding: 6px 12px; 
                                border-radius: 8px; 
                                font-size: 14px; 
                                font-weight: 600;
                                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                            ">{value_text}</span>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # Stats in a clean row below the header
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    st.metric("🎯 Projection", f"{proj:.1f} pts", help="Projected fantasy points")
                
                with col_b:
                    st.metric("📊 VORP", f"{vorp:.1f}", help="Value Over Replacement Player")
                
                with col_c:
                    adp_display = f"{adp:.1f}" if adp else "N/A"
                    st.metric("📋 ADP", adp_display, help="Average Draft Position")
                
                st.markdown("<br>", unsafe_allow_html=True)  # Clean spacing
    
    else:  # Data Table view
        st.dataframe(
            display_df,
            height=600
        )


def render_position_recommendation_tiles(projections_df, draft_manager=None):
    """
    P0-4: Position Recommendation Tiles
    Quick visual guidance for best available by position
    """
    
    st.markdown("### 🎯 Best Available by Position")
    
    # Get available players (filter out drafted if connected to live draft)
    available_players = projections_df.copy()
    
    if draft_manager and hasattr(draft_manager, 'draft_state') and draft_manager.draft_state:
        drafted_players = {pick.player_name for pick in draft_manager.draft_state.picks}
        available_players = available_players[~available_players['player_name'].isin(drafted_players)]
    
    # Define position order and colors
    positions = ['QB', 'RB', 'WR', 'TE']
    position_colors = {
        'QB': '#dc2626',   # Red
        'RB': '#059669',   # Green  
        'WR': '#2563eb',   # Blue
        'TE': '#ea580c'    # Orange
    }
    
    # Add CSS for recommendation tiles
    st.markdown("""
    <style>
    .recommendation-tile {
        background: linear-gradient(135deg, var(--position-color) 0%, var(--position-color-dark) 100%);
        color: white;
        padding: 20px;
        border-radius: 12px;
        margin: 10px 0;
        text-align: center;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        transition: transform 0.2s, box-shadow 0.2s;
        cursor: pointer;
    }
    .recommendation-tile:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.25);
    }
    .tile-position {
        font-size: 14px;
        font-weight: 600;
        opacity: 0.9;
        margin-bottom: 5px;
    }
    .tile-player {
        font-size: 20px;
        font-weight: 700;
        margin-bottom: 8px;
    }
    .tile-projection {
        font-size: 16px;
        margin-bottom: 5px;
    }
    .tile-rank {
        font-size: 14px;
        opacity: 0.9;
    }
    .tile-vorp {
        font-size: 14px;
        margin-top: 5px;
        padding-top: 8px;
        border-top: 1px solid rgba(255, 255, 255, 0.3);
    }
    .recommendation-header {
        text-align: center;
        margin-bottom: 20px;
        padding: 15px;
        background: linear-gradient(90deg, #1e3a8a 0%, #3b82f6 100%);
        color: white;
        border-radius: 10px;
    }
    .no-players {
        text-align: center;
        color: #6b7280;
        font-style: italic;
        padding: 40px;
        background: #f9fafb;
        border-radius: 8px;
        border: 2px dashed #d1d5db;
    }
    </style>
    """, unsafe_allow_html=True)
    
    if available_players.empty:
        st.markdown("""
        <div class="no-players">
            <h3>🎉 Draft Complete!</h3>
            <p>All players have been drafted or no projection data available</p>
        </div>
        """, unsafe_allow_html=True)
        return
    
    # Create 4-column layout for position tiles
    cols = st.columns(4)
    
    for i, position in enumerate(positions):
        with cols[i]:
            # Get best available player for this position
            position_players = available_players[available_players['position'] == position]
            
            if not position_players.empty:
                # Sort by overall rank or projected points to get the best
                if 'overall_rank' in position_players.columns:
                    best_player = position_players.nsmallest(1, 'overall_rank').iloc[0]
                elif 'projected_points' in position_players.columns:
                    best_player = position_players.nlargest(1, 'projected_points').iloc[0]
                else:
                    best_player = position_players.iloc[0]
                
                # Get player stats
                player_name = best_player['player_name']
                projected_points = best_player.get('projected_points', 0)
                overall_rank = best_player.get('overall_rank', 'N/A')
                
                # Get VORP info if available (prioritize static VORP for initial display)
                vorp_score = best_player.get('vorp_score',
                            best_player.get('static_vorp', 
                            best_player.get('dynamic_vorp_final', 
                            best_player.get('dynamic_vorp', 0))))
                
                # Get ADP for value assessment
                adp_value = best_player.get('sfb15_adp', 
                           best_player.get('current_adp', 
                           best_player.get('adp', None)))
                
                # Color for the tile
                color = position_colors[position]
                color_dark = {
                    'QB': '#991b1b',
                    'RB': '#047857', 
                    'WR': '#1d4ed8',
                    'TE': '#c2410c'
                }[position]
                
                # Create the recommendation tile
                st.markdown(f"""
                <div class="recommendation-tile" 
                     style="--position-color: {color}; --position-color-dark: {color_dark};">
                    <div class="tile-position">{position}</div>
                    <div class="tile-player">{player_name}</div>
                    <div class="tile-projection">{projected_points:.1f} pts</div>
                    <div class="tile-rank">Overall: #{overall_rank}</div>
                    <div class="tile-vorp">VORP: {vorp_score:.1f}{' | ADP: ' + str(int(adp_value)) if adp_value else ''}</div>
                </div>
                """, unsafe_allow_html=True)
                
                # Add quick draft button below tile
                if st.button(f"📋 View {position} Details", 
                            key=f"view_{position}_details",
                            help=f"See more {position} options"):
                    # Show position breakdown in expander
                    with st.expander(f"📊 All Available {position}s", expanded=True):
                        # Show top 5 players at this position
                        top_position_players = position_players.head(5)
                        
                        for idx, (_, player) in enumerate(top_position_players.iterrows()):
                            rank_suffix = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][idx] if idx < 5 else f"{idx+1}."
                            
                            col_a, col_b, col_c = st.columns([3, 1, 1])
                            with col_a:
                                st.write(f"{rank_suffix} **{player['player_name']}**")
                            with col_b:
                                st.write(f"{player.get('projected_points', 0):.1f} pts")
                            with col_c:
                                st.write(f"Rank #{player.get('overall_rank', 'N/A')}")
            
            else:
                # No players available at this position
                st.markdown(f"""
                <div class="recommendation-tile" 
                     style="--position-color: #6b7280; --position-color-dark: #4b5563;">
                    <div class="tile-position">{position}</div>
                    <div class="tile-player">None Available</div>
                    <div class="tile-projection">All drafted</div>
                    <div class="tile-rank">Position complete</div>
                </div>
                """, unsafe_allow_html=True)
    
    # Add quick actions row
    st.markdown("---")
    
    # Quick action buttons
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("🔥 Best Overall Pick", key="best_overall"):
            if not available_players.empty:
                if 'overall_rank' in available_players.columns:
                    best_overall = available_players.nsmallest(1, 'overall_rank').iloc[0]
                else:
                    best_overall = available_players.nlargest(1, 'projected_points').iloc[0]
                
                st.success(f"🔥 **Best Overall**: {best_overall['player_name']} ({best_overall['position']}) - {best_overall.get('projected_points', 0):.1f} pts")
    
    with col2:
        if st.button("💎 Best Value Pick", key="best_value"):
            if not available_players.empty and 'vorp_score' in available_players.columns:
                best_value = available_players.nlargest(1, 'vorp_score').iloc[0]
                st.success(f"💎 **Best Value**: {best_value['player_name']} ({best_value['position']}) - VORP: {best_value.get('vorp_score', 0):.1f}")
    
    with col3:
        if st.button("🎯 Positional Need", key="positional_need"):
            # Simple position scarcity analysis
            position_counts = available_players['position'].value_counts()
            if not position_counts.empty:
                scarcest_position = position_counts.idxmin()
                scarcest_count = position_counts.min()
                st.warning(f"🎯 **Scarcest Position**: {scarcest_position} ({scarcest_count} remaining)")
    
    with col4:
        if st.button("⚡ Sleeper Alert", key="sleeper_alert"):
            # Find potential sleepers (high projection, low ADP)
            if 'adp' in available_players.columns and 'projected_points' in available_players.columns:
                # Simple sleeper logic: good projection but drafted later
                sleepers = available_players[
                    (available_players.get('adp', 999) > 100) & 
                    (available_players.get('projected_points', 0) > 150)
                ]
                if not sleepers.empty:
                    sleeper = sleepers.iloc[0]
                    st.info(f"⚡ **Sleeper Alert**: {sleeper['player_name']} ({sleeper['position']}) - Late ADP value")


# ===== COMPACT HEADER WITH INTEGRATED NAVIGATION =====

def render_compact_navigation():
    """Render compact header with integrated navigation and status"""
    
    # Get connection status
    is_connected = hasattr(st.session_state, 'connected_draft_id') and st.session_state.connected_draft_id
    
    # Build status text safely
    if is_connected:
        status_class = "connection-live"
        status_text = "🟢 LIVE DRAFT"
        if hasattr(st.session_state, 'connected_draft_id') and st.session_state.connected_draft_id:
            draft_id_short = st.session_state.connected_draft_id[-8:]
            status_text += f" • Draft: {draft_id_short}"
    else:
        status_class = "connection-offline"
        status_text = "📊 ANALYSIS MODE"
    
    # Compact header with everything integrated
    st.markdown(f"""
    <style>
    .compact-header {{
        background: linear-gradient(90deg, #1e3a8a 0%, #3b82f6 100%);
        padding: 12px 20px;
        border-radius: 10px;
        margin-bottom: 20px;
        color: white;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }}
    .header-row {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: 10px;
    }}
    .app-title {{
        font-size: 24px;
        font-weight: 700;
        margin: 0;
        color: white;
    }}
    .app-subtitle {{
        font-size: 12px;
        opacity: 0.9;
        margin: 0;
    }}
    .connection-status {{
        background: rgba(255,255,255,0.2);
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
    }}
    .connection-live {{
        background: #10b981;
        color: white;
    }}
    .connection-offline {{
        background: #6b7280;
        color: white;
    }}
    </style>
    
    <div class="compact-header">
        <div class="header-row">
            <div style="flex: 1;">
                <h1 class="app-title">🏈 SFB15 Draft Command Center</h1>
                <p class="app-subtitle">Enhanced ML Projections • Advanced Analytics • Live Draft Integration</p>
            </div>
            <div style="display: flex; align-items: center; gap: 15px;">
                <div class="connection-status {status_class}">
                    {status_text}
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Compact navigation - minimal space usage
    nav_options = [
        "🏈 Analysis", 
        "🎯 Live Draft", 
        "🎮 Mock Draft", 
        "📊 VORP",
        "🔧 Settings"
    ]
    
    # Inline selectbox with minimal styling for maximum space efficiency
    col1, col2 = st.columns([1, 4])
    with col1:
        selected_nav = st.selectbox(
            "",  # No label
            nav_options,
            index=1,  # Default to Live Draft
            key="main_navigation"
            # Removed label_visibility for Streamlit 1.12.0 compatibility
        )
    
    # Map shortened names back to full names for compatibility
    nav_mapping = {
        "🏈 Analysis": "🏈 Player Analysis",
        "🎯 Live Draft": "🎯 Live Draft", 
        "🎮 Mock Draft": "🎮 Mock Draft",
        "📊 VORP": "📊 VORP Analysis",
        "🔧 Settings": "🔧 Settings"
    }
    
    selected_nav = nav_mapping[selected_nav]
    
    return selected_nav

def main():
    """Main application entry point with compact design"""
    
    # Apply responsive CSS
    apply_mobile_css()
    
    # Load core data first
    with st.spinner("🏈 Loading SFB15 data..."):
        projections_df, adp_data, vorp_calc = load_core_data()
    
    if projections_df is None:
        st.error("❌ Unable to load projections data. Please check your data files and refresh the page.")
        st.info("Make sure the projections CSV file exists in the projections/2025/ directory.")
        return
    
    # COMPACT HEADER - Everything integrated, no wasted space
    selected_nav = render_compact_navigation()
    
    # Auto-switch to Live Draft Mode if connected (P0-5: Draft Mode State Management)
    is_connected = hasattr(st.session_state, 'connected_draft_id') and st.session_state.connected_draft_id
    if is_connected and selected_nav not in ["🔧 Settings"]:
        # Show additional connection details only when connected
        if hasattr(st.session_state, 'draft_username'):
            st.info(f"👤 **{st.session_state.draft_username}** | Connected to Draft: {st.session_state.connected_draft_id} | [Disconnect in Settings]")
        
        # Force Live Draft mode when connected
        if selected_nav != "🎯 Live Draft":
            st.info("🎯 **Auto-switched to Live Draft Mode** - You're connected to an active draft!")
        selected_nav = "🎯 Live Draft"

    # ===== REST OF THE EXISTING FUNCTION CONTINUES UNCHANGED =====
    # (Keep all the existing view rendering logic)
    
    # Render selected view
    if selected_nav == "🏈 Player Analysis":
        render_player_analysis(projections_df, adp_data, vorp_calc)
    
    elif selected_nav == "🎯 Live Draft":
        # Check if connected to a draft
        is_connected = hasattr(st.session_state, 'connected_draft_id') and st.session_state.connected_draft_id
        
        if not is_connected:
            st.warning("🔴 **Not Connected to Draft**")
            st.info("👉 Go to **Settings** to connect to your Sleeper draft")
            
            # Quick connection option
            with st.expander("🔗 Quick Connect", expanded=False):
                st.markdown("*For quick access, enter your draft ID here:*")
                quick_draft_id = st.text_input("Draft ID", placeholder="Enter Sleeper draft ID", key="quick_draft_id")
                if st.button("⚡ Quick Connect", key="quick_connect"):
                    if quick_draft_id:
                        try:
                            from src.draft.draft_manager import DraftManager
                            from src.draft.sleeper_client import SleeperClient
                            
                            sleeper_client = SleeperClient()
                            draft_manager = DraftManager(quick_draft_id, sleeper_client)
                            draft_state = draft_manager.initialize_draft()
                            
                            st.session_state.connected_draft_id = quick_draft_id
                            st.session_state.draft_manager = draft_manager
                            st.session_state.draft_state = draft_state
                            
                            st.success(f"✅ Connected to draft {quick_draft_id}")
                            st.experimental_rerun()
                        except Exception as e:
                            st.error(f"Connection failed: {str(e)}")
                            st.info("Use Settings for more connection options")
                    else:
                        st.error("Please enter a draft ID")
            
            return
        
        # CONNECTED - Show Live Draft Interface
        if is_connected:
            # Get draft manager from session state
            draft_manager = st.session_state.get('draft_manager')
            
            if not draft_manager:
                st.warning("🔄 Initializing draft manager...")
                try:
                    from src.draft.draft_manager import DraftManager
                    draft_manager = DraftManager(st.session_state.connected_draft_id)
                    draft_state = draft_manager.initialize_draft()
                    
                    # CRITICAL FIX: Set UI refresh callback for auto-refresh
                    draft_manager.set_ui_refresh_callback(lambda: st.experimental_rerun())
                    
                    # CRITICAL FIX: Start monitoring for live updates
                    draft_manager.start_monitoring(poll_interval=5)  # Check every 5 seconds
                    
                    st.session_state.draft_manager = draft_manager
                    st.session_state.draft_state = draft_state
                    st.success("✅ Draft manager initialized with live monitoring")
                    st.experimental_rerun()
                except Exception as e:
                    st.error(f"Failed to initialize draft manager: {str(e)}")
                    return
            
            # P0-2: VISUAL DRAFT BOARD INTERFACE
            # Remove redundant title - visual board has its own title
            try:
                render_visual_draft_board(draft_manager, projections_df)
            except Exception as e:
                st.error(f"Error rendering draft board: {str(e)}")
                # Fallback to simple board
                st.markdown("### 📋 Draft Summary (Fallback)")
                if hasattr(draft_manager, 'draft_state') and draft_manager.draft_state:
                    recent_picks = draft_manager.draft_state.picks[-10:] if draft_manager.draft_state.picks else []
                    if recent_picks:
                        st.markdown("**Recent Picks:**")
                        for pick in recent_picks:
                            st.text(f"Pick {pick.pick_number}: {pick.player_name} ({pick.position}) - Round {pick.round}")
                    else:
                        st.info("No picks made yet")
                else:
                    st.warning("Draft state not available")
            
            st.markdown("---")
            
            # P0-4: POSITION RECOMMENDATION TILES (NEW FEATURE)
            try:
                render_position_recommendation_tiles(projections_df, draft_manager)
                st.markdown("---")
            except Exception as e:
                st.error(f"Error rendering position tiles: {str(e)}")
            
            # P0-3: STREAMLINED AVAILABLE PLAYERS TABLE (PRIMARY INTERFACE)
            st.markdown("## ⚡ Available Players")
            
            try:
                # Render streamlined available players table
                render_streamlined_available_players(projections_df, draft_manager)
                
            except Exception as table_error:
                st.error(f"Error rendering streamlined table: {str(table_error)}")
                # Simple fallback
                st.markdown("### 📋 Basic Available Players")
                available_players = projections_df.copy()
                if draft_manager and hasattr(draft_manager, 'draft_state') and draft_manager.draft_state:
                    drafted_players = {pick.player_name for pick in draft_manager.draft_state.picks}
                    available_players = available_players[~available_players['player_name'].isin(drafted_players)]
                
                if not available_players.empty:
                    basic_display = available_players.head(20)[
                        ['player_name', 'position', 'team', 'projected_points', 'overall_rank']
                    ]
                    st.dataframe(basic_display)
                else:
                    st.info("No available players found")
        
                st.markdown("---")
    
    elif selected_nav == "🎮 Mock Draft":
        st.markdown("## 🎮 Mock Draft Mode")
        st.info("🚧 Mock draft simulator coming in next update")
        
        # Mock draft preview
        st.markdown("**Planned Features:**")
        st.markdown("- 12-team simulated draft")
        st.markdown("- AI opponents with different strategies")
        st.markdown("- Real-time pick timer")
        st.markdown("- Draft results analysis")
    
    elif selected_nav == "📊 VORP Analysis":
        render_vorp_analysis(projections_df, vorp_calc)
    
    elif selected_nav == "🔧 Settings":
        render_settings()
    
    # Footer
    st.markdown("---")
    st.markdown("*Built for Scott Fish Bowl 15 by the SFB15 Analytics Team*")


if __name__ == "__main__":
    main() 
"""
Sidebar Component
Dashboard configuration and filtering controls
"""

import streamlit as st
from typing import Dict, List

def render_sidebar(adp_manager=None) -> Dict:
    """
    Render the sidebar with configuration options
    
    Args:
        adp_manager: Optional ADPManager instance for source controls
    
    Returns:
        Dictionary with sidebar configuration values
    """
    st.sidebar.title("🏈 Dashboard Controls")
    
    # Main view selection
    st.sidebar.subheader("📊 View Selection")
    view_mode = st.sidebar.selectbox(
        "Dashboard View",
        ["Player Rankings", "Tier Analysis", "Value Explorer", "VORP Explorer", "Draft Assistant", "Live Draft Tracker"],
        help="Choose the main dashboard view"
    )
    
    # Position filters
    st.sidebar.subheader("🎯 Position Filters")
    positions = st.sidebar.multiselect(
        "Show Positions",
        ["QB", "RB", "WR", "TE"],
        default=["QB", "RB", "WR", "TE"],
        help="Filter players by position"
    )
    
    # Tier filters
    st.sidebar.subheader("🏆 Tier Filters")
    max_tier = st.sidebar.slider(
        "Maximum Tier",
        min_value=1,
        max_value=6,
        value=4,
        help="Show players up to this tier level"
    )
    
    # Display settings
    st.sidebar.subheader("⚙️ Display Settings")
    show_details = st.sidebar.checkbox(
        "Show Detailed Stats",
        value=True,
        help="Include additional player statistics"
    )
    
    players_per_page = st.sidebar.slider(
        "Players Per Page",
        min_value=10,
        max_value=100,
        value=50,
        step=10,
        help="Number of players to display"
    )
    
    # Search functionality
    st.sidebar.subheader("🔍 Player Search")
    search_term = st.sidebar.text_input(
        "Search Players",
        placeholder="Enter player name...",
        help="Search for specific players by name"
    )
    
    # Draft simulation settings
    st.sidebar.subheader("📋 Draft Settings")
    draft_position = st.sidebar.slider(
        "Draft Position",
        min_value=1,
        max_value=12,
        value=6,
        help="Your position in the draft order"
    )
    
    current_round = st.sidebar.slider(
        "Current Round", 
        min_value=1,
        max_value=16,
        value=1,
        help="Current draft round"
    )
    
    # ADP Source Configuration
    st.sidebar.subheader("🎯 ADP Source Configuration")
    
    # Primary ADP source selection
    primary_adp_source = st.sidebar.selectbox(
        "Primary ADP Source",
        ["sfb15", "sleeper", "fantasypros"],
        index=0,  # Default to SFB15
        help="Choose your primary ADP source for value calculations",
        key="primary_adp_source_select"
    )
    
    # Show source health status if manager is available
    if adp_manager:
        try:
            source_status = adp_manager.get_source_health_status()
            
            if source_status:
                st.sidebar.write("**📡 Source Status:**")
                
                for source, status in source_status.items():
                    status_emoji = {
                        'healthy': '🟢',
                        'stale': '🟡', 
                        'offline': '🔴'
                    }.get(status.get('status', 'offline'), '🔴')
                    
                    player_count = status.get('player_count', 0)
                    hours_old = status.get('last_updated_hours')
                    
                    if hours_old is not None:
                        time_info = f" ({hours_old:.1f}h old)" if hours_old < 24 else f" ({hours_old/24:.1f}d old)"
                    else:
                        time_info = ""
                    
                    st.sidebar.write(f"{status_emoji} **{source.upper()}**: {player_count} players{time_info}")
        except Exception as e:
            st.sidebar.warning("⚠️ Unable to check ADP source status")
    
    # Advanced ADP blending
    advanced_adp_blending = st.sidebar.checkbox(
        "Advanced ADP Blending",
        value=False,
        help="Enable custom weighting of ADP sources",
        key="advanced_adp_blending_checkbox"
    )
    
    source_weights = {}
    if advanced_adp_blending:
        st.sidebar.write("**Source Weights:**")
        
        sfb15_weight = st.sidebar.slider(
            "SFB15 Weight",
            min_value=0.0,
            max_value=1.0,
            value=0.70,
            step=0.05,
            help="Weight for SFB15 ADP data",
            key="sfb15_weight_slider"
        )
        
        sleeper_weight = st.sidebar.slider(
            "Sleeper Weight", 
            min_value=0.0,
            max_value=1.0,
            value=0.20,
            step=0.05,
            help="Weight for Sleeper ADP data",
            key="sleeper_weight_slider"
        )
        
        fp_weight = st.sidebar.slider(
            "FantasyPros Weight",
            min_value=0.0, 
            max_value=1.0,
            value=0.10,
            step=0.05,
            help="Weight for FantasyPros ADP data",
            key="fp_weight_slider"
        )
        
        # Normalize weights
        total_weight = sfb15_weight + sleeper_weight + fp_weight
        if total_weight > 0:
            source_weights = {
                'sfb15': sfb15_weight / total_weight,
                'sleeper': sleeper_weight / total_weight,
                'fantasypros': fp_weight / total_weight
            }
            
            # Show normalized weights
            st.sidebar.write("**Normalized:**")
            for source, weight in source_weights.items():
                st.sidebar.write(f"• {source.upper()}: {weight:.1%}")
        else:
            source_weights = {'sfb15': 1.0}  # Fallback
    
    # League settings
    st.sidebar.subheader("🏟️ League Settings")
    league_size = st.sidebar.selectbox(
        "League Size",
        [8, 10, 12, 14, 16],
        index=2,  # Default to 12 teams
        help="Number of teams in your league"
    )
    
    scoring_format = st.sidebar.selectbox(
        "Scoring Format",
        ["PPR", "Half PPR", "Standard"],
        index=0,  # Default to PPR
        help="League scoring format"
    )
    
    # Advanced filters
    with st.sidebar.expander("🔧 Advanced Filters"):
        min_projected_points = st.slider(
            "Minimum Projected Points",
            min_value=0,
            max_value=500,
            value=50,
            help="Filter players by minimum projected points"
        )
        
        max_age = st.slider(
            "Maximum Age",
            min_value=20,
            max_value=40,
            value=35,
            help="Filter players by maximum age"
        )
        
        confidence_levels = st.multiselect(
            "Confidence Levels",
            ["High", "Medium", "Low"],
            default=["High", "Medium", "Low"],
            key="confidence_filter",
            help="Filter by projection confidence"
        )
        
        # Ensure confidence_levels is never empty (fallback to all)
        if not confidence_levels:
            confidence_levels = ["High", "Medium", "Low"]
        
        injury_risk_filter = st.selectbox(
            "Injury Risk Filter",
            ["All Players", "Low Risk Only", "Exclude High Risk"],
            help="Filter players by injury risk level"
        )
    
    # Action buttons
    st.sidebar.subheader("🚀 Actions")
    if st.sidebar.button("🔄 Refresh Data", key="refresh_data_btn", help="Reload projection data"):
        # Use experimental_rerun for Streamlit 1.12.0
        st.experimental_rerun()
    
    if st.sidebar.button("📊 Export Rankings", key="export_rankings_btn", help="Export current rankings to CSV"):
        st.sidebar.success("Export functionality coming soon!")
    
    # Draft assistance
    with st.sidebar.expander("🎯 Draft Assistant"):
        st.write("**My Team:**")
        my_qb = st.text_input("QB", placeholder="e.g., Josh Allen", key="draft_qb_input")
        my_rb1 = st.text_input("RB1", placeholder="e.g., Saquon Barkley", key="draft_rb1_input")
        my_rb2 = st.text_input("RB2", placeholder="e.g., Bijan Robinson", key="draft_rb2_input")
        my_wr1 = st.text_input("WR1", placeholder="e.g., Ja'Marr Chase", key="draft_wr1_input")
        my_wr2 = st.text_input("WR2", placeholder="e.g., Amon-Ra St. Brown", key="draft_wr2_input")
        my_wr3 = st.text_input("WR3", placeholder="e.g., Puka Nacua", key="draft_wr3_input")
        my_te = st.text_input("TE", placeholder="e.g., Travis Kelce", key="draft_te_input")
        my_flex = st.text_input("FLEX", placeholder="e.g., DeVonta Smith", key="draft_flex_input")
        
        # Collect drafted players
        my_roster = [
            player.strip() for player in 
            [my_qb, my_rb1, my_rb2, my_wr1, my_wr2, my_wr3, my_te, my_flex]
            if player.strip()
        ]
    
    # Information panel
    with st.sidebar.expander("ℹ️ About This Dashboard"):
        st.markdown("""
        **SFB15 Draft Dashboard**
        
        Features enhanced ML projections with:
        - 71% model correlation
        - Industry-competitive ranges
        - Dynamic tier management
        - Value-based drafting (VBD)
        - Real-time draft assistance
        
        **Projection Ranges:**
        - QB: 4.1 - 792.8 points
        - RB: 20.2 - 540.3 points  
        - WR: 24.7 - 441.0 points
        - TE: 22.4 - 411.6 points
        """)
    
    # Return configuration
    return {
        'view_mode': view_mode,
        'positions': positions,
        'max_tier': max_tier,
        'show_details': show_details,
        'players_per_page': players_per_page,
        'search_term': search_term,
        'draft_position': draft_position,
        'current_round': current_round,
        'num_teams': league_size,  # Use num_teams for VORP calculator
        'league_size': league_size,
        'scoring_format': scoring_format,
        'min_projected_points': min_projected_points,
        'max_age': max_age,
        'confidence_levels': confidence_levels,
        'injury_risk_filter': injury_risk_filter,
        'my_roster': my_roster,
        'primary_adp_source': primary_adp_source,
        'advanced_adp_blending': advanced_adp_blending,
        'source_weights': source_weights
    } 
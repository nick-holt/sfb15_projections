"""
Main View Component
Renders the main dashboard content based on sidebar configuration
"""

import streamlit as st
import pandas as pd
from typing import Dict, Any

# Try to import plotly with error handling
try:
    import plotly.express as px
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

from ..utils.styling import format_player_card_html, get_tier_badge_html, get_position_badge_html

def render_main_view(projections: pd.DataFrame, value_calc, tier_manager, config: Dict[str, Any]):
    """
    Render the main dashboard view based on configuration
    
    Args:
        projections: DataFrame with player projections and analytics
        value_calc: ValueCalculator instance
        tier_manager: TierManager instance
        config: Configuration dictionary from sidebar
    """
    
    # Apply filters to projections
    filtered_projections = apply_filters(projections, config)
    
    # Render based on selected view mode
    if config['view_mode'] == "Player Rankings":
        render_player_rankings(filtered_projections, config)
    elif config['view_mode'] == "Tier Analysis":
        render_tier_analysis(filtered_projections, tier_manager, config)
    elif config['view_mode'] == "Value Explorer":
        render_value_explorer(filtered_projections, value_calc, config)
    elif config['view_mode'] == "Draft Assistant":
        render_draft_assistant(filtered_projections, value_calc, tier_manager, config)

def apply_filters(projections: pd.DataFrame, config: Dict[str, Any]) -> pd.DataFrame:
    """Apply sidebar filters to projections DataFrame"""
    df = projections.copy()
    
    # Debug: print filter info
    print(f"Starting with {len(df)} players")
    print(f"Positions filter: {config['positions']}")
    print(f"Max tier: {config['max_tier']}")
    print(f"Min projected points: {config['min_projected_points']}")
    
    # Position filter
    if config['positions']:
        df = df[df['position'].isin(config['positions'])]
        print(f"After position filter: {len(df)} players")
    
    # Tier filter (only apply if tier column exists)
    if 'tier' in df.columns:
        df = df[df['tier'] <= config['max_tier']]
        print(f"After tier filter: {len(df)} players")
    
    # Search filter
    if config['search_term']:
        search_mask = df['player_name'].str.contains(config['search_term'], case=False, na=False)
        df = df[search_mask]
        print(f"After search filter: {len(df)} players")
    
    # Projected points filter
    df = df[df['projected_points'] >= config['min_projected_points']]
    print(f"After points filter: {len(df)} players")
    
    # Age filter (if age column exists)
    if 'age' in df.columns:
        df = df[df['age'] <= config['max_age']]
        print(f"After age filter: {len(df)} players")
    
    # Confidence filter (if confidence column exists)
    if 'confidence' in df.columns:
        confidence_levels = config.get('confidence_levels', ['High', 'Medium', 'Low'])
        
        # Only apply filter if confidence_levels is not empty
        if confidence_levels:
            df = df[df['confidence'].isin(confidence_levels)]
        print(f"After confidence filter: {len(df)} players")
    
    print(f"Final filtered result: {len(df)} players")
    return df

def render_player_rankings(projections: pd.DataFrame, config: Dict[str, Any]):
    """Render the player rankings view"""
    st.subheader("🏆 Player Rankings")
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Players", len(projections))
    with col2:
        st.metric("Elite Tier (1)", len(projections[projections['tier'] == 1]))
    with col3:
        st.metric("Strong Tier (2)", len(projections[projections['tier'] == 2]))
    with col4:
        if len(projections) > 0:
            st.metric("Avg Points", f"{projections['projected_points'].mean():.1f}")
    
    # Position tabs (now supported in Streamlit 1.12.0+)
    tab_qb, tab_rb, tab_wr, tab_te, tab_all = st.tabs(["🎯 QB", "🏃 RB", "🏃‍♂️ WR", "🎯 TE", "📊 All"])
    
    positions = ['QB', 'RB', 'WR', 'TE']
    tabs = [tab_qb, tab_rb, tab_wr, tab_te]
    
    # Position-specific views
    for pos, tab in zip(positions, tabs):
        with tab:
            pos_players = projections[projections['position'] == pos].head(config['players_per_page'])
            render_position_rankings(pos_players, config, position=pos)
    
    # All players view
    with tab_all:
        render_all_players_table(projections.head(config['players_per_page']), config)

def render_position_rankings(pos_players: pd.DataFrame, config: Dict[str, Any], position: str = "All"):
    """Render rankings for a specific position"""
    if len(pos_players) == 0:
        st.info("No players found matching the current filters.")
        return
    
    # Display format options
    display_format = st.radio(
        "Display Format",
        ["Cards", "Table"],
        horizontal=True,
        key=f"display_format_{position}"
    )
    
    if display_format == "Cards":
        render_player_cards(pos_players, config)
    else:
        render_player_table(pos_players, config)

def render_player_cards(players: pd.DataFrame, config: Dict[str, Any]):
    """Render players as cards"""
    for idx, player in players.iterrows():
        player_dict = player.to_dict()
        card_html = format_player_card_html(player_dict)
        st.markdown(card_html, unsafe_allow_html=True)

def render_player_table(players: pd.DataFrame, config: Dict[str, Any]):
    """Render players as a data table"""
    # Select columns to display - only include columns that exist
    base_columns = ['player_name', 'position', 'team', 'projected_points']
    optional_base_columns = ['tier', 'value_tier']
    
    # Add optional base columns if they exist
    for col in optional_base_columns:
        if col in players.columns:
            base_columns.append(col)
    
    if config['show_details']:
        detail_columns = ['age', 'confidence', 'vbd_score', 'draft_value']
        detail_columns = [col for col in detail_columns if col in players.columns]
        display_columns = base_columns + detail_columns
    else:
        display_columns = base_columns
    
    # Format the display table
    display_df = players[display_columns].copy()
    display_df['projected_points'] = display_df['projected_points'].round(1)
    
    if 'vbd_score' in display_df.columns:
        display_df['vbd_score'] = display_df['vbd_score'].round(1)
    if 'draft_value' in display_df.columns:
        display_df['draft_value'] = display_df['draft_value'].round(1)
    
    st.dataframe(display_df)

def render_all_players_table(projections: pd.DataFrame, config: Dict[str, Any]):
    """Render all players in a comprehensive table"""
    st.write(f"**Top {len(projections)} Players Overall**")
    render_player_table(projections, config)

def render_tier_analysis(projections: pd.DataFrame, tier_manager, config: Dict[str, Any]):
    """Render the tier analysis view"""
    st.subheader("🏆 Tier Analysis")
    
    # Tier summary
    tier_summary = tier_manager.get_tier_summary(projections)
    
    # Tier distribution chart
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.write("**Tier Distribution by Position**")
        
        # Create tier distribution data for plotting
        tier_data = []
        for position in ['QB', 'RB', 'WR', 'TE']:
            pos_summary = tier_summary.get(position, {'tiers': {}})
            for tier, info in pos_summary.get('tiers', {}).items():
                tier_data.append({
                    'Position': position,
                    'Tier': f"Tier {tier}",
                    'Count': info['count'],
                    'Label': info['label']
                })
        
        if tier_data:
            tier_df = pd.DataFrame(tier_data)
            if PLOTLY_AVAILABLE:
                fig = px.bar(
                    tier_df, 
                    x='Position', 
                    y='Count', 
                    color='Tier',
                    title="Player Distribution by Tier and Position",
                    color_discrete_sequence=px.colors.qualitative.Set3
                )
                st.plotly_chart(fig)
            else:
                st.write("**Tier Distribution Data:**")
                st.dataframe(tier_df)
    
    with col2:
        st.write("**Tier Summary**")
        for position in ['QB', 'RB', 'WR', 'TE']:
            pos_summary = tier_summary.get(position, {})
            total_players = pos_summary.get('total', 0)
            
            if total_players > 0:
                st.markdown(f"**{position}** ({total_players} players)")
                tiers = pos_summary.get('tiers', {})
                for tier in sorted(tiers.keys())[:3]:  # Show top 3 tiers
                    tier_info = tiers[tier]
                    st.markdown(
                        f"Tier {tier}: {tier_info['count']} players "
                        f"({tier_info['avg_points']:.1f} avg pts)"
                    )
                st.markdown("---")
    
    # Tier recommendations
    st.write("**Tier-Based Recommendations**")
    recommendations = tier_manager.get_tier_recommendations(projections, config['my_roster'])
    
    col1, col2 = st.columns(2)
    with col1:
        if recommendations['tier_1_targets']:
            st.write("🎯 **Elite Tier Targets:**")
            for player in recommendations['tier_1_targets'][:5]:
                st.write(f"• {player}")
    
    with col2:
        if recommendations['tier_2_values']:
            st.write("💎 **Strong Value Plays:**")
            for player in recommendations['tier_2_values'][:5]:
                st.write(f"• {player}")

def render_value_explorer(projections: pd.DataFrame, value_calc, config: Dict[str, Any]):
    """Render the value explorer view"""
    st.subheader("💎 Value Explorer")
    
    # Value-based metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        elite_values = projections[projections['value_tier'] == 'Elite Value']
        st.metric("Elite Values", len(elite_values))
    
    with col2:
        strong_values = projections[projections['value_tier'] == 'Strong Value']
        st.metric("Strong Values", len(strong_values))
    
    with col3:
        if 'vbd_score' in projections.columns:
            avg_vbd = projections['vbd_score'].mean()
            st.metric("Avg VBD Score", f"{avg_vbd:.1f}")
    
    with col4:
        scarcity_scores = value_calc.calculate_positional_scarcity(projections)
        most_scarce = max(scarcity_scores, key=scarcity_scores.get)
        st.metric("Most Scarce", most_scarce)
    
    # VBD vs Projected Points scatter plot
    if 'vbd_score' in projections.columns and 'draft_value' in projections.columns:
        st.write("**Value vs Projection Analysis**")
        
        if PLOTLY_AVAILABLE:
            fig = px.scatter(
                projections,
                x='projected_points',
                y='vbd_score',
                color='position',
                size='draft_value',
                hover_data=['player_name', 'tier', 'value_tier'],
                title="VBD Score vs Projected Points",
                labels={
                    'projected_points': 'Projected Fantasy Points',
                    'vbd_score': 'Value Based Drafting Score'
                }
            )
            st.plotly_chart(fig)
        else:
            st.write("**Top VBD vs Projection Players:**")
            analysis_df = projections[['player_name', 'position', 'projected_points', 'vbd_score', 'draft_value']].head(20)
            st.dataframe(analysis_df)
    
    # Value recommendations
    recommendations = value_calc.get_value_recommendations(projections, config['my_roster'])
    
    col1, col2 = st.columns(2)
    with col1:
        st.write("🏆 **Best Values:**")
        for player in recommendations['best_values'][:8]:
            player_data = projections[projections['player_name'] == player]
            if not player_data.empty:
                p = player_data.iloc[0]
                st.write(f"• {player} ({p['position']}) - {p['projected_points']:.1f} pts")
    
    with col2:
        st.write("🛡️ **Safe Picks:**")
        for player in recommendations['safe_picks'][:8]:
            player_data = projections[projections['player_name'] == player]
            if not player_data.empty:
                p = player_data.iloc[0]
                st.write(f"• {player} ({p['position']}) - {p['projected_points']:.1f} pts")

def render_draft_assistant(projections: pd.DataFrame, value_calc, tier_manager, config: Dict[str, Any]):
    """Render the draft assistant view"""
    st.subheader("🎯 Draft Assistant")
    
    # Current draft context
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Draft Position", config['draft_position'])
    with col2:
        st.metric("Current Round", config['current_round'])
    with col3:
        st.metric("My Roster Size", len(config['my_roster']))
    
    # My current roster
    if config['my_roster']:
        st.write("**My Current Roster:**")
        for i, player in enumerate(config['my_roster'], 1):
            player_data = projections[projections['player_name'] == player]
            if not player_data.empty:
                p = player_data.iloc[0]
                st.write(f"{i}. {player} ({p['position']}, {p['team']}) - {p['projected_points']:.1f} pts")
    
    # Available players (filtered out my roster)
    available_players = projections[~projections['player_name'].isin(config['my_roster'])]
    
    # Draft suggestions based on round
    st.write("**Round-Based Suggestions:**")
    suggestions = tier_manager.suggest_tier_targets(
        available_players, 
        config['my_roster'],
        config['draft_position'],
        config['current_round']
    )
    
    # Display suggestions in columns
    if suggestions:
        cols = st.columns(len(suggestions))
        for i, suggestion in enumerate(suggestions):
            with cols[i]:
                st.write(f"**{suggestion['position']} - {suggestion['tier_label']}**")
                for player in suggestion['players'][:3]:  # Top 3 per position
                    player_data = available_players[available_players['player_name'] == player]
                    if not player_data.empty:
                        p = player_data.iloc[0]
                        st.write(f"• {player} ({p['projected_points']:.1f})")
    
    # Best available players
    st.write("**Best Available Players:**")
    best_available = available_players.head(12)  # Top 12 available
    
    # Display in a clean format
    for idx, player in best_available.iterrows():
        col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
        with col1:
            st.write(f"**{player['player_name']}** ({player['position']}, {player['team']})")
        with col2:
            st.write(f"Tier {player['tier']}")
        with col3:
            st.write(f"{player['projected_points']:.1f} pts")
        with col4:
            if st.button("Draft", key=f"draft_{player['player_name']}"):
                st.success(f"Drafted {player['player_name']}!")
                # In a real implementation, this would update the roster 
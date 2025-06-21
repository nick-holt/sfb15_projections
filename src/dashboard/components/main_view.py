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
    
    # Confidence filter (if confidence column exists and has valid data)
    if 'confidence' in df.columns:
        confidence_levels = config.get('confidence_levels', ['High', 'Medium', 'Low'])
        
        # Check if confidence column has valid data (not all NaN)
        valid_confidence = df['confidence'].notna().any()
        
        if confidence_levels and valid_confidence:
            # Check if confidence is numeric or categorical
            first_valid_confidence = df['confidence'].dropna().iloc[0] if len(df['confidence'].dropna()) > 0 else None
            
            if isinstance(first_valid_confidence, (int, float)):
                # Numeric confidence scores - convert to categorical
                print("Converting numeric confidence to categories...")
                
                def categorize_confidence(score):
                    if pd.isna(score):
                        return 'Medium'
                    elif score >= 80:
                        return 'High'
                    elif score >= 50:
                        return 'Medium'
                    else:
                        return 'Low'
                
                df['confidence_category'] = df['confidence'].apply(categorize_confidence)
                df = df[df['confidence_category'].isin(confidence_levels)]
                print(f"Confidence distribution: {df['confidence_category'].value_counts().to_dict()}")
                
            else:
                # Categorical confidence - use as is
                df = df[df['confidence'].isin(confidence_levels)]
                print(f"Confidence distribution: {df['confidence'].value_counts().to_dict()}")
        elif not valid_confidence:
            print("Warning: Confidence column contains only NaN values, skipping confidence filter")
        
        print(f"After confidence filter: {len(df)} players")
    
    print(f"Final filtered result: {len(df)} players")
    return df

def render_player_rankings(projections: pd.DataFrame, config: Dict[str, Any]):
    """
    Render player rankings with position-specific views
    """
    st.subheader("🏈 Player Rankings")
    
    # Position filter for older Streamlit versions (replace tabs)
    position_options = ["All", "QB", "RB", "WR", "TE"]
    selected_position = st.selectbox(
        "Select Position",
        options=position_options,
        index=0,
        key="position_rankings_selector"
    )
    
    # Filter by position if not "All"
    if selected_position != "All":
        pos_projections = projections[projections['position'] == selected_position].copy()
        st.subheader(f"{selected_position} Rankings")
        render_position_rankings(pos_projections, config)
    else:
        st.subheader("All Players")
        render_all_players_table(projections.head(config['players_per_page']), config)

def render_position_rankings(projections: pd.DataFrame, config: Dict[str, Any]):
    """
    Render rankings for a specific position
    """
    if projections.empty:
        st.info("No players found for this position.")
        return
    
    # Display format toggle
    # Create unique key based on position and timestamp to avoid duplicates
    import time
    unique_key = f"display_format_{projections['position'].iloc[0] if not projections.empty else 'unknown'}_{int(time.time() * 1000) % 10000}"
    display_format = st.radio(
        "Display Format",
        ["Table", "Cards"],
        index=0,
        key=unique_key
    )
    
    if display_format == "Table":
        render_player_table(projections.head(config['players_per_page']), config)
    else:
        render_player_cards(projections.head(config['players_per_page']), config)

def render_player_cards(players: pd.DataFrame, config: Dict[str, Any]):
    """Render players as cards"""
    for idx, player in players.iterrows():
        player_dict = player.to_dict()
        card_html = format_player_card_html(player_dict)
        st.markdown(card_html, unsafe_allow_html=True)

def render_player_table(projections: pd.DataFrame, config: Dict[str, Any]):
    """
    Render player data as a table
    """
    # Select columns for display
    display_columns = [
        'player_name', 'position', 'team', 'projected_points', 
        'tier_label', 'draft_value', 'overall_rank'
    ]
    
    # Check which columns exist
    available_columns = [col for col in display_columns if col in projections.columns]
    
    if available_columns:
        display_df = projections[available_columns].copy()
        
        # Round numeric columns
        numeric_columns = display_df.select_dtypes(include=['float64', 'int64']).columns
        for col in numeric_columns:
            if col != 'overall_rank':  # Don't round ranks
                display_df[col] = display_df[col].round(1)
        
        # Remove use_container_width for compatibility with Streamlit 1.12.0
        st.dataframe(display_df)
    else:
        st.error("No valid columns found for display")

def render_all_players_table(projections: pd.DataFrame, config: Dict[str, Any]):
    """
    Render all players table
    """
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
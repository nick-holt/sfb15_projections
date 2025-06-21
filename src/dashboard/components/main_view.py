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

def render_main_view(projections: pd.DataFrame, value_calc, tier_manager, adp_data: pd.DataFrame, config: Dict[str, Any]):
    """
    Main dashboard view with enhanced projections and ADP integration
    """
    st.subheader("🏈 Enhanced Player Analysis")
    
    # Merge projections with ADP data if available
    enhanced_projections = projections.copy()
    if adp_data is not None and not adp_data.empty:
        # John Carmack approach: minimal fix - normalize names during merge only
        from src.utils.name_normalizer import name_normalizer
        
        # Prepare ADP data for joining with name normalization
        adp_join_df = adp_data[adp_data['name'].notna()].copy()
        adp_join_df['normalized_name'] = adp_join_df['name'].apply(name_normalizer.normalize_name)
        
        # Prepare projections for joining
        proj_join_df = projections.copy()
        proj_join_df['normalized_name'] = proj_join_df['player_name'].apply(name_normalizer.normalize_name)
        
        # Merge on normalized names
        enhanced_projections = pd.merge(
            proj_join_df,
            adp_join_df[['normalized_name', 'consensus_adp']],
            on='normalized_name',
            how='left'
        )
        
        # Clean up
        enhanced_projections = enhanced_projections.drop(columns=['normalized_name'])
        
        # Also get raw SFB15 ADP data directly from the scraper
        try:
            from src.data.adp_manager import ADPManager
            adp_manager = ADPManager()
            raw_sfb15_data = adp_manager.fetch_sfb15_adp()
            
            if not raw_sfb15_data.empty:
                # Normalize SFB15 names for joining
                raw_sfb15_for_join = raw_sfb15_data.copy()
                raw_sfb15_for_join['normalized_name'] = raw_sfb15_for_join['name'].apply(name_normalizer.normalize_name)
                
                # Create temporary normalized name column for enhanced_projections
                enhanced_projections['normalized_name'] = enhanced_projections['player_name'].apply(name_normalizer.normalize_name)
                
                # Merge raw SFB15 data with different column names using normalized names
                enhanced_projections = pd.merge(
                    enhanced_projections,
                    raw_sfb15_for_join[['normalized_name', 'consensus_adp', 'rank']].rename(columns={
                        'consensus_adp': 'sfb15_raw_adp',  # Different name to avoid conflict
                        'rank': 'sfb15_rank'
                    }),
                    on='normalized_name',
                    how='left'
                )
                
                # Drop the temporary normalized name column
                enhanced_projections = enhanced_projections.drop(columns=['normalized_name'])
            
        except Exception as e:
            st.warning(f"Could not load raw SFB15 ADP data: {str(e)}")
        
        # Calculate ADP values (projection rank - ADP rank = value, positive is good)
        if 'consensus_adp' in enhanced_projections.columns:
            # Use blended ADP for value calculation
            enhanced_projections['adp_value'] = enhanced_projections['overall_rank'] - enhanced_projections['consensus_adp']
        
        if 'sfb15_rank' in enhanced_projections.columns:
            # Calculate raw SFB15 ADP value
            enhanced_projections['sfb15_adp_value'] = enhanced_projections['overall_rank'] - enhanced_projections['sfb15_rank']
    
    # Apply filters from sidebar
    filtered_projections = apply_filters(enhanced_projections, config)
    
    if filtered_projections.empty:
        st.warning("No players match the current filters. Please adjust your criteria.")
        return
    
    # Main content
    render_player_rankings(filtered_projections, config)

def apply_filters(projections: pd.DataFrame, config: Dict[str, Any]) -> pd.DataFrame:
    """Apply sidebar filters to projections DataFrame"""
    df = projections.copy()
    
    # Position filter
    if config['positions']:
        df = df[df['position'].isin(config['positions'])]
    
    # Tier filter (only apply if tier column exists)
    if 'tier' in df.columns:
        df = df[df['tier'] <= config['max_tier']]
    
    # Search filter
    if config['search_term']:
        search_mask = df['player_name'].str.contains(config['search_term'], case=False, na=False)
        df = df[search_mask]
    
    # Projected points filter
    df = df[df['projected_points'] >= config['min_projected_points']]
    
    # Age filter (if age column exists)
    if 'age' in df.columns:
        df = df[df['age'] <= config['max_age']]
    
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
                
            else:
                # Categorical confidence - use as is
                df = df[df['confidence'].isin(confidence_levels)]
    
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
    Render player data as a table with enhanced ADP integration
    """
    # Select columns for display - include ADP data if available
    display_columns = [
        'player_name', 'position', 'team', 'projected_points', 
        'tier_label', 'draft_value', 'overall_rank'
    ]
    
    # Add ADP columns if they exist
    if 'sfb15_raw_adp' in projections.columns:
        display_columns.extend(['sfb15_raw_adp', 'sfb15_adp_value'])
    if 'consensus_adp' in projections.columns:
        display_columns.extend(['consensus_adp', 'adp_value'])
    
    # Check which columns exist
    available_columns = [col for col in display_columns if col in projections.columns]
    
    if available_columns:
        display_df = projections[available_columns].copy()
        
        # Rename columns for better display
        column_renames = {
            'player_name': 'Player',
            'position': 'Pos',
            'team': 'Team',
            'projected_points': 'Proj Pts',
            'tier_label': 'Tier',
            'draft_value': 'Value',
            'overall_rank': 'Proj Rank',
            'sfb15_raw_adp': 'SFB15 ADP',
            'sfb15_adp_value': 'SFB15 Value',
            'consensus_adp': 'Blended ADP',
            'adp_value': 'Blend Value'
        }
        
        # Only rename columns that exist
        actual_renames = {k: v for k, v in column_renames.items() if k in display_df.columns}
        display_df = display_df.rename(columns=actual_renames)
        
        # Format numeric columns
        numeric_columns = ['Proj Pts', 'Proj Rank', 'SFB15 ADP', 'Blended ADP']
        for col in numeric_columns:
            if col in display_df.columns:
                display_df[col] = pd.to_numeric(display_df[col], errors='coerce').round(1)
        
        # Format value columns (can be negative)
        value_columns = ['Value', 'SFB15 Value', 'Blend Value']
        for col in value_columns:
            if col in display_df.columns:
                display_df[col] = pd.to_numeric(display_df[col], errors='coerce').round(1)
        
        # Display the table
        st.dataframe(display_df)
    else:
        st.error("No valid columns found for display.")

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
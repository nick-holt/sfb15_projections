#!/usr/bin/env python3
"""
ADP View Component for SFB15 Fantasy Football Dashboard
Displays ADP analysis, value opportunities, and market intelligence
"""

import streamlit as st
import pandas as pd
import numpy as np
from typing import Dict, List, Any

# Try to import plotly with error handling
try:
    import plotly.express as px
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

def render_adp_view(projections: pd.DataFrame, adp_data: pd.DataFrame, 
                   adp_analyzer, config: Dict[str, Any]) -> None:
    """Render the ADP analysis view"""
    
    if adp_data.empty:
        st.warning("⚠️ No ADP data available. Please check your data sources.")
        return
    
    # Calculate ADP value metrics
    with st.spinner("Calculating ADP value metrics..."):
        value_df = adp_analyzer.calculate_adp_value_metrics(projections, adp_data)
    
    if value_df.empty:
        st.error("❌ Unable to calculate ADP value metrics. Please check data compatibility.")
        return
    
    # ADP Analysis Header
    st.header("📊 ADP Analysis & Market Intelligence")
    
    # Create tabs for different ADP views - using selectbox for Streamlit 1.12.0 compatibility
    adp_tab_names = ["🎯 Value Opportunities", "💎 Sleepers & Busts", "📈 Market Trends", 
                     "🎲 Draft Strategy", "🚨 Live Alerts"]
    selected_adp_tab = st.selectbox("Select ADP Analysis:", adp_tab_names, key="adp_tab_selector")
    
    if selected_adp_tab == "🎯 Value Opportunities":
        render_value_opportunities(value_df, config)
    
    elif selected_adp_tab == "💎 Sleepers & Busts":
        render_sleepers_and_busts(value_df, adp_analyzer, config)
    
    elif selected_adp_tab == "📈 Market Trends":
        render_market_trends(value_df, adp_analyzer, config)
    
    elif selected_adp_tab == "🎲 Draft Strategy":
        render_draft_strategy(value_df, adp_analyzer, config)
    
    elif selected_adp_tab == "🚨 Live Alerts":
        render_live_alerts(value_df, adp_analyzer, config)

def render_value_opportunities(value_df: pd.DataFrame, config: Dict[str, Any]) -> None:
    """Render value opportunities analysis"""
    
    st.subheader("🎯 ADP Value Opportunities")
    
    # Filter controls
    col1, col2, col3 = st.columns(3)
    
    with col1:
        min_value_gap = st.slider(
            "Minimum Value Gap (Rounds)",
            min_value=0,
            max_value=50,
            value=10,
            help="Minimum rounds of value to display"
        )
    
    with col2:
        position_filter = st.multiselect(
            "Positions",
            options=['QB', 'RB', 'WR', 'TE'],
            default=['QB', 'RB', 'WR', 'TE'],
            help="Filter by position"
        )
    
    with col3:
        max_adp = st.slider(
            "Maximum ADP",
            min_value=1,
            max_value=300,
            value=200,
            help="Only show players with ADP below this value"
        )
    
    # Filter data
    filtered_df = value_df[
        (value_df['adp_value'] >= min_value_gap) &
        (value_df['position'].isin(position_filter)) &
        (value_df['consensus_adp'] <= max_adp)
    ].copy()
    
    if filtered_df.empty:
        st.info("No value opportunities found with current filters.")
        return
    
    # Value opportunities metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Value Opportunities",
            len(filtered_df),
            help="Players with significant ADP value"
        )
    
    with col2:
        avg_value = filtered_df['adp_value'].mean()
        st.metric(
            "Avg Value Gap",
            f"{avg_value:.1f} rounds",
            help="Average rounds of value"
        )
    
    with col3:
        best_value = filtered_df['adp_value'].max()
        st.metric(
            "Best Value",
            f"{best_value:.1f} rounds",
            help="Largest value gap found"
        )
    
    with col4:
        late_round_values = len(filtered_df[filtered_df['consensus_adp'] > 100])
        st.metric(
            "Late Round Values",
            late_round_values,
            help="Value opportunities after round 8"
        )
    
    # ADP vs Projection scatter plot
    st.subheader("📈 ADP vs Projection Analysis")
    
    if PLOTLY_AVAILABLE:
        fig = px.scatter(
            filtered_df,
            x='consensus_adp',
            y='projected_points',
            color='position',
            size='adp_value',
            hover_data=['player_name', 'value_tier', 'draft_urgency'],
            title="ADP vs Projected Points (Size = Value Gap)",
            labels={
                'consensus_adp': 'Consensus ADP',
                'projected_points': 'Projected Fantasy Points'
            }
        )
        
        # Add diagonal line showing perfect correlation
        max_points = filtered_df['projected_points'].max()
        min_adp = filtered_df['consensus_adp'].min()
        max_adp = filtered_df['consensus_adp'].max()
        
        fig.add_trace(
            go.Scatter(
                x=[min_adp, max_adp],
                y=[max_points * (max_adp/min_adp), max_points * (min_adp/max_adp)],
                mode='lines',
                name='Perfect Correlation',
                line=dict(dash='dash', color='gray')
            )
        )
        
        fig.update_layout(height=500)
        st.plotly_chart(fig)
    else:
        st.info("Install plotly for interactive charts: pip install plotly")
    
    # Top value opportunities table
    st.subheader("🏆 Top Value Opportunities")
    
    display_columns = [
        'player_name', 'position', 'team', 'consensus_adp', 
        'projected_points', 'adp_value', 'value_tier', 'draft_urgency'
    ]
    
    # Check which columns exist
    available_columns = [col for col in display_columns if col in filtered_df.columns]
    
    if available_columns:
        # Rename columns for display
        display_df = filtered_df[available_columns].copy()
        
        # Create column mapping
        column_mapping = {
            'player_name': 'Player',
            'position': 'Pos',
            'team': 'Team',
            'consensus_adp': 'ADP',
            'projected_points': 'Proj Pts',
            'adp_value': 'Value Gap',
            'value_tier': 'Value Tier',
            'draft_urgency': 'Draft Urgency'
        }
        
        # Rename only available columns
        display_df = display_df.rename(columns={k: v for k, v in column_mapping.items() if k in display_df.columns})
        
        # Sort by value gap if available
        if 'Value Gap' in display_df.columns:
            display_df = display_df.sort_values('Value Gap', ascending=False)
        
        st.dataframe(display_df)
    else:
        st.error("Required columns not found in data")

def render_sleepers_and_busts(value_df: pd.DataFrame, adp_analyzer, config: Dict[str, Any]) -> None:
    """Render sleepers and busts analysis"""
    
    st.subheader("💎 Sleepers & Busts Analysis")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🚀 Sleeper Candidates")
        
        # Identify sleepers
        sleepers = adp_analyzer.identify_sleepers(value_df, min_value_gap=15)
        
        if not sleepers.empty:
            # Sleeper metrics
            st.metric("Sleeper Candidates", len(sleepers))
            
            # Top sleepers
            sleeper_columns = ['player_name', 'position', 'consensus_adp', 'sleeper_score', 'adp_value']
            available_sleeper_cols = [col for col in sleeper_columns if col in sleepers.columns]
            
            if available_sleeper_cols:
                sleeper_display = sleepers[available_sleeper_cols].head(10)
                
                # Rename columns
                column_mapping = {
                    'player_name': 'Player',
                    'position': 'Pos',
                    'consensus_adp': 'ADP',
                    'sleeper_score': 'Sleeper Score',
                    'adp_value': 'Value Gap'
                }
                
                sleeper_display = sleeper_display.rename(columns={k: v for k, v in column_mapping.items() if k in sleeper_display.columns})
                st.dataframe(sleeper_display)
            
            # Sleeper score distribution
            if PLOTLY_AVAILABLE and 'sleeper_score' in sleepers.columns:
                fig = px.histogram(
                    sleepers,
                    x='sleeper_score',
                    nbins=20,
                    title="Sleeper Score Distribution",
                    labels={'sleeper_score': 'Sleeper Score', 'count': 'Number of Players'}
                )
                st.plotly_chart(fig)
        else:
            st.info("No sleeper candidates found with current criteria.")
    
    with col2:
        st.subheader("⚠️ Bust Candidates")
        
        # Identify busts
        busts = adp_analyzer.identify_busts(value_df, min_reach=-20)
        
        if not busts.empty:
            # Bust metrics
            st.metric("Bust Candidates", len(busts))
            
            # Top busts
            bust_columns = ['player_name', 'position', 'consensus_adp', 'bust_risk', 'adp_value']
            available_bust_cols = [col for col in bust_columns if col in busts.columns]
            
            if available_bust_cols:
                bust_display = busts[available_bust_cols].head(10)
                
                # Rename columns
                column_mapping = {
                    'player_name': 'Player',
                    'position': 'Pos',
                    'consensus_adp': 'ADP',
                    'bust_risk': 'Bust Risk',
                    'adp_value': 'Value Gap'
                }
                
                bust_display = bust_display.rename(columns={k: v for k, v in column_mapping.items() if k in bust_display.columns})
                st.dataframe(bust_display)
            
            # Bust risk distribution
            if PLOTLY_AVAILABLE and 'bust_risk' in busts.columns:
                fig = px.histogram(
                    busts,
                    x='bust_risk',
                    nbins=20,
                    title="Bust Risk Distribution",
                    labels={'bust_risk': 'Bust Risk Score', 'count': 'Number of Players'}
                )
                st.plotly_chart(fig)
        else:
            st.info("No bust candidates found with current criteria.")

def render_market_trends(value_df: pd.DataFrame, adp_analyzer, config: Dict[str, Any]) -> None:
    """Render market trends and efficiency analysis"""
    
    st.subheader("📈 Market Trends & Efficiency")
    
    # Market efficiency metrics
    efficiency_metrics = adp_analyzer.calculate_market_efficiency_score(value_df)
    
    if efficiency_metrics:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Market Efficiency",
                f"{efficiency_metrics['overall_efficiency']:.1f}%",
                help="Percentage of fairly valued players"
            )
        
        with col2:
            st.metric(
                "Avg Value Gap",
                f"{efficiency_metrics['avg_value_gap']:.1f}",
                help="Average absolute value gap"
            )
        
        with col3:
            st.metric(
                "Undervalued Players",
                efficiency_metrics['undervalued_players'],
                help="Players with 10+ rounds of value"
            )
        
        with col4:
            st.metric(
                "Overvalued Players",
                efficiency_metrics['overvalued_players'],
                help="Players reaching 10+ rounds"
            )
    
    # Positional ADP trends
    st.subheader("📊 Positional ADP Trends")
    
    position_analysis = adp_analyzer.analyze_positional_adp_trends(value_df)
    
    if position_analysis:
        # Create position comparison chart
        pos_data = []
        for pos, data in position_analysis.items():
            pos_data.append({
                'Position': pos,
                'Avg ADP': data['avg_adp'],
                'Avg Projection': data['avg_projection'],
                'Avg Value Gap': data['avg_value_gap'],
                'Value Opportunities': data['value_opportunities'],
                'Potential Reaches': data['potential_reaches']
            })
        
        pos_df = pd.DataFrame(pos_data)
        
        # Position efficiency chart
        if PLOTLY_AVAILABLE:
            fig = px.bar(
                pos_df,
                x='Position',
                y=['Value Opportunities', 'Potential Reaches'],
                title="Value Opportunities vs Potential Reaches by Position",
                barmode='group'
            )
            st.plotly_chart(fig)
        
        # Position details
        for pos, data in position_analysis.items():
            with st.expander(f"{pos} Position Analysis"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("**Top Values:**")
                    for player in data['top_values']:
                        st.write(f"• {player['player_name']}: +{player['adp_value']:.1f} rounds")
                
                with col2:
                    st.write("**Biggest Reaches:**")
                    for player in data['biggest_reaches']:
                        st.write(f"• {player['player_name']}: {player['adp_value']:.1f} rounds")

def render_draft_strategy(value_df: pd.DataFrame, adp_analyzer, config: Dict[str, Any]) -> None:
    """Render draft strategy recommendations"""
    
    st.subheader("🎲 Draft Strategy Recommendations")
    
    # Draft position input
    col1, col2 = st.columns(2)
    
    with col1:
        draft_position = st.selectbox(
            "Your Draft Position",
            options=list(range(1, 13)),
            index=5,  # Default to 6th position
            help="Select your draft position"
        )
    
    with col2:
        num_teams = st.selectbox(
            "Number of Teams",
            options=[8, 10, 12, 14, 16],
            index=2,  # Default to 12 teams
            help="Number of teams in your league"
        )
    
    # Generate recommendations
    recommendations = adp_analyzer.generate_draft_strategy_recommendations(
        value_df, draft_position, num_teams
    )
    
    if recommendations:
        # Early round targets
        st.subheader("🎯 Early Round Targets (Rounds 1-5)")
        if recommendations['early_round_targets']:
            early_df = pd.DataFrame(recommendations['early_round_targets'])
            early_df.columns = ['Player', 'Position', 'ADP', 'Value Gap']
            st.dataframe(early_df)
        else:
            st.info("No early round targets identified.")
        
        # Middle round values
        st.subheader("💰 Middle Round Values (Rounds 6-10)")
        if recommendations['middle_round_values']:
            middle_df = pd.DataFrame(recommendations['middle_round_values'])
            middle_df.columns = ['Player', 'Position', 'ADP', 'Value Gap']
            st.dataframe(middle_df)
        else:
            st.info("No middle round values identified.")
        
        # Late round sleepers
        st.subheader("💎 Late Round Sleepers (Rounds 11+)")
        if recommendations['late_round_sleepers']:
            late_df = pd.DataFrame(recommendations['late_round_sleepers'])
            late_df.columns = ['Player', 'Position', 'ADP', 'Value Gap']
            st.dataframe(late_df)
        else:
            st.info("No late round sleepers identified.")
        
        # Players to avoid
        st.subheader("⚠️ Players to Avoid")
        if recommendations['players_to_avoid']:
            avoid_df = pd.DataFrame(recommendations['players_to_avoid'])
            avoid_df.columns = ['Player', 'Position', 'ADP', 'Value Gap']
            st.dataframe(avoid_df)
        else:
            st.info("No players to avoid identified.")
        
        # Positional strategy
        st.subheader("📋 Positional Strategy")
        for position, strategy in recommendations['positional_strategy'].items():
            with st.expander(f"{position} Strategy"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("**Best Values:**")
                    for player in strategy['best_values']:
                        st.write(f"• {player['player_name']} (ADP: {player['consensus_adp']:.1f}, Value: +{player['adp_value']:.1f})")
                
                with col2:
                    st.write("**Recommended Rounds:**")
                    if strategy['recommended_rounds']:
                        for round_num in strategy['recommended_rounds']:
                            st.write(f"• Round {round_num}")
                    else:
                        st.write("• No specific rounds recommended")

def render_live_alerts(value_df: pd.DataFrame, adp_analyzer, config: Dict[str, Any]) -> None:
    """Render live ADP alerts and notifications"""
    
    st.subheader("🚨 Live ADP Alerts")
    
    # Alert threshold
    alert_threshold = st.slider(
        "Alert Threshold (Rounds)",
        min_value=5,
        max_value=50,
        value=20,
        help="Minimum value gap to trigger alerts"
    )
    
    # Generate alerts
    alerts = adp_analyzer.get_adp_alerts(value_df, alert_threshold)
    
    if alerts:
        st.success(f"🔔 {len(alerts)} active alerts found!")
        
        for alert in alerts:
            if alert['type'] == 'value_opportunity':
                st.success(f"💰 **{alert['message']}**")
            elif alert['type'] == 'bust_warning':
                st.warning(f"⚠️ **{alert['message']}**")
            else:
                st.info(f"ℹ️ **{alert['message']}**")
    else:
        st.info("No alerts at current threshold. Try lowering the alert threshold.")
    
    # Alert summary
    if alerts:
        alert_types = {}
        for alert in alerts:
            alert_types[alert['type']] = alert_types.get(alert['type'], 0) + 1
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("Value Opportunities", alert_types.get('value_opportunity', 0))
        
        with col2:
            st.metric("Bust Warnings", alert_types.get('bust_warning', 0))
    
    # Auto-refresh option
    if st.checkbox("Auto-refresh alerts (every 30 seconds)"):
        st.experimental_rerun() 
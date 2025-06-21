#!/usr/bin/env python3
"""
SFB15 Fantasy Football Draft Dashboard
Main Streamlit Application

Integrates enhanced ML projections with live ADP data, 
draft rankings, and advanced analytics for Scott Fish Bowl 15.
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import os
import sys

# Try to import plotly with error handling
try:
    import plotly.express as px
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    st.error("Plotly is not installed. Please run: pip install plotly")
    PLOTLY_AVAILABLE = False

# Add src directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

# Try to import dashboard components with error handling
try:
    from src.data.projections import ProjectionManager
    from src.data.adp_manager import ADPManager
    from src.analytics.value_calculator import ValueCalculator
    from src.analytics.tier_manager import TierManager
    from src.analytics.adp_analyzer import ADPAnalyzer
    from src.dashboard.components.sidebar import render_sidebar
    from src.dashboard.components.main_view import render_main_view
    from src.dashboard.components.adp_view import render_adp_view
    from src.dashboard.utils.styling import apply_custom_css
    COMPONENTS_AVAILABLE = True
except ImportError as e:
    st.error(f"Error importing dashboard components: {str(e)}")
    st.error("Please ensure all source files are in place and try refreshing.")
    COMPONENTS_AVAILABLE = False

# Page Configuration
st.set_page_config(
    page_title="SFB15 Draft Dashboard",
    page_icon="🏈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Apply custom styling
apply_custom_css()

def load_data():
    """Load and cache projection and ADP data"""
    try:
        # Load enhanced projections
        projection_manager = ProjectionManager()
        projections = projection_manager.load_enhanced_projections()
        print(f"Loaded {len(projections)} projections")
        print(f"Columns before VBD: {projections.columns.tolist()}")
        
        # Initialize analytics engines
        value_calc = ValueCalculator()
        tier_manager = TierManager()
        adp_manager = ADPManager()
        adp_analyzer = ADPAnalyzer()
        
        # Calculate VBD and tiers
        print("Calculating VBD scores...")
        projections_with_vbd = value_calc.calculate_vbd_scores(projections)
        print(f"Columns after VBD: {projections_with_vbd.columns.tolist()}")
        
        print("Assigning dynamic tiers...")
        projections_with_tiers = tier_manager.assign_dynamic_tiers(projections_with_vbd)
        print(f"Final columns: {projections_with_tiers.columns.tolist()}")
        print(f"Final shape: {projections_with_tiers.shape}")
        
        # Load ADP data with SFB15 priority
        print("Loading ADP data...")
        adp_data = adp_manager.get_blended_adp()  # Use blended ADP by default
        print(f"Loaded ADP data for {len(adp_data)} players")
        
        return projections_with_tiers, value_calc, tier_manager, adp_data, adp_analyzer
        
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        print(f"Exception details: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return None, None, None, None, None

def main():
    """Main application entry point"""
    
    # Header
    st.title("🏈 SFB15 Fantasy Football Draft Dashboard")
    st.markdown("**Enhanced ML Projections • Live ADP • Advanced Analytics**")
    
    # Check if all components are available
    if not COMPONENTS_AVAILABLE:
        st.error("Dashboard components are not available. Please check the installation.")
        return
    
    if not PLOTLY_AVAILABLE:
        st.warning("Plotly is not available. Some visualizations may not work.")
    
    # Load data
    with st.spinner("Loading enhanced projections and analytics..."):
        projections, value_calc, tier_manager, adp_data, adp_analyzer = load_data()
    
    if projections is None:
        st.error("Failed to load projection data. Please check your data files.")
        return
    
    # Create ADP manager instance for sidebar controls
    adp_manager = ADPManager()
    
    # Sidebar configuration (pass ADP manager for source controls)
    sidebar_config = render_sidebar(adp_manager)
    
    # Handle ADP source switching based on sidebar config
    if sidebar_config.get('primary_adp_source'):
        adp_manager.switch_primary_source(sidebar_config['primary_adp_source'])
    
    # Get fresh ADP data if source weights changed
    if sidebar_config.get('advanced_adp_blending') and sidebar_config.get('source_weights'):
        with st.spinner("Updating ADP blend..."):
            adp_data = adp_manager.get_blended_adp(weights=sidebar_config['source_weights'])
    elif adp_data is None or adp_data.empty:
        with st.spinner("Loading ADP data..."):
            adp_data = adp_manager.get_blended_adp()
    
    # Main dashboard tabs - using selectbox for Streamlit 1.12.0 compatibility
    main_tab_names = ["🏈 Player Analysis", "📈 ADP Analysis"]
    selected_main_tab = st.selectbox("Select Analysis View:", main_tab_names, key="main_tab_selector")
    
    if selected_main_tab == "🏈 Player Analysis":
        # Main dashboard view - pass ADP data for enhanced player analysis
        render_main_view(projections, value_calc, tier_manager, adp_data, sidebar_config)
    
    elif selected_main_tab == "📈 ADP Analysis":
        # ADP analysis view
        if adp_data is not None and not adp_data.empty:
            render_adp_view(projections, adp_data, adp_analyzer, sidebar_config)
        else:
            st.warning("⚠️ ADP data not available. Please check your data sources.")
            st.info("ADP data will be automatically fetched from multiple sources including Sleeper and FantasyPros.")
    
    # Footer
    st.markdown("---")
    st.markdown(
        "**SFB15 Draft Dashboard** | "
        f"Enhanced ML Models • {len(projections)} Players • "
        f"Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )

if __name__ == "__main__":
    main() 
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
    from src.analytics.value_calculator import ValueCalculator
    from src.analytics.tier_manager import TierManager
    from src.dashboard.components.sidebar import render_sidebar
    from src.dashboard.components.main_view import render_main_view
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
        
        # Calculate VBD and tiers
        print("Calculating VBD scores...")
        projections_with_vbd = value_calc.calculate_vbd_scores(projections)
        print(f"Columns after VBD: {projections_with_vbd.columns.tolist()}")
        
        print("Assigning dynamic tiers...")
        projections_with_tiers = tier_manager.assign_dynamic_tiers(projections_with_vbd)
        print(f"Final columns: {projections_with_tiers.columns.tolist()}")
        print(f"Final shape: {projections_with_tiers.shape}")
        
        return projections_with_tiers, value_calc, tier_manager
        
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        print(f"Exception details: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return None, None, None

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
        projections, value_calc, tier_manager = load_data()
    
    if projections is None:
        st.error("Failed to load projection data. Please check your data files.")
        return
    
    # Sidebar configuration
    sidebar_config = render_sidebar()
    
    # Main dashboard view
    render_main_view(projections, value_calc, tier_manager, sidebar_config)
    
    # Footer
    st.markdown("---")
    st.markdown(
        "**SFB15 Draft Dashboard** | "
        f"Enhanced ML Models • {len(projections)} Players • "
        f"Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )

if __name__ == "__main__":
    main() 
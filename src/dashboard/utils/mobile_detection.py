"""
Mobile Detection Utility
Detects mobile devices and provides responsive design helpers
"""

import streamlit as st
import re
from typing import Dict, Any


def detect_mobile_device() -> bool:
    """
    Detect if user is on mobile device
    
    Returns:
        bool: True if mobile device detected
    """
    try:
        # Try to get user agent from Streamlit context
        # Note: This may not work in all Streamlit versions
        if hasattr(st, 'context') and hasattr(st.context, 'headers'):
            user_agent = st.context.headers.get("user-agent", "").lower()
            
            mobile_patterns = [
                r'mobile', r'android', r'iphone', r'ipad', r'ipod',
                r'blackberry', r'opera mini', r'windows phone'
            ]
            
            for pattern in mobile_patterns:
                if re.search(pattern, user_agent):
                    return True
        
        # Fallback: Use JavaScript to detect screen width
        try:
            import streamlit.components.v1 as components
            
            # Simple mobile detection via screen width
            mobile_check = components.html("""
                <script>
                if (window.screen.width <= 768) {
                    window.parent.postMessage({mobile: true}, "*");
                } else {
                    window.parent.postMessage({mobile: false}, "*");
                }
                </script>
            """, height=0)
            
            # For now, assume desktop since we can't easily get the return value
            return False
            
        except Exception:
            # Final fallback: assume desktop
            return False
            
    except Exception:
        # If all fails, assume desktop
        return False


def get_responsive_config() -> Dict[str, Any]:
    """
    Get responsive configuration based on device type
    
    Returns:
        Dict with responsive settings
    """
    is_mobile = detect_mobile_device()
    
    if is_mobile:
        return {
            "layout": "centered",
            "sidebar_state": "collapsed",
            "columns_per_row": 1,
            "card_height": 120,
            "font_size": "small",
            "show_details": False,
            "players_per_page": 10,
            "use_compact_tables": True
        }
    else:
        return {
            "layout": "wide", 
            "sidebar_state": "expanded",
            "columns_per_row": 4,
            "card_height": 150,
            "font_size": "normal",
            "show_details": True,
            "players_per_page": 25,
            "use_compact_tables": False
        }


def apply_mobile_css():
    """Apply mobile-optimized CSS styles"""
    
    mobile_css = """
    <style>
    /* Mobile-first responsive design */
    @media (max-width: 768px) {
        .stApp {
            padding: 0.5rem;
        }
        
        .stButton button {
            width: 100%;
            height: 3rem;
            font-size: 1.1rem;
            margin: 0.25rem 0;
        }
        
        .stSelectbox, .stMultiSelect {
            margin-bottom: 0.5rem;
        }
        
        .draft-card {
            padding: 0.75rem;
            margin: 0.25rem 0;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .recommendation-banner {
            padding: 1rem;
            text-align: center;
            border-radius: 10px;
            margin: 0.5rem 0;
        }
        
        .mobile-quick-pick {
            background: linear-gradient(45deg, #FF6B6B, #4ECDC4);
            color: white;
            padding: 1.5rem;
            border-radius: 15px;
            text-align: center;
            margin: 1rem 0;
        }
        
        .stMetric {
            background: white;
            padding: 0.5rem;
            border-radius: 5px;
            margin: 0.25rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
    }
    
    /* Desktop optimizations */
    @media (min-width: 769px) {
        .draft-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 1rem;
            margin: 1rem 0;
        }
        
        .mission-control {
            position: sticky;
            top: 0;
            z-index: 100;
            background: white;
            border-bottom: 2px solid #f0f2f6;
            padding: 1rem 0;
            margin-bottom: 1rem;
        }
    }
    
    /* Common styles */
    .urgent-indicator {
        animation: pulse 1s infinite;
    }
    
    @keyframes pulse {
        0% { opacity: 1; }
        50% { opacity: 0.7; }
        100% { opacity: 1; }
    }
    
    .tier-1 { background-color: #e74c3c; color: white; }
    .tier-2 { background-color: #f39c12; color: white; }
    .tier-3 { background-color: #f1c40f; color: black; }
    .tier-4 { background-color: #27ae60; color: white; }
    .tier-5 { background-color: #3498db; color: white; }
    
    .position-qb { border-left: 4px solid #3498db; }
    .position-rb { border-left: 4px solid #e74c3c; }
    .position-wr { border-left: 4px solid #f1c40f; }
    .position-te { border-left: 4px solid #27ae60; }
    
    .value-high { border-left: 4px solid #e74c3c; }
    .value-medium { border-left: 4px solid #f39c12; }
    .value-low { border-left: 4px solid #f1c40f; }
    </style>
    """
    
    st.markdown(mobile_css, unsafe_allow_html=True)


def render_mobile_navigation(nav_options: list, current_selection: int = 0) -> int:
    """
    Render mobile-optimized navigation
    
    Args:
        nav_options: List of navigation option names
        current_selection: Current selected index
        
    Returns:
        Selected index
    """
    if detect_mobile_device():
        # Use streamlit-option-menu for mobile if available
        try:
            from streamlit_option_menu import option_menu
            
            selected = option_menu(
                menu_title=None,
                options=nav_options,
                default_index=current_selection,
                orientation="horizontal",
                styles={
                    "container": {"padding": "0", "margin": "0"},
                    "nav-link": {"font-size": "12px", "text-align": "center", "margin": "0px"},
                    "nav-link-selected": {"background-color": "#FF6B6B"}
                }
            )
            return nav_options.index(selected)
            
        except (ImportError, Exception):
            # Fallback to selectbox
            selected = st.selectbox("Navigation", nav_options, index=current_selection)
            return nav_options.index(selected)
    else:
        # Use selectbox for desktop too (simpler)
        selected = st.selectbox("Navigation", nav_options, index=current_selection)
        return nav_options.index(selected) 
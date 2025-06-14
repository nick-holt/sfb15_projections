"""
Styling Utilities
Custom CSS styling for the SFB15 Dashboard
"""

import streamlit as st

def apply_custom_css():
    """Apply custom CSS styling to the dashboard"""
    
    custom_css = """
    <style>
    /* Main app styling */
    .main {
        padding-top: 1rem;
    }
    
    /* Header styling */
    .stApp > header {
        background-color: transparent;
    }
    
    /* Sidebar styling */
    .css-1d391kg {
        background-color: #f0f2f6;
    }
    
    /* Player cards styling */
    .player-card {
        background-color: white;
        padding: 1rem;
        border-radius: 0.5rem;
        border: 1px solid #e0e0e0;
        margin: 0.5rem 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    /* Tier badge styling */
    .tier-badge {
        display: inline-block;
        padding: 0.2rem 0.5rem;
        border-radius: 1rem;
        font-size: 0.8rem;
        font-weight: bold;
        margin-right: 0.5rem;
    }
    
    .tier-elite {
        background-color: #d4edda;
        color: #155724;
    }
    
    .tier-strong {
        background-color: #cce7ff;
        color: #004085;
    }
    
    .tier-solid {
        background-color: #fff3cd;
        color: #856404;
    }
    
    .tier-serviceable {
        background-color: #f8d7da;
        color: #721c24;
    }
    
    /* Value indicators */
    .value-high {
        color: #28a745;
        font-weight: bold;
    }
    
    .value-medium {
        color: #ffc107;
        font-weight: bold;
    }
    
    .value-low {
        color: #dc3545;
        font-weight: bold;
    }
    
    /* Position badges */
    .pos-qb { background-color: #ff6b6b; color: white; }
    .pos-rb { background-color: #4ecdc4; color: white; }
    .pos-wr { background-color: #45b7d1; color: white; }
    .pos-te { background-color: #96ceb4; color: white; }
    
    .position-badge {
        display: inline-block;
        padding: 0.2rem 0.4rem;
        border-radius: 0.3rem;
        font-size: 0.7rem;
        font-weight: bold;
        margin-right: 0.3rem;
    }
    
    /* Metrics styling */
    .metric-container {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    
    /* Table styling */
    .dataframe {
        font-size: 0.9rem;
    }
    
    .dataframe th {
        background-color: #f1f3f4;
        font-weight: bold;
    }
    
    /* Button styling */
    .stButton > button {
        background-color: #1f77b4;
        color: white;
        border-radius: 0.5rem;
        border: none;
        padding: 0.5rem 1rem;
        font-weight: bold;
    }
    
    .stButton > button:hover {
        background-color: #1565c0;
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Custom spacing */
    .element-container {
        margin-bottom: 1rem;
    }
    </style>
    """
    
    st.markdown(custom_css, unsafe_allow_html=True)

def get_tier_badge_html(tier: int, tier_label: str) -> str:
    """
    Generate HTML for tier badge
    
    Args:
        tier: Tier number (1-6)
        tier_label: Tier label string
        
    Returns:
        HTML string for tier badge
    """
    tier_classes = {
        1: "tier-elite",
        2: "tier-strong", 
        3: "tier-solid",
        4: "tier-serviceable",
        5: "tier-deep",
        6: "tier-deep"
    }
    
    css_class = tier_classes.get(tier, "tier-deep")
    return f'<span class="tier-badge {css_class}">Tier {tier}</span>'

def get_position_badge_html(position: str) -> str:
    """
    Generate HTML for position badge
    
    Args:
        position: Position abbreviation (QB, RB, WR, TE)
        
    Returns:
        HTML string for position badge
    """
    position_classes = {
        'QB': 'pos-qb',
        'RB': 'pos-rb',
        'WR': 'pos-wr', 
        'TE': 'pos-te'
    }
    
    css_class = position_classes.get(position, 'pos-qb')
    return f'<span class="position-badge {css_class}">{position}</span>'

def get_value_indicator_html(value_tier: str) -> str:
    """
    Generate HTML for value indicator
    
    Args:
        value_tier: Value tier string
        
    Returns:
        HTML string for value indicator
    """
    if "Elite" in value_tier or "Strong" in value_tier:
        css_class = "value-high"
    elif "Fair" in value_tier:
        css_class = "value-medium"
    else:
        css_class = "value-low"
        
    return f'<span class="{css_class}">{value_tier}</span>'

def format_player_card_html(player_data: dict) -> str:
    """
    Generate HTML for a player card
    
    Args:
        player_data: Dictionary with player information
        
    Returns:
        HTML string for player card
    """
    name = player_data.get('player_name', 'Unknown')
    position = player_data.get('position', 'N/A')
    team = player_data.get('team', 'N/A')
    points = player_data.get('projected_points', 0)
    tier = player_data.get('tier', 6)
    tier_label = player_data.get('tier_label', 'Deep')
    value_tier = player_data.get('value_tier', 'Fair Value')
    
    pos_badge = get_position_badge_html(position)
    tier_badge = get_tier_badge_html(tier, tier_label)
    value_indicator = get_value_indicator_html(value_tier)
    
    return f"""
    <div class="player-card">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <strong>{name}</strong> {pos_badge} <small>({team})</small>
                <br>
                {tier_badge} {value_indicator}
            </div>
            <div style="text-align: right;">
                <div style="font-size: 1.2rem; font-weight: bold; color: #1f77b4;">
                    {points:.1f} pts
                </div>
            </div>
        </div>
    </div>
    """ 
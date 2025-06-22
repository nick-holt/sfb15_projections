"""
Pick Now View - Ultimate Decision Interface
The money shot - optimal draft decision in <5 seconds
"""

import streamlit as st
import pandas as pd
from typing import Dict, Any, List, Optional
import time

from ...utils.mobile_detection import detect_mobile_device, get_responsive_config


class PickNowView:
    """Ultimate decision interface for live drafts"""
    
    def __init__(self):
        self.responsive_config = get_responsive_config()
        self.is_mobile = detect_mobile_device()
    
    def render(self, projections_df: pd.DataFrame, draft_state=None, dynamic_vorp_calc=None) -> Optional[Dict[str, Any]]:
        """
        Render the Pick Now interface
        
        Args:
            projections_df: Enhanced projections with VORP
            draft_state: Current draft state 
            dynamic_vorp_calc: Dynamic VORP calculator
            
        Returns:
            Dict with selected player info if pick made, None otherwise
        """
        
        # Get top recommendation
        top_recommendation = self._get_top_recommendation(projections_df, draft_state, dynamic_vorp_calc)
        
        if not top_recommendation:
            st.error("⚠️ No recommendations available. Please check data.")
            return None
        
        # Render main recommendation banner
        self._render_recommendation_banner(top_recommendation)
        
        # Decision support columns
        self._render_decision_support(top_recommendation, projections_df, draft_state)
        
        # Action buttons
        selected_player = self._render_action_buttons(top_recommendation, projections_df)
        
        # Show alternatives if requested
        if st.session_state.get('show_alternatives', False):
            self._render_alternatives(projections_df, draft_state, dynamic_vorp_calc)
        
        return selected_player
    
    def _get_top_recommendation(self, projections_df: pd.DataFrame, draft_state=None, dynamic_vorp_calc=None) -> Optional[Dict[str, Any]]:
        """Get the top recommendation based on dynamic VORP"""
        
        try:
            # Filter out already drafted players if we have draft state
            available_df = projections_df.copy()
            
            if draft_state and hasattr(draft_state, 'picks'):
                drafted_player_ids = {pick.player_id for pick in draft_state.picks}
                available_df = available_df[~available_df['player_id'].isin(drafted_player_ids)]
            
            if available_df.empty:
                return None
            
            # Use dynamic VORP if available, otherwise fall back to static VORP
            if 'dynamic_vorp_final' in available_df.columns:
                vorp_column = 'dynamic_vorp_final'
            elif 'dynamic_vorp' in available_df.columns:
                vorp_column = 'dynamic_vorp'
            elif 'vorp_score' in available_df.columns:
                vorp_column = 'vorp_score'
            else:
                # Fallback to projected points
                vorp_column = 'projected_points'
            
            # Get top player by VORP
            top_player = available_df.nlargest(1, vorp_column).iloc[0]
            
            # Build recommendation dict
            recommendation = {
                'player_id': top_player.get('player_id', ''),
                'name': top_player.get('player_name', 'Unknown'),
                'position': top_player.get('position', ''),
                'team': top_player.get('team', ''),
                'projected_points': round(top_player.get('projected_points', 0), 1),
                'vorp_score': round(top_player.get(vorp_column, 0), 1),
                'tier': top_player.get('tier', 5),
                'tier_label': top_player.get('tier_label', 'Depth'),
                'overall_rank': int(top_player.get('overall_rank', 999)),
                'position_rank': int(top_player.get('position_rank', 99)),
                'adp': top_player.get('consensus_adp', top_player.get('sfb15_raw_adp', None)),
                'confidence': top_player.get('confidence', 'Medium'),
                'injury_risk': top_player.get('injury_risk_category', 'Low')
            }
            
            # Calculate value over ADP
            if recommendation['adp']:
                recommendation['value_over_adp'] = recommendation['overall_rank'] - recommendation['adp']
            else:
                recommendation['value_over_adp'] = 0
            
            # Generate recommendation reasons
            recommendation['reasons'] = self._generate_recommendation_reasons(top_player, available_df, draft_state)
            recommendation['considerations'] = self._generate_considerations(top_player, draft_state)
            
            return recommendation
            
        except Exception as e:
            st.error(f"Error generating recommendation: {str(e)}")
            return None
    
    def _render_recommendation_banner(self, recommendation: Dict[str, Any]):
        """Render the impossible-to-miss recommendation banner"""
        
        # Get tier color
        tier_colors = {
            1: "#e74c3c",  # Red - Elite
            2: "#f39c12",  # Orange - Great  
            3: "#f1c40f",  # Yellow - Good
            4: "#27ae60",  # Green - Solid
            5: "#3498db"   # Blue - Depth
        }
        
        tier_color = tier_colors.get(recommendation['tier'], "#95a5a6")
        
        # Build value indicator
        value_text = ""
        if recommendation['value_over_adp'] > 0:
            value_text = f"📈 +{recommendation['value_over_adp']} Value"
        elif recommendation['value_over_adp'] < 0:
            value_text = f"📉 {recommendation['value_over_adp']} Reach"
        else:
            value_text = "📊 Fair Value"
        
        # Main recommendation banner
        st.markdown(f"""
        <div style='
            background: linear-gradient(90deg, {tier_color}, {tier_color}dd);
            padding: 20px;
            border-radius: 15px;
            text-align: center;
            margin-bottom: 20px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        '>
            <h1 style='color: white; margin: 0; font-size: 2.5rem;'>🎯 DRAFT RECOMMENDATION</h1>
            <h2 style='color: white; margin: 10px 0; font-size: 2rem;'>{recommendation['name']} - {recommendation['position']}</h2>
            <p style='color: white; font-size: 18px; margin: 0;'>
                Dynamic VORP: {recommendation['vorp_score']} • Tier {recommendation['tier']} • {value_text}
            </p>
            <p style='color: white; font-size: 16px; margin: 5px 0 0 0; opacity: 0.9;'>
                Projected: {recommendation['projected_points']} pts • Rank: #{recommendation['overall_rank']} overall, #{recommendation['position_rank']} {recommendation['position']}
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    def _render_decision_support(self, recommendation: Dict[str, Any], projections_df: pd.DataFrame, draft_state=None):
        """Render three-column decision support"""
        
        if self.is_mobile:
            # Mobile: Stack vertically
            self._render_mobile_decision_support(recommendation, projections_df, draft_state)
        else:
            # Desktop: Three columns
            col1, col2, col3 = st.columns([1, 1, 1])
            
            with col1:
                st.markdown("### 🔥 Why This Pick")
                for reason in recommendation['reasons'][:3]:
                    st.markdown(f"• **{reason}**")
            
            with col2:
                st.markdown("### ⚠️ Considerations")
                for consideration in recommendation['considerations'][:3]:
                    st.markdown(f"• {consideration}")
            
            with col3:
                st.markdown("### 🎲 Alternatives")
                alternatives = self._get_top_alternatives(projections_df, draft_state, exclude_id=recommendation['player_id'])
                for alt in alternatives[:3]:
                    st.markdown(f"• **{alt['name']}** ({alt['position']}) - VORP: {alt['vorp_score']}")
    
    def _render_mobile_decision_support(self, recommendation: Dict[str, Any], projections_df: pd.DataFrame, draft_state=None):
        """Render mobile version of decision support"""
        
        # Expandable sections for mobile
        with st.expander("🔥 Why This Pick", expanded=True):
            for reason in recommendation['reasons'][:3]:
                st.markdown(f"• **{reason}**")
        
        with st.expander("⚠️ Considerations"):
            for consideration in recommendation['considerations'][:3]:
                st.markdown(f"• {consideration}")
    
    def _render_action_buttons(self, recommendation: Dict[str, Any], projections_df: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """Render clear action buttons with affordances"""
        
        if self.is_mobile:
            # Mobile: Stack buttons vertically
            if st.button("✅ DRAFT THIS PLAYER", type="primary", key="draft_primary"):
                return recommendation
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔄 ALTERNATIVES", key="show_alts"):
                    st.session_state.show_alternatives = True
                    st.rerun()
            
            with col2:
                if st.button("📊 ANALYSIS", key="switch_analysis"):
                    st.session_state.ui_mode = 'analysis'
                    st.rerun()
        
        else:
            # Desktop: Three-column layout
            col1, col2, col3 = st.columns([1, 1, 1])
            
            with col1:
                if st.button("✅ DRAFT THIS PLAYER", type="primary", key="draft_primary_desktop"):
                    return recommendation
            
            with col2:
                if st.button("🔄 SHOW ALTERNATIVES", key="show_alts_desktop"):
                    st.session_state.show_alternatives = True
                    st.rerun()
            
            with col3:
                if st.button("⏭️ SKIP TO ANALYSIS", key="switch_analysis_desktop"):
                    st.session_state.ui_mode = 'analysis'
                    st.rerun()
        
        return None
    
    def _render_alternatives(self, projections_df: pd.DataFrame, draft_state=None, dynamic_vorp_calc=None):
        """Render alternative player options"""
        
        st.markdown("---")
        st.markdown("### 🔄 Alternative Picks")
        
        alternatives = self._get_top_alternatives(projections_df, draft_state, limit=5)
        
        for i, alt in enumerate(alternatives):
            # Alternative card
            tier_colors = {1: "#e74c3c", 2: "#f39c12", 3: "#f1c40f", 4: "#27ae60", 5: "#3498db"}
            color = tier_colors.get(alt['tier'], "#95a5a6")
            
            st.markdown(f"""
            <div style='
                border-left: 5px solid {color};
                padding: 15px;
                margin: 10px 0;
                background: #f8f9fa;
                border-radius: 5px;
            '>
                <h4 style='margin: 0 0 10px 0;'>#{i+2} {alt['name']} ({alt['position']})</h4>
                <div style='display: flex; justify-content: space-between;'>
                    <div>
                        <strong>VORP:</strong> {alt['vorp_score']} | <strong>Proj:</strong> {alt['projected_points']} pts
                    </div>
                    <div>
                        <strong>Tier:</strong> {alt['tier']} | <strong>Rank:</strong> #{alt['overall_rank']}
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Quick draft button
            col1, col2 = st.columns([3, 1])
            with col2:
                if st.button(f"✅ Draft", key=f"draft_alt_{alt['player_id']}", type="secondary"):
                    return alt
    
    def _get_top_alternatives(self, projections_df: pd.DataFrame, draft_state=None, exclude_id: str = None, limit: int = 5) -> List[Dict[str, Any]]:
        """Get top alternative recommendations"""
        
        try:
            # Filter available players
            available_df = projections_df.copy()
            
            if draft_state and hasattr(draft_state, 'picks'):
                drafted_player_ids = {pick.player_id for pick in draft_state.picks}
                available_df = available_df[~available_df['player_id'].isin(drafted_player_ids)]
            
            if exclude_id:
                available_df = available_df[available_df['player_id'] != exclude_id]
            
            if available_df.empty:
                return []
            
            # Use best available VORP column
            if 'dynamic_vorp_final' in available_df.columns:
                vorp_column = 'dynamic_vorp_final'
            elif 'dynamic_vorp' in available_df.columns:
                vorp_column = 'dynamic_vorp'
            else:
                vorp_column = 'vorp_score'
            
            # Get top alternatives
            top_alternatives = available_df.nlargest(limit, vorp_column)
            
            alternatives = []
            for _, player in top_alternatives.iterrows():
                alternatives.append({
                    'player_id': player.get('player_id', ''),
                    'name': player.get('player_name', 'Unknown'),
                    'position': player.get('position', ''),
                    'vorp_score': round(player.get(vorp_column, 0), 1),
                    'projected_points': round(player.get('projected_points', 0), 1),
                    'tier': player.get('tier', 5),
                    'overall_rank': int(player.get('overall_rank', 999))
                })
            
            return alternatives
            
        except Exception as e:
            st.error(f"Error getting alternatives: {str(e)}")
            return []
    
    def _generate_recommendation_reasons(self, player_row: pd.Series, available_df: pd.DataFrame, draft_state=None) -> List[str]:
        """Generate compelling reasons for this recommendation"""
        
        reasons = []
        
        try:
            # VORP-based reasons
            if hasattr(player_row, 'dynamic_vorp_final') and player_row.dynamic_vorp_final > 0:
                reasons.append(f"Highest dynamic VORP ({player_row.dynamic_vorp_final:.1f})")
            
            # Tier-based reasons
            if hasattr(player_row, 'tier') and player_row.tier <= 2:
                reasons.append(f"Elite tier {player_row.tier} player available")
            
            # Value reasons
            if hasattr(player_row, 'consensus_adp') and hasattr(player_row, 'overall_rank'):
                value = player_row.overall_rank - player_row.consensus_adp
                if value > 10:
                    reasons.append(f"Excellent value - falling {value:.0f} picks")
            
            # Position scarcity
            position_count = len(available_df[available_df['position'] == player_row.position])
            if position_count < 5:
                reasons.append(f"Position scarcity - only {position_count} {player_row.position}s left")
            
            # Injury risk
            if hasattr(player_row, 'injury_risk_category') and player_row.injury_risk_category == 'Low':
                reasons.append("Low injury risk profile")
            
            # Age/experience
            if hasattr(player_row, 'age') and player_row.age >= 25 and player_row.age <= 28:
                reasons.append("Prime age for fantasy production")
            
            # Default reasons if none generated
            if not reasons:
                reasons = [
                    "Top projected points available",
                    "Best overall value at position", 
                    "Recommended by our algorithms"
                ]
            
        except Exception:
            reasons = [
                "Top available player",
                "Strong projection",
                "Good value pick"
            ]
        
        return reasons[:3]  # Return max 3 reasons
    
    def _generate_considerations(self, player_row: pd.Series, draft_state=None) -> List[str]:
        """Generate considerations and potential concerns"""
        
        considerations = []
        
        try:
            # Injury concerns
            if hasattr(player_row, 'injury_risk_category') and player_row.injury_risk_category == 'High':
                considerations.append("High injury risk - monitor health reports")
            
            # Age concerns
            if hasattr(player_row, 'age'):
                if player_row.age < 23:
                    considerations.append("Young player - potential inconsistency")
                elif player_row.age > 30:
                    considerations.append("Veteran age - possible decline risk")
            
            # ADP vs rank
            if hasattr(player_row, 'consensus_adp') and hasattr(player_row, 'overall_rank'):
                value = player_row.overall_rank - player_row.consensus_adp
                if value < -10:
                    considerations.append(f"Reaching {abs(value):.0f} picks above ADP")
            
            # Team situation (placeholder)
            considerations.append("Monitor team depth chart changes")
            
            # Consistency
            if hasattr(player_row, 'confidence') and player_row.confidence == 'Low':
                considerations.append("Lower projection confidence")
            
            # Default considerations
            if not considerations:
                considerations = [
                    "Standard fantasy risks apply",
                    "Monitor news before drafting",
                    "Consider team needs balance"
                ]
            
        except Exception:
            considerations = [
                "Monitor injury reports",
                "Check recent news",
                "Consider positional balance"
            ]
        
        return considerations[:3]  # Return max 3 considerations


def render_pick_now_view(projections_df: pd.DataFrame, draft_state=None, dynamic_vorp_calc=None) -> Optional[Dict[str, Any]]:
    """
    Convenience function to render Pick Now view
    
    Returns:
        Dict with selected player info if pick made, None otherwise
    """
    view = PickNowView()
    return view.render(projections_df, draft_state, dynamic_vorp_calc)
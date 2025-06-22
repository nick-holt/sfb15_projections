"""
Mission Control Header Component
Always-visible draft status and context management
"""

import streamlit as st
from datetime import datetime
from typing import Dict, Any, Optional
import time

from ...utils.mobile_detection import detect_mobile_device, get_responsive_config


class MissionControl:
    """Mission Control Header - Always visible draft context"""
    
    def __init__(self):
        self.responsive_config = get_responsive_config()
        self.is_mobile = detect_mobile_device()
        
    def render(self, draft_state=None, projections_data=None) -> Dict[str, Any]:
        """
        Render mission control header
        
        Args:
            draft_state: Current draft state from DraftManager
            projections_data: Player projections data
            
        Returns:
            Dict with current mode and context settings
        """
        # Apply mission control CSS
        st.markdown("""
        <div class="mission-control">
        """, unsafe_allow_html=True)
        
        # Main header row
        if self.is_mobile:
            return self._render_mobile_header(draft_state, projections_data)
        else:
            return self._render_desktop_header(draft_state, projections_data)
    
    def _render_desktop_header(self, draft_state, projections_data) -> Dict[str, Any]:
        """Render desktop version of mission control header"""
        
        col1, col2, col3, col4, col5 = st.columns([3, 1, 1, 1, 1])
        
        with col1:
            st.markdown("### 🏈 SFB15 Draft Command Center")
            if projections_data is not None:
                st.caption(f"Enhanced ML Projections • {len(projections_data)} Players")
        
        # Draft status indicator
        with col2:
            if draft_state and hasattr(draft_state, 'status'):
                if draft_state.status == 'in_progress':
                    current_pick = getattr(draft_state, 'current_pick', 1)
                    st.success(f"🔴 LIVE")
                    st.caption(f"Pick #{current_pick}")
                elif draft_state.status == 'complete':
                    st.info("✅ Complete")
                else:
                    st.warning("⏸️ Paused") 
            else:
                st.info("📊 Analysis Mode")
                st.caption("No active draft")
        
        # Time pressure indicator
        with col3:
            time_remaining = self._get_time_remaining(draft_state)
            if time_remaining:
                if time_remaining < 30:
                    st.error(f"⏱️ {time_remaining}s")
                    st.markdown('<div class="urgent-indicator">URGENT!</div>', unsafe_allow_html=True)
                elif time_remaining < 60:
                    st.warning(f"⏱️ {time_remaining}s")
                    st.caption("Time pressure")
                else:
                    st.info(f"⏱️ {time_remaining}s")
                    st.caption("Comfortable")
            else:
                st.metric("Time", "∞")
                st.caption("No timer")
        
        # Next pick indicator
        with col4:
            next_pick = self._get_next_pick_number(draft_state)
            if next_pick:
                picks_away = next_pick - self._get_current_pick(draft_state)
                if picks_away <= 1:
                    st.error(f"#{next_pick}")
                    st.caption("YOUR TURN!")
                elif picks_away <= 3:
                    st.warning(f"#{next_pick}")
                    st.caption(f"{picks_away} picks away")
                else:
                    st.info(f"#{next_pick}")
                    st.caption(f"{picks_away} picks away")
            else:
                st.metric("Next Pick", "TBD")
        
        # Mode toggle
        with col5:
            current_mode = st.session_state.get('ui_mode', 'analysis')
            
            # Only show draft mode if we have an active draft
            if draft_state and hasattr(draft_state, 'status') and draft_state.status == 'in_progress':
                mode_options = ["🎯 Draft", "📊 Analyze"]
                default_index = 0 if current_mode == 'draft' else 1
            else:
                mode_options = ["📊 Analyze", "🎮 Mock Draft"]
                default_index = 0 if current_mode == 'analysis' else 1
            
            selected_mode = st.radio(
                "Mode",
                mode_options,
                index=default_index,
                horizontal=True,
                key="mode_selector"
            )
            
            # Update session state
            if selected_mode == "🎯 Draft":
                st.session_state.ui_mode = 'draft'
            elif selected_mode == "🎮 Mock Draft":
                st.session_state.ui_mode = 'mock_draft'
            else:
                st.session_state.ui_mode = 'analysis'
        
        st.markdown("</div>", unsafe_allow_html=True)
        
        return {
            'mode': st.session_state.ui_mode,
            'draft_active': draft_state and draft_state.status == 'in_progress',
            'time_pressure': time_remaining and time_remaining < 60,
            'your_turn': self._is_your_turn(draft_state),
            'responsive_config': self.responsive_config
        }
    
    def _render_mobile_header(self, draft_state, projections_data) -> Dict[str, Any]:
        """Render mobile version of mission control header"""
        
        # Mobile: Stack vertically, show essential info only
        st.markdown("### 🏈 SFB15 Command Center")
        
        # Status row
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if draft_state and hasattr(draft_state, 'status'):
                if draft_state.status == 'in_progress':
                    st.success("🔴 LIVE")
                else:
                    st.info("📊 Analysis")
            else:
                st.info("📊 Analysis")
        
        with col2:
            time_remaining = self._get_time_remaining(draft_state)
            if time_remaining and time_remaining < 60:
                st.error(f"⏱️ {time_remaining}s")
            elif time_remaining:
                st.info(f"⏱️ {time_remaining}s")
            else:
                st.metric("Time", "∞")
        
        with col3:
            if self._is_your_turn(draft_state):
                st.error("YOUR TURN!")
            else:
                next_pick = self._get_next_pick_number(draft_state)
                if next_pick:
                    current = self._get_current_pick(draft_state)
                    picks_away = next_pick - current
                    st.info(f"{picks_away} picks")
                else:
                    st.info("Ready")
        
        # Mode selector - simplified for mobile
        current_mode = st.session_state.get('ui_mode', 'analysis')
        
        if draft_state and hasattr(draft_state, 'status') and draft_state.status == 'in_progress':
            mode_options = ["🎯 Draft", "📊 Analyze"]
            default_index = 0 if current_mode == 'draft' else 1
        else:
            mode_options = ["📊 Analyze"]
            default_index = 0
        
        selected_mode = st.selectbox(
            "Mode",
            mode_options,
            index=default_index,
            key="mobile_mode_selector"
        )
        
        # Update session state
        if selected_mode == "🎯 Draft":
            st.session_state.ui_mode = 'draft'
        else:
            st.session_state.ui_mode = 'analysis'
        
        return {
            'mode': st.session_state.ui_mode,
            'draft_active': draft_state and draft_state.status == 'in_progress',
            'time_pressure': time_remaining and time_remaining < 60,
            'your_turn': self._is_your_turn(draft_state),
            'responsive_config': self.responsive_config
        }
    
    def _get_time_remaining(self, draft_state) -> Optional[int]:
        """Get time remaining for current pick"""
        if not draft_state or not hasattr(draft_state, 'current_pick_start_time'):
            return None
        
        try:
            pick_timer = getattr(draft_state.settings, 'pick_timer', 120)  # Default 2 minutes
            start_time = draft_state.current_pick_start_time
            
            if start_time:
                elapsed = time.time() - start_time
                remaining = max(0, pick_timer - elapsed)
                return int(remaining)
            
            return None
        except Exception:
            return None
    
    def _get_current_pick(self, draft_state) -> int:
        """Get current overall pick number"""
        if not draft_state:
            return 1
        
        try:
            return getattr(draft_state, 'current_pick', 1)
        except Exception:
            return 1
    
    def _get_next_pick_number(self, draft_state) -> Optional[int]:
        """Get your next pick number"""
        if not draft_state or not hasattr(draft_state, 'settings'):
            return None
        
        try:
            # This would need to be calculated based on draft order and current pick
            # For now, return None - this will be implemented when draft state is fully integrated
            return None
        except Exception:
            return None
    
    def _is_your_turn(self, draft_state) -> bool:
        """Check if it's currently your turn to pick"""
        if not draft_state:
            return False
        
        try:
            # This would check if current pick belongs to user
            # Implementation depends on how user identity is tracked in draft_state
            return False
        except Exception:
            return False
    
    def render_alerts(self, draft_state=None) -> None:
        """Render urgent alerts and notifications"""
        
        alerts = []
        
        # Time pressure alerts
        time_remaining = self._get_time_remaining(draft_state)
        if time_remaining and time_remaining < 30:
            alerts.append({
                'type': 'error',
                'message': f"🚨 URGENT: Only {time_remaining} seconds remaining!"
            })
        
        # Your turn alerts
        if self._is_your_turn(draft_state):
            alerts.append({
                'type': 'error',
                'message': "🎯 YOUR TURN TO PICK!"
            })
        
        # Position run alerts (placeholder - would integrate with analytics)
        # if position_run_detected:
        #     alerts.append({
        #         'type': 'warning',
        #         'message': f"🏃 {position} RUN DETECTED - Act fast!"
        #     })
        
        # Render alerts
        for alert in alerts:
            if alert['type'] == 'error':
                st.error(alert['message'])
            elif alert['type'] == 'warning':
                st.warning(alert['message'])
            elif alert['type'] == 'info':
                st.info(alert['message'])
            elif alert['type'] == 'success':
                st.success(alert['message'])


def render_mission_control(draft_state=None, projections_data=None) -> Dict[str, Any]:
    """
    Convenience function to render mission control header
    
    Returns:
        Dict with current UI context
    """
    mission_control = MissionControl()
    context = mission_control.render(draft_state, projections_data)
    mission_control.render_alerts(draft_state)
    
    return context 
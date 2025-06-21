#!/usr/bin/env python3
"""
ADP Analyzer for SFB15 Fantasy Football Dashboard
Advanced ADP analytics and value identification
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
import logging

class ADPAnalyzer:
    """Advanced ADP analysis and value identification"""
    
    def __init__(self):
        self.logger = self._setup_logging()
        
    def _setup_logging(self) -> logging.Logger:
        """Setup logging for ADP analyzer"""
        logger = logging.getLogger('ADPAnalyzer')
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            
        return logger
    
    def calculate_adp_value_metrics(self, projections_df: pd.DataFrame, adp_df: pd.DataFrame) -> pd.DataFrame:
        """Calculate comprehensive ADP value metrics"""
        try:
            # John Carmack approach: normalize only valid names during join
            from src.utils.name_normalizer import name_normalizer
            
            # Filter ADP data to only valid names and normalize
            adp_valid = adp_df[adp_df['name'].notna()].copy()
            adp_valid['normalized_name'] = adp_valid['name'].apply(name_normalizer.normalize_name)
            
            # Normalize projection names
            proj_norm = projections_df.copy()
            proj_norm['normalized_name'] = proj_norm['player_name'].apply(name_normalizer.normalize_name)
            
            # Merge on normalized names
            merged_df = pd.merge(
                proj_norm, 
                adp_valid, 
                on='normalized_name', 
                how='inner'
            )
            
            # Clean up
            merged_df = merged_df.drop(columns=['normalized_name'])
            
            if merged_df.empty:
                self.logger.warning("No matching players found for ADP analysis")
                return pd.DataFrame()
            
            # Handle position column naming conflict
            # After merge, we get position_x (from projections) and position_y (from ADP)
            # Use position from projections as it's more reliable for our analysis
            if 'position_x' in merged_df.columns:
                merged_df['position'] = merged_df['position_x']
            elif 'position' not in merged_df.columns and 'position_y' in merged_df.columns:
                merged_df['position'] = merged_df['position_y']
            
            # Calculate ranking metrics
            merged_df['projection_rank'] = merged_df['projected_points'].rank(ascending=False, method='min')
            merged_df['adp_rank'] = merged_df['consensus_adp'].rank(method='min')
            
            # Calculate value metrics
            merged_df['adp_value'] = merged_df['adp_rank'] - merged_df['projection_rank']
            merged_df['value_per_round'] = merged_df['adp_value'] / 12  # Assuming 12-team leagues
            
            # Position-specific rankings
            position_ranks = merged_df.groupby('position').apply(
                lambda x: x.assign(
                    position_proj_rank=x['projected_points'].rank(ascending=False, method='min'),
                    position_adp_rank=x['consensus_adp'].rank(method='min')
                )
            ).reset_index(drop=True)
            
            merged_df = position_ranks.copy()
            merged_df['position_value'] = merged_df['position_adp_rank'] - merged_df['position_proj_rank']
            
            # Calculate value tiers
            merged_df['value_tier'] = self._assign_value_tiers(merged_df['adp_value'])
            
            # Calculate draft urgency (how soon player will likely be drafted)
            merged_df['draft_urgency'] = self._calculate_draft_urgency(merged_df)
            
            self.logger.info(f"Calculated ADP value metrics for {len(merged_df)} players")
            return merged_df
            
        except Exception as e:
            self.logger.error(f"Error calculating ADP value metrics: {str(e)}")
            return pd.DataFrame()
    
    def _assign_value_tiers(self, adp_values: pd.Series) -> List[str]:
        """Assign value tiers based on ADP vs projection gaps"""
        tiers = []
        
        for value in adp_values:
            if value >= 30:
                tiers.append("Elite Value")
            elif value >= 15:
                tiers.append("Great Value")
            elif value >= 5:
                tiers.append("Good Value")
            elif value >= -5:
                tiers.append("Fair Value")
            elif value >= -15:
                tiers.append("Slight Reach")
            else:
                tiers.append("Significant Reach")
        
        return tiers
    
    def _calculate_draft_urgency(self, df: pd.DataFrame) -> List[str]:
        """Calculate how urgently a player should be drafted"""
        urgency = []
        
        for _, row in df.iterrows():
            adp = row['consensus_adp']
            value = row['adp_value']
            
            if value > 20 and adp > 100:
                urgency.append("Late Round Steal")
            elif value > 15:
                urgency.append("High Priority")
            elif value > 5:
                urgency.append("Target")
            elif value > -5:
                urgency.append("Monitor")
            else:
                urgency.append("Avoid")
        
        return urgency
    
    def identify_sleepers(self, value_df: pd.DataFrame, min_value_gap: float = 15) -> pd.DataFrame:
        """Identify sleeper candidates based on ADP vs projection value"""
        try:
            sleepers = value_df[
                (value_df['adp_value'] >= min_value_gap) & 
                (value_df['consensus_adp'] >= 50)  # Later round picks
            ].copy()
            
            # Sort by value gap
            sleepers = sleepers.sort_values('adp_value', ascending=False)
            
            # Add sleeper score
            sleepers['sleeper_score'] = self._calculate_sleeper_score(sleepers)
            
            self.logger.info(f"Identified {len(sleepers)} sleeper candidates")
            return sleepers
            
        except Exception as e:
            self.logger.error(f"Error identifying sleepers: {str(e)}")
            return pd.DataFrame()
    
    def _calculate_sleeper_score(self, df: pd.DataFrame) -> List[float]:
        """Calculate comprehensive sleeper score"""
        scores = []
        
        for _, row in df.iterrows():
            # Base score from ADP value
            base_score = min(row['adp_value'] / 30 * 100, 100)
            
            # Bonus for later ADP (more upside potential)
            adp_bonus = min((row['consensus_adp'] - 50) / 100 * 20, 20)
            
            # Bonus for younger players (if age available)
            age_bonus = 0
            if pd.notna(row.get('age')):
                if row['age'] <= 25:
                    age_bonus = 10
                elif row['age'] <= 27:
                    age_bonus = 5
            
            # Position scarcity bonus
            position_bonus = 0
            if row['position'] in ['RB', 'TE']:
                position_bonus = 5
            
            total_score = base_score + adp_bonus + age_bonus + position_bonus
            scores.append(min(total_score, 100))
        
        return scores
    
    def identify_busts(self, value_df: pd.DataFrame, min_reach: float = -20) -> pd.DataFrame:
        """Identify potential bust candidates (overvalued by ADP)"""
        try:
            busts = value_df[
                (value_df['adp_value'] <= min_reach) & 
                (value_df['consensus_adp'] <= 100)  # Early round picks
            ].copy()
            
            # Sort by biggest reaches
            busts = busts.sort_values('adp_value', ascending=True)
            
            # Add bust risk score
            busts['bust_risk'] = self._calculate_bust_risk(busts)
            
            self.logger.info(f"Identified {len(busts)} potential bust candidates")
            return busts
            
        except Exception as e:
            self.logger.error(f"Error identifying busts: {str(e)}")
            return pd.DataFrame()
    
    def _calculate_bust_risk(self, df: pd.DataFrame) -> List[float]:
        """Calculate bust risk score"""
        risks = []
        
        for _, row in df.iterrows():
            # Base risk from negative ADP value
            base_risk = min(abs(row['adp_value']) / 30 * 100, 100)
            
            # Higher risk for earlier ADP
            adp_risk = max((100 - row['consensus_adp']) / 100 * 30, 0)
            
            # Age risk (older players more risky)
            age_risk = 0
            if pd.notna(row.get('age')):
                if row['age'] >= 30:
                    age_risk = 15
                elif row['age'] >= 28:
                    age_risk = 10
            
            total_risk = base_risk + adp_risk + age_risk
            risks.append(min(total_risk, 100))
        
        return risks
    
    def analyze_positional_adp_trends(self, value_df: pd.DataFrame) -> Dict[str, Dict]:
        """Analyze ADP trends by position"""
        try:
            position_analysis = {}
            
            for position in value_df['position'].unique():
                pos_data = value_df[value_df['position'] == position]
                
                analysis = {
                    'total_players': len(pos_data),
                    'avg_adp': pos_data['consensus_adp'].mean(),
                    'avg_projection': pos_data['projected_points'].mean(),
                    'avg_value_gap': pos_data['adp_value'].mean(),
                    'value_opportunities': len(pos_data[pos_data['adp_value'] > 10]),
                    'potential_reaches': len(pos_data[pos_data['adp_value'] < -10]),
                    'top_values': pos_data.nlargest(3, 'adp_value')[['player_name', 'adp_value']].to_dict('records'),
                    'biggest_reaches': pos_data.nsmallest(3, 'adp_value')[['player_name', 'adp_value']].to_dict('records')
                }
                
                position_analysis[position] = analysis
            
            self.logger.info(f"Analyzed ADP trends for {len(position_analysis)} positions")
            return position_analysis
            
        except Exception as e:
            self.logger.error(f"Error analyzing positional ADP trends: {str(e)}")
            return {}
    
    def generate_draft_strategy_recommendations(self, value_df: pd.DataFrame, draft_position: int = 6, 
                                              num_teams: int = 12) -> Dict[str, List]:
        """Generate draft strategy recommendations based on ADP analysis"""
        try:
            recommendations = {
                'early_round_targets': [],
                'middle_round_values': [],
                'late_round_sleepers': [],
                'players_to_avoid': [],
                'positional_strategy': {}
            }
            
            # Calculate draft picks for this position
            picks = [draft_position + (round_num * num_teams) for round_num in range(16)]
            if draft_position > num_teams / 2:  # Snake draft adjustment
                picks = [draft_position + (round_num * num_teams) if round_num % 2 == 0 
                        else (num_teams * (round_num + 1)) - draft_position + 1 
                        for round_num in range(16)]
            
            # Early round targets (first 5 rounds)
            early_picks = [p for p in picks[:5]]
            early_targets = value_df[
                (value_df['consensus_adp'].between(min(early_picks) - 12, max(early_picks) + 12)) &
                (value_df['adp_value'] > 0)
            ].nlargest(10, 'adp_value')
            
            recommendations['early_round_targets'] = early_targets[['player_name', 'position', 'consensus_adp', 'adp_value']].to_dict('records')
            
            # Middle round values (rounds 6-10)
            middle_picks = [p for p in picks[5:10]]
            middle_values = value_df[
                (value_df['consensus_adp'].between(min(middle_picks) - 12, max(middle_picks) + 12)) &
                (value_df['adp_value'] > 5)
            ].nlargest(15, 'adp_value')
            
            recommendations['middle_round_values'] = middle_values[['player_name', 'position', 'consensus_adp', 'adp_value']].to_dict('records')
            
            # Late round sleepers (rounds 11+)
            late_picks = [p for p in picks[10:]]
            sleepers = value_df[
                (value_df['consensus_adp'] >= min(late_picks)) &
                (value_df['adp_value'] > 10)
            ].nlargest(20, 'adp_value')
            
            recommendations['late_round_sleepers'] = sleepers[['player_name', 'position', 'consensus_adp', 'adp_value']].to_dict('records')
            
            # Players to avoid
            avoid_players = value_df[
                (value_df['adp_value'] < -15) &
                (value_df['consensus_adp'] <= 120)
            ].nsmallest(10, 'adp_value')
            
            recommendations['players_to_avoid'] = avoid_players[['player_name', 'position', 'consensus_adp', 'adp_value']].to_dict('records')
            
            # Positional strategy
            for position in ['QB', 'RB', 'WR', 'TE']:
                pos_data = value_df[value_df['position'] == position]
                if not pos_data.empty:
                    recommendations['positional_strategy'][position] = {
                        'best_values': pos_data.nlargest(5, 'adp_value')[['player_name', 'consensus_adp', 'adp_value']].to_dict('records'),
                        'recommended_rounds': self._get_recommended_draft_rounds(pos_data, position)
                    }
            
            self.logger.info("Generated comprehensive draft strategy recommendations")
            return recommendations
            
        except Exception as e:
            self.logger.error(f"Error generating draft strategy recommendations: {str(e)}")
            return {}
    
    def _get_recommended_draft_rounds(self, pos_data: pd.DataFrame, position: str) -> List[int]:
        """Get recommended draft rounds for a position based on value"""
        try:
            # Find rounds with best value opportunities
            pos_data = pos_data.copy()  # Fix SettingWithCopyWarning
            pos_data['draft_round'] = ((pos_data['consensus_adp'] - 1) // 12) + 1
            
            round_values = pos_data.groupby('draft_round')['adp_value'].agg(['mean', 'count']).reset_index()
            round_values = round_values[round_values['count'] >= 2]  # At least 2 players in round
            
            # Recommend rounds with positive average value
            recommended = round_values[round_values['mean'] > 0]['draft_round'].tolist()
            
            # Position-specific logic
            if position == 'QB':
                # QBs typically have value in middle-late rounds
                recommended = [r for r in recommended if r >= 6]
            elif position == 'RB':
                # RBs are valuable early, but also late
                recommended = [r for r in recommended if r <= 8 or r >= 12]
            elif position == 'TE':
                # TEs often have value in middle rounds
                recommended = [r for r in recommended if 4 <= r <= 10]
            
            return sorted(recommended)[:3]  # Top 3 recommended rounds
            
        except Exception as e:
            self.logger.error(f"Error getting recommended rounds for {position}: {str(e)}")
            return []
    
    def calculate_market_efficiency_score(self, value_df: pd.DataFrame) -> Dict[str, float]:
        """Calculate overall market efficiency metrics"""
        try:
            # Calculate various efficiency metrics
            total_players = len(value_df)
            
            # Value distribution
            undervalued = len(value_df[value_df['adp_value'] > 10])
            overvalued = len(value_df[value_df['adp_value'] < -10])
            fairly_valued = total_players - undervalued - overvalued
            
            # Market efficiency score (0-100, higher = more efficient)
            efficiency_score = (fairly_valued / total_players) * 100
            
            # Average absolute value gap
            avg_abs_gap = value_df['adp_value'].abs().mean()
            
            # Position efficiency
            position_efficiency = {}
            for position in value_df['position'].unique():
                pos_data = value_df[value_df['position'] == position]
                pos_efficiency = (len(pos_data[pos_data['adp_value'].abs() <= 10]) / len(pos_data)) * 100
                position_efficiency[position] = pos_efficiency
            
            metrics = {
                'overall_efficiency': efficiency_score,
                'avg_value_gap': avg_abs_gap,
                'undervalued_players': undervalued,
                'overvalued_players': overvalued,
                'fairly_valued_players': fairly_valued,
                'position_efficiency': position_efficiency
            }
            
            self.logger.info(f"Calculated market efficiency score: {efficiency_score:.1f}%")
            return metrics
            
        except Exception as e:
            self.logger.error(f"Error calculating market efficiency: {str(e)}")
            return {}
    
    def get_adp_alerts(self, value_df: pd.DataFrame, alert_threshold: float = 20) -> List[Dict]:
        """Generate ADP-based alerts for significant value opportunities"""
        try:
            alerts = []
            
            # High value alerts
            high_value_players = value_df[value_df['adp_value'] >= alert_threshold]
            for _, player in high_value_players.iterrows():
                alerts.append({
                    'type': 'value_opportunity',
                    'priority': 'high',
                    'player': player['player_name'],
                    'position': player['position'],
                    'message': f"{player['player_name']} ({player['position']}) has {player['adp_value']:.1f} rounds of value (ADP: {player['consensus_adp']:.1f})",
                    'adp': player['consensus_adp'],
                    'value_gap': player['adp_value']
                })
            
            # Bust alerts
            bust_players = value_df[value_df['adp_value'] <= -alert_threshold]
            for _, player in bust_players.iterrows():
                alerts.append({
                    'type': 'bust_warning',
                    'priority': 'medium',
                    'player': player['player_name'],
                    'position': player['position'],
                    'message': f"{player['player_name']} ({player['position']}) may be overvalued by {abs(player['adp_value']):.1f} rounds (ADP: {player['consensus_adp']:.1f})",
                    'adp': player['consensus_adp'],
                    'value_gap': player['adp_value']
                })
            
            # Sort alerts by priority and value gap
            priority_order = {'high': 0, 'medium': 1, 'low': 2}
            alerts.sort(key=lambda x: (priority_order[x['priority']], -abs(x['value_gap'])))
            
            self.logger.info(f"Generated {len(alerts)} ADP alerts")
            return alerts[:20]  # Return top 20 alerts
            
        except Exception as e:
            self.logger.error(f"Error generating ADP alerts: {str(e)}")
            return [] 
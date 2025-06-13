"""
Feature Engineering Audit - P0 Critical Analysis

This script audits our current feature engineering against what's needed
to properly differentiate elite players and match industry projection ranges.

Based on raw predictions vs FootballGuys analysis.
"""

import pandas as pd
import numpy as np
import os
import pickle
from collections import defaultdict

class FeatureEngineeringAuditor:
    """Audit current features and identify gaps for better modeling"""
    
    def __init__(self):
        self.historical_data = None
        self.current_features = {}
        self.position_requirements = {}
        self.setup_position_requirements()
        
    def setup_position_requirements(self):
        """Define what features each position needs for elite differentiation"""
        
        self.position_requirements = {
            'QB': {
                'critical_missing': [
                    'rushing_attempts_per_game',
                    'designed_runs_percentage', 
                    'goal_line_rush_rate',
                    'red_zone_rush_attempts',
                    'qb_rating_under_pressure',
                    'mobility_score'
                ],
                'current_gaps': [
                    'Team offensive pace',
                    'Red zone passing efficiency', 
                    'Air yards per attempt trends',
                    'Pocket time metrics'
                ],
                'elite_separators': [
                    'Rushing upside (Lamar, Josh Allen type)',
                    'Red zone rushing opportunities',
                    'Designed QB runs vs scrambles'
                ]
            },
            'RB': {
                'critical_missing': [
                    'snap_count_percentage',
                    'target_share',
                    'red_zone_carries_per_game',
                    'goal_line_touches',
                    'third_down_usage_rate',
                    'two_minute_drill_usage'
                ],
                'current_gaps': [
                    'Workload sustainability metrics',
                    'Pass-catching role evolution',
                    'Goal line opportunity share'
                ],
                'elite_separators': [
                    'Three-down versatility',
                    'Red zone efficiency',
                    'Target share in passing game'
                ]
            },
            'WR': {
                'critical_missing': [
                    'target_share',
                    'air_yards_share', 
                    'red_zone_targets_per_game',
                    'snap_count_percentage',
                    'slot_vs_outside_rate',
                    'deep_target_rate'
                ],
                'current_gaps': [
                    'Route running metrics',
                    'Separation vs coverage type',
                    'Target quality (air yards)',
                    'Red zone role definition'
                ],
                'elite_separators': [
                    'Target dominance (20%+ share)',
                    'Red zone target priority', 
                    'High-value route running'
                ]
            },
            'TE': {
                'critical_missing': [
                    'route_participation_rate',
                    'inline_vs_slot_usage',
                    'red_zone_targets_per_game',
                    'snap_count_percentage',
                    'blocking_snap_percentage'
                ],
                'current_gaps': [
                    'Role definition (receiving vs blocking)',
                    'Route tree complexity',
                    'Red zone usage patterns'
                ],
                'elite_separators': [
                    'Primary receiving role vs blocking',
                    'Red zone target share',
                    'Route diversity'
                ]
            }
        }
    
    def load_and_analyze_current_features(self):
        """Load current data and analyze existing feature coverage"""
        
        print("🔍 AUDITING CURRENT FEATURE ENGINEERING")
        print("=" * 60)
        
        # Load historical data
        try:
            self.historical_data = pd.read_parquet('data/processed/season_stats.parquet')
            print(f"✅ Loaded {len(self.historical_data)} historical records")
        except Exception as e:
            print(f"❌ Error loading historical data: {e}")
            return False
        
        # Load current model features
        positions = ['qb', 'rb', 'wr', 'te']
        for position in positions:
            feature_path = f'models/final_proper/{position}/feature_columns.pkl'
            if os.path.exists(feature_path):
                try:
                    with open(feature_path, 'rb') as f:
                        self.current_features[position.upper()] = pickle.load(f)
                    print(f"✅ Loaded {len(self.current_features[position.upper()])} features for {position.upper()}")
                except Exception as e:
                    print(f"❌ Error loading {position} features: {e}")
        
        return True
    
    def analyze_data_availability(self):
        """Check what data we have available for creating missing features"""
        
        print(f"\n🗂️  DATA AVAILABILITY ANALYSIS")
        print("=" * 60)
        
        # Check available columns in historical data
        available_cols = list(self.historical_data.columns)
        print(f"📊 Available columns in historical data: {len(available_cols)}")
        
        # Categorize available data
        stat_categories = {
            'passing': [col for col in available_cols if 'pass' in col.lower()],
            'rushing': [col for col in available_cols if 'rush' in col.lower()],
            'receiving': [col for col in available_cols if any(x in col.lower() for x in ['receiv', 'target', 'catch'])],
            'scoring': [col for col in available_cols if any(x in col.lower() for x in ['touchdown', 'td', 'points'])],
            'efficiency': [col for col in available_cols if any(x in col.lower() for x in ['avg', 'per', 'rate', 'pct'])],
            'situational': [col for col in available_cols if any(x in col.lower() for x in ['red', 'goal', 'third', 'fourth'])]
        }
        
        print(f"\n📈 Available stat categories:")
        for category, cols in stat_categories.items():
            print(f"  {category.title()}: {len(cols)} columns")
            if len(cols) <= 10:  # Show details for smaller categories
                for col in cols[:5]:
                    print(f"    - {col}")
                if len(cols) > 5:
                    print(f"    ... and {len(cols)-5} more")
        
        return stat_categories
    
    def identify_feature_gaps(self):
        """Identify specific feature gaps by position"""
        
        print(f"\n🚨 CRITICAL FEATURE GAPS BY POSITION")
        print("=" * 60)
        
        gap_analysis = {}
        
        for position in ['QB', 'RB', 'WR', 'TE']:
            if position in self.current_features:
                current_feats = self.current_features[position]
                requirements = self.position_requirements[position]
                
                print(f"\n--- {position} ANALYSIS ---")
                print(f"Current features: {len(current_feats)}")
                
                # Check for critical missing features
                missing_critical = []
                for feat in requirements['critical_missing']:
                    if not any(feat.lower() in cf.lower() for cf in current_feats):
                        missing_critical.append(feat)
                
                if missing_critical:
                    print(f"🔴 Critical missing features ({len(missing_critical)}):")
                    for feat in missing_critical:
                        print(f"   - {feat}")
                
                # Show current feature sample
                print(f"📝 Current feature sample:")
                for feat in current_feats[:8]:
                    print(f"   ✓ {feat}")
                if len(current_feats) > 8:
                    print(f"   ... and {len(current_feats)-8} more")
                
                gap_analysis[position] = {
                    'total_current': len(current_feats),
                    'missing_critical': missing_critical,
                    'gap_count': len(missing_critical)
                }
        
        return gap_analysis
    
    def analyze_elite_player_separation(self):
        """Analyze how well current features separate elite from average players"""
        
        print(f"\n⭐ ELITE PLAYER SEPARATION ANALYSIS")
        print("=" * 60)
        
        # For each position, look at top performers vs average
        for position in ['QB', 'RB', 'WR', 'TE']:
            print(f"\n--- {position} Elite Separation ---")
            
            pos_data = self.historical_data[self.historical_data['position'] == position]
            
            if len(pos_data) == 0:
                continue
            
            # Get recent seasons for better relevance
            recent_data = pos_data[pos_data['season'] >= 2022]
            
            if len(recent_data) < 20:
                recent_data = pos_data  # Fall back to all data
            
            # Define elite (top 10%) and average (40-60%)
            elite_threshold = recent_data['total_points'].quantile(0.9)
            avg_lower = recent_data['total_points'].quantile(0.4)
            avg_upper = recent_data['total_points'].quantile(0.6)
            
            elite_players = recent_data[recent_data['total_points'] >= elite_threshold]
            avg_players = recent_data[(recent_data['total_points'] >= avg_lower) & 
                                    (recent_data['total_points'] <= avg_upper)]
            
            print(f"Elite players (top 10%): {len(elite_players)}")
            print(f"Average players (40-60%): {len(avg_players)}")
            print(f"Elite threshold: {elite_threshold:.1f} points")
            
            # Show some elite examples
            if len(elite_players) > 0:
                top_examples = elite_players.nlargest(3, 'total_points')
                print(f"Top elite examples:")
                for _, player in top_examples.iterrows():
                    print(f"  {player.get('player_name', 'Unknown')} ({player['season']}): {player['total_points']:.1f} pts")
    
    def recommend_feature_improvements(self):
        """Provide specific recommendations for feature engineering improvements"""
        
        print(f"\n🎯 FEATURE ENGINEERING RECOMMENDATIONS")
        print("=" * 60)
        
        recommendations = {
            'immediate_wins': [],
            'medium_term': [],
            'data_needed': []
        }
        
        # Immediate wins - features we can create from existing data
        print(f"\n🚀 IMMEDIATE WINS (from existing data):")
        immediate_features = [
            "Career rushing yards per game (QB)",
            "Historical red zone touches (RB)",
            "Target share percentage calculation (WR/TE)",
            "Games with 100+ yards trends",
            "Season-over-season improvement rates"
        ]
        
        for feat in immediate_features:
            print(f"  ✅ {feat}")
            recommendations['immediate_wins'].append(feat)
        
        # Medium term - require some data enhancement
        print(f"\n⏳ MEDIUM TERM (enhanced data needed):")
        medium_features = [
            "Snap count percentages (need snap data)",
            "Route participation rates (need route data)", 
            "Red zone opportunity shares (need situational data)",
            "Team pace and efficiency metrics",
            "Air yards and target quality metrics"
        ]
        
        for feat in medium_features:
            print(f"  🔶 {feat}")
            recommendations['medium_term'].append(feat)
        
        # Data needed
        print(f"\n📊 NEW DATA SOURCES NEEDED:")
        data_sources = [
            "Weekly snap count data (FantasyData API)",
            "Route running data (Pro Football Focus)",
            "Red zone situation breakdowns",
            "Team pace and efficiency stats",
            "Target separation and air yards data"
        ]
        
        for source in data_sources:
            print(f"  📈 {source}")
            recommendations['data_needed'].append(source)
        
        return recommendations
    
    def create_action_plan(self):
        """Create specific action plan for implementing improvements"""
        
        print(f"\n📋 IMPLEMENTATION ACTION PLAN")
        print("=" * 60)
        
        action_plan = [
            {
                'priority': 'P0 - Critical',
                'task': 'Create enhanced feature engineering pipeline',
                'subtasks': [
                    'Build QB rushing features from existing data',
                    'Calculate target shares for WR/TE from reception data',
                    'Create red zone usage metrics',
                    'Add career trend and efficiency features'
                ],
                'timeline': '1-2 days',
                'impact': 'High - Should improve elite separation immediately'
            },
            {
                'priority': 'P1 - High',
                'task': 'Enhance team context features',
                'subtasks': [
                    'Add team offensive pace metrics',
                    'Calculate red zone efficiency by team',
                    'Create scoring environment features',
                    'Add strength of schedule adjustments'
                ],
                'timeline': '2-3 days', 
                'impact': 'Medium-High - Better situational modeling'
            },
            {
                'priority': 'P2 - Medium',
                'task': 'External data integration',
                'subtasks': [
                    'Integrate snap count data if available',
                    'Add route running metrics if accessible',
                    'Enhance with target quality data'
                ],
                'timeline': '1 week',
                'impact': 'Medium - Depends on data availability'
            }
        ]
        
        for i, plan in enumerate(action_plan, 1):
            print(f"\n{i}. {plan['priority']}: {plan['task']}")
            print(f"   Timeline: {plan['timeline']}")
            print(f"   Impact: {plan['impact']}")
            print(f"   Subtasks:")
            for subtask in plan['subtasks']:
                print(f"     - {subtask}")
        
        return action_plan
    
    def run_full_audit(self):
        """Run the complete feature engineering audit"""
        
        print("🔍 STARTING COMPREHENSIVE FEATURE ENGINEERING AUDIT")
        print("=" * 70)
        
        # Load data and current features
        if not self.load_and_analyze_current_features():
            return None
        
        # Run all analyses
        stat_categories = self.analyze_data_availability()
        gap_analysis = self.identify_feature_gaps()
        self.analyze_elite_player_separation()
        recommendations = self.recommend_feature_improvements()
        action_plan = self.create_action_plan()
        
        # Save audit results
        audit_results = {
            'stat_categories': stat_categories,
            'gap_analysis': gap_analysis,
            'recommendations': recommendations,
            'action_plan': action_plan
        }
        
        # Save to file
        output_dir = 'analysis/feature_audit'
        os.makedirs(output_dir, exist_ok=True)
        
        import json
        with open(f'{output_dir}/feature_audit_results.json', 'w') as f:
            json.dump(audit_results, f, indent=2, default=str)
        
        print(f"\n💾 Audit results saved to: {output_dir}/feature_audit_results.json")
        print("\n🎯 NEXT STEPS: Begin P0 feature engineering improvements")
        
        return audit_results

def main():
    """Run the feature engineering audit"""
    auditor = FeatureEngineeringAuditor()
    results = auditor.run_full_audit()
    return results

if __name__ == "__main__":
    audit_results = main() 
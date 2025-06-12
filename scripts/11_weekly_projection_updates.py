"""
Weekly Projection Updates System

This script provides a framework for updating projections throughout the season
based on:
- Injury reports and player status changes
- Coaching staff changes and scheme updates  
- Trade impacts and depth chart changes
- Weekly performance adjustments
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os

class WeeklyProjectionUpdater:
    def __init__(self):
        self.base_projections = None
        self.current_projections = None
        self.update_log = []
        
    def load_base_projections(self):
        """Load the base season-long projections"""
        print("Loading base projections...")
        self.base_projections = pd.read_csv('projections/2025/fantasy_projections_2025.csv')
        self.current_projections = self.base_projections.copy()
        print(f"Loaded {len(self.base_projections)} base projections")
        
    def create_injury_update_framework(self):
        """Framework for applying injury updates"""
        
        # Example injury impact multipliers
        injury_impacts = {
            'out': 0.0,           # Player ruled out
            'doubtful': 0.2,      # Very unlikely to play
            'questionable': 0.7,   # 50/50 chance, reduced effectiveness
            'probable': 0.9,       # Likely to play, minimal impact
            'healthy': 1.0,        # No injury concerns
            'ir': 0.0,            # Injured reserve
            'suspended': 0.0       # Suspended
        }
        
        return injury_impacts
    
    def apply_injury_updates(self, injury_updates):
        """
        Apply injury status updates to projections
        
        injury_updates format:
        [
            {'player_name': 'Christian McCaffrey', 'status': 'questionable', 'weeks_affected': 1},
            {'player_name': 'Tyreek Hill', 'status': 'out', 'weeks_affected': 2},
        ]
        """
        print(f"Applying {len(injury_updates)} injury updates...")
        
        injury_impacts = self.create_injury_update_framework()
        
        for update in injury_updates:
            player_name = update['player_name']
            status = update['status']
            weeks_affected = update.get('weeks_affected', 1)
            
            # Find player in projections
            player_mask = self.current_projections['player_name'] == player_name
            
            if player_mask.any():
                # Calculate adjustment
                impact_multiplier = injury_impacts.get(status, 1.0)
                
                # Adjust based on weeks affected in season
                weeks_remaining = 17  # Could be dynamic based on current week
                season_impact = 1 - (weeks_affected / weeks_remaining) * (1 - impact_multiplier)
                
                # Store original projection for reference
                if 'original_projected_points' not in self.current_projections.columns:
                    self.current_projections['original_projected_points'] = self.current_projections['projected_points'].copy()
                
                # Apply adjustment
                original_points = self.current_projections.loc[player_mask, 'original_projected_points'].iloc[0]
                adjusted_points = original_points * season_impact
                
                self.current_projections.loc[player_mask, 'projected_points'] = adjusted_points
                
                # Log the update
                self.update_log.append({
                    'timestamp': datetime.now().isoformat(),
                    'player_name': player_name,
                    'update_type': 'injury',
                    'status': status,
                    'weeks_affected': weeks_affected,
                    'original_points': original_points,
                    'adjusted_points': adjusted_points,
                    'point_change': adjusted_points - original_points
                })
                
                print(f"  Updated {player_name}: {status} -> {adjusted_points:.1f} pts ({adjusted_points - original_points:+.1f})")
            else:
                print(f"  Warning: Player '{player_name}' not found in projections")
    
    def apply_depth_chart_changes(self, depth_chart_updates):
        """
        Apply depth chart changes (trades, releases, promotions)
        
        depth_chart_updates format:
        [
            {'player_name': 'Calvin Ridley', 'change_type': 'trade', 'new_team': 'TEN', 'target_share_change': 0.15},
            {'player_name': 'Jonathan Taylor', 'change_type': 'promotion', 'workload_change': 0.25},
        ]
        """
        print(f"Applying {len(depth_chart_updates)} depth chart changes...")
        
        for update in depth_chart_updates:
            player_name = update['player_name']
            change_type = update['change_type']
            
            player_mask = self.current_projections['player_name'] == player_name
            
            if player_mask.any():
                original_points = self.current_projections.loc[player_mask, 'projected_points'].iloc[0]
                
                if change_type == 'trade':
                    # Handle trade impact
                    new_team = update.get('new_team')
                    target_share_change = update.get('target_share_change', 0)
                    
                    # Update team
                    if new_team:
                        self.current_projections.loc[player_mask, 'team'] = new_team
                    
                    # Adjust projections based on new opportunity
                    adjustment_multiplier = 1 + target_share_change
                    adjusted_points = original_points * adjustment_multiplier
                    
                elif change_type == 'promotion':
                    # Handle role promotion (backup becomes starter, etc.)
                    workload_change = update.get('workload_change', 0)
                    adjustment_multiplier = 1 + workload_change
                    adjusted_points = original_points * adjustment_multiplier
                    
                elif change_type == 'demotion':
                    # Handle role demotion
                    workload_change = update.get('workload_change', 0)
                    adjustment_multiplier = 1 - workload_change
                    adjusted_points = original_points * adjustment_multiplier
                    
                else:
                    adjusted_points = original_points
                
                self.current_projections.loc[player_mask, 'projected_points'] = adjusted_points
                
                # Log the update
                self.update_log.append({
                    'timestamp': datetime.now().isoformat(),
                    'player_name': player_name,
                    'update_type': 'depth_chart',
                    'change_type': change_type,
                    'original_points': original_points,
                    'adjusted_points': adjusted_points,
                    'point_change': adjusted_points - original_points
                })
                
                print(f"  Updated {player_name}: {change_type} -> {adjusted_points:.1f} pts ({adjusted_points - original_points:+.1f})")
    
    def apply_performance_adjustments(self, performance_updates):
        """
        Apply performance-based adjustments (hot/cold streaks, coaching changes)
        
        performance_updates format:
        [
            {'player_name': 'Josh Allen', 'adjustment_type': 'hot_streak', 'multiplier': 1.1},
            {'player_name': 'Russell Wilson', 'adjustment_type': 'coaching_change', 'multiplier': 1.15},
        ]
        """
        print(f"Applying {len(performance_updates)} performance adjustments...")
        
        for update in performance_updates:
            player_name = update['player_name']
            adjustment_type = update['adjustment_type']
            multiplier = update.get('multiplier', 1.0)
            
            player_mask = self.current_projections['player_name'] == player_name
            
            if player_mask.any():
                original_points = self.current_projections.loc[player_mask, 'projected_points'].iloc[0]
                adjusted_points = original_points * multiplier
                
                self.current_projections.loc[player_mask, 'projected_points'] = adjusted_points
                
                # Log the update
                self.update_log.append({
                    'timestamp': datetime.now().isoformat(),
                    'player_name': player_name,
                    'update_type': 'performance',
                    'adjustment_type': adjustment_type,
                    'multiplier': multiplier,
                    'original_points': original_points,
                    'adjusted_points': adjusted_points,
                    'point_change': adjusted_points - original_points
                })
                
                print(f"  Updated {player_name}: {adjustment_type} -> {adjusted_points:.1f} pts ({adjusted_points - original_points:+.1f})")
    
    def recalculate_rankings(self):
        """Recalculate all rankings after updates"""
        print("Recalculating rankings...")
        
        # Overall rankings
        self.current_projections['overall_rank'] = self.current_projections['projected_points'].rank(
            ascending=False, method='min'
        )
        
        # Position rankings
        for position in ['QB', 'RB', 'WR', 'TE']:
            pos_mask = self.current_projections['position'] == position
            self.current_projections.loc[pos_mask, 'position_rank'] = (
                self.current_projections.loc[pos_mask, 'projected_points'].rank(
                    ascending=False, method='min'
                )
            )
    
    def create_update_summary(self):
        """Create summary of all updates applied"""
        print("\n" + "="*60)
        print("WEEKLY UPDATE SUMMARY")
        print("="*60)
        
        if not self.update_log:
            print("No updates applied.")
            return
        
        print(f"Total updates applied: {len(self.update_log)}")
        print(f"Update timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Group by update type
        update_types = {}
        total_impact = 0
        
        for update in self.update_log:
            update_type = update['update_type']
            if update_type not in update_types:
                update_types[update_type] = []
            update_types[update_type].append(update)
            total_impact += update['point_change']
        
        print(f"\\nTotal point impact across all players: {total_impact:+.1f}")
        
        # Show updates by type
        for update_type, updates in update_types.items():
            print(f"\\n{update_type.upper()} UPDATES ({len(updates)}):")
            
            # Show biggest impacts
            updates_sorted = sorted(updates, key=lambda x: abs(x['point_change']), reverse=True)
            for update in updates_sorted[:10]:  # Top 10 impacts
                print(f"  {update['player_name']:<20} - {update['point_change']:+6.1f} pts "
                      f"({update.get('status', update.get('change_type', update.get('adjustment_type', 'N/A')))})")
    
    def save_updated_projections(self, week_number=None):
        """Save updated projections with timestamp"""
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M')
        
        if week_number:
            filename_suffix = f"_week{week_number}_{timestamp}"
        else:
            filename_suffix = f"_updated_{timestamp}"
        
        # Save main projections
        output_file = f'projections/2025/fantasy_projections_2025{filename_suffix}.csv'
        self.current_projections.to_csv(output_file, index=False)
        
        # Save position-specific files
        for position in ['QB', 'RB', 'WR', 'TE']:
            pos_data = self.current_projections[
                self.current_projections['position'] == position
            ].sort_values('position_rank')
            
            pos_file = f'projections/2025/{position}_projections_2025{filename_suffix}.csv'
            pos_data.to_csv(pos_file, index=False)
        
        # Save update log
        log_file = f'projections/2025/update_log{filename_suffix}.json'
        with open(log_file, 'w') as f:
            json.dump(self.update_log, f, indent=2)
        
        print(f"\\nUpdated projections saved:")
        print(f"  Main file: {output_file}")
        print(f"  Update log: {log_file}")
        
        return output_file
    
    def run_example_weekly_update(self):
        """Run an example weekly update with sample data"""
        print("Running example weekly update...")
        
        # Example injury updates
        injury_updates = [
            {'player_name': 'Saquon Barkley', 'status': 'questionable', 'weeks_affected': 1},
            {'player_name': 'Travis Kelce', 'status': 'probable', 'weeks_affected': 1},
            {'player_name': 'Tua Tagovailoa', 'status': 'out', 'weeks_affected': 2},
        ]
        
        # Example depth chart changes
        depth_chart_updates = [
            {'player_name': 'Jayden Daniels', 'change_type': 'promotion', 'workload_change': 0.30},  # Rookie gets starting job
            {'player_name': 'Tony Pollard', 'change_type': 'trade', 'new_team': 'TEN', 'target_share_change': 0.20},
        ]
        
        # Example performance adjustments
        performance_updates = [
            {'player_name': 'Josh Allen', 'adjustment_type': 'hot_streak', 'multiplier': 1.08},
            {'player_name': 'Baker Mayfield', 'adjustment_type': 'coaching_change', 'multiplier': 1.12},
        ]
        
        # Apply updates
        self.apply_injury_updates(injury_updates)
        self.apply_depth_chart_changes(depth_chart_updates)
        self.apply_performance_adjustments(performance_updates)
        
        # Recalculate and save
        self.recalculate_rankings()
        self.create_update_summary()
        
        return self.save_updated_projections(week_number=1)

def main():
    updater = WeeklyProjectionUpdater()
    updater.load_base_projections()
    
    # Run example update
    output_file = updater.run_example_weekly_update()
    
    print(f"\\nWeekly update system ready!")
    print(f"Use this framework to apply real-time updates throughout the season.")

if __name__ == "__main__":
    main() 
"""
Add QB Starter Probability Feature and Update Projections

This script creates a starter probability feature for QBs and adjusts
projections based on depth chart position and competition.
"""

import pandas as pd
import numpy as np
import os

class QBStarterProbabilityEngine:
    def __init__(self):
        self.qb_depth_chart = {}
        self.qb_projections = None
        
    def load_current_projections(self):
        """Load current QB projections"""
        print("Loading current QB projections...")
        self.qb_projections = pd.read_csv('projections/2025/QB_projections_2025.csv')
        print(f"Loaded {len(self.qb_projections)} QB projections")
        
    def create_depth_chart_mapping(self):
        """Create realistic depth chart mapping based on NFL reality"""
        print("Creating depth chart mapping...")
        
        # Define 2025 NFL starting QBs based on training camp/preseason
        # This would be updated throughout season
        confirmed_starters = {
            'BAL': ('Lamar Jackson', 0.98),
            'BUF': ('Josh Allen', 0.98),
            'CIN': ('Joe Burrow', 0.95),
            'CLE': ('Deshaun Watson', 0.85),  # Some uncertainty
            'DEN': ('Bo Nix', 0.80),  # Rookie competition
            'HOU': ('C.J. Stroud', 0.95),
            'IND': ('Anthony Richardson', 0.75),  # Competition with Flacco
            'JAX': ('Trevor Lawrence', 0.90),
            'KC': ('Patrick Mahomes', 0.98),
            'LV': ('Gardner Minshew', 0.60),  # Real competition with O'Connell
            'LAC': ('Justin Herbert', 0.95),
            'MIA': ('Tua Tagovailoa', 0.90),
            'NE': ('Drake Maye', 0.70),  # Rookie battle
            'NYJ': ('Aaron Rodgers', 0.85),  # Age concerns
            'PIT': ('Russell Wilson', 0.55),  # Real competition with Fields
            'TEN': ('Will Levis', 0.75),
            
            'ARI': ('Kyler Murray', 0.90),
            'ATL': ('Kirk Cousins', 0.85),
            'CAR': ('Bryce Young', 0.80),
            'CHI': ('Caleb Williams', 0.85),  # Rookie
            'DAL': ('Dak Prescott', 0.90),
            'DET': ('Jared Goff', 0.95),
            'GB': ('Jordan Love', 0.90),
            'LA': ('Matthew Stafford', 0.90),
            'MIN': ('Sam Darnold', 0.60),  # Competition with J.J. McCarthy
            'NO': ('Derek Carr', 0.85),
            'NYG': ('Daniel Jones', 0.70),  # Unclear situation
            'PHI': ('Jalen Hurts', 0.95),
            'SF': ('Brock Purdy', 0.90),
            'SEA': ('Geno Smith', 0.80),
            'TB': ('Baker Mayfield', 0.90),
            'WAS': ('Jayden Daniels', 0.75)  # Rookie
        }
        
        return confirmed_starters
    
    def assign_starter_probabilities(self):
        """Assign starter probabilities to all QBs"""
        print("Assigning starter probabilities...")
        
        confirmed_starters = self.create_depth_chart_mapping()
        
        # Initialize starter probability column
        self.qb_projections['starter_probability'] = 0.01  # Default for deep backups
        
        # Process each team
        for team in self.qb_projections['team'].unique():
            team_qbs = self.qb_projections[self.qb_projections['team'] == team].copy()
            team_qbs = team_qbs.sort_values('projected_points', ascending=False)
            
            if team in confirmed_starters:
                starter_name, starter_prob = confirmed_starters[team]
                
                # Find the starter
                starter_mask = (self.qb_projections['team'] == team) & \
                              (self.qb_projections['player_name'] == starter_name)
                
                if starter_mask.any():
                    self.qb_projections.loc[starter_mask, 'starter_probability'] = starter_prob
                    
                    # Assign remaining probability to backup(s)
                    remaining_prob = 1.0 - starter_prob
                    backups = self.qb_projections[(self.qb_projections['team'] == team) & 
                                                 (~starter_mask)]
                    
                    if len(backups) > 0:
                        # Primary backup gets most of remaining probability
                        if len(backups) == 1:
                            backup_prob = remaining_prob
                        else:
                            backup_prob = remaining_prob * 0.8  # Primary backup
                            
                        # Find highest projected backup
                        backup_idx = backups['projected_points'].idxmax()
                        self.qb_projections.loc[backup_idx, 'starter_probability'] = backup_prob
                        
                        # Distribute remaining among other backups
                        if len(backups) > 1:
                            other_backups = backups.drop(backup_idx)
                            remaining_for_others = remaining_prob - backup_prob
                            prob_per_other = remaining_for_others / len(other_backups)
                            
                            for idx in other_backups.index:
                                self.qb_projections.loc[idx, 'starter_probability'] = prob_per_other
            else:
                # If team not in confirmed starters, use projection-based logic
                if len(team_qbs) > 0:
                    top_qb_idx = team_qbs.index[0]
                    self.qb_projections.loc[top_qb_idx, 'starter_probability'] = 0.70
                    
                    if len(team_qbs) > 1:
                        second_qb_idx = team_qbs.index[1]
                        self.qb_projections.loc[second_qb_idx, 'starter_probability'] = 0.25
                        
                        # Remaining QBs get small probability
                        for idx in team_qbs.index[2:]:
                            self.qb_projections.loc[idx, 'starter_probability'] = 0.05 / (len(team_qbs) - 2)
    
    def adjust_projections_for_starter_probability(self):
        """Adjust projected points based on starter probability"""
        print("Adjusting projections based on starter probability...")
        
        # Store original projections for reference
        self.qb_projections['original_projected_points'] = self.qb_projections['projected_points'].copy()
        
        # Adjust projections: heavily penalize low starter probability
        def adjust_projection(row):
            original_points = row['original_projected_points']
            starter_prob = row['starter_probability']
            
            # Starter probability adjustment curve
            if starter_prob >= 0.80:
                # Clear starters: minimal adjustment
                multiplier = 1.0
            elif starter_prob >= 0.60:
                # Likely starters: small reduction
                multiplier = 0.95
            elif starter_prob >= 0.40:
                # Competition situation: moderate reduction
                multiplier = 0.75
            elif starter_prob >= 0.20:
                # Backup with chance: significant reduction
                multiplier = 0.45
            elif starter_prob >= 0.10:
                # Unlikely starter: heavy reduction
                multiplier = 0.25
            else:
                # Deep backup: minimal points
                multiplier = 0.15
                
            # Apply adjustment
            adjusted_points = original_points * multiplier
            
            # Add starter probability component (expected starter games)
            starter_games = starter_prob * 17  # 17 game season
            base_starter_value = min(200, original_points * 0.4)  # Base value for being starter
            starter_component = (starter_games / 17) * base_starter_value
            
            return adjusted_points + starter_component
        
        self.qb_projections['projected_points'] = self.qb_projections.apply(adjust_projection, axis=1)
        
        # Recalculate rankings after adjustment
        self.qb_projections['overall_rank'] = self.qb_projections['projected_points'].rank(ascending=False, method='min')
        self.qb_projections['position_rank'] = self.qb_projections['projected_points'].rank(ascending=False, method='min')
    
    def update_tier_assignments(self):
        """Update tier assignments after starter probability adjustments"""
        print("Updating tier assignments...")
        
        # Sort by adjusted projections
        sorted_qbs = self.qb_projections.sort_values('projected_points', ascending=False)
        
        # Assign tiers based on new rankings
        tier_assignments = []
        for i, (idx, row) in enumerate(sorted_qbs.iterrows()):
            if i < 3:
                tier = 1  # Elite QB1
            elif i < 12:
                tier = 2  # QB1
            elif i < 24:
                tier = 3  # QB2
            else:
                tier = 4  # Backup
            tier_assignments.append((idx, tier))
        
        # Apply tier assignments
        tier_dict = dict(tier_assignments)
        self.qb_projections['tier'] = self.qb_projections.index.map(tier_dict)
        
        # Update tier labels
        tier_labels = {1: 'Elite QB1', 2: 'QB1', 3: 'QB2', 4: 'Backup'}
        self.qb_projections['tier_label'] = self.qb_projections['tier'].map(tier_labels)
    
    def save_updated_projections(self):
        """Save updated projections with starter probability"""
        print("Saving updated QB projections...")
        
        # Save QB-specific file
        self.qb_projections.to_csv('projections/2025/QB_projections_2025.csv', index=False)
        
        # Update main projections file
        main_projections = pd.read_csv('projections/2025/fantasy_projections_2025.csv')
        
        # Update QB rows in main file
        qb_mask = main_projections['position'] == 'QB'
        main_projections = main_projections[~qb_mask]  # Remove old QB data
        main_projections = pd.concat([main_projections, self.qb_projections], ignore_index=True)
        
        # Sort by overall rank
        main_projections = main_projections.sort_values('overall_rank')
        main_projections.to_csv('projections/2025/fantasy_projections_2025.csv', index=False)
        
        print(f"Updated projections saved with starter probability feature")
    
    def create_summary_report(self):
        """Create summary of starter probability impact"""
        print("\n" + "="*60)
        print("QB STARTER PROBABILITY IMPACT ANALYSIS")
        print("="*60)
        
        # Show top QBs with starter probability
        print("\nTop 15 QBs After Starter Probability Adjustment:")
        top_qbs = self.qb_projections.sort_values('projected_points', ascending=False).head(15)
        
        for _, row in top_qbs.iterrows():
            original = row['original_projected_points']
            adjusted = row['projected_points']
            change = adjusted - original
            starter_prob = row['starter_probability']
            
            print(f"{row['position_rank']:2.0f}. {row['player_name']:<20} ({row['team']}) "
                  f"- {adjusted:5.1f} pts ({change:+5.1f}) "
                  f"- {starter_prob:.0%} starter prob ({row['tier_label']})")
        
        # Show biggest adjustments
        print("\nBiggest Positive Adjustments:")
        self.qb_projections['point_change'] = (self.qb_projections['projected_points'] - 
                                              self.qb_projections['original_projected_points'])
        
        biggest_gains = self.qb_projections.nlargest(5, 'point_change')
        for _, row in biggest_gains.iterrows():
            print(f"  {row['player_name']:<20} ({row['team']}) - {row['point_change']:+5.1f} pts "
                  f"({row['starter_probability']:.0%} starter)")
        
        print("\nBiggest Negative Adjustments:")
        biggest_losses = self.qb_projections.nsmallest(5, 'point_change')
        for _, row in biggest_losses.iterrows():
            print(f"  {row['player_name']:<20} ({row['team']}) - {row['point_change']:+5.1f} pts "
                  f"({row['starter_probability']:.0%} starter)")
    
    def run_starter_probability_update(self):
        """Run complete starter probability update pipeline"""
        self.load_current_projections()
        self.assign_starter_probabilities()
        self.adjust_projections_for_starter_probability()
        self.update_tier_assignments()
        self.create_summary_report()
        self.save_updated_projections()

def main():
    engine = QBStarterProbabilityEngine()
    engine.run_starter_probability_update()

if __name__ == "__main__":
    main() 
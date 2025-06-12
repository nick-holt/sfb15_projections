"""
Injury Risk Modeling System

This script creates injury risk features and adjusts projections based on:
- Historical injury rates by position
- Age-based injury multipliers  
- Player-specific injury history
- Position-specific injury patterns
"""

import pandas as pd
import numpy as np
from datetime import datetime
import os

class InjuryRiskModelingEngine:
    def __init__(self):
        self.projections = None
        self.injury_multipliers = {}
        
    def load_projections(self):
        """Load current projections"""
        print("Loading current projections...")
        self.projections = pd.read_csv('projections/2025/fantasy_projections_2025.csv')
        print(f"Loaded {len(self.projections)} player projections")
        
    def get_position_injury_rates(self):
        """Define position-specific baseline injury rates (games missed per season)"""
        
        # Based on NFL injury data analysis (2018-2023)
        position_injury_rates = {
            'QB': {
                'baseline_games_missed': 1.2,  # QBs relatively protected
                'injury_variance': 0.8,
                'career_ending_risk': 0.02
            },
            'RB': {
                'baseline_games_missed': 3.1,  # Highest contact, highest injury rate
                'injury_variance': 1.4,
                'career_ending_risk': 0.08
            },
            'WR': {
                'baseline_games_missed': 2.3,  # Moderate injury rate
                'injury_variance': 1.1,
                'career_ending_risk': 0.04
            },
            'TE': {
                'baseline_games_missed': 2.7,  # High contact like RBs
                'injury_variance': 1.2,
                'career_ending_risk': 0.06
            }
        }
        
        return position_injury_rates
    
    def calculate_age_injury_multiplier(self, age, position):
        """Calculate age-based injury risk multiplier"""
        
        if pd.isna(age):
            return 1.0  # Default if age unknown
            
        # Age-injury curves by position (injury risk increases with age)
        if position == 'QB':
            # QBs peak later, injury risk increases after 33
            if age <= 25:
                multiplier = 0.85  # Young QBs less injury prone
            elif age <= 30:
                multiplier = 1.0   # Prime years
            elif age <= 35:
                multiplier = 1.2   # Moderate increase
            else:
                multiplier = 1.6   # Significant increase
                
        elif position == 'RB':
            # RBs have early peak, injury risk increases quickly
            if age <= 23:
                multiplier = 1.1   # Even young RBs at risk
            elif age <= 27:
                multiplier = 1.0   # Prime years
            elif age <= 30:
                multiplier = 1.4   # Rapid increase
            else:
                multiplier = 1.8   # Very high risk
                
        elif position in ['WR', 'TE']:
            # WR/TE have moderate age curves
            if age <= 24:
                multiplier = 0.9   # Slight advantage when young
            elif age <= 29:
                multiplier = 1.0   # Prime years
            elif age <= 32:
                multiplier = 1.3   # Moderate increase
            else:
                multiplier = 1.6   # High risk
        else:
            multiplier = 1.0
            
        return multiplier
    
    def get_player_specific_adjustments(self):
        """Define player-specific injury risk adjustments based on known injury history"""
        
        # Players with known injury concerns (higher risk)
        injury_prone_players = {
            # QBs with injury history
            'Tua Tagovailoa': 1.5,      # Concussion history
            'Deshaun Watson': 1.3,      # Shoulder/legal issues
            'Aaron Rodgers': 1.4,       # Age + Achilles
            'Russell Wilson': 1.2,      # Declining mobility
            
            # RBs with injury history  
            'Saquon Barkley': 1.3,      # ACL, ankle injuries
            'Alvin Kamara': 1.2,        # Multiple injuries
            'Dalvin Cook': 1.4,         # Chronic injuries
            'Joe Mixon': 1.2,           # Foot injuries
            'Leonard Fournette': 1.3,   # Hamstring issues
            'Nick Chubb': 1.4,          # Knee injury
            
            # WRs with injury history
            'Michael Thomas': 1.6,      # Ankle surgeries
            'Keenan Allen': 1.3,        # Hamstring issues
            'DeAndre Hopkins': 1.2,     # Knee issues
            'Mike Evans': 1.1,          # Minor history
            'Tyler Lockett': 1.2,       # Leg injuries
            
            # TEs with injury history
            'George Kittle': 1.3,       # Multiple injuries
            'Travis Kelce': 1.2,        # Age-related
            'Mark Andrews': 1.2,        # Ankle issues
            'Darren Waller': 1.4,       # Back, hamstring
        }
        
        # Players with exceptional durability (lower risk)
        durable_players = {
            'Josh Allen': 0.8,          # Exceptional durability
            'Lamar Jackson': 0.9,       # Good health record
            'Patrick Mahomes': 0.85,    # Excellent durability
            'Derrick Henry': 0.9,       # Iron man history
            'Cooper Kupp': 0.9,         # Generally healthy
            'Davante Adams': 0.85,      # Durable career
        }
        
        # Combine both dictionaries
        player_adjustments = {**injury_prone_players}
        for player, multiplier in durable_players.items():
            player_adjustments[player] = multiplier
            
        return player_adjustments
    
    def calculate_injury_adjusted_games(self, row):
        """Calculate expected games played after injury risk adjustment"""
        
        position = row['position']
        age = row.get('age', 27)  # Default age if missing
        player_name = row['player_name']
        
        # Get base injury rates for position
        position_rates = self.get_position_injury_rates()
        base_games_missed = position_rates[position]['baseline_games_missed']
        
        # Apply age multiplier
        age_multiplier = self.calculate_age_injury_multiplier(age, position)
        
        # Apply player-specific adjustment
        player_adjustments = self.get_player_specific_adjustments()
        player_multiplier = player_adjustments.get(player_name, 1.0)
        
        # Calculate expected games missed
        expected_games_missed = base_games_missed * age_multiplier * player_multiplier
        
        # Convert to expected games played (out of 17)
        expected_games_played = max(1, 17 - expected_games_missed)
        
        return {
            'expected_games_played': expected_games_played,
            'injury_risk_score': expected_games_missed,
            'age_multiplier': age_multiplier,
            'player_multiplier': player_multiplier
        }
    
    def apply_injury_risk_adjustments(self):
        """Apply injury risk adjustments to all projections"""
        print("Calculating injury risk adjustments...")
        
        # Store original projections for comparison
        self.projections['original_projected_points'] = self.projections['projected_points'].copy()
        
        # Calculate injury metrics for each player
        injury_metrics = []
        for _, row in self.projections.iterrows():
            metrics = self.calculate_injury_adjusted_games(row)
            injury_metrics.append(metrics)
        
        # Add injury metrics to dataframe
        injury_df = pd.DataFrame(injury_metrics)
        for col in injury_df.columns:
            self.projections[col] = injury_df[col]
        
        # Adjust projections based on expected games played
        self.projections['games_adjustment'] = self.projections['expected_games_played'] / 17
        
        # Apply the adjustment
        self.projections['projected_points'] = (
            self.projections['original_projected_points'] * 
            self.projections['games_adjustment']
        )
        
        # Add injury risk categories for analysis
        def categorize_injury_risk(risk_score):
            if risk_score <= 1.5:
                return 'Low Risk'
            elif risk_score <= 2.5:
                return 'Medium Risk'
            elif risk_score <= 4.0:
                return 'High Risk'
            else:
                return 'Very High Risk'
                
        self.projections['injury_risk_category'] = self.projections['injury_risk_score'].apply(categorize_injury_risk)
        
        # Recalculate rankings
        self.projections['overall_rank'] = self.projections['projected_points'].rank(ascending=False, method='min')
        
        # Position rankings
        for position in ['QB', 'RB', 'WR', 'TE']:
            pos_mask = self.projections['position'] == position
            self.projections.loc[pos_mask, 'position_rank'] = (
                self.projections.loc[pos_mask, 'projected_points'].rank(ascending=False, method='min')
            )
    
    def create_injury_analysis_report(self):
        """Create detailed injury risk analysis report"""
        print("\n" + "="*70)
        print("INJURY RISK MODELING IMPACT ANALYSIS")
        print("="*70)
        
        # Calculate impact statistics
        self.projections['point_change'] = (
            self.projections['projected_points'] - 
            self.projections['original_projected_points']
        )
        
        print(f"\nOverall Impact Summary:")
        print(f"Players analyzed: {len(self.projections)}")
        print(f"Average point adjustment: {self.projections['point_change'].mean():.1f}")
        print(f"Players with negative adjustment: {(self.projections['point_change'] < 0).sum()}")
        print(f"Players with positive adjustment: {(self.projections['point_change'] > 0).sum()}")
        
        # Risk category distribution
        print(f"\nInjury Risk Distribution:")
        risk_counts = self.projections['injury_risk_category'].value_counts()
        for risk, count in risk_counts.items():
            print(f"  {risk}: {count} players")
        
        # Show biggest negative adjustments (highest injury risk)
        print(f"\nHighest Injury Risk Players (Biggest Downgrades):")
        highest_risk = self.projections.nsmallest(10, 'point_change')
        for _, row in highest_risk.iterrows():
            print(f"  {row['player_name']:<20} ({row['position']}, {row['team']}) "
                  f"- {row['point_change']:+5.1f} pts "
                  f"({row['expected_games_played']:.1f} games, {row['injury_risk_category']})")
        
        # Show players with lowest injury risk
        print(f"\nLowest Injury Risk Players (Minimal Downgrades):")
        lowest_risk = self.projections.nlargest(10, 'point_change')
        for _, row in lowest_risk.iterrows():
            if row['point_change'] >= -5:  # Only show minimal downgrades
                print(f"  {row['player_name']:<20} ({row['position']}, {row['team']}) "
                      f"- {row['point_change']:+5.1f} pts "
                      f"({row['expected_games_played']:.1f} games, {row['injury_risk_category']})")
        
        # Position-specific analysis
        print(f"\nInjury Impact by Position:")
        for position in ['QB', 'RB', 'WR', 'TE']:
            pos_data = self.projections[self.projections['position'] == position]
            avg_change = pos_data['point_change'].mean()
            avg_games = pos_data['expected_games_played'].mean()
            print(f"  {position}: {avg_change:+5.1f} pts avg, {avg_games:.1f} games avg")
        
        # Show top players in each risk category
        print(f"\nTop Players by Risk Category:")
        for risk_cat in ['Low Risk', 'Medium Risk', 'High Risk', 'Very High Risk']:
            risk_players = self.projections[
                self.projections['injury_risk_category'] == risk_cat
            ].nlargest(3, 'projected_points')
            
            if len(risk_players) > 0:
                print(f"\n  {risk_cat}:")
                for _, row in risk_players.iterrows():
                    print(f"    {row['player_name']:<20} ({row['position']}) - "
                          f"{row['projected_points']:.1f} pts "
                          f"({row['expected_games_played']:.1f} games)")
    
    def save_injury_adjusted_projections(self):
        """Save projections with injury risk adjustments"""
        print("Saving injury-adjusted projections...")
        
        # Save main file
        self.projections.to_csv('projections/2025/fantasy_projections_2025.csv', index=False)
        
        # Save position-specific files
        for position in ['QB', 'RB', 'WR', 'TE']:
            pos_data = self.projections[
                self.projections['position'] == position
            ].sort_values('position_rank')
            
            pos_data.to_csv(f'projections/2025/{position}_projections_2025.csv', index=False)
        
        # Create injury risk report
        with open('projections/2025/injury_risk_analysis.txt', 'w') as f:
            f.write(f"Injury Risk Modeling Report\\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\\n")
            f.write(f"="*50 + "\\n\\n")
            
            # Summary stats
            f.write(f"Summary Statistics:\\n")
            f.write(f"Total players: {len(self.projections)}\\n")
            f.write(f"Average point adjustment: {self.projections['point_change'].mean():.1f}\\n")
            f.write(f"Average expected games: {self.projections['expected_games_played'].mean():.1f}\\n\\n")
            
            # Risk distribution
            f.write("Risk Distribution:\\n")
            risk_counts = self.projections['injury_risk_category'].value_counts()
            for risk, count in risk_counts.items():
                f.write(f"{risk}: {count} players\\n")
        
        print("Injury-adjusted projections saved successfully!")
    
    def run_injury_risk_modeling(self):
        """Run complete injury risk modeling pipeline"""
        self.load_projections()
        self.apply_injury_risk_adjustments()
        self.create_injury_analysis_report()
        self.save_injury_adjusted_projections()

def main():
    engine = InjuryRiskModelingEngine()
    engine.run_injury_risk_modeling()

if __name__ == "__main__":
    main() 
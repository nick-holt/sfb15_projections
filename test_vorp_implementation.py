#!/usr/bin/env python3
"""
Test VORP Implementation
Validates the VORP calculator with realistic fantasy football data
"""

import sys
import os
sys.path.append('src')

import pandas as pd
import numpy as np
from analytics.vorp_calculator import VORPCalculator

def create_test_data():
    """Create realistic test data for VORP validation"""
    
    # Create realistic player data based on 2024 fantasy football projections
    test_players = [
        # Elite QBs
        {'player_name': 'Josh Allen', 'position': 'QB', 'projected_points': 420.5},
        {'player_name': 'Lamar Jackson', 'position': 'QB', 'projected_points': 410.2},
        {'player_name': 'Jalen Hurts', 'position': 'QB', 'projected_points': 395.8},
        
        # Mid-tier QBs
        {'player_name': 'Tua Tagovailoa', 'position': 'QB', 'projected_points': 320.4},
        {'player_name': 'Kirk Cousins', 'position': 'QB', 'projected_points': 315.7},
        {'player_name': 'Geno Smith', 'position': 'QB', 'projected_points': 310.2},
        
        # Replacement level QBs (QB12-15 range)
        {'player_name': 'Derek Carr', 'position': 'QB', 'projected_points': 295.5},
        {'player_name': 'Ryan Tannehill', 'position': 'QB', 'projected_points': 290.8},
        {'player_name': 'Mac Jones', 'position': 'QB', 'projected_points': 285.3},
        {'player_name': 'Jimmy Garoppolo', 'position': 'QB', 'projected_points': 280.1},
        {'player_name': 'Kenny Pickett', 'position': 'QB', 'projected_points': 275.6},
        {'player_name': 'Desmond Ridder', 'position': 'QB', 'projected_points': 270.2},
        {'player_name': 'Sam Howell', 'position': 'QB', 'projected_points': 265.8}, # QB13 - replacement level
        
        # Elite RBs
        {'player_name': 'Christian McCaffrey', 'position': 'RB', 'projected_points': 350.2},
        {'player_name': 'Austin Ekeler', 'position': 'RB', 'projected_points': 320.8},
        {'player_name': 'Saquon Barkley', 'position': 'RB', 'projected_points': 315.5},
        {'player_name': 'Derrick Henry', 'position': 'RB', 'projected_points': 310.3},
        
        # Mid-tier RBs
        {'player_name': 'Josh Jacobs', 'position': 'RB', 'projected_points': 280.7},
        {'player_name': 'Nick Chubb', 'position': 'RB', 'projected_points': 275.4},
        {'player_name': 'Joe Mixon', 'position': 'RB', 'projected_points': 270.1},
        {'player_name': 'Kenneth Walker III', 'position': 'RB', 'projected_points': 265.8},
        
        # Add more RBs to reach replacement level (RB24 + 1 = RB25)
        *[{'player_name': f'RB{i}', 'position': 'RB', 'projected_points': 250 - (i * 5)} 
          for i in range(1, 20)],
        
        # Elite WRs
        {'player_name': 'Cooper Kupp', 'position': 'WR', 'projected_points': 320.5},
        {'player_name': 'Davante Adams', 'position': 'WR', 'projected_points': 315.2},
        {'player_name': 'Tyreek Hill', 'position': 'WR', 'projected_points': 310.8},
        {'player_name': 'Stefon Diggs', 'position': 'WR', 'projected_points': 305.4},
        
        # Mid-tier WRs
        {'player_name': 'DeAndre Hopkins', 'position': 'WR', 'projected_points': 280.7},
        {'player_name': 'Keenan Allen', 'position': 'WR', 'projected_points': 275.3},
        {'player_name': 'Mike Evans', 'position': 'WR', 'projected_points': 270.9},
        {'player_name': 'Chris Godwin', 'position': 'WR', 'projected_points': 265.5},
        
        # Add more WRs to reach replacement level (WR36 + 1 = WR37)
        *[{'player_name': f'WR{i}', 'position': 'WR', 'projected_points': 240 - (i * 3)} 
          for i in range(1, 30)],
        
        # Elite TEs
        {'player_name': 'Travis Kelce', 'position': 'TE', 'projected_points': 280.5},
        {'player_name': 'Mark Andrews', 'position': 'TE', 'projected_points': 245.8},
        {'player_name': 'George Kittle', 'position': 'TE', 'projected_points': 235.2},
        
        # Mid-tier TEs
        {'player_name': 'T.J. Hockenson', 'position': 'TE', 'projected_points': 210.7},
        {'player_name': 'Kyle Pitts', 'position': 'TE', 'projected_points': 205.3},
        {'player_name': 'Dallas Goedert', 'position': 'TE', 'projected_points': 200.1},
        
        # Add more TEs to reach replacement level (TE12 + 1 = TE13)
        *[{'player_name': f'TE{i}', 'position': 'TE', 'projected_points': 180 - (i * 8)} 
          for i in range(1, 10)],
    ]
    
    return pd.DataFrame(test_players)

def test_vorp_calculations():
    """Test VORP calculations with realistic data"""
    print("🏈 Testing VORP Implementation")
    print("=" * 50)
    
    # Create test data
    test_data = create_test_data()
    print(f"Created test data with {len(test_data)} players")
    
    # Test different league sizes
    league_sizes = [10, 12, 14]
    
    for league_size in league_sizes:
        print(f"\n📊 Testing {league_size}-team league")
        print("-" * 30)
        
        # Initialize VORP calculator
        vorp_calc = VORPCalculator(num_teams=league_size)
        
        # Calculate VORP scores
        result_df = vorp_calc.calculate_vorp_scores(test_data)
        
        # Show replacement levels
        replacement_levels = {}
        for position in ['QB', 'RB', 'WR', 'TE']:
            pos_data = result_df[result_df['position'] == position]
            if not pos_data.empty:
                replacement_levels[position] = pos_data.iloc[0]['replacement_points']
        
        print("Replacement Levels:")
        for pos, level in replacement_levels.items():
            starters_needed = vorp_calc.starting_lineup[pos] * league_size
            print(f"  {pos}: {level:.1f} pts (after {starters_needed} starters)")
        
        # Show top VORP players by position
        print("\nTop VORP Players by Position:")
        for position in ['QB', 'RB', 'WR', 'TE']:
            pos_data = result_df[result_df['position'] == position]
            top_vorp = pos_data.nlargest(3, 'vorp_score')
            
            print(f"\n  {position}:")
            for _, player in top_vorp.iterrows():
                print(f"    {player['player_name']}: {player['vorp_score']:.1f} VORP "
                      f"({player['projected_points']:.1f} proj, {player['replacement_points']:.1f} repl)")
        
        # Show VORP insights
        insights = vorp_calc.get_vorp_insights(result_df)
        print(f"\nVORP Insights:")
        print(f"  Total positive VORP players: {insights['overall']['total_positive_vorp']}")
        print(f"  Average VORP: {insights['overall']['average_vorp']:.1f}")
        print(f"  Most scarce position: {insights['overall']['most_scarce_position']}")

def test_adp_vorp_integration():
    """Test VORP integration with ADP data"""
    print("\n\n💎 Testing VORP-ADP Integration")
    print("=" * 50)
    
    # Create test data with ADP
    test_data = create_test_data()
    
    # Add realistic ADP data (consensus_adp)
    np.random.seed(42)  # For reproducible results
    
    # Simulate ADP that doesn't perfectly match projections (creates value opportunities)
    adp_data = []
    for _, player in test_data.iterrows():
        # Base ADP on projected points with some noise
        base_adp = len(test_data) - (player['projected_points'] / test_data['projected_points'].max()) * len(test_data)
        
        # Add position-specific ADP bias
        if player['position'] == 'QB':
            base_adp += 30  # QBs drafted later than projections suggest
        elif player['position'] == 'TE':
            base_adp += 15  # TEs also drafted later
        
        # Add random noise
        noise = np.random.normal(0, 10)
        consensus_adp = max(1, base_adp + noise)
        
        adp_data.append(consensus_adp)
    
    test_data['consensus_adp'] = adp_data
    
    # Calculate VORP with ADP integration
    vorp_calc = VORPCalculator(num_teams=12)
    result_df = vorp_calc.calculate_vorp_scores(test_data)
    result_df = vorp_calc.calculate_adp_vorp_value(result_df, 'consensus_adp')
    
    # Show best VORP-ADP values
    print("Best VORP-ADP Value Opportunities:")
    best_values = result_df[result_df['vorp_adp_value'] > 0].nlargest(10, 'vorp_adp_value')
    
    for _, player in best_values.iterrows():
        print(f"  {player['player_name']} ({player['position']}): "
              f"VORP {player['vorp_score']:.1f}, "
              f"ADP Value +{player['vorp_adp_value']:.0f} "
              f"({player['vorp_adp_tier']})")
    
    # Show VORP distribution
    print(f"\nVORP-ADP Value Distribution:")
    distribution = result_df['vorp_adp_tier'].value_counts()
    for tier, count in distribution.items():
        print(f"  {tier}: {count} players")

def test_draft_recommendations():
    """Test VORP-based draft recommendations"""
    print("\n\n🎯 Testing VORP Draft Recommendations")
    print("=" * 50)
    
    # Create test data
    test_data = create_test_data()
    test_data['consensus_adp'] = range(1, len(test_data) + 1)  # Simple ADP
    
    # Calculate VORP
    vorp_calc = VORPCalculator(num_teams=12)
    result_df = vorp_calc.calculate_vorp_scores(test_data)
    result_df = vorp_calc.calculate_adp_vorp_value(result_df, 'consensus_adp')
    
    # Test recommendations for different draft scenarios
    scenarios = [
        {'current_roster': [], 'draft_position': 6, 'current_round': 1},
        {'current_roster': ['Josh Allen', 'Christian McCaffrey'], 'draft_position': 6, 'current_round': 3},
        {'current_roster': ['Josh Allen', 'Christian McCaffrey', 'Cooper Kupp', 'Austin Ekeler'], 'draft_position': 6, 'current_round': 5}
    ]
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\nScenario {i}: Round {scenario['current_round']}, {len(scenario['current_roster'])} players drafted")
        
        recommendations = vorp_calc.get_draft_recommendations(
            result_df,
            scenario['current_roster'],
            scenario['draft_position'],
            scenario['current_round']
        )
        
        print(f"Strategy: {recommendations['round_strategy'][scenario['current_round']]}")
        
        print("Top VORP Targets:")
        for j, player in enumerate(recommendations['vorp_targets'][:5], 1):
            print(f"  {j}. {player['player_name']} ({player['position']}) - "
                  f"VORP: {player['vorp_score']:.1f} ({player['vorp_tier']})")

if __name__ == "__main__":
    test_vorp_calculations()
    test_adp_vorp_integration()
    test_draft_recommendations()
    
    print("\n✅ All VORP tests completed successfully!")
    print("\nVORP Implementation Summary:")
    print("- Dynamic replacement levels based on league size and starting lineup requirements")
    print("- Position scarcity adjustments")
    print("- ADP-VORP value integration for identifying draft opportunities")
    print("- Round-specific draft strategy recommendations")
    print("- Comprehensive insights and analytics") 
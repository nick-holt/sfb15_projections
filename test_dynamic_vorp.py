"""
Test script for Dynamic VORP Calculator
Tests Feature 1: Dynamic Replacement Level Shifts
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

import pandas as pd
import numpy as np
from datetime import datetime
from analytics.dynamic_vorp_calculator import DynamicVORPCalculator
from draft.draft_state import DraftState, DraftSettings, DraftPick, TeamRoster

def create_sample_projections():
    """Create sample player projections for testing"""
    players = []
    
    # QB projections
    qb_data = [
        ("Josh Allen", "QB", "BUF", 420),
        ("Lamar Jackson", "QB", "BAL", 410),
        ("Jalen Hurts", "QB", "PHI", 400),
        ("Patrick Mahomes", "QB", "KC", 390),
        ("Joe Burrow", "QB", "CIN", 380),
        ("Dak Prescott", "QB", "DAL", 370),
        ("Justin Herbert", "QB", "LAC", 365),
        ("Tua Tagovailoa", "QB", "MIA", 350),
        ("Kyler Murray", "QB", "ARI", 340),
        ("Russell Wilson", "QB", "DEN", 330),
        ("Aaron Rodgers", "QB", "NYJ", 325),
        ("Trevor Lawrence", "QB", "JAX", 320),
    ]
    
    # RB projections
    rb_data = [
        ("Christian McCaffrey", "RB", "SF", 380),
        ("Austin Ekeler", "RB", "LAC", 350),
        ("Derrick Henry", "RB", "TEN", 340),
        ("Saquon Barkley", "RB", "NYG", 330),
        ("Josh Jacobs", "RB", "LV", 320),
        ("Nick Chubb", "RB", "CLE", 315),
        ("Tony Pollard", "RB", "DAL", 310),
        ("Alvin Kamara", "RB", "NO", 305),
        ("Joe Mixon", "RB", "CIN", 300),
        ("Najee Harris", "RB", "PIT", 295),
        ("Kenneth Walker", "RB", "SEA", 290),
        ("Miles Sanders", "RB", "CAR", 285),
        ("Dameon Pierce", "RB", "HOU", 280),
        ("Alexander Mattison", "RB", "MIN", 270),
        ("Raheem Mostert", "RB", "MIA", 265),
        ("Isiah Pacheco", "RB", "KC", 260),
    ]
    
    # WR projections
    wr_data = [
        ("Cooper Kupp", "WR", "LAR", 360),
        ("Tyreek Hill", "WR", "MIA", 350),
        ("Stefon Diggs", "WR", "BUF", 340),
        ("Davante Adams", "WR", "LV", 335),
        ("DeAndre Hopkins", "WR", "ARI", 330),
        ("A.J. Brown", "WR", "PHI", 325),
        ("Ja'Marr Chase", "WR", "CIN", 320),
        ("Justin Jefferson", "WR", "MIN", 315),
        ("Mike Evans", "WR", "TB", 310),
        ("Keenan Allen", "WR", "LAC", 305),
        ("DK Metcalf", "WR", "SEA", 300),
        ("CeeDee Lamb", "WR", "DAL", 295),
        ("Tee Higgins", "WR", "CIN", 290),
        ("Amon-Ra St. Brown", "WR", "DET", 285),
        ("Calvin Ridley", "WR", "JAX", 280),
        ("Chris Godwin", "WR", "TB", 275),
    ]
    
    # TE projections
    te_data = [
        ("Travis Kelce", "TE", "KC", 280),
        ("Mark Andrews", "TE", "BAL", 260),
        ("T.J. Hockenson", "TE", "MIN", 240),
        ("George Kittle", "TE", "SF", 235),
        ("Darren Waller", "TE", "NYG", 230),
        ("Kyle Pitts", "TE", "ATL", 225),
        ("Dallas Goedert", "TE", "PHI", 220),
        ("Pat Freiermuth", "TE", "PIT", 210),
        ("Tyler Higbee", "TE", "LAR", 200),
        ("Gerald Everett", "TE", "LAC", 195),
        ("David Njoku", "TE", "CLE", 190),
        ("Evan Engram", "TE", "JAX", 185),
    ]
    
    # Combine all players
    all_players = qb_data + rb_data + wr_data + te_data
    
    for i, (name, pos, team, points) in enumerate(all_players):
        players.append({
            'player_id': f'player_{i+1}',
            'player_name': name,
            'position': pos,
            'team': team,
            'projected_points': points,
            'confidence': np.random.uniform(0.7, 0.95)
        })
    
    return pd.DataFrame(players)

def create_sample_draft_state():
    """Create a sample draft state with some picks already made"""
    settings = DraftSettings(
        league_id='test_league',
        draft_id='test_draft',
        league_name='Test League',
        total_teams=12,
        total_rounds=15,
        pick_timer=120,
        draft_type='snake',
        scoring_type='ppr',
        roster_positions=['QB', 'RB', 'RB', 'WR', 'WR', 'TE', 'FLEX', 'K', 'DEF', 'BN', 'BN', 'BN', 'BN', 'BN', 'BN'],
        draft_order={f'user_{i}': i for i in range(1, 13)},
        slot_to_roster={i: i for i in range(1, 13)}
    )
    
    draft_state = DraftState(
        settings=settings,
        status='drafting',
        current_pick=25,  # Round 3, Pick 1
        current_round=3,
        current_draft_slot=1
    )
    
    # Add some sample picks (first 2 rounds)
    sample_picks = [
        # Round 1
        DraftPick(1, 1, 1, 'player_17', 'Christian McCaffrey', 'RB', 'SF', 1, 'user_1'),
        DraftPick(2, 1, 2, 'player_18', 'Austin Ekeler', 'RB', 'LAC', 2, 'user_2'),
        DraftPick(3, 1, 3, 'player_25', 'Cooper Kupp', 'WR', 'LAR', 3, 'user_3'),
        DraftPick(4, 1, 4, 'player_26', 'Tyreek Hill', 'WR', 'MIA', 4, 'user_4'),
        DraftPick(5, 1, 5, 'player_19', 'Derrick Henry', 'RB', 'TEN', 5, 'user_5'),
        DraftPick(6, 1, 6, 'player_27', 'Stefon Diggs', 'WR', 'BUF', 6, 'user_6'),
        DraftPick(7, 1, 7, 'player_20', 'Saquon Barkley', 'RB', 'NYG', 7, 'user_7'),
        DraftPick(8, 1, 8, 'player_28', 'Davante Adams', 'WR', 'LV', 8, 'user_8'),
        DraftPick(9, 1, 9, 'player_21', 'Josh Jacobs', 'RB', 'LV', 9, 'user_9'),
        DraftPick(10, 1, 10, 'player_29', 'DeAndre Hopkins', 'WR', 'ARI', 10, 'user_10'),
        DraftPick(11, 1, 11, 'player_22', 'Nick Chubb', 'RB', 'CLE', 11, 'user_11'),
        DraftPick(12, 1, 12, 'player_37', 'Travis Kelce', 'TE', 'KC', 12, 'user_12'),
        
        # Round 2 (snake order - reverse)
        DraftPick(13, 2, 12, 'player_1', 'Josh Allen', 'QB', 'BUF', 12, 'user_12'),
        DraftPick(14, 2, 11, 'player_30', 'A.J. Brown', 'WR', 'PHI', 11, 'user_11'),
        DraftPick(15, 2, 10, 'player_23', 'Tony Pollard', 'RB', 'DAL', 10, 'user_10'),
        DraftPick(16, 2, 9, 'player_31', 'Ja\'Marr Chase', 'WR', 'CIN', 9, 'user_9'),
        DraftPick(17, 2, 8, 'player_24', 'Alvin Kamara', 'RB', 'NO', 8, 'user_8'),
        DraftPick(18, 2, 7, 'player_32', 'Justin Jefferson', 'WR', 'MIN', 7, 'user_7'),
        DraftPick(19, 2, 6, 'player_2', 'Lamar Jackson', 'QB', 'BAL', 6, 'user_6'),
        DraftPick(20, 2, 5, 'player_38', 'Mark Andrews', 'TE', 'BAL', 5, 'user_5'),
        DraftPick(21, 2, 4, 'player_33', 'Mike Evans', 'WR', 'TB', 4, 'user_4'),
        DraftPick(22, 2, 3, 'player_25', 'Joe Mixon', 'RB', 'CIN', 3, 'user_3'),
        DraftPick(23, 2, 2, 'player_34', 'Keenan Allen', 'WR', 'LAC', 2, 'user_2'),
        DraftPick(24, 2, 1, 'player_3', 'Jalen Hurts', 'QB', 'PHI', 1, 'user_1'),
    ]
    
    # Add picks to draft state
    for pick in sample_picks:
        draft_state.add_pick(pick)
    
    return draft_state

def test_dynamic_vorp():
    """Test the dynamic VORP calculator"""
    print("🧪 Testing Dynamic VORP Calculator - Feature 1: Dynamic Replacement Level Shifts")
    print("=" * 80)
    
    # Create test data
    projections_df = create_sample_projections()
    draft_state = create_sample_draft_state()
    
    print(f"📊 Created {len(projections_df)} player projections")
    print(f"🏈 Draft state: {len(draft_state.picks)} picks made, Round {draft_state.current_round}")
    print()
    
    # Initialize dynamic VORP calculator
    calc = DynamicVORPCalculator(num_teams=12)
    
    # Calculate static VORP (baseline)
    print("1️⃣ Calculating Static VORP (baseline)...")
    static_df = calc.calculate_vorp_scores(projections_df.copy())
    print(f"   ✅ Static replacement levels calculated")
    
    # Calculate dynamic VORP with draft state
    print("2️⃣ Calculating Dynamic VORP with draft state...")
    dynamic_df = calc.calculate_dynamic_vorp(projections_df.copy(), draft_state)
    print(f"   ✅ Dynamic replacement levels calculated")
    print()
    
    # Show replacement level changes
    print("📈 REPLACEMENT LEVEL SHIFTS:")
    print("-" * 40)
    for pos in ['QB', 'RB', 'WR', 'TE']:
        pos_data = dynamic_df[dynamic_df['position'] == pos]
        if not pos_data.empty:
            static_repl = pos_data['static_replacement_level'].iloc[0]
            dynamic_repl = pos_data['dynamic_replacement_level'].iloc[0]
            shift = dynamic_repl - static_repl
            direction = "⬆️" if shift > 0 else "⬇️" if shift < 0 else "➡️"
            print(f"{direction} {pos}: {static_repl:.1f} → {dynamic_repl:.1f} ({shift:+.1f})")
    print()
    
    # Show position scarcity analysis
    print("🎯 POSITION SCARCITY ANALYSIS:")
    print("-" * 40)
    for pos in ['QB', 'RB', 'WR', 'TE']:
        pos_data = dynamic_df[dynamic_df['position'] == pos]
        if not pos_data.empty:
            avg_scarcity = pos_data['position_scarcity_multiplier'].mean()
            level = "High" if avg_scarcity > 1.2 else "Medium" if avg_scarcity > 1.0 else "Low"
            color = "🔴" if level == "High" else "🟡" if level == "Medium" else "🟢"
            print(f"{color} {pos}: {level} scarcity ({avg_scarcity:.2f}x multiplier)")
    print()
    
    # Show biggest VORP changes
    print("🔥 BIGGEST VORP CHANGES:")
    print("-" * 40)
    biggest_changes = dynamic_df.nlargest(5, 'vorp_change')[
        ['player_name', 'position', 'static_vorp', 'dynamic_vorp_final', 'vorp_change']
    ]
    for _, player in biggest_changes.iterrows():
        change = player['vorp_change']
        arrow = "🚀" if change > 0 else "📉" if change < 0 else "➡️"
        print(f"{arrow} {player['player_name']} ({player['position']}): "
              f"{player['static_vorp']:.1f} → {player['dynamic_vorp_final']:.1f} ({change:+.1f})")
    print()
    
    # Show top dynamic recommendations
    print("🏆 TOP DYNAMIC VORP RECOMMENDATIONS:")
    print("-" * 40)
    # Filter out drafted players
    drafted_players = {pick.player_id for pick in draft_state.picks}
    available_players = dynamic_df[~dynamic_df['player_id'].isin(drafted_players)]
    top_available = available_players.nlargest(10, 'dynamic_vorp_final')
    
    for i, (_, player) in enumerate(top_available.iterrows()):
        static_rank = int(player['vorp_overall_rank'])
        dynamic_rank = int(player['dynamic_vorp_overall_rank'])
        rank_change = static_rank - dynamic_rank
        rank_arrow = "⬆️" if rank_change > 0 else "⬇️" if rank_change < 0 else "➡️"
        
        print(f"{i+1:2d}. {player['player_name']:20} ({player['position']:2}) "
              f"VORP: {player['dynamic_vorp_final']:5.1f} "
              f"Rank: #{dynamic_rank:2d} {rank_arrow}({rank_change:+d})")
    print()
    
    # Test insights generation
    print("💡 DYNAMIC VORP INSIGHTS:")
    print("-" * 40)
    insights = calc.get_dynamic_vorp_insights(dynamic_df, draft_state)
    
    progress = insights['draft_progress']
    print(f"Draft Progress: {progress['picks_made']}/{progress['picks_made'] + (12*15 - progress['picks_made'])} picks "
          f"({progress['completion_percentage']:.1f}% complete)")
    
    print("\nPosition Scarcity Levels:")
    for pos, data in insights['position_scarcity'].items():
        level = data['scarcity_level']
        multiplier = data['scarcity_multiplier']
        color = "🔴" if level == "High" else "🟡" if level == "Medium" else "🟢"
        print(f"  {color} {pos}: {level} ({multiplier:.2f}x)")
    
    print(f"\n✅ Dynamic VORP Feature 1 test completed successfully!")
    print(f"📊 Processed {len(dynamic_df)} players with real-time draft adjustments")

def test_feature_2_draft_context_awareness():
    """Test Feature 2: Draft Context Awareness"""
    print("\n🧪 Testing Dynamic VORP Calculator - Feature 2: Draft Context Awareness")
    print("=" * 80)
    
    # Create sample projections
    projections = create_sample_projections()
    print(f"📊 Created {len(projections)} sample projections")
    
    # Test different draft scenarios
    scenarios = [
        ("Early Draft (Round 1)", 5),
        ("Mid Draft (Round 5)", 50),
        ("Late Draft (Round 10)", 110)
    ]
    
    calculator = DynamicVORPCalculator(num_teams=12)
    
    for scenario_name, picks_made in scenarios:
        print(f"\n📅 {scenario_name} - {picks_made} picks made:")
        print("-" * 50)
        
        # Create draft state for this scenario
        base_draft_state = create_sample_draft_state()
        
        # Adjust picks to match scenario by duplicating/extending existing picks
        while len(base_draft_state.picks) < picks_made:
            # Add more picks (simplified - just duplicate existing ones with new IDs)
            additional_picks = []
            for i, pick in enumerate(base_draft_state.picks[:min(10, picks_made - len(base_draft_state.picks))]):
                new_pick = DraftPick(
                    pick_number=len(base_draft_state.picks) + i + 1,
                    round_number=((len(base_draft_state.picks) + i) // 12) + 1,
                    round_pick=((len(base_draft_state.picks) + i) % 12) + 1,
                    player_id=f"extra_player_{len(base_draft_state.picks) + i + 1}",
                    player_name=f"Extra Player {len(base_draft_state.picks) + i + 1}",
                    position=pick.position,
                    team=pick.team,
                    draft_slot=pick.draft_slot,
                    user_id=pick.user_id
                )
                additional_picks.append(new_pick)
            
            for pick in additional_picks:
                base_draft_state.add_pick(pick)
        
        # Calculate dynamic VORP
        results = calculator.calculate_dynamic_vorp(projections, base_draft_state)
        
        # Show context awareness metrics
        current_round = results.iloc[0]['current_round']
        draft_progress = results.iloc[0]['draft_progress']
        
        print(f"📍 Current Round: {current_round}")
        print(f"📈 Draft Progress: {draft_progress:.1%}")
        
        # Show round strategy adjustments by position
        print(f"\n🎯 Round Strategy Adjustments:")
        for position in ['QB', 'RB', 'WR', 'TE']:
            pos_data = results[results['position'] == position]
            if not pos_data.empty:
                avg_adjustment = pos_data['round_strategy_adjustment'].mean()
                trend = "📈" if avg_adjustment > 1.05 else "📉" if avg_adjustment < 0.95 else "➡️"
                print(f"  {trend} {position}: {avg_adjustment:.3f} average adjustment")
        
        # Show top players with highest context adjustments
        print(f"\n🚀 Top 5 Context-Boosted Players:")
        top_adjusted = results.nlargest(5, 'round_strategy_adjustment')
        for i, (_, player) in enumerate(top_adjusted.iterrows()):
            boost = player['round_strategy_adjustment']
            boost_pct = (boost - 1) * 100
            print(f"  {i+1}. {player['player_name']:20} ({player['position']:2}): "
                  f"{boost:.3f} ({boost_pct:+.1f}%)")
        
        # Show context-aware value changes
        print(f"\n💎 Biggest Context-Driven Value Changes:")
        context_changes = results.copy()
        context_changes['context_impact'] = (context_changes['round_strategy_adjustment'] - 1) * context_changes['dynamic_vorp_final']
        top_context_impact = context_changes.nlargest(3, 'context_impact')
        
        for i, (_, player) in enumerate(top_context_impact.iterrows()):
            impact = player['context_impact']
            print(f"  {i+1}. {player['player_name']:20} ({player['position']:2}): "
                  f"{impact:+.1f} VORP boost from context")
    
    print(f"\n✅ Feature 2 (Draft Context Awareness) test completed successfully!")
    return results

if __name__ == "__main__":
    # Test both features
    test_dynamic_vorp()
    test_feature_2_draft_context_awareness() 
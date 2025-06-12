"""
Analyze QB depth chart patterns to create starter probability feature
"""
import pandas as pd

# Load QB projections
qb_df = pd.read_csv('projections/2025/QB_projections_2025.csv')

print("Teams with multiple QBs:")
print("="*50)

team_qbs = qb_df.groupby('team').agg({
    'player_name': list, 
    'projected_points': list
}).reset_index()

# Analyze teams with multiple QBs
multi_qb_teams = []
for _, row in team_qbs.iterrows():
    if len(row['player_name']) > 1:
        team = row['team']
        qbs = list(zip(row['player_name'], [round(p, 1) for p in row['projected_points']]))
        qbs_sorted = sorted(qbs, key=lambda x: x[1], reverse=True)
        
        print(f"\n{team}:")
        for i, (name, pts) in enumerate(qbs_sorted):
            role = "Starter" if i == 0 else f"Backup {i}"
            print(f"  {i+1}. {name:<20} - {pts:>6.1f} pts ({role})")
        
        multi_qb_teams.append((team, qbs_sorted))

print(f"\nTotal teams with multiple QBs: {len(multi_qb_teams)}")

# Identify clear starter patterns
print("\nStarter Probability Analysis:")
print("="*50)

for team, qbs in multi_qb_teams:
    if len(qbs) >= 2:
        starter_pts = qbs[0][1]
        backup_pts = qbs[1][1]
        pts_gap = starter_pts - backup_pts
        
        # Determine starter probability based on points gap
        if pts_gap > 100:
            starter_prob = 0.95
            backup_prob = 0.05
        elif pts_gap > 50:
            starter_prob = 0.85
            backup_prob = 0.15
        elif pts_gap > 25:
            starter_prob = 0.75
            backup_prob = 0.25
        else:
            starter_prob = 0.60
            backup_prob = 0.40
            
        print(f"\n{team}:")
        print(f"  {qbs[0][0]:<20} - Starter Prob: {starter_prob:.2f}")
        print(f"  {qbs[1][0]:<20} - Starter Prob: {backup_prob:.2f}")
        if len(qbs) > 2:
            for i in range(2, len(qbs)):
                print(f"  {qbs[i][0]:<20} - Starter Prob: 0.01")

# Check for problematic cases (backup QBs with high projections)
print("\nPotential Issues (Backups with High Projections):")
print("="*50)

for team, qbs in multi_qb_teams:
    if len(qbs) >= 2:
        starter_pts = qbs[0][1]
        backup_pts = qbs[1][1]
        
        # Flag if backup has unusually high projection
        if backup_pts > 200:  # Backup with 200+ points seems high
            print(f"⚠️  {team}: {qbs[1][0]} has {backup_pts} pts as backup") 
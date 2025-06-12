# PRIORITY ACTION PLAN - Fix Unrealistic Projections

## 🚨 CRITICAL ISSUE IDENTIFIED

**Root Cause:** Our projection logic treats historical `total_points` (season totals) as if they were per-game averages, leading to massive over-projections.

**Evidence:**
- Patrick Mahomes 2018: 1,821 total points over 18 games = 101 ppg (realistic)
- Our projection: 1,770 points (treating 1,821 as per-game average)
- Reality check: Elite QBs score 300-450 total points per season

---

## IMMEDIATE FIXES (Priority Order)

### 1. 🔥 CRITICAL - Fix Baseline Projection Logic
**File:** `scripts/07_quick_2025_projections.py`
**Issue:** `calculate_baseline_projection()` uses raw `total_points` without normalizing by games
**Fix:** Convert to per-game basis before averaging

```python
# CURRENT (WRONG):
baseline_points = np.average(recent_seasons['total_points'], weights=weights)

# SHOULD BE:
ppg_values = recent_seasons['total_points'] / recent_seasons['games_played']
baseline_ppg = np.average(ppg_values, weights=weights)
baseline_points = baseline_ppg * 17  # Expected games in 2025
```

### 2. 🔥 CRITICAL - Add Position-Specific Reality Caps
**File:** `scripts/07_quick_2025_projections.py`
**Add after projection calculation:**

```python
# Reality check caps
position_caps = {
    'QB': 450,   # Elite: ~26 ppg × 17 games
    'RB': 350,   # Elite: ~20 ppg × 17 games  
    'WR': 350,   # Elite: ~20 ppg × 17 games
    'TE': 250,   # Elite: ~15 ppg × 17 games
    'K': 150     # Elite: ~9 ppg × 17 games
}
projected_points = min(projected_points, position_caps.get(position, 200))
```

### 3. 🔥 CRITICAL - Fix Rookie/No-History Baselines
**Current rookie baselines are also too high:**
```python
# CURRENT (WRONG):
position_averages = {'QB': 200, 'RB': 120, 'WR': 130, 'TE': 90, 'K': 110}

# SHOULD BE (per-game × 17):
position_averages = {
    'QB': 12 * 17,   # 12 ppg rookie QB
    'RB': 8 * 17,    # 8 ppg rookie RB
    'WR': 8 * 17,    # 8 ppg rookie WR
    'TE': 5 * 17,    # 5 ppg rookie TE
    'K': 7 * 17      # 7 ppg rookie K
}
```

### 4. 🔥 HIGH - Validate Age Adjustments
**Current age curves may be too aggressive when applied to inflated bases**
- Review multipliers in `apply_age_adjustment()`
- Consider reducing magnitude of adjustments

### 5. 🔥 HIGH - Validate Team Adjustments  
**5% boosts on inflated numbers create compound errors**
- Review team adjustment logic in `apply_position_adjustments()`
- Consider reducing from 5% to 2-3%

---

## VALIDATION STEPS

### Before Fix - Current Results:
- Patrick Mahomes: 1,770 pts (impossible)
- Josh Allen: 1,740 pts (impossible)
- Average QB: 377 pts (too high)

### After Fix - Expected Results:
- Patrick Mahomes: ~400-450 pts (realistic elite)
- Josh Allen: ~400-450 pts (realistic elite)  
- Average QB: ~250-300 pts (realistic)

### Cross-Reference Benchmarks:
- 2024 Josh Allen actual: ~420 fantasy points
- 2024 Patrick Mahomes actual: ~380 fantasy points
- 2024 Lamar Jackson actual: ~390 fantasy points

---

## IMPLEMENTATION PRIORITY

1. **Fix `calculate_baseline_projection()`** - 30 minutes
2. **Add position caps** - 15 minutes  
3. **Fix rookie baselines** - 10 minutes
4. **Test and validate** - 30 minutes
5. **Re-run projections** - 5 minutes

**Total estimated time:** ~90 minutes to fix critical issues

---

## SUCCESS CRITERIA

✅ **No player projected above realistic maximums**
- QB max: ~450 points
- RB/WR max: ~350 points  
- TE max: ~250 points

✅ **Top players align with expert consensus**
- Mahomes, Allen, Hurts in top 3 QBs
- Reasonable point spreads between tiers

✅ **Projections pass sanity check**
- Elite players: 20-26 ppg
- Average starters: 12-18 ppg
- Backups/rookies: 5-12 ppg

---

## NEXT STEPS AFTER FIXES

1. **Re-run model training** with corrected feature engineering
2. **Implement advanced optimizations** from backlog
3. **Add starter probability features** for QB accuracy
4. **Cross-validate against 2024 actuals**

This fix will make the projections immediately usable while we work on more sophisticated improvements. 
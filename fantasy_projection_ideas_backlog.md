# Fantasy Projection Model – Ideas & Experiments Backlog

_This document lists optional avenues to explore, organized by the same five phases in the project tracker.  Treat it as a buffet—pull items into the main tracker when you're ready to commit._

---

## 🚨 CRITICAL ISSUES - IMMEDIATE FIXES NEEDED

**Current Status:** ✅ **RESOLVED** - The quick projections have been fixed and now produce realistic results.

### Issue Analysis & Resolution (December 2024)
- **Problem:** Patrick Mahomes projected at 1,770 points (~104 pts/game over 17 games)
- **Root Cause:** Historical data was treating season totals as per-game averages
- **Solution Applied:** Proper conversion of `total_points` to per-game averages with games-played normalization
- **Current Results:** Realistic projections (Mahomes: 321 pts, Allen: 391 pts, Barkley: 413 pts)

---

## 🔥 NEW HIGH PRIORITY - PIPELINE IMPROVEMENTS

**Current Status:** Manual fallback system working, but ML models need integration.

### IMMEDIATE PRIORITIES (Next 1-2 weeks)

| Priority | Item | Effort | Impact | Notes |
|----------|------|--------|--------|-------|
| **`P0 - CRITICAL`** | **Fix ML Model Persistence** | 4 hours | High | Models train successfully but don't save/load properly. Need to debug model serialization in `04_train_models.py` and `06_generate_2025_predictions.py` |
| **`P0 - CRITICAL`** | **Hybrid ML + Manual System** | 6 hours | High | Use ML models as base predictions, apply manual adjustments for validation and edge cases |
| **`P1 - HIGH`** | **Model Performance Validation** | 3 hours | Medium | Cross-validate ML model predictions against 2024 actuals to ensure they're realistic |
| **`P1 - HIGH`** | **Ensemble Integration** | 4 hours | Medium | Combine CatBoost + LightGBM predictions with manual logic for robust projections |

### MEDIUM TERM PRIORITIES (Next 2-4 weeks)

| Priority | Item | Effort | Impact | Notes |
|----------|------|--------|--------|-------|
| **`P2 - MEDIUM`** | **Weekly Update Pipeline** | 8 hours | High | Implement in-season projection updates as new data becomes available |
| **`P2 - MEDIUM`** | **Injury Integration** | 6 hours | Medium | Factor in injury history and current status in projections |
| **`P2 - MEDIUM`** | **Matchup Context Features** | 5 hours | Medium | Add opponent strength, weather, and game script factors |
| **`P3 - LOW`** | **Advanced Confidence Scoring** | 4 hours | Low | Improve confidence levels based on data quality and model uncertainty |

### LONG TERM PRIORITIES (Next 1-2 months)

| Priority | Item | Effort | Impact | Notes |
|----------|------|--------|--------|-------|
| **`P3 - LOW`** | **Real-time Feature Pipeline** | 12 hours | High | Live injury reports, snap counts, target share integration |
| **`P3 - LOW`** | **Advanced ML Models** | 16 hours | Medium | Neural networks, time series models, transformer architectures |
| **`P3 - LOW`** | **Multi-timeframe Projections** | 10 hours | Medium | Season, weekly, and daily projection capabilities |

---

## Phase 1 — Data Ingestion & Cleaning

| Idea | Rationale / Notes |
|------|-------------------|
| **`COMPLETED` - Scoring System Audit** | ✅ Verified fantasy scoring is correct. Issue was data interpretation, not scoring rules. |
| **`COMPLETED` - Games Played Normalization** | ✅ Fixed per-game normalization in projection logic. All historical averages now properly calculated. |
| **Add combine & athletic testing data** | Height‑adjusted speed score, burst score—can proxy upside for rookies. Sources: NFLCombineResults.com, `nflreadr::combine`.
| **Coach & scheme table** | Head‑coach + OC IDs, historical pass‑rate‑over‑expected (PROE); can help model usage shifts after coordinator changes.
| **Weather & dome flags** | Simple one‑hot for home‑stadium dome (IND, NO, DAL, ATL, DET, LV, ARI, MIN, LAR). Minor but free signal.
| **Depth chart start-of‑season snapshot** | Merge FantasyLife's Week 1 projected starters to capture camp battles.
| **Data versioning via DVC** | Lightweight tracking of `data/raw` to ensure downstream reproducibility without bloating Git.
| **Unit tests for scoring function** | Verify 1:1 with official SFB14 scoring on a handful of hand‑calculated plays; guards against future rule tweaks.

---

## Phase 2 — Feature Engineering

| Idea | Rationale / Notes |
|------|-------------------|
| **`COMPLETED` - Per-Game Feature Recalculation** | ✅ All projection logic now uses proper per-game calculations with games-played normalization. |
| **`HIGH PRIORITY` - QB Starter Probability Feature** | The QB model's high RMSE is likely due to difficulty separating starters from backups. Engineer features to predict `is_starter` status. Sources: Depth charts (FantasyLife), Vegas odds, team contract data, prior season snap counts. This will be the most impactful next step for QB accuracy.
| **`COMPLETED` - Realistic Baseline Validation** | ✅ Validated against 2024 results. Current projections align well with actual performance. |
| **Exponential‑decay weighted stats** | Gives 2024 > 2023 > 2022 weight—tune λ inside Optuna.
| **Injury propensity index** | Logistic model using games_missed_last3, BMI, position; output probability to miss ≥2 games.
| **Player similarity embeddings** | UMAP/T‑SNE of raw per‑play vectors → k‑nearest historical comps; add the average future‑points of comps as feature.
| **Age*Usage interaction term** | Captures diminishing returns for older high‑touch RBs.
| **Team pace & play volume** | Merge FootballOutsiders seconds‑per‑play; multiply by Vegas implied totals for a "plays opportunity" metric.
| **Contract‑year flag + years_remaining** | RBs historically see uptick in touches in contract years.
| **Stack‑rank percentile features** | Convert certain aggregates into within‑position percentiles (e.g., targets %).
| **Lagged efficiency deltas** | Year‑over‑year change in yards per carry/route, capturing improving/declining skill.

---

## Phase 3 — Modeling & Evaluation

| Idea | Rationale / Notes |
|------|-------------------|
| **`COMPLETED` - Projection Sanity Checks** | ✅ Added position-specific caps and validation against historical maximums. |
| **`COMPLETED` - Cross-Validation Against 2024 Actuals** | ✅ Validated projections against known 2024 results. Scale and accuracy confirmed. |
| **`IN PROGRESS` - Position‑specific sub‑models** | ✅ Models exist and trained successfully, but need proper persistence/loading integration. |
| **Quantile regression** | CatBoost supports `Quantile:alpha=0.9` → gives upside distribution for risk‑adjusted drafting.
| **TabNet or FT‑Transformer** | Deep‑learning tabular models may capture higher‑order interactions; useful experiment for 1‑week bake‑off.
| **Monotonic constraints in LightGBM** | Force projections to increase with positive features (e.g., more targets ⇒ more points) to reduce nonsense.
| **Blending with public consensus** | Linear blend (λ) with FantasyPros ECR or ESPN projections; often boosts accuracy out‑of‑sample.
| **SHAP clustering heatmap** | Visual sanity check that drivers make football sense (age negative, targets positive, etc.).
| **K‑fold OOB ensembling** | 5× CatBoost models with different seeds; average predictions for variance reduction.
| **Cost‑sensitive evaluation** | Weight errors by ADP; small mis‑rank within top 24 matters more than a miss on the RB56.

---

## Phase 4 — Final Training & Export

| Idea | Rationale / Notes |
|------|-------------------|
| **Post‑hoc injury adjustment** | Multiply projection by (1 – injury probability) for floor‑seeking drafter variant.
| **Tier smoothing** | Apply isotonic regression to enforce non‑decreasing rank order after ensemble blending.
| **Scenario generator** | Produce "Best 5 %", "Median", "Worst 5 %" quantile projections for risk diagnostics.
| **Time‑stamp model file with Git SHA** | Easier traceability when multiple rebuilds occur.

---

## Phase 5 — Deployment & Handoff

| Idea | Rationale / Notes |
|------|-------------------|
| **REST endpoint for projections** | FastAPI wrapper so the draft app can pull live data rather than reading static Parquet.
| **Lightweight Streamlit prototype** | Quick smoke test UI before full Shiny build; supports drag‑and‑drop CSV of draft board.
| **On‑draft pick tracking** | Socket connection listening to Sleeper API; auto‑recalculates top available players.
| **CI badge in README** | Visual cue that pipeline passes on latest commit.
| **Schedule nightly cron in July–August** | Auto‑refresh ADP, injuries, and re‑score; send email diff if rank delta > 5 for any top‑36 player.
| **Automated PDF summary** | Quarto renders top 200 projections with SHAP insights so you have a printable cheat sheet.

---

## Nice‑to‑Have / Stretch Ideas
- **Reinforcement‑learning draft bot** that simulates end‑to‑end drafting vs. market to learn optimal pick strategy.
- **In‑season weekly projection pipeline** reusing most features but switching target to Week X fantasy points.
- **Live GCP Vertex ML pipeline** for scale‑out hyper‑parameter sweeps if local hardware becomes bottleneck.

> **How to use this doc:** Move an item to the main tracker once you decide to pursue it.  Delete or archive once complete to keep focus tight.


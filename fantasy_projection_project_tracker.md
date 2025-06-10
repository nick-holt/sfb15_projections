# Season‑Long Fantasy Projection Model – Project Tracker

_A living document to coordinate all work streams for the 2025 draft‑prep projection system._

---

## 0. Quick Links  
*(Update as URLs/paths become available)*
| Item | Link / Path |
|------|-------------|
| Git repo | `github.com/<org>/fantasy‑projection` |
| Data lake root | `data/` |
| MLflow UI | _TBD_ |
| Docker image registry | _TBD_ |
| Draft‑assistant UI | `app/` |

---

## 1. Objectives
- Produce season‑total fantasy‑point projections for **QB, RB, WR, TE, K** covering the 2025 NFL season.
- Maximize **draft‑day ranking accuracy** (Spearman ρ & Top‑X Hit Rate) while minimizing RMSE.
- Export a `players.parquet` feed powering a Shiny/Streamlit draft assistant.
- Ensure the pipeline is **reproducible** (Docker + Conda + MLflow) and refreshable next preseason with one command.

---

## 2. Data Inventory
| # | Dataset | Granularity | Location | Status | Notes |
|---|---------|------------|----------|--------|-------|
| 1 | `season_stats.parquet` | Season | `data/processed/` | ☐ | Output of build script (total points + *_points fields) |
| 2 | `weekly_stats.parquet` | Weekly | `data/processed/` | ☐ | Needed only for `games_played` & `games_missed` |
| 3 | Roster snapshot | Season | `data/raw/roster_2025‑01‑15.csv` | ☐ | Height, weight, DOB, experience |
| 4 | Injury table | Weekly | `data/raw/injuries_*.parquet` | ☐ | Scrape DraftSharks / PFR |
| 5 | Contract table | Season | `data/raw/contracts.csv` | ☐ | Spotrac scrape |
| 6 | Depth chart snaps | Weekly | `data/raw/snaps.parquet` | ☐ | FantasyLife API |
| 7 | Vegas & ADP | Season / Preseason | `data/raw/vegas_adp.parquet` | ☐ | Sportsbook & Underdog APIs |

Legend: ☐ = Not started, ◐ = In progress, ☑ = Complete

---

## 3. Task Board

### Phase 1 — Data Ingestion & Cleaning
- [ ] **Set up repo & env** (`environment.yml`, Dockerfile)
- [ ] Convert CSV/XLSX to Parquet (`season_stats.parquet`, `weekly_stats.parquet`)
- [ ] Snapshot roster data and join `player_id` keys
- [ ] Build & schedule **injury scraper**
- [ ] Build contract scraper (Spotrac)
- [ ] Fetch depth‑chart snap counts
- [ ] Pull Vegas win totals & implied points
- [ ] Pull preseason ADP feed

### Phase 2 — Feature Engineering
- [ ] Implement `features/build_features.py` pipeline
- [ ] Derive `games_played`, `games_missed`
- [ ] Add exponential‑decay historical aggregates
- [ ] Merge injury & contract features
- [ ] Write feature schema JSON for model ingest

### Phase 3 — Modeling & Evaluation
- [ ] Implement Season‑Series CV splitter
- [ ] Baseline Linear/L2 & GAM models
- [ ] Optuna study for **CatBoostRegressor**
- [ ] Train LightGBM (fallback)
- [ ] Build stacking ensemble (CatBoost + LightGBM + GAM)
- [ ] Log all runs to MLflow
- [ ] Compute evaluation dashboard (RMSE, MAE, Spearman, Top‑X)
- [ ] Implement Monte‑Carlo draft simulation metric (SDV)

### Phase 4 — Final Training & Export
- [ ] Retrain best model on 2010‑2024
- [ ] Score 2025 preseason feature set
- [ ] Save artifacts (`predictions_2025.csv`, `catboost_model_2025.cbm`, `feature_map.json`)

### Phase 5 — Deployment & Handoff
- [ ] Build Docker image (`make all` entrypoint)
- [ ] Document runbook (`README.md` + architecture diagram)
- [ ] Provide data contract to UI team
- [ ] Archive notebook‑based EDA report (`outputs/eda_report.html`)

---

## 4. Milestone Timeline (Target)
| Week | Dates (Mon‑Sun) | Milestone | Owner | Status | Notes |
|------|-----------------|-----------|-------|--------|-------|
| 1 | Jun 16 – Jun 22 | Ingestion scripts functional | | ☐ | |
| 2 | Jun 23 – Jun 29 | Feature pipeline + EDA report | | ☐ | |
| 3 | Jun 30 – Jul 06 | Baseline & tuned CatBoost | | ☐ | |
| 4 | Jul 07 – Jul 13 | Ensemble & evaluation dashboard | | ☐ | |
| 5 | Jul 14 – Jul 20 | Final model + deliverables | | ☐ | |

---

## 5. Metrics & Acceptance Criteria
- **RMSE (2023 test)** ≤ baseline × 0.85
- **Spearman ρ** ≥ 0.80 across all positions
- **Top‑36 Hit Rate (RB/WR)** ≥ 70 %
- **Simulated Draft Value gain** ≥ +1.0 wins per season (12‑team sim)

---

## 6. Risks & Mitigation
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|-----------|
| External APIs rate‑limit | Medium | Med | Cache raw pulls; stagger requests |
| Inconsistent player IDs across tables | High | High | Maintain master `dim_players` mapping with GSIS ids |
| CatBoost overfits smaller position groups (TE, K) | Medium | Med | Use group‑specific regularization; monitor CV curves |
| Data drift in new scoring tweaks | Low | High | Freeze scoring function; add unit tests |

---

## 7. Change Log
| Date | Author | Description |
|------|--------|-------------|
| 2025‑06‑10 | Initial | Document created from ChatGPT blueprint |

---

> _Keep this tracker up to date. When tasks move forward, flip the checkbox and add notes._


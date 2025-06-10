# Fantasy Projection Model – Ideas & Experiments Backlog

_This document lists optional avenues to explore, organized by the same five phases in the project tracker.  Treat it as a buffet—pull items into the main tracker when you’re ready to commit._

---

## Phase 1 — Data Ingestion & Cleaning

| Idea | Rationale / Notes |
|------|-------------------|
| **Add combine & athletic testing data** | Height‑adjusted speed score, burst score—can proxy upside for rookies. Sources: NFLCombineResults.com, `nflreadr::combine`.
| **Coach & scheme table** | Head‑coach + OC IDs, historical pass‑rate‑over‑expected (PROE); can help model usage shifts after coordinator changes.
| **Weather & dome flags** | Simple one‑hot for home‑stadium dome (IND, NO, DAL, ATL, DET, LV, ARI, MIN, LAR). Minor but free signal.
| **Depth chart start-of‑season snapshot** | Merge FantasyLife’s Week 1 projected starters to capture camp battles.
| **Data versioning via DVC** | Lightweight tracking of `data/raw` to ensure downstream reproducibility without bloating Git.
| **Unit tests for scoring function** | Verify 1:1 with official SFB14 scoring on a handful of hand‑calculated plays; guards against future rule tweaks.

---

## Phase 2 — Feature Engineering

| Idea | Rationale / Notes |
|------|-------------------|
| **Exponential‑decay weighted stats** | Gives 2024 > 2023 > 2022 weight—tune λ inside Optuna.
| **Injury propensity index** | Logistic model using games_missed_last3, BMI, position; output probability to miss ≥2 games.
| **Player similarity embeddings** | UMAP/T‑SNE of raw per‑play vectors → k‑nearest historical comps; add the average future‑points of comps as feature.
| **Age*Usage interaction term** | Captures diminishing returns for older high‑touch RBs.
| **Team pace & play volume** | Merge FootballOutsiders seconds‑per‑play; multiply by Vegas implied totals for a "plays opportunity" metric.
| **Contract‑year flag + years_remaining** | RBs historically see uptick in touches in contract years.
| **Stack‑rank percentile features** | Convert certain aggregates into within‑position percentiles (e.g., targets %).
| **Lagged efficiency deltas** | Year‑over‑year change in yards per carry/route, capturing improving/declining skill.

---

## Phase 3 — Modeling & Evaluation

| Idea | Rationale / Notes |
|------|-------------------|
| **Position‑specific sub‑models** | Separate CatBoost for QB vs RB vs WR vs TE; captures unique data‑generating processes.
| **Quantile regression** | CatBoost supports `Quantile:alpha=0.9` → gives upside distribution for risk‑adjusted drafting.
| **TabNet or FT‑Transformer** | Deep‑learning tabular models may capture higher‑order interactions; useful experiment for 1‑week bake‑off.
| **Monotonic constraints in LightGBM** | Force projections to increase with positive features (e.g., more targets ⇒ more points) to reduce nonsense.
| **Blending with public consensus** | Linear blend (λ) with FantasyPros ECR or ESPN projections; often boosts accuracy out‑of‑sample.
| **SHAP clustering heatmap** | Visual sanity check that drivers make football sense (age negative, targets positive, etc.).
| **K‑fold OOB ensembling** | 5× CatBoost models with different seeds; average predictions for variance reduction.
| **Cost‑sensitive evaluation** | Weight errors by ADP; small mis‑rank within top 24 matters more than a miss on the RB56.

---

## Phase 4 — Final Training & Export

| Idea | Rationale / Notes |
|------|-------------------|
| **Post‑hoc injury adjustment** | Multiply projection by (1 – injury probability) for floor‑seeking drafter variant.
| **Tier smoothing** | Apply isotonic regression to enforce non‑decreasing rank order after ensemble blending.
| **Scenario generator** | Produce "Best 5 %", "Median", "Worst 5 %" quantile projections for risk diagnostics.
| **Time‑stamp model file with Git SHA** | Easier traceability when multiple rebuilds occur.

---

## Phase 5 — Deployment & Handoff

| Idea | Rationale / Notes |
|------|-------------------|
| **REST endpoint for projections** | FastAPI wrapper so the draft app can pull live data rather than reading static Parquet.
| **Lightweight Streamlit prototype** | Quick smoke test UI before full Shiny build; supports drag‑and‑drop CSV of draft board.
| **On‑draft pick tracking** | Socket connection listening to Sleeper API; auto‑recalculates top available players.
| **CI badge in README** | Visual cue that pipeline passes on latest commit.
| **Schedule nightly cron in July–August** | Auto‑refresh ADP, injuries, and re‑score; send email diff if rank delta > 5 for any top‑36 player.
| **Automated PDF summary** | Quarto renders top 200 projections with SHAP insights so you have a printable cheat sheet.

---

## Nice‑to‑Have / Stretch Ideas
- **Reinforcement‑learning draft bot** that simulates end‑to‑end drafting vs. market to learn optimal pick strategy.
- **In‑season weekly projection pipeline** reusing most features but switching target to Week X fantasy points.
- **Live GCP Vertex ML pipeline** for scale‑out hyper‑parameter sweeps if local hardware becomes bottleneck.

> **How to use this doc:** Move an item to the main tracker once you decide to pursue it.  Delete or archive once complete to keep focus tight.


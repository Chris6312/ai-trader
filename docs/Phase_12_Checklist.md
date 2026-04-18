Phase 12 Checklist
ML Scoring Engine + Historical Backtesting / Training Pipeline
PROJECT STATE (Target)

Current Phase:
Phase 12 – Machine Learning scoring layer

Goal:
Use historical candles + historical features + historical replay/backtesting to train ML models that improve ranking of candidates for:

trend_continuation
pullback_reclaim

ML must enhance ranking only.
ML must not control execution logic.
ML must not bypass deterministic filters, risk, or execution rails.

Phase 12A — Historical Training Universe Freeze

Purpose:
Create the historical universe snapshot set used for replay and model training.

Requirements:

freeze symbol membership by date
support stocks and crypto separately
avoid survivorship bias where practical
preserve delisted/missing-history handling rules
store source-of-truth symbol registry snapshots for each replay period

Inputs:

Phase 11 symbol registry
yFinance stock history
Kraken/crypto historical symbol universe

Deliverables:

historical universe snapshot table or persisted snapshots
replay-ready symbol membership by date
Phase 12B — Historical Feature Store Builder

Purpose:
Build feature rows for each symbol on each historical decision date.

Each row should contain:

symbol
asset_class
decision_date
strategy_eligibility flags
regime state
technical features
sentiment features if available
feature_schema_version

Important:

These must be the same feature definitions used in live scoring.

Constraints:

features must only use data available up to that historical decision date
no future leakage
no forward-looking values in rolling indicators
all features timestamped by decision date

Deliverables:

historical feature store builder
persisted feature table(s)
feature validation checks for leakage prevention
Phase 12C — Historical Strategy Replay / Backtesting Engine

Purpose:
Replay historical dates as if the bot were running live, so we can determine which candidates actually followed through.

This is the missing bridge.

The replay engine should:

iterate historical decision dates
load only features available on that date
apply deterministic eligibility filters
assign candidate symbols to:
trend_continuation
pullback_reclaim
avoid
simulate what the AI/ML layer would have seen on that day
measure what happened afterward over the defined forward window

This is not execution backtesting at first.
This is candidate follow-through replay.

Outputs per symbol/date:

was eligible or not
strategy bucket
forward return windows
max favorable excursion
max adverse excursion
structure invalidation flag
follow-through success/failure label

Deliverables:

historical replay engine
replay result table
per-strategy replay metrics
Phase 12D — Label Generation from Historical Replay

Purpose:
Turn replay outcomes into supervised learning labels.

Labels must be generated from replay results, not guessed directly from raw returns.

Trend Continuation label examples

Success if, over next N bars:

forward return exceeds threshold
structure remains intact
no major invalidation below reference level
favorable excursion exceeds minimum target

Possible fields:

trend_success_binary
trend_forward_return_n
trend_mfe_n
trend_mae_n
trend_invalidation_flag
Pullback Reclaim label examples

Success if, over next N bars:

reclaim level holds
forward return exceeds threshold
trend spine remains intact
price does not immediately fail below reclaim zone

Possible fields:

reclaim_success_binary
reclaim_forward_return_n
reclaim_mfe_n
reclaim_mae_n
reclaim_failure_flag

Constraints:

labels must be deterministic
labels must be reproducible
labels must be versioned

Deliverables:

label generation module
strategy-specific label definitions
label version registry
Phase 12E — Backtesting Policy Definitions

Purpose:
Lock how historical replay decides success/failure so training does not drift.

Must define:

decision timeframe
forward evaluation window
benchmark comparisons if used
success threshold
failure threshold
structure invalidation rules
missing-bar handling
corporate action / split handling for stocks where applicable
weekend/24-7 handling differences for crypto

Example policies:

Trend Continuation
evaluate next 5 bars or 10 bars
success requires minimum forward return or ATR multiple
fail if structure breaks before target-quality move occurs
Pullback Reclaim
evaluate next 3 bars or 5 bars
success requires reclaim hold plus positive follow-through
fail if reclaim level breaks quickly

Deliverables:

replay/backtest policy doc
policy constants in code
versioned policy identifier on replay results
Phase 12F — Training Dataset Builder

Purpose:
Assemble final ML-ready dataset from:

historical feature store
historical replay outputs
generated labels

Each training row:

symbol
asset_class
decision_date
strategy_bucket
feature vector
regime state
label(s)
replay policy version
feature version
label version

Constraints:

one row per symbol per decision date per strategy context
no future leakage
training dataset reproducible from stored snapshots

Deliverables:

training dataset builder service
exportable ML dataset
dataset integrity checks
Phase 12G — Baseline ML Model

Purpose:
Train initial models using replay-derived labels.

Initial model types:

LogisticRegression
RandomForest
XGBoost

Recommended v1:

one model per strategy
trend_continuation model
pullback_reclaim model

Model output:

probability of successful follow-through
ranking score
optional confidence band

Constraints:

model must be explainable
model must not replace deterministic strategy eligibility
model must score only eligible candidates

Deliverables:

training pipeline
saved model artifacts
model metadata persistence
Phase 12H — Walk-Forward Backtesting / Validation

Purpose:
Validate model performance the way it would have behaved historically.

Process:

train on prior window
score next unseen window
compare predictions against replay-derived outcomes
roll forward and repeat

Example windows:

Stocks:

train on prior 12–24 months
test on next 1–2 months

Crypto:

train on prior 6–12 months
test on next 2–4 weeks

Metrics:

precision
recall
rank correlation
top-N hit rate
success rate of top decile candidates
stability by regime
stability by asset class

Important:

This is where historical backtesting directly supports ML training quality.

Deliverables:

walk-forward validation runner
per-window validation reports
summary evaluation report
Phase 12I — Feature Importance + Drift Review

Purpose:
Understand what the model is learning and whether that changes over time.

Review:

feature importance
importance drift by retrain period
regime-specific feature behavior
asset-class-specific feature behavior

Deliverables:

feature importance reports
drift monitoring outputs
Phase 12J — ML Scoring Integration

Purpose:
Integrate model scores into the universe composer.

Composite example:

composite_score =
0.40 technical_score +
0.20 sentiment_score +
0.15 regime_alignment_score +
0.25 ml_followthrough_score

Constraints:

ML can rank only after deterministic filters pass
ML cannot create unsupported symbols
ML cannot bypass risk or execution
ML cannot modify open-position management rules

Deliverables:

ML score integration in universe composer
ranked output including model score
Phase 12K — Retraining Schedule

Purpose:
Define how the model stays current without constant churn.

Schedule:

daily: score current candidates
weekly: retrain model
monthly: deeper performance review

Recommended retrain cadence:

weekend retraining
stocks: rolling 12–24 month window
crypto: rolling 6–12 month window

Deliverables:

retrain script
model versioning
retrain metadata persistence
Phase 12L — Model Persistence and Reproducibility

Purpose:
Ensure any score can be traced back to:

model version
training window
replay policy version
feature version
label version

Deliverables:

model registry table or metadata persistence
reproducibility metadata on scored outputs
Phase 12M — ML Inspection API

Endpoints:

GET /api/ml/model-info
GET /api/ml/feature-importance
GET /api/ml/symbol-score/{symbol}
GET /api/ml/validation/latest

Constraints:

read-only
inspectable
tied to versioned artifacts
Phase 12N — Audit Guard

Create:

docs/Phase_12_Checklist.md
docs/Phase_12_Audit.md

Must document:

how replay/backtesting creates labels
how walk-forward validation is performed
what ML is allowed to influence
what ML is forbidden to influence
Phase 12 Complete When
historical replay engine exists
replay outputs generate deterministic labels
ML training uses replay-derived outcomes
walk-forward validation is green enough to justify ranking use
ML improves candidate ranking without touching execution logic
all scoring is reproducible and inspectable
The key correction

The missing architecture piece is:

historical candles
→ historical features by decision date
→ historical strategy replay/backtesting
→ deterministic labels
→ ML training dataset
→ model training
→ walk-forward validation
→ live ranking score

That replay/backtesting layer is what makes the ML legitimate instead of decorative wallpaper.
Below is the **locked-in Phase 12 specification** for AI-Trader-v1.
This serves two purposes:

1. **Updated Phase 12 Checklist**
2. **ML Contract** → defines what ML is allowed to do, what it is NOT allowed to do, and how drift is prevented

Think of this as the constitution for the ML layer 🏛️🤖
Models may evolve, but the laws of the land remain stable.

---

# Phase 12 Checklist (Updated)

## Phase 12 — ML Scoring Engine + Historical Backtesting / Training Pipeline

### 12A — Historical Training Universe Freeze

Create replay-safe symbol membership snapshots so training data reflects what was actually tradable at each decision date.

Requirements:

* freeze symbol membership by decision_date
* separate stock and crypto universes
* avoid survivorship bias where practical
* persist symbol registry snapshot references
* store universe metadata:

  * source
  * snapshot timestamp
  * asset class
  * inclusion rationale version
* ensure future feature rows derive only from information available at decision time

Deliverables:

* historical_universe_snapshots table
* persistence service
* replay-safe lookup methods
* tests proving membership immutability

---

### 12B — Historical Feature Store Builder

Create point-in-time feature snapshots for every symbol in the historical universe.

Features must be reproducible using only past data.

Feature categories:

* price structure
* volatility
* volume behavior
* regime context
* sentiment signals
* derived strategy indicators

Examples:

* SMA/EMA stacks
* ATR %
* relative volume
* breakout structure features
* pullback structure features
* regime flags
* sentiment score snapshots

Requirements:

* no future leakage
* versioned feature definitions
* deterministic feature calculation
* reproducible dataset builds

Deliverables:

* feature store schema
* feature generation services
* feature version tracking

---

### 12C — Historical Strategy Replay / Backtesting Engine

Replay strategies using historical candles and frozen universes.

Reconstruct decision context as if the bot were running live at each historical timestamp.

Requirements:

* reuse deterministic strategy logic
* reuse deterministic risk rules
* simulate trade lifecycle
* simulate exit policies
* track entry signals
* track exit triggers
* store replay results

Replay outputs:

* entry decision context
* exit outcome
* trade duration
* max favorable excursion
* max adverse excursion

Deliverables:

* replay engine service
* replay result persistence
* deterministic reproducibility tests

---

### 12D — Label Generation from Historical Replay

Create ML labels using replay outcomes.

Labels derived from:

* forward returns
* trade success criteria
* strategy-specific success thresholds

Examples:

* profitable trade within max_hold_hours
* target reached before stop
* follow-through strength
* drawdown constraints

Requirements:

* labels derived only from replay results
* no future leakage
* versioned label policy definitions

Deliverables:

* label generator service
* label schema
* label version metadata

---

### 12E — Backtesting Policy Definitions

Define the rule set governing replay and labeling behavior.

Includes:

* trade evaluation window
* success criteria
* acceptable drawdown levels
* regime-aware evaluation adjustments

Policies must be versioned.

Deliverables:

* backtesting policy schema
* policy registry
* policy version tracking

---

### 12F — Training Dataset Builder

Assemble final ML dataset.

Dataset combines:

* historical universe membership
* point-in-time feature rows
* replay-derived labels
* regime classification
* strategy context

Requirements:

* version dataset builds
* include dataset metadata
* maintain reproducibility

Deliverables:

* dataset builder service
* dataset version schema

---

### 12G — Baseline ML Model

Train initial model(s).

Initial scope:

* one model per strategy
* gradient boosted trees or equivalent
* interpretable feature inputs

Strategies:

* pullback_reclaim
* trend_continuation

Deliverables:

* baseline model artifacts
* training pipeline
* hyperparameter configuration

---

### 12H — Walk-Forward Backtesting / Validation

Validate models using walk-forward methodology.

Evaluate:

* predictive power stability
* regime performance differences
* degradation behavior

Metrics:

* win rate
* average return
* drawdown profile
* calibration quality

Deliverables:

* walk-forward validation reports
* validation metric persistence

---

### 12I — Feature Importance + Drift Review

Generate explainability artifacts.

Methods:

* SHAP importance
* permutation importance
* tree-based importance

Track:

* global importance
* regime-specific importance
* strategy-specific importance
* drift signals

Deliverables:

* feature importance persistence
* drift metrics persistence

---

### 12J — ML Scoring Integration

Integrate model scoring into candidate ranking flow.

ML responsibilities:

* rank eligible candidates
* produce confidence scores
* provide explanation payloads

ML must not:

* bypass deterministic filters
* override risk controls
* override execution constraints

Deliverables:

* scoring service
* ranking integration logic

---

### 12K — Retraining Schedule

Define retraining cadence.

Examples:

* weekly retraining
* rolling dataset updates
* drift-triggered retraining

Deliverables:

* retrain scheduler config
* retrain job pipeline

---

### 12L — Model Persistence and Reproducibility

Persist model artifacts and metadata.

Track:

* dataset version
* feature version
* label version
* policy version
* training window
* hyperparameters

Deliverables:

* model registry
* artifact storage references

---

### 12M — ML Transparency UI + API Contract

Expose what the model learned.

Includes:

Global learning view:

* top feature importance
* SHAP summary
* permutation importance
* regime importance

Per-trade explanation view:

* score
* probability
* baseline expectation
* positive contributors
* negative contributors
* feature snapshot

Model health view:

* validation metrics
* walk-forward metrics
* calibration
* confusion matrix
* score bucket returns
* drift signals

Frontend pages:

* ML Overview
* Model Registry
* Symbol Explain Drawer

Deliverables:

* ML transparency endpoints
* React pages
* explanation payload schema

---

### 12N — ML Runtime Controls + Guardrails

Add operator controls.

Runtime controls:

* ML mode:

  * OFF
  * OBSERVE
  * ASSIST
  * ACTIVE
* active model selector
* rollback to previous model
* minimum score threshold
* asset scope selection
* emergency ML disable

Guardrails:

* regime scope
* session scope
* drift fail-safe
* drawdown disable trigger
* data freshness gating

All changes must be:

* auditable
* reversible
* confirmed

Deliverables:

* runtime config schema
* runtime control endpoints
* audit logging

---

### 12O — ML Inspection API + Strategy Learning Panels

Provide deeper inspection surfaces.

Strategy panels:

* feature importance by strategy
* regime performance by strategy
* model comparison views
* version change impact

Deliverables:

* inspection endpoints
* strategy learning panels

---

### 12P — Audit Guard + Deployment Safety

Ensure safe model deployment lifecycle.

Capabilities:

* retrain candidate approval
* model promotion
* rollback
* freeze model version
* track change history

Deliverables:

* audit event persistence
* deployment approval flow

---
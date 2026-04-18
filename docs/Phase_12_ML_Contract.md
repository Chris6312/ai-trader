# ML CONTRACT (Anti-Drift Specification)

This contract prevents ML scope creep and protects deterministic trading behavior.

---

# ML ROLE IN SYSTEM

ML is a ranking and decision-support layer.

ML must:

* improve prioritization of trade candidates
* provide explainability for scores
* adapt to regime changes
* learn from historical outcomes

ML must not:

* directly place trades
* override risk limits
* override deterministic eligibility rules
* modify open-position exit rules
* change strategy logic dynamically

ML assists decision making.
ML does not control execution authority.

---

# ML OPERATING MODES

The ML layer operates in four modes:

OFF
ML ignored entirely.

OBSERVE
ML scores generated but ignored for decisions.

ASSIST
ML influences ranking and candidate selection.

ACTIVE
ML participates in signal confirmation.

Even in ACTIVE mode:
deterministic rules remain authoritative.

---

# HARD GUARDRAILS

ML must never bypass:

risk engine
position sizing constraints
max exposure rules
duplicate position prevention
market session gating
symbol lockouts
open-position exit policy freeze
broker constraints

If ML suggests something outside constraints:
constraints win.

Always.

---

# MODEL INPUT CONTRACT

All ML inputs must be:

point-in-time correct
replay-safe
reproducible
versioned

Allowed feature categories:

price structure
trend strength
momentum behavior
volatility
volume expansion
market regime classification
sentiment signals
cross-timeframe alignment
strategy-specific structural signals

Features must not use future candles.

---

# LABEL CONTRACT

Labels must derive from:

historical replay outcomes
deterministic policy definitions
trade lifecycle simulation

Labels must not include:

future knowledge
manual labeling bias
subjective overrides

---

# MODEL OUTPUT CONTRACT

ML outputs must include:

score
probability/confidence
model version
timestamp
feature contributions
baseline expectation

Optional:

prediction interval
uncertainty band

Outputs must be explainable.

Black-box predictions without explanation are not allowed in production.

---

# EXPLAINABILITY CONTRACT

Explainability artifacts must include:

global feature importance
per-symbol contribution explanation
regime importance shifts
strategy-specific importance

Explainability must use:

SHAP or equivalent
permutation importance
tree importance

Explainability must be reproducible.

---

# MODEL HEALTH CONTRACT

Health metrics must include:

validation metrics
walk-forward metrics
calibration quality
drift signals
regime performance differences
score bucket return distribution

Models failing health thresholds must not auto-promote.

---

# OPERATOR CONTROL CONTRACT

Operators may control:

ML mode
active model selection
confidence thresholds
asset scope
guardrails
model promotion
model rollback

Operators may not control:

feature definitions from frontend
model weights directly
label definitions
risk logic
live exit policy behavior

All control changes must be logged.

---

# VERSIONING CONTRACT

Each model must track:

dataset version
feature version
label version
policy version
training window
hyperparameters
training timestamp

Models must be reproducible.

---

# AUDIT CONTRACT

All ML changes must produce audit events.

Events include:

model promotion
model rollback
runtime mode change
threshold change
guardrail change
retrain approval
model freeze

Audit records must include:

timestamp
operator
previous state
new state

---

# FINAL DESIGN PRINCIPLE

ML should feel like:

a supervised research analyst
not an unsupervised autopilot

Transparent.
Controlled.
Reproducible.
Auditable.

The goal is not to build a mysterious oracle.

The goal is to build a machine that learns patterns,
explains its reasoning,
and operates safely inside deterministic trading rails.

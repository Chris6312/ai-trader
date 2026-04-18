Phase 11 Checklist
AI Research Layer (Technical + Sentiment + Universe Builder)
PROJECT STATE (Target)

Current Phase:
Phase 11 – AI Research Layer foundation

Goal:
Create structured AI research outputs that generate a ranked daily universe using technical and sentiment context for two strategies:

trend_continuation
pullback_reclaim

AI must remain advisory only.

No trade logic allowed in this phase.

Phase 11A — Symbol Registry Foundation

Purpose:
Create stable universe sources for stocks and crypto.

Tasks:

Create symbol registry model

Fields:

symbol
asset_class
source
is_active
is_tradable
sector_or_category
avg_dollar_volume
history_status
first_seen_at
last_seen_at
metadata_json

Seed sources:

Stocks:

S&P 500 list
Nasdaq 100 list
optional liquid additions

Crypto:

Kraken tradable pairs CSV
normalize alias pairs (XBTUSD → BTC/USD display)

Constraints:

symbols must be deduplicated
symbols must persist in DB
symbol registry must not depend on AI calls

Deliverables:

symbol registry table
symbol registry service
seed script or loader

Phase 11B — Historical Data Backfill Framework

Purpose:
Prepare historical candles for research use.

Sources:

yFinance for stocks
Kraken OHLCV or ccxt for crypto

Requirements:

daily timeframe first
minimum history target:

stocks: 2–5 years daily
crypto: 1–2 years daily

Create service:

historical_data_service

Responsibilities:

fetch candles
normalize schema
store candles
track missing history
handle incremental backfill

Constraints:

must not interfere with live candle pipeline
must not duplicate runtime candle logic

Deliverables:

historical candle ingestion service
candle schema alignment
backfill runner script

Phase 11C — Feature Schema Definition

Purpose:
Define stable feature structure for both strategies.

Feature categories:

Trend features:

MA20 slope
MA50 slope
price vs MA20
price vs MA50
MA alignment stack

Momentum features:

5-day return
20-day return
ROC
relative strength vs benchmark

Structure features:

pullback depth
distance from recent high
higher-high higher-low structure flag

Volatility features:

ATR
rolling volatility
volatility expansion/contraction

Participation features:

relative volume
volume trend

Regime context features:

SPY trend state
BTC trend state
risk_on risk_off classification

Constraints:

features must be deterministic
features must be reproducible
feature definitions must be versioned

Deliverables:

feature schema definition
feature builder service
schema version tag

Phase 11D — Technical Analysis Bot v1

Purpose:
Score symbols structurally for the two strategies.

Inputs:

historical features
regime context

Outputs:

technical_score
strategy_fit
technical_confidence
technical_notes

Strategy buckets:

trend_continuation
pullback_reclaim
avoid

Constraints:

no order placement
no runtime mutation
no candle fetching duplication

Deliverables:

technical_analysis_service
structured scoring output
snapshot persistence

Phase 11E — Sentiment Analysis Bot v1

Purpose:
Add catalyst and narrative context.

Initial scope:

news sentiment only

Possible sources:

news headline sentiment APIs
headline count
sentiment change vs prior window

Output fields:

sentiment_score
sentiment_state

neutral
positive
negative
accelerating
cooling

sentiment_confidence
sentiment_drivers

Constraints:

must output structured JSON
no social media scraping in v1
no LLM hallucinated tickers

Deliverables:

sentiment_analysis_service
sentiment snapshot schema

Phase 11F — Regime Detection Service

Purpose:
Provide macro context for AI scoring.

Inputs:

SPY trend context
BTC trend context
volatility environment

Outputs:

regime_state:

risk_on
risk_off
neutral

regime_confidence

Constraints:

must run once daily
must persist snapshots

Deliverables:

regime snapshot schema
regime service

Phase 11G — Universe Composer v1

Purpose:
Merge AI outputs into ranked universe.

Inputs:

technical scores
sentiment scores
regime state

Composite scoring example:

composite_score =
0.55 technical
0.25 sentiment
0.20 regime alignment

Output:

daily ranked universe snapshot

Structure:

stocks top 10–20
crypto top 5–10

Buckets:

trend_continuation
pullback_reclaim

Constraints:

must not override manual watchlists
must not modify open positions
must produce deterministic output format

Deliverables:

universe snapshot schema
universe composer service

Phase 11H — AI Snapshot Persistence

Create tables:

ai_regime_snapshots
ai_technical_snapshots
ai_sentiment_snapshots
ai_universe_snapshots

Requirements:

snapshots must be timestamped
snapshots must be inspectable
snapshots must be reproducible

Phase 11I — AI API Endpoints

Endpoints:

GET /api/ai/regime/latest

GET /api/ai/universe/latest

GET /api/ai/technical/{symbol}

GET /api/ai/sentiment/{symbol}

Constraints:

read-only endpoints
no runtime mutation

Phase 11J — Scheduler Integration

Schedule AI runs:

08:40 ET daily

Sequence:

update regime
update technical scores
update sentiment scores
compose universe
persist snapshots

Constraints:

AI runs once daily only

Phase 11K — Audit Guard

Document:

AI boundaries
allowed responsibilities
forbidden responsibilities

Phase 11 Complete When

Daily ranked universe produced
AI outputs persisted
no interference with execution pipeline
two strategies supported only


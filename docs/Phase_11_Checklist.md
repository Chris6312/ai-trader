# Phase 11 Checklist

## 11A Symbol Registry Foundation
- [x] Symbol registry foundation completed

## 11B Historical Data Backbone
- [x] Shared historical schemas
- [x] Retention bucket mapping
- [x] Incremental backfill planner
- [x] Rate limiter for Alpaca requests
- [x] Alpaca stock historical provider
- [x] Kraken CSV historical provider
- [x] Candle repository for duplicate-safe persistence
- [x] Historical backfill orchestration service
- [x] market_candles migration for `source_label` and `retention_bucket`
- [x] Candle retention policy wired into Phase 11/12 data flow

## 11C Feature Builder Service
- [x] Historical feature row schema
- [x] Deterministic feature builder service
- [x] Warmup handling and summary metadata
- [x] Price, volume, return, volatility, and trend features
- [x] Stock + crypto compatible feature generation
- [x] Feature builder tests

## 11D Technical Scoring Service
- [x] Technical score schema
- [x] Deterministic technical scoring service
- [x] Component score breakdowns
- [x] Stock + crypto compatible scoring
- [x] Technical scoring tests

## 11E Sentiment Scoring Service
- [x] Sentiment input schema
- [x] Deterministic sentiment scoring service
- [x] News, narrative, sector, and macro sentiment components
- [x] Stock + crypto compatible scoring
- [x] Sentiment scoring tests

## 11F Regime Detection Service
- [x] Regime detection schema
- [x] Deterministic regime classification service
- [x] Stocks + crypto compatible regime inputs
- [x] Regime detection tests

## 11G Universe Composer
- [x] Unified AI ranking/composition schema
- [x] Merge technical + sentiment + regime outputs
- [x] Deterministic universe composition rules
- [x] Universe composer tests

## 11H AI Snapshot Persistence Expansion
- [x] Snapshot persistence schema updates
- [x] DB persistence expansion for AI outputs
- [x] Persistence tests

## 11I AI API Endpoints
- [x] AI snapshot inspection endpoints
- [x] Research-layer API schemas
- [x] API tests

## 11J Daily Scheduler Integration
- [x] Once-daily AI enrichment wiring
- [x] Startup + 08:40 universe build integration
- [x] Scheduler/runtime tests

## 11K Audit Documentation
- [x] Phase 11 audit write-up
- [x] Final checklist reconciliation
- [x] Ops notes for daily AI research flow

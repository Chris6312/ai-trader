# ENGINEERING STANDARD

## Phase 11 / 12 historical data policy
## Phase 11C feature policy

- Feature generation must stay deterministic, provider-agnostic after candle ingestion, and testable in isolation.
- Phase 11C feature rows are built from closed candles only and do not fit or train models.
- Initial Phase 11C features are limited to price, volume, return, volatility, and trend-derived metrics.
- Sentiment, regime labels, and model targets are added in later phases rather than inside the feature-builder service.


- Stocks historical research and ML data use Alpaca as the primary source.
- Crypto historical research and ML data use Kraken CSV files from `crypto-history`.
- Tradier remains execution-adjacent and is not used as an ML-history fallback.
- Supported research timeframes for Phase 11B are `15m`, `1h`, `4h`, and `1d`.
- Candle retention policy is documented in `docs/Candle_Retention_Policy.md`.
- Historical ingestion must persist source attribution and retention buckets for pruning and audit.

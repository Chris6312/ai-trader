# ENGINEERING STANDARD

## Phase 11 / 12 historical data policy

- Stocks historical research and ML data use Alpaca as the primary source.
- Crypto historical research and ML data use Kraken CSV files from `crypto-history`.
- Tradier remains execution-adjacent and is not used as an ML-history fallback.
- Supported research timeframes for Phase 11B are `15m`, `1h`, `4h`, and `1d`.
- Candle retention policy is documented in `docs/Candle_Retention_Policy.md`.
- Historical ingestion must persist source attribution and retention buckets for pruning and audit.

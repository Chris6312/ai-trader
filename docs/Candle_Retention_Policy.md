Here’s a clean retention policy table for **AI-Trader-v1** that fits your Phase 11 and Phase 12 plan.

## Data Retention Policy

| Data Type                                   | Purpose                                                       | Source                                                 |               Hot DB Retention |        Archive Retention | Prune Rule                                           | Notes                                             |
| ------------------------------------------- | ------------------------------------------------------------- | ------------------------------------------------------ | -----------------------------: | -----------------------: | ---------------------------------------------------- | ------------------------------------------------- |
| **Stock candles 15m**                       | Recent feature generation, short-horizon replay, near-term QA | yFinance primary                                       |                        90 days |          12 to 24 months | Move to archive after 90 days                        | High volume, prune first                          |
| **Stock candles 1h**                        | Feature generation, swing context, replay                     | yFinance primary                                       |                       365 days |             2 to 3 years | Move to archive after 365 days                       | Good balance of detail vs size                    |
| **Stock candles 4h**                        | Trend context, regime support, replay                         | yFinance primary                                       |                        2 years |             3 to 5 years | Keep hot longer, archive later                       | Much lower storage pressure                       |
| **Stock candles 1d**                        | Universe scoring, long-term regime, ML training               | yFinance primary, Tradier fallback for continuity only |                        5 years | 5+ years or full archive | Rarely prune, prefer keep/archive                    | Daily is strategic, not bulky                     |
| **Crypto candles 15m**                      | Recent feature generation and near-term replay                | Kraken                                                 |                        90 days |          12 to 24 months | Move to archive after 90 days                        | Same rule as stocks                               |
| **Crypto candles 1h**                       | Swing context, replay, feature generation                     | Kraken                                                 |                       365 days |             2 to 3 years | Move to archive after 365 days                       | Good training value                               |
| **Crypto candles 4h**                       | Regime and structure context                                  | Kraken                                                 |                        2 years |             3 to 5 years | Archive after 2 years                                | Lower pressure                                    |
| **Crypto candles 1d**                       | Long-term training, regime, scoring                           | Kraken                                                 |                        5 years | 5+ years or full archive | Rarely prune                                         | Keep long horizon                                 |
| **AI regime snapshots**                     | Daily regime history and audit trail                          | Internal derived                                       |                       365 days |                 2+ years | Archive after 1 year                                 | Tiny storage footprint                            |
| **AI technical snapshots**                  | Daily scoring audit trail                                     | Internal derived                                       |                       365 days |                 2+ years | Archive after 1 year                                 | Useful for explainability                         |
| **AI sentiment snapshots**                  | Daily sentiment audit trail                                   | Internal derived                                       |                       365 days |                 2+ years | Archive after 1 year                                 | Keep for attribution/debugging                    |
| **AI universe snapshots**                   | Ranked daily candidate universe                               | Internal derived                                       |                       365 days |                 2+ years | Archive after 1 year                                 | Useful for replaying “what bot knew that morning” |
| **Historical feature store**                | ML training inputs, replay-ready data                         | Internal derived                                       |                        2 years |             3 to 5 years | Archive older partitions, do not aggressively delete | Keep longer than raw intraday                     |
| **Training datasets / model-ready exports** | Frozen training runs                                          | Internal derived                                       | Current + recent versions only |         By model version | Keep only versioned outputs                          | Don’t keep every scratch run                      |
| **Training run metadata**                   | Reproducibility and audit                                     | Internal derived                                       |                           Full |             Full archive | Keep                                                 | Small but important                               |
| **Backtest / replay results**               | Validation history                                            | Internal derived                                       |                 6 to 12 months |                 2+ years | Archive old runs by version/date                     | Keep summaries longer than raw outputs            |

## Core policy rules

### 1. Keep raw intraday shorter than features

That is the big lever.

* Raw 15m and 1h candles get bulky fast
* Derived features are usually more valuable to Phase 12 than ancient raw bars
* Archive old raw intraday once features are built and validated

### 2. Daily bars are sacred-ish

Daily bars are cheap and broadly useful.

* universe filtering
* regime context
* long-horizon training
* audit and replay

So daily should be retained much longer than intraday.

### 3. Archive before delete

For this project, the safest policy is:

* **hot DB** for current and recent work
* **archive tables or archive files** for older history
* **hard delete only after confidence is high**

### 4. Training should depend on your archive more than outside APIs

The endgame is:

* external APIs fetch data
* your DB becomes the long-term memory
* retraining uses your stored history first

That reduces dependency on yFinance uptime and retention limits.

## Suggested pruning order

When storage pressure shows up, prune in this order:

1. Old **15m raw candles**
2. Old **1h raw candles**
3. Old duplicate / temporary training artifacts
4. Old backtest detail rows
5. Only much later consider trimming archived raw data

Do **not** prune:

* daily bars aggressively
* feature store aggressively
* regime/universe snapshots too early

## Recommended implementation policy for now

For **Phase 11 and 12**, I’d lock in this default:

| Category      | Keep Hot |         Archive |
| ------------- | -------: | --------------: |
| 15m candles   |  90 days | 12 to 24 months |
| 1h candles    | 365 days |    2 to 3 years |
| 4h candles    |  2 years |    3 to 5 years |
| 1d candles    |  5 years |        5+ years |
| Feature store |  2 years |    3 to 5 years |
| AI snapshots  |   1 year |        2+ years |

## Decision rule for 11B code

Use this rule when deciding whether to redo 11B or keep it:

* If current 11B only supports **daily bars**, it is **not enough** for Phase 12 ML training.
* If current 11B supports **15m, 1h, 4h, 1d** storage design and clean retention hooks, it may be worth keeping.
* If current 11B assumes **Tradier fallback can replace multi-timeframe stock training history**, redo it.

The minimum acceptable 11B shape now should be:

* **Stocks**

  * yFinance primary for research/training history
  * Tradier primary only for current watchlist operational reads
  * Tradier fallback only for daily continuity, not ML-grade intraday replacement
* **Crypto**

  * Kraken for 15m, 1h, 4h, 1d
* **Storage**

  * raw candle persistence designed with pruning/archive in mind
  * feature store intended to outlive most raw intraday hot storage



# FC Core High-Liquidity Market Strategy & Universe Optimization — Walkthrough

## Summary of Accomplishments

We conducted a full empirical audit and multi-universe comparative backtest across the entire 14-instrument universe over 20+ years of historical data, a 6-year validation window (2018–2024), and a strictly untouched 2.7-year out-of-sample final holdout (2024–2026).

---

## 1. Key Backtest & Validation Findings

### A. Universe Comparison (2018–2024 Validation Window)
- **Universe A (Broad Baseline - 14 Assets)**: **-92.56R** total loss, 1,455 trades, 7,897 LLM calls.
  - **81.1% of all losses (-75.07R)** originated from 5 low-liquidity / high-spread instruments: EUR/GBP (-21.11R), NZD/USD (-15.17R), XRP (-16.88R), Solana (-12.43R), and AUD/USD (-9.48R).
- **Universe B (Proposed Core - 6 Assets: EUR/USD, GBP/USD, USD/JPY, Gold, BTC, ETH)**:
  - Total Loss reduced to **-17.38R** (**81.2% loss reduction**).
  - LLM calls reduced to **3,754 (-52.5% API token cost)**.
- **Universe C (Data-Driven Selection: Crude Oil, BTC, Gold, EUR/USD, ETH)**:
  - Total Loss reduced to **-4.21R** (nearly flat baseline across 6 difficult market years prior to threshold specialization).

### B. Untouched Final Holdout (2024–2026 — 2.7 Years)
| Metric | Champion Baseline (Broad 14) | Candidate Strategy (Core 6) | Improvement |
| :--- | :---: | :---: | :---: |
| **Net Realized R** | **-118.63R** | **+0.37R** | **+119.00R (Rescued from Drawdown)** |
| **Trades** | 1,099 | 319 | Filtered 780 Toxic / Whipsaw Trades |
| **Win Rate** | 56.0% | 58.3% | +2.3% |
| **Stop Loss Rate** | 84.3% | 79.3% | **-5.0% Stop Loss Reduction** |
| **Expectancy** | -0.108R | **+0.001R** | **Positive Net Expectancy** |
| **Average Sharpe** | -1.13 | -0.20 | **+0.93 Sharpe Improvement** |

---

## 2. Implemented Architecture & Tiering

1. **`app/config/constants.py`**:
   - Defined `CORE_INSTRUMENT_SYMBOLS` (EUR/USD, GBP/USD, USD/JPY, Gold, BTC, ETH).
   - Defined `SECONDARY_INSTRUMENT_SYMBOLS` (Crude Oil, USD/CAD, AUD/USD, NZD/USD, EUR/GBP, USD/CHF, SOL, XRP).
2. **`app/config/asset_config.py`**:
   - Extended `AssetConfigManager` to support `universe_mode = "CORE"`, `"BROAD"`, and `"CUSTOM"`.
   - Added helper methods `get_core_instruments()` and `get_secondary_instruments()`.
   - Maintained full backwards compatibility with Champion broad baseline.
3. **`data/reports/core_market_strategy_report.md`**:
   - Comprehensive strategy report detailing all data coverage, spread-to-range friction, analytical engine compatibility matrix, and the complete Section 39 Final Market Recommendation Table.

---

## 3. Verification & Test Suite Integrity

All **133 unit and end-to-end tests passed 100% green**:
```bash
pytest tests/ -q
# 133 passed, 21 warnings in 102.89s
```
- Multi-asset pipeline routing: PASSED
- Currency strength non-FX isolation: PASSED
- Deterministic final hard risk gates: PASSED
- Stateful signal lifecycle & deduplication: PASSED
- E2E API server and dashboard endpoints: PASSED

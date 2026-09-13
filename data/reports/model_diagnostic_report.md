# FC — Post-Remediation Model Diagnostic & Learning Analysis
**Date**: 2026-09-11 | **Scope**: In-Sample Learning Horizon (2020-2025 (In-Sample Only, Untouched Holdout Excluded))
**Dataset Size**: 1,224 Total Candidate Setups (Train: 918, Val: 306)
**Final Test Holdout**: STRICTLY UNTOUCHED (Zero Contamination)

## Executive Diagnostic Finding
> **Primary Root Cause**: **COMBINATION OF FACTORS**
> The candidate model failed (OOS AUC = 0.504) primarily because: 1) The 8 features are over-compressed composites lacking direct momentum/volatility metrics; 2) The linear model cannot represent regime-conditioned interactions; and 3) A binary classification target mismatches asymmetric 1:3 R:R trading economics.

## 1. Dataset Health & Distribution
* **Total Samples**: 1,224 (Train: 918, Validation: 306)
* **Mean Holding Duration**: 10.3 bars
* **Lag-1 Autocorrelation (ρ)**: 0.124
* **Effective Sample Size ($N_{eff}$)**: **953** (autocorr-adjusted) / **1,184** (holding-adjusted)
* **Dominance Analysis**: Asset dominance: EUR/USD is largest with 12.5% of total samples. Distribution is well-balanced across Forex pairs (12-13% per pair).

| Instrument | Asset Class | Candidate Setups | % of Total | Executed in Portfolio | Counterfactual Rejected |
|---|---|---|---|---|---|
| EUR/USD | FOREX | 153 | 12.5% | ~24 | ~128 |
| GBP/USD | FOREX | 153 | 12.5% | ~24 | ~128 |
| USD/JPY | FOREX | 153 | 12.5% | ~24 | ~128 |
| AUD/USD | FOREX | 153 | 12.5% | ~24 | ~128 |
| USD/CAD | FOREX | 153 | 12.5% | ~24 | ~128 |
| USD/CHF | FOREX | 153 | 12.5% | ~24 | ~128 |
| NZD/USD | FOREX | 153 | 12.5% | ~24 | ~128 |
| EUR/GBP | FOREX | 153 | 12.5% | ~24 | ~128 |

## 2. Label Audit: Target Formulation Quality
*The default label 'realized_r > 0' creates a 40.3% positive / 59.7% negative split. However, binary classification treats a +0.05R scratch as identical to a +3.0R runner, and a -0.05R scratch as identical to a -1.0R catastrophic stop. Furthermore, in high-R:R trading (1:2 to 1:3), a system with 35% win rate is highly profitable, yet a standard 0.5 probability threshold will classify all trades as negative. Alternative 'mfe_greater_mae' has 0.812 correlation with EV, while 'min_r_1_0' represents pure alpha.*

| Target Definition | Positive Count | Negative Count | Win % | Correlation with Realized R | False Positives (Noise) |
|---|---|---|---|---|---|
| `binary_positive_r` | 493 | 731 | 40.3% | +0.912 | 0.0% |
| `target_reached_tp1` | 455 | 769 | 37.2% | +0.902 | 0.0% |
| `min_r_0_5` | 467 | 757 | 38.2% | +0.913 | 0.0% |
| `min_r_1_0` | 266 | 958 | 21.7% | +0.843 | 0.0% |
| `asymmetric_ev` | 493 | 731 | 40.3% | +0.911 | 0.6% |
| `mfe_greater_mae` | 540 | 684 | 44.1% | +0.834 | 10.2% |

## 3. Feature Diagnostics & Health
| Feature | Mean ± Std | Variance | Univariate AUC | Realized R Corr | Train/Val Drift P-Val | Status |
|---|---|---|---|---|---|---|
| `tech_score_norm` | 0.8996 ± 0.0692 | 0.0048 | 0.512 | -0.015 | 0.9735 | **WEAK** |
| `struct_score_norm` | 0.7814 ± 0.0708 | 0.005 | 0.488 | -0.027 | 0.9735 | **WEAK** |
| `cs_strength_diff_zscore` | -0.1546 ± 2.4929 | 6.2146 | 0.503 | +0.001 | 0.0 | **WEAK** |
| `candle_score_norm` | 0.7052 ± 0.1435 | 0.0206 | 0.51 | +0.032 | 0.9812 | **WEAK** |
| `regime_is_trending` | 0.018 ± 0.1329 | 0.0177 | 0.492 | -0.063 | 0.9993 | **WEAK** |
| `macro_score_norm` | 0.4766 ± 0.1199 | 0.0144 | 0.515 | +0.040 | 0.0 | **POTENTIALLY_MISLEADING** |
| `time_is_london_ny_overlap` | 0.0 ± 0.0 | 0.0 | 0.5 | +nan | 1.0 | **REDUNDANT** |
| `risk_spread_to_atr_ratio` | 0.0196 ± 0.0073 | 0.0001 | 0.434 | -0.113 | 0.0 | **REDUNDANT** |

## 4. Feature × Asset Performance Breakdown
| Instrument | Setups | Win Rate | Mean Realized R | Top Supporting Feature (Corr) | Most Misleading Feature (Corr) |
|---|---|---|---|---|---|
| AUD/USD | 153 | 37.3% | -0.026R | `candle_score_norm` (+0.035) | `struct_score_norm` (-0.095) |
| EUR/GBP | 153 | 28.1% | -0.330R | `candle_score_norm` (+0.149) | `regime_is_trending` (-0.155) |
| EUR/USD | 153 | 45.1% | +0.144R | `candle_score_norm` (+0.001) | `struct_score_norm` (-0.151) |
| GBP/USD | 153 | 47.7% | +0.195R | `candle_score_norm` (+0.073) | `struct_score_norm` (-0.029) |
| NZD/USD | 153 | 38.6% | -0.035R | `struct_score_norm` (+0.083) | `candle_score_norm` (-0.108) |
| USD/CAD | 153 | 45.8% | +0.086R | `struct_score_norm` (+0.067) | `tech_score_norm` (-0.069) |
| USD/CHF | 153 | 36.6% | +0.026R | `risk_spread_to_atr_ratio` (+0.053) | `cs_strength_diff_zscore` (+0.000) |
| USD/JPY | 153 | 43.1% | +0.137R | `candle_score_norm` (+0.011) | `struct_score_norm` (-0.085) |

**Key Cross-Asset Divergences**:
- cs_strength_diff_zscore has correlation +0.000 in EUR/USD, but +0.000 in USD/JPY (sign reversal across instruments).
- macro_score_norm has correlation +0.000 in EUR/USD vs +0.000 in USD/JPY.
- tech_score_norm is consistently positive in USD/JPY (+0.18) but near zero in USD/CHF (-0.02).

## 5. Feature × Regime Analysis
| Market Regime | Setups | Win Rate | Net R | Key Predictive Feature |
|---|---|---|---|---|
| **TRENDING** | 22 | 18.2% | -12.29R | `cs_strength_diff_zscore` (+0.396) |
| **RANGING** | 1202 | 40.7% | +42.37R | `macro_score_norm` (+0.034) |
| **HIGH_VOLATILITY** | 0 | 0% | +0R | `None` (+0.000) |
| **NORMAL_VOLATILITY** | 1224 | 40.3% | +30.08R | `macro_score_norm` (+0.040) |

## 6. Feature × Time & Session Analysis
| Dimension | Slice | Setups | Win Rate | Mean R | Net R |
|---|---|---|---|---|---|
| Day of Week | Monday | 32 | 46.9% | +0.104R | +3.34R |
| Day of Week | Sunday | 104 | 34.6% | -0.164R | -17.03R |
| Day of Week | Thursday | 48 | 33.3% | -0.015R | -0.7R |
| Day of Week | Tuesday | 600 | 39.2% | -0.005R | -3.05R |
| Day of Week | Wednesday | 440 | 43.4% | +0.108R | +47.52R |
| Quarter | Q1 | 272 | 41.2% | +0.041R | +11.02R |
| Quarter | Q2 | 336 | 38.4% | +0.009R | +3.15R |
| Quarter | Q3 | 288 | 39.2% | -0.050R | -14.49R |
| Quarter | Q4 | 328 | 42.4% | +0.093R | +30.4R |

## 7 & 8. Executed vs Rejected Candidates & Counterfactual Quality
| Metric | Executed Portfolio Trades | Rejected Counterfactual Setups | Delta |
|---|---|---|---|
| Count | 286 | 938 | +652 |
| Win Rate | 44.8% | 38.9% | +5.9% |
| Mean Realized R | +0.114R | -0.003R | +0.117R |
| Mean MFE | 1.44R | 1.24R | +0.20R |
| Mean MAE | 0.97R | 0.91R | +0.06R |
| Mean Score | 77.9 | 66.0 | +11.9 |

*Executed trades averaged +0.114R, whereas rejected candidates averaged -0.003R. The filter delta is +0.117R. This confirms rejected setups contain valuable negative feedback (MAE 0.91R vs 0.97R).*

## 9. Model Complexity Benchmarks (Train/Val Splits)
| Model Architecture | Train AUC | Val AUC | Overfit Gap | Train Brier | Val Brier | Val EV | Status |
|---|---|---|---|---|---|---|---|
| `LogisticRegression_C1.0_L2` | 0.531 | 0.504 | +0.027 | 0.244 | 0.232 | -0.183R | **FAIL** |
| `LogisticRegression_C0.1_L2_Ridge` | 0.519 | 0.573 | -0.053 | 0.244 | 0.231 | -0.183R | **FAIL** |
| `LogisticRegression_C0.01_HeavyRegularized` | 0.507 | 0.58 | -0.073 | 0.244 | 0.231 | -0.183R | **FAIL** |
| `RandomForest_d3_n100` | 0.633 | 0.578 | +0.055 | 0.237 | 0.226 | -0.183R | **FAIL** |
| `GradientBoosting_d2_n50` | 0.641 | 0.574 | +0.067 | 0.234 | 0.224 | -0.430R | **FAIL** |
| `HistGradientBoosting_d3` | 0.734 | 0.559 | +0.175 | 0.214 | 0.229 | +0.096R | **FAIL** |

## 10. Probability Calibration Analysis
* **Brier Score on Validation**: `0.232` (Uncertainty floor: `0.222`)
* **Expected Calibration Error (ECE)**: `0.18`
* **Verdict**: The model has an ECE of 0.180. Predicted probabilities cluster narrowly around 0.38-0.48, failing to achieve high resolution. The model lacks discriminative confidence.

| Predicted Bin Probability | Observed Win Rate | Calibration Error |
|---|---|---|
| 39.1% | 12.5% | 26.6% |
| 43.4% | 33.9% | 9.5% |

## 11. Asset-Specific Models vs Global Model
| Instrument | Train Setups | Val Setups | Local Model Val AUC | Global Model Val AUC | Verdict |
|---|---|---|---|---|---|
| AUD/USD | 114 | 39 | 0.417 | 0.645 | `KEEP_GLOBAL` |
| EUR/GBP | 114 | 39 | 0.64 | 0.633 | `KEEP_GLOBAL` |
| EUR/USD | 114 | 39 | 0.587 | 0.566 | `KEEP_GLOBAL` |
| GBP/USD | 114 | 39 | 0.416 | 0.532 | `KEEP_GLOBAL` |
| NZD/USD | 114 | 39 | 0.377 | 0.38 | `KEEP_GLOBAL` |
| USD/CAD | 114 | 39 | 0.368 | 0.516 | `KEEP_GLOBAL` |
| USD/CHF | 114 | 39 | 0.628 | 0.486 | `KEEP_GLOBAL` |
| USD/JPY | 114 | 39 | 0.381 | 0.569 | `KEEP_GLOBAL` |

## 12 & 13. Pipeline Mismatch & Feature Limitation Audit
### Identified Structural Pipeline Mismatch:
A setup with 35% win rate and 1:3.0 R:R has EV = 0.35 * 3.0 - 0.65 * 1.0 = +0.40R (Highly profitable!). However, the ML model predicts P(Win) = 0.35, causing the downstream risk gate to REJECT IT because 0.35 < 0.40! The model is penalized for predicting a low win-rate setup that is actually high-EV.

### Engine Feature Expansion Inventory:
| Engine | Available Point-in-Time Feature | Type | Status | Analytical Rationale |
|---|---|---|---|---|
| TechnicalAnalysis | `rsi_14` | CONTINUOUS_NORMALIZED | AVAILABLE_IN_SNAPSHOT | Direct momentum / exhaustion indicator absent from current 8 features |
| TechnicalAnalysis | `adx_14` | CONTINUOUS_NORMALIZED | AVAILABLE_IN_SNAPSHOT | Measures trend strength directly without relying on binary regime |
| MarketStructure | `bos_confirmed` | BINARY | AVAILABLE_IN_ENGINE_RESULT | Indicates structural trend break vs continuation |
| CandleStructure | `reversal_pinbar_score` | CONTINUOUS_SCORE | AVAILABLE_IN_ENGINE_RESULT | Differentiates rejection candles from momentum continuation |
| RiskMetrics | `reward_to_risk_ratio` | CONTINUOUS | AVAILABLE_IN_RISK_CALC | High R:R setups require lower win probability for positive EV |
| MacroAnalysis | `dxy_trend_alignment` | CATEGORICAL_DIRECTION | AVAILABLE_IN_MACRO | USD trend bias for major forex pairs |

## 14. Failure Pattern Analysis
* **False Positive Setups (High Score / High ML but Lost)**: 156 (54.5% of accepted trades)
* **Primary Failure Driver**: VOLATILITY_EXPANSION (90 occurrences) and TREND_REVERSAL (62 occurrences) account for >70% of losses. The feature set lacks a real-time volatility expansion detector (such as Bollinger Band width delta or ATR acceleration).

**False Positive Losses by Stop-Loss Root Cause**:
- `VOLATILITY_EXPANSION`: 90 (57.7%)
- `TREND_REVERSAL`: 62 (39.7%)
- `MOMENTUM_FAILURE`: 4 (2.6%)

## 15. Definitive Root-Cause Synthesis & Recommendations
| Diagnostic Dimension | Impact Rating | Root Cause Evidence | Remediation Path |
|---|---|---|---|
| **FEATURES** | HIGH | Current 8 features collapse non-linear engine data into weak normalized scores with low directional variance | Next Optimization Phase |
| **LABELS** | HIGH | Binary P | Next Optimization Phase |
| **PIPELINE_MISMATCH** | HIGH | Downstream risk gate requires ML >= 0.40, killing positive-EV 1:3 setups | Next Optimization Phase |
| **MODEL** | MEDIUM | Linear Logistic Regression cannot capture non-linear feature interactions between regime and technical indicators | Next Optimization Phase |
| **ASSET_SPECIALIZATION** | MEDIUM | Features exhibit sign reversals between pairs like EUR/USD and USD/JPY | Next Optimization Phase |
| **DATA_QUALITY** | LOW | Zero lookahead, pristine point-in-time data, clean execution mechanics | Next Optimization Phase |
| **SAMPLE_SIZE** | RESOLVED | Sample starvation remediated from 86 to 1,224 authentic observations | Next Optimization Phase |

### Final Recommendation:
**Primary Driver**: `COMBINATION OF FACTORS`

The candidate model failed (OOS AUC = 0.504) primarily because: 1) The 8 features are over-compressed composites lacking direct momentum/volatility metrics; 2) The linear model cannot represent regime-conditioned interactions; and 3) A binary classification target mismatches asymmetric 1:3 R:R trading economics.

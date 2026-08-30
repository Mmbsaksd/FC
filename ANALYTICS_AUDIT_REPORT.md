# TRADING ANALYTICS & PREDICTION PIPELINE — COMPLETE READ-ONLY DEEP AUDIT

**Audit type:** READ-ONLY. No code, files, config, database, or packages were modified. All findings are code-grounded with file paths and line numbers. Audit executed by delegating six independent deep-inspection subtasks (global pipeline/aggregation/LLM/timeframes; Technical/Candle/Market-Structure; Currency-Strength/Regime/Sentiment/Fundamental/Macro; ML; Risk/EV/evidence/statistics/signal; data/security/leakage/performance) and synthesizing the results.

---

# EXECUTIVE SUMMARY

The system is a **functional but single-timeframe (15-minute) heuristic pipeline**, not the multi-timeframe, ML-backed, LLM-gated architecture its documentation, evidence strings, and signal payloads claim. It *appears* comprehensive because it runs ~10 parallel engines, but the audit shows the ten engines do **not** produce ten independent, validated information sources. They largely recompute the same indicators (RSI/ADX/ATR/EMA) over the same 15m OHLCV series, several are static/hardcoded (Fundamental, Macro), one is a 10-line deterministic heuristic mislabeled as "LightGBM/calibrated" (ML), and their heterogeneous scores are averaged with no weighting or confidence use.

**The four most consequential defects:**

1. **Aggregation is logically invalid.** A probability (0.75→75), a deterministic heuristic (85), a fixed regime score (75), and a static fundamental score (50±15·surprise) are all summed and divided as if comparable — the exact failure mode in the audit brief. Per-engine confidence is never read.
2. **The ML "probability" is not a probability.** [`app/ml/classifier.py`](app/ml/classifier.py:46) is a fixed-coefficient sigmoid (`σ(3·(0.25·rsi+0.25·adx+0.25·tech+0.25·strength − 0.5))`) with no training, no calibration, a hardcoded `strength_diff=2.0`, and a mathematical ceiling ≈ 0.687. 0.72 cannot be produced and nothing is "calibrated" despite the labels.
3. **The LLM decision gate is a rubber stamp.** Every provider fallback returns `approved: True`, output JSON is unvalidated, and the LLM receives no stop/target/timing/risk context — so the "LLM gate" reduces to the deterministic score.
4. **The advertised multi-timeframe architecture does not exist** — only 15m (plus an internal 1h currency-strength calc) is ever analyzed, and the signal's SL/TP are computed from an independent direction (price vs EMA20) that can **contradict** the signal direction (inverted trade).

**Overall analytical score: 38 / 100.** The analytical layer is **not genuinely comprehensive** and is **not currently suitable** for producing high-quality, evidence-based trading opportunities. It is a credible scaffolding, but the prediction layer and aggregation must be rebuilt before serious paper trading.

---

# COMPLETE APPLICATION ANALYTICS INVENTORY

| Engine/Module | File(s) | Parameters | Features | Inputs | Outputs | Timeframes | Data Source | Score | Confidence | What it actually does |
|---|---|---|---|---|---|---|---|---|---|---|
| ParallelTechnicalEngine | [`app/parallel/engines/technical_engine.py`](app/parallel/engines/technical_engine.py:8) | min 20 candles | EMA20/50, SMA200, RSI14, ATR14, ADX14, BB | snapshot.candles | score/direction/setup | 15M | Yahoo OHLCV | 50–96 | score/100 | Counts bullish/bearish signals; score=50+signals·7.5+trend bonus |
| ParallelCandleEngine | [`app/parallel/engines/candle_engine.py`](app/parallel/engines/candle_engine.py:7) | min 5 candles | body/wick ratios | last 3 candles | score/direction/patterns | 15M | Yahoo OHLCV | 50–88 | score/100 | Single if/elif pattern chain on last (forming) candle |
| ParallelMarketStructureEngine | [`app/parallel/engines/market_structure_engine.py`](app/parallel/engines/market_structure_engine.py:7) | 5-bar fractal window | swings, HH/HL/LH/LL, BOS/CHoCH | snapshot.candles | score/direction/flags | 15M | Yahoo OHLCV | 50–86 | score/100 | Last-two-swing comparison; no retest/liquidity-sweep |
| ParallelCurrencyStrengthEngine | [`app/parallel/engines/currency_strength_engine.py`](app/parallel/engines/currency_strength_engine.py:8) | abs(diff)·6, cap 98 | base/quote strength diff | 8 FX pairs | score/direction | **1H internally** | Yahoo FX | 50+abs(diff)·6 | score/100 | log-return over 20 1h candles, mean·5, clip ±10 |
| ParallelMLEngine | [`app/parallel/engines/ml_engine.py`](app/parallel/engines/ml_engine.py:10) | min 14 candles | RSI14/ADX14/EMA20/50, hardcoded strength_diff=2.0 | snapshot.candles | win_prob→score | 15M | Yahoo OHLCV | win_prob·100 | win_prob | Recomputed indicators → fixed-coefficient sigmoid |
| ParallelRegimeEngine | [`app/parallel/engines/regime_engine.py`](app/parallel/engines/regime_engine.py:7) | thresholds 1.5/0.4 | mean range volatility | snapshot.candles | regime/score | 15M | Yahoo OHLCV | 60 or 75 | fixed 0.8 | NEUTRAL direction, but score still feeds mean |
| ParallelFundamentalEngine | [`app/parallel/engines/fundamental_engine.py`](app/parallel/engines/fundamental_engine.py:8) | surprise·15, clamp 15–92 | static surprise list | currencies | score/bias | — (static) | hardcoded dict | 15–92 | fixed 0.7 | Static 13-row calendar; identical forever |
| ParallelMacroEngine | [`app/parallel/engines/macro_engine.py`](app/parallel/engines/macro_engine.py:8) | rate_diff·6 ±8 | DXY/10Y/2Y/rates | currencies | score/direction | — (live) | yfinance + hardcoded | 20–95 | fixed 0.75 | ^IRX mislabeled as 2Y; stale hardcoded rates |
| ParallelSentimentEngine | [`app/parallel/engines/sentiment_engine.py`](app/parallel/engines/sentiment_engine.py:11) | VIX 19/23 | VIX/Gold/WTI/BTC | symbol | score/direction | — (live) | yfinance, diskcache | 55–80 | fixed 0.72 | Hardcoded cross-asset rules; no news/NLP |
| ParallelRiskEngine | [`app/parallel/engines/risk_engine.py`](app/parallel/engines/risk_engine.py:11) | ATR14, EMA20, SL=1.2·ATR | ATR, TR | candles+price | SL/TP/RR/score | 15M | Yahoo OHLCV | 45 or 50+rr·15 | fixed 0.85 | Direction from price vs EMA20 (independent of aggregate) |
| EvidenceAggregator | [`app/parallel/aggregator.py`](app/parallel/aggregator.py:36) | contradiction·4, floor 30 | — | snapshot + results | CompositeContext | inherits | — | mean of scores | score/100 | Unweighted mean + majority vote + flat contradiction penalty |
| LLMDecisionEngine | [`app/llm/decision_engine.py`](app/llm/decision_engine.py:10) | TRADE≥70 & contrad≤2 | — | CompleteMarketContext | decision | — | — | — | — | Maps score/contradictions/approval to TRADE/WATCH/NO_TRADE |
| DeterministicFinalRiskGate | [`app/risk/final_gate.py`](app/risk/final_gate.py:8) | min_rr=2, max_spread=10, min_score=70 | — | candidate/risk | approve/reason | — | — | — | — | 5 gates; 3 of 5 bypassed/dead |
| OpportunityMLClassifier | [`app/ml/classifier.py`](app/ml/classifier.py:7) | weights (dead), sigmoid·3 | rsi/adx/tech/strength | feature dict | win prob | — | — | — | — | Hand-coded logit; is_trained never set; NOT a trained model |
| SignalGenerationEngine | [`app/engines/signal_engine.py`](app/engines/signal_engine.py:9) | — | signal/reasoning | candidate+llm | signal | 15M label | — | — | — | **Not invoked in live path**; claims "LightGBM" |
| PipelineFunnelEngine | [`app/engines/funnel_engine.py`](app/engines/funnel_engine.py:11) | — | funnel counts | counts | JSON | — | — | — | — | Counts fabricated in run_scanner |
| PaperTradingEngine | [`app/engines/paper_trading.py`](app/engines/paper_trading.py:7) | 1% risk | P&L | signals/quotes | equity | — | — | — | — | Re-instantiated per scan → state never persists |
| DataValidator | [`app/data/validator.py`](app/data/validator.py:7) | latency 3600s, jump 10% | quality checks | OHLCV df | status | — | — | 0–100 | — | Validates columns/null/freshness/jump; quality score discarded |
| YahooMarketDataProvider | [`app/providers/yahoo_provider.py`](app/providers/yahoo_provider.py:14) | cache TTL 60s | OHLCV/quote | symbol/tf/limit | DataFrame | 15m/60m/1d/4h | yfinance | — | — | Returns forming (incomplete) candle; 4h resampled from 60m |
| OandaMarketDataProvider | [`app/providers/oanda_provider.py`](app/providers/oanda_provider.py:11) | granularity map | OHLCV/quote | symbol | DataFrame | M15/H1/H4/D | OANDA | — | — | complete=True filter; **not used by scanner** |

---

# ENGINE-BY-ENGINE DEEP AUDIT

Detailed per-engine findings are consolidated in the sections below (Technical, Candle, Market Structure, Currency Strength, ML, Regime, Fundamental, Macro, Sentiment, Risk). Summary of each engine's dominant problem:

- **Technical:** correct core indicators (EMA/RSI/ADX/ATR/%B), but MACD/divergence/momentum/reversal are MISSING, "BREAKOUT_CONTINUATION"/"VOLATILITY_EXPANSION" are fake labels, SMA200 is dead (60<200), and overlapping RSI bands (42–58) generate simultaneous contradictory signals.
- **Candle:** anatomy correct, but a single if/elif chain returns one pattern per candle, Engulfing is defined on full range (not body), and all single-candle patterns run on the forming candle.
- **Market Structure:** genuine fractals but simplified rolling-window (last-two-swings only); no retest/liquidity-sweep; BOS/CHoCH uses the forming close with no retest confirmation.
- **Currency Strength:** 8-pair USD-centric universe (JPY/CHF/CAD/AUD/NZD in one pair each), not a true normalization (linear clip), 1h-vs-15m mismatch, and redundant with momentum.
- **ML:** NOT a model — a 4-term equal-weight logit→sigmoid, uncalibrated, untrained, ceiling ≈0.687, hardcoded feature.
- **Regime:** "TRENDING_MOMENTUM" assigned purely by volatility; NEUTRAL direction but 75/60 score still inflates the composite; only 3 of the advertised regimes.
- **Fundamental:** frozen static calendar; identical biases forever; event risk always 0; no commodity fundamentals.
- **Macro:** ^IRX mislabeled as 2Y; stale hardcoded rates (USD 5.50 = 2023); silent fallback defaults produce deterministic BEARISH_USD+RISK_ON.
- **Sentiment:** no news/sentiment at all — pure hardcoded cross-asset thresholds; all relationships assumed, none measured.
- **Risk:** ATR/TR formula correct and LONG/SHORT SL/TP correct in isolation, but direction not reconciled with signal direction (inverted-trade risk) and RR is a constant 3.0.

---

# PARAMETER-BY-PARAMETER AUDIT

## What parameters currently exist
Technical: signal weight 7.5, ADX trend bonus 10/5, RSI bands 42–68/32–58, BB %B 0.6/0.4, bandwidth 3.0. Candle: pattern score table 50–88, body ratio 0.70, wick 0.55, doji 0.12. Market structure: fractal window 5, scores 86/82/80/66/50. Currency strength: clip ×5 ±10, score ×6 cap 98. ML: sigmoid slope 3.0, equal weights 0.25, NEUTRAL 0.40, strength_diff 2.0. Regime: volatility 0.4/1.5, scores 60/75, confidence 0.8. Fundamental: surprise ×15, clamp 15–92, deadband ±0.1. Macro: rate_diff ×6 ±8, DXY 103.5/104.5, TNX 4.45. Sentiment: VIX 19/23, fixed bins 55–80. Risk: SL 1.2·ATR, TP1 1.5R, TP2 3R, score +rr·15. Aggregator: contradiction penalty 4.0, floor 30. Gate: min_rr 2.0, max_spread 10, min_score 70.

## What parameters are missing
Per-engine weights for aggregation; confidence thresholds; minimum-engine-count guard; calibration curves; volatility percentiles; probability-of-hit for TP1/TP2; spread/slippage per symbol; session/time-of-day filters; event-window gating; lookback windows for momentum; cross-validation splits; benchmark baselines.

## Questionable parameters
Every hardcoded threshold (RSI bands, VIX 19/23, volatility 0.4/1.5, DXY 103.5/104.5, TNX 4.45, rate_diff·6, surprise·15, clip·5) has no statistical basis in the codebase.

## Incorrectly defined
^IRX (13-week T-bill) labeled as 2Y; TIMEFRAMES["4H"]="1h"; "10 candles" comment vs actual 20-candle window in currency strength; RSI overlap 42–58 generating simultaneous buy+sell signals; Engulfing defined on full range.

## Redundant
SMA200 (dead, 60<200); strength_diff hardcoded (constant contribution); regime score (NEUTRAL but constant); RR "measurement" (always 3.0); the min-RR branch (unreachable); the data-quality gate (dead).

## Hardcoded
`strength_diff=2.0`, `expected_value=1.25`, `ml_probability=0.65`, `technical_score=75.0`, `risk_reward=2.5`, spread=1.0 pip, `session="LONDON/NY_OVERLAP"`, macro rates dict, fundamental calendar, VIX/Gold/WTI/BTC fallbacks, LLM fallback `approved: True`.

## Parameters needing statistical validation
ALL of them — see STATISTICAL VALIDATION REQUIREMENTS.

## Independent information
Genuinely distinct dimensions: Market Structure (swing topology), Currency Strength (cross-pair relative), Macro yields/DXY, Candle patterns, Risk ATR levels. These five are weakly correlated.

## Likely noise
Regime score, hardcoded strength_diff, Fundamental static surprise, Sentiment fixed bins, the contradiction-count penalty.

---

# TECHNICAL ANALYSIS AUDIT

| Indicator | Classification | Finding |
|---|---|---|
| EMA(20/50) | CORRECT | Standard ewm; used for trend/pullback |
| SMA(200) | REDUNDANT/dead | 60 candles < 200 → always NaN → fallback EMA50 |
| Wilder RSI(14) | CORRECT | Formula correct; but 42–58 overlap gives simultaneous buy+sell (QUESTIONABLE thresholds) |
| ATR(14) | CORRECT | EMA-based (not true Wilder seed) — LOW |
| Wilder ADX(14) | CORRECT | Used for trend bonus; threshold unvalidated |
| Bollinger(20,2σ) | QUESTIONABLE | `std(ddof=1)` instead of population ddof=0 |
| BB Bandwidth | NEEDS VALIDATION | Label-only; not independently interpreted |
| BB %B | CORRECT | 0.6/0.4 thresholds |
| MACD | MISSING | No MACD anywhere in code |
| Divergence | MISSING | Not implemented |
| Momentum/ROC | MISSING | Not implemented |
| Reversal detector | MISSING | Not implemented |
| Breakout / trend-continuation | INCORRECT | "BREAKOUT_CONTINUATION" emitted with no breakout computation |
| Pullback | CORRECT (basic) | prev close vs prev EMA20 |

**Score formula:** `score = min(96, 50 + signals·7.5 + trend_bonus)`; `trend_bonus = 10 if ADX>25 else (5 if ADX>20 else 0)`.

**Severity:** HIGH — fake breakout labels; HIGH — forming candle as decisive row; MEDIUM — SMA200 dead, RSI overlap, ddof.

---

# CANDLE ANALYSIS AUDIT

| Pattern | Classification | Finding |
|---|---|---|
| OHLC anatomy | CORRECT | body/upper/lower wick ratios correct |
| Doji | CORRECT | body ratio ≤0.12 |
| Hammer / Shooting Star | QUESTIONABLE | wick≥0.55, no prior-trend requirement |
| Engulfing | INCORRECT | `c>p_high AND o<p_low` (full range), not body engulf |
| Inside Bar | QUESTIONABLE | correct definition but direction from previous candle color |
| Outside Bar | CORRECT | — |
| Marubozu | QUESTIONABLE | ≥0.70, no context |
| Morning/Evening Star | QUESTIONABLE | midpoint penetration, no gap requirement |
| Rejection/continuation/reversal | MISSING | Not structurally detected |

**CRITICAL structural flaw:** single if/elif chain → only one pattern per candle; `max(score)` is cosmetic.
**CRITICAL:** the last (forming, incomplete) candle is used directly — single-candle patterns appear/vanish mid-bar.
**Missing:** candle strength, location, sequence metrics, volume.

---

# MARKET STRUCTURE AUDIT

- 5-bar fractal swing; confirmation lag 2 bars.
- HH/HL/LH/LL compare only the **last two swings** — simplified rolling-window, not genuine multi-level structure.
- BOS: higher_high + close>last_sh; CHoCH: lower_high + close>last_sh (short mirrored).
- Scoring: HH+HL 86/80; CHoCH 82; partial 66; else 50.
- **MISSING:** retest, consolidation (passive string only), liquidity sweep, breakout validation.
- **Look-ahead:** no `.shift(-k)` bias; BUT most recent swing (n-3) is confirmed using the forming candle as right neighbor → retroactive invalidation; BOS/CHoCH uses forming close with no confirmed-close/retest → false breaks (HIGH).

**Verdict:** genuine fractal detection, but simplified rolling-window structure logic with unconfirmed breaks.

---

# CURRENCY STRENGTH AUDIT

- Universe: 8 pairs (EUR/USD, GBP/USD, USD/JPY, AUD/USD, USD/CAD, USD/CHF, NZD/USD, EUR/GBP).
- Return: `log(end/start)·100` over 20 **1h** candles; base +ret, quote −ret; `np.mean`; `clip(avg·5, ±10)`.
- Wrapper score: `min(98, 50 + |diff|·6)`.

**Findings:**
- **CRITICAL:** sparse USD-centric universe — JPY/CHF/CAD/AUD/NZD appear in one pair each; missing 16+ cross pairs; single-pair currencies → 0.0 on failure.
- **HIGH:** "10 candles" comment vs actual full 20-candle single log-return; ×5 clip is not normalization; 1h-vs-15m timeframe mismatch.
- **MEDIUM:** redundant with technical momentum; |diff|≥8 saturates at 98.
- **Answer to brief:** adds cross-pair relative information beyond single-pair momentum (weakly), but not robustly measured — essentially a relative log-return ranking, not a normalized strength index.

---

# ML / PREDICTION AUDIT

**Model type:** NOT a trained model. No `fit()`, no learned parameters, no persistence, no ML libraries in requirements.

**Exact formula:**
```
rsi_norm = clip((rsi-30)/40, 0,1)   # LONG (mirrored for SHORT)
adx_norm = clip(adx/50, 0,1)
tech_norm = clip(tech/100, 0,1)
strength_norm = clip(|strength_diff|/10, 0,1)
logit = 0.25·rsi_norm + 0.25·adx_norm + 0.25·tech_norm + 0.25·strength_norm
prob = 1/(1+exp(-3.0·(logit-0.5)))
```
Equivalent: `P = σ(1.5 − 0.75·rsi − 0.75·adx − 0.75·tech − 0.75·strength)` — symmetric averaging, not a learned boundary.

**Target mismatch:** docstring claims "Target-Before-Stop" win probability; actual output is a trend-strength heuristic. No TP/SL geometry, no horizon, no next-candle direction, no R:R. **"Next candle direction" is NOT "probability this trade is profitable."**

**Leakage findings:**
- Train/test leakage: NO ISSUE (no training exists).
- Feature look-ahead: NO ISSUE (lagged correctly via diff()/shift(1)).
- Normalization leakage: NO ISSUE (fixed constants).
- **CRITICAL** — objective misrepresentation: target-vs-stop never modeled.
- **HIGH** — `strength_diff=2.0` hardcoded (constant +0.05 logit).
- **HIGH** — 0.72 is mathematically impossible (max ≈0.6873); 0.72/0.65/0.70 are hardcoded fallbacks.
- **MEDIUM** — NEUTRAL returns constant 0.40; downstream defaults fabricate 0.65/0.70.

**Calibration:** none. **Direct answer: a value of 0.72 CANNOT be interpreted as 72% success probability** — it is an uncalibrated heuristic; the live engine cannot even produce it; a realistic "good" LONG yields ≈0.57.

**Misrepresentation:** "Quantitative Tree / Calibrated Logit Classifier"; "LightGBM classifier"; "ML Target-vs-Stop Win Probability" — none true.

---

# MARKET REGIME AUDIT

- Volatility: `norm_vol = ((high-low).mean()/close.mean())·100`.
- Thresholds: >1.5 HIGH_VOLATILITY_EXPANSION; <0.4 LOW_VOLATILITY_CONSOLIDATION; else TRENDING_MOMENTUM.
- Score 75 (not HIGH) / 60 (HIGH); direction always NEUTRAL; confidence fixed 0.8.

**Findings:**
- **CRITICAL:** NEUTRAL direction but constant 75/60 score still enters the aggregator mean, inflating every composite with zero directional vote.
- **CRITICAL:** "TRENDING_MOMENTUM" assigned by volatility alone (no ADX/slope) — choppy mid-vol markets mislabeled.
- **HIGH:** only 3 of advertised regimes; 0.4/1.5 uncalibrated; <20-candle fallback returns SUCCESS 75/0.8.
- **MEDIUM:** volatility is a mean-range proxy; 75 for both MEDIUM and LOW carries no trend-vs-range signal.
- **Integration:** no other engine consumes regime output.

---

# FUNDAMENTAL AUDIT

- Source: hardcoded 13-row static `economic_events` list.
- Surprise: `(actual − consensus)/std`; score `50 + net_surprise·15`, clamp [15,92]; bias deadband ±0.1.

**Findings:**
- **CRITICAL:** frozen static calendar → identical biases forever (EUR/USD ≈39 SHORT; USD/JPY ≈52; EUR/GBP ≈42.5; USD/CAD, USD/CHF ≈57).
- **CRITICAL:** `upcoming_high_impact_events` always 0, yet evidence asserts "No high-impact releases scheduled" — fabricated assertion.
- **HIGH:** `importance` never applied; no commodity fundamentals (commodities get spurious USD-only scores).
- **MEDIUM:** no timestamps; no per-event sign conventions; no rate-expectation/monetary-divergence.
- **Verdict:** event labeling only, not genuine fundamental analysis.

---

# MACRO AUDIT

- Hardcoded rates: USD 5.50, GBP 5.25, NZD 5.25, CAD 4.75, AUD 4.35, EUR 3.75, CHF 1.25, JPY 0.25, XAU/WTI/BTC/ETH 0.00.
- Fallbacks: dxy 104.20, 10Y 4.25, short 4.10. Tickers: DX-Y.NYB/UUP/DX=F, ^TNX, ^IRX.
- Rate diff `base−quote` default 5.0; DXY bias >103.5 BULLISH; risk RISK_ON if dxy<104.5 AND 10Y<4.45; score `50 + rate_diff·6 ±8` clamp [20,95].

**Findings:**
- **CRITICAL:** `^IRX` (13-week T-bill) mislabeled as 2Y → "2s10s" is actually 13w-vs-10y.
- **CRITICAL:** central-bank rates stale (USD 5.50 = 2023), never fetched.
- **HIGH:** commodities/crypto rate 0.00 → rate_diff −5.50 → score pinned to ~20 floor; silent fallbacks produce deterministic BEARISH_USD+RISK_ON; built-in contradiction (DXY in [103.5,104.5] is BEARISH yet RISK_ON bonus).
- **MEDIUM:** dxy_bias/yield_curve computed but unused in score; UUP ×3.65 approximation.

---

# NEWS / SENTIMENT / CROSS-ASSET AUDIT

- Benchmarks/fallbacks: gold `GC=F|GLD|2450`, VIX `^VIX|16.5`, WTI `CL=F|USO|76`, BTC `BTC-USD|60000`.
- VIX thresholds: risk-on <19, high-fear >23. Fixed bins: CAD 78, Gold 80, haven 72, crypto 75/55, default 65.

**Findings:**
- **CRITICAL:** no news ingestion/NLP/event classification — this is pure cross-asset benchmark comparison, not sentiment.
- **CRITICAL:** all cross-asset relationships hardcoded/assumed; nothing dynamically measured or statistically validated; equities and yields not even fetched.
- **HIGH:** hardcoded fallbacks (16.5 VIX, 2450 gold, 76 WTI, 60000 BTC) silently produce confident directional signals on failure; ETF fallback scale mismatch (GC=F ~2400 vs GLD ~230).
- **MEDIUM:** fixed score bins ignore magnitude; confidence fixed 0.72.

---

# ECONOMIC EVENT AUDIT

- Calendar: hardcoded static list; importance/previous/forecast/actual all constants.
- Surprise standardized over the static table.
- **Time-to-event, pre-event conditions, post-event reaction: MISSING.**
- **Event risk:** `upcoming_events=0` never incremented; "No high-impact events" asserted unconditionally.
- **Verdict:** major events are NOT meaningfully incorporated; the economic-event dimension is effectively decorative.

---

# MARKET MICROSTRUCTURE AUDIT

**CURRENTLY AVAILABLE:** OHLCV only. **Spread:** fabricated as always 1.0 pip — `bid=close−0.5·pip`, `ask=close+0.5·pip`.
**NOT AVAILABLE (requires different provider):** bid/ask, real spread, liquidity, tick volume (Yahoo), order book, market depth, slippage, price impact, volatility bursts (only a crude mean-range proxy).
**Note:** OANDA real bid/ask/spread exists but is never wired into the scanner. Volume is populated but no engine reads it.
**HIGH:** spread gate is dead — max_spread=10, fabricated spread=1.0 → never fires.

---

# MULTI-TIMEFRAME AUDIT

- **CRITICAL:** the 1m/5m/15m/30m/1h/4h/daily/weekly architecture does not exist in the live path — only a single 15m series, hardcoded `timeframe="15M"`.
- **HIGH:** timeframe inconsistency mixed into one score (currency strength 1h vs everything else 15m).
- **HIGH:** forming (incomplete) candle consumed by Candle/Technical/ML/Risk (Yahoo unfiltered; OANDA filters complete=True but unused).
- **MEDIUM:** `TIMEFRAMES["4H"]="1h"` wrong and unused; 4h resample UTC-anchored; 1D never exercised.
- **LOW:** timezone internally consistent (UTC), but no canonical session conversion.
- Entry/setup/confirmation/trend/macro timeframe roles: NOT implemented.

---

# RISK AUDIT

**ATR/TR:** True Range formula correct; ATR is EMA-seeded (LOW, not true Wilder); fallback `max(price·0.002, pip·15)` (LOW).

**SL/TP formulas:** SL = entry ± 1.2·ATR; TP1 = ±1.8·ATR (1.5R); TP2 = ±3.6·ATR (3R); LONG/SHORT correctly mirrored **in isolation** (unit tests confirm).

- **CRITICAL — direction mismatch:** risk engine derives its own direction from price vs EMA20; the signal direction comes from the aggregator vote. No reconciliation → a LONG signal can carry SL above entry and TP below entry (inverted trade).
- **CRITICAL — RR is constant 3.0:** `reward = 3·risk` by construction → RR always 3.0; min-RR branch unreachable dead code; the "RR" is not market-derived.
- **HIGH:** spread fabricated (always 1 pip); event risk dead; concentration risk MISSING; liquidity risk MISSING.
- **MEDIUM:** correlation risk ad-hoc only; volatility is a crude label.

---

# AGGREGATION AUDIT

- Composite = **unweighted arithmetic mean** of every SUCCESS engine score.
- Contradiction penalty: `max(30, score − 4·len(contradicting))`; confidence = `score/100`.
- Direction = majority of LONG/SHORT votes (NEUTRAL ignored).

**Findings:**
- **CRITICAL:** heterogeneous scores (probability vs heuristic vs fixed regime score vs static fundamental score) averaged as directly comparable — exactly the failure mode in the brief.
- **CRITICAL:** per-engine confidence ignored; `overall_confidence` is a redundant transform of score.
- **HIGH:** NEUTRAL engines (Regime 75/60) inflate the mean with zero directional vote; 9 NEUTRAL + 1 LONG yields dominant LONG (misrepresentation); vote ignores score magnitude.
- **HIGH:** correlated double-counting (RSI/ADX/EMA recomputed in Technical, ML, Risk; strength_diff also in ML).
- **MEDIUM:** contradiction penalty counts caveat strings; missing-data normalizes over fewer engines with no minimum-count guard; staleness not re-checked.
- **NO ISSUE:** evidence lists preserved with prefixes.

---

# LLM CONTEXT AUDIT

- Payload: symbol, direction, score, confidence, price, supporting/contradicting/neutral evidence, missing_engines, engine_summaries.
- **CRITICAL:** LLM cannot veto — every provider fallback returns `approved: True`; output JSON unvalidated; missing `approved` key defaults True.
- **HIGH:** LLM can fabricate freely within output (no schema validation); context omits entry/stop/target/timeframe/timestamp/data-quality/spread/invalidation → cannot verify trade validity, only direction plausibility.
- **MEDIUM:** LLM confidence not propagated; raw metrics blobs; router fallback reads missing `ml_probability` key → always 0.70.
- **LOW:** `main_risk`/LLM contradictions requested but never consumed.

---

# BENCHMARK AUDIT

**No meaningful benchmark exists for any component.**
- ML: no naive baseline, no backtest, no evaluation at all.
- Technical: no simple momentum/mean-reversion baseline.
- Currency strength: no simple relative-return baseline comparison (though it *is* essentially that baseline — unvalidated).
- News/sentiment: no no-news baseline.
- Regime: no volatility-bucket validation.
- **Verdict:** current scores are arbitrary numbers with no demonstrated predictive meaning. Every score/pattern/threshold must be benchmarked before being trusted.

---

# REDUNDANCY AUDIT (Information-Overlap Matrix)

| Component | Overlaps With | Degree | Recommendation |
|---|---|---|---|
| ML feature RSI/ADX/EMA | Technical engine | HIGH (same indicators) | COMBINE (compute once, share) |
| ML strength_diff | Currency Strength | HIGH (hardcoded duplicate) | REMOVE hardcode, feed real value |
| Currency Strength | Technical momentum | MEDIUM (same OHLCV) | REDUCE/COMBINE |
| Regime score | Aggregator | HIGH (NEUTRAL but counted) | REMOVE from mean |
| EMA trend / ADX | Market Structure | MEDIUM (both trend) | VALIDATE independence |
| Macro | Fundamental | MEDIUM (both rates/policy) | COMBINE into one macro-fundamental layer |
| Technical pullback | Candle patterns | MEDIUM | VALIDATE |
| Sentiment cross-asset | Macro DXY/yields | MEDIUM (overlapping proxies) | COMBINE/COORDINATE |
| RSI overbought caveat | Contradiction list | HIGH (misclassified) | RE-CLASSIFY as caveat |

---

# LOOK-AHEAD / DATA-LEAKAGE AUDIT

| Issue | Severity |
|---|---|
| Forming (incomplete) candle consumed as settled data by all engines | HIGH |
| Objective misrepresentation (target-vs-stop never modeled) | CRITICAL |
| Hardcoded historical "actual" macro/fundamental data (stale by construction) | MEDIUM |
| No future indexing/negative shifts (rolling uses shift(1)/diff) | NO ISSUE |
| No future highs/lows/labels/news | NO ISSUE |
| No normalization on future data | NO ISSUE |
| No train/test contamination (classifier untrained) | NO ISSUE |
| `strength_diff=2.0` hardcoded constant feature | HIGH |

---

# PERFORMANCE AUDIT

- **HIGH:** currency strength computes full 8-pair matrix per instrument (14× per scan) though only base/quote lookup differs.
- **HIGH:** per-engine 3.5s timeout cannot kill threads — slow network engines keep running, results discarded.
- **HIGH:** Macro engine makes uncached per-instrument yfinance calls (up to 5×14).
- **MEDIUM:** sentiment re-fetches GC=F/CL=F/BTC-USD already fetched as instruments; RSI/ADX/ATR/EMA recomputed 2–3×; LLM routing sequential (~30s/instrument worst case).
- **LOW:** new ThreadPoolExecutor per instrument; import inside loop; `expected_value=1.25` hardcoded.
- **NO ISSUE:** bounded memory (≤100-candle DataFrames, diskcache).

---

# SECURITY / VULNERABILITY AUDIT

- **CRITICAL:** live Telegram bot token + chat ID committed in README (same in .env). Treat as compromised; rotate immediately.
- **HIGH:** live Azure OpenAI key and OANDA key/account in local .env.
- **HIGH:** unauthenticated runtime-secret-mutation and outbound-trigger endpoints: `/api/config/telegram/save`, `/api/config/llm/save`, `/api/config/oanda/save`, `/api/scan/trigger`.
- **HIGH:** SSRF/exfiltration via `/api/config/oanda/test` and `/api/config/telegram/test` (client-supplied endpoints cause outbound requests whose responses return to caller).
- **HIGH:** CORS `allow_origins=["*"]` + `allow_credentials=True`.
- **MEDIUM:** `/api/config` leaks chat_id and key-presence unauthenticated; LLM prompt-injection surface (candidate/evidence interpolated into prompts).
- **LOW:** hardcoded seed signals served; error bodies logged.
- **NO ISSUE:** no eval/exec/pickle/yaml.load; parameterized Supabase insert (no SQL injection); no unsafe model loading; HTTPS with TLS; JSON-only serialization.

---

# ENGINE SCORECARD

| Engine | Completeness | Correctness | Relevance | Robustness | Statistical Validity | Integration | Overall |
|---|---:|---:|---:|---:|---:|---:|---:|
| Technical | 45 | 55 | 70 | 50 | 35 | 60 | **52** |
| Candle | 40 | 40 | 55 | 35 | 25 | 55 | **42** |
| Market Structure | 35 | 45 | 65 | 40 | 30 | 55 | **45** |
| Currency Strength | 40 | 50 | 60 | 40 | 30 | 50 | **45** |
| ML / Prediction | 20 | 30 | 50 | 20 | 10 | 40 | **28** |
| Market Regime | 25 | 35 | 55 | 30 | 20 | 40 | **34** |
| Fundamental | 25 | 30 | 40 | 20 | 15 | 45 | **29** |
| Macro | 35 | 30 | 55 | 25 | 20 | 45 | **35** |
| Sentiment / Cross-Asset | 30 | 35 | 50 | 25 | 15 | 45 | **33** |
| Risk | 45 | 50 | 70 | 40 | 30 | 55 | **48** |
| Aggregation | 30 | 25 | 60 | 30 | 15 | 40 | **33** |
| LLM Decision | 35 | 30 | 55 | 25 | 20 | 40 | **34** |

**Weak-score explanations:** ML (28) — not a model, uncalibrated, objective mismatch. Fundamental (29) — static frozen data, zero event risk. Sentiment (33) — no sentiment, hardcoded rules. Regime (34) — volatility-only, NEUTRAL-but-counted. Aggregation (33) — invalid heterogeneous averaging.

---

# PARAMETER COMPLETENESS MATRIX

| Engine | Existing Parameters | Missing Parameters | Questionable | Redundant | Needs Validation |
|---|---|---|---|---|---|
| Technical | weights 7.5, ADX bonus, RSI/BB/bandwidth bands | MACD/divergence/momentum params, lookback windows | RSI overlap 42–58, ddof=1 | SMA200 | ALL thresholds |
| Candle | pattern scores, body 0.70, wick 0.55, doji 0.12 | context/trend/location params, volume | full-range engulf, no prior-trend | — | pattern definitions |
| Market Structure | fractal 5, scores | retest/liquidity params | last-2-swing only | — | BOS/CHoCH confirmation |
| Currency Strength | clip ×5 ±10, score ×6 | weighting, vol-normalization, more pairs | ×5 clip | redundant w/ momentum | normalization |
| ML | sigmoid 3.0, weights 0.25, NEUTRAL 0.40 | training/calibration/horizon | equal weights | strength_diff=2.0 | entire model |
| Regime | vol 0.4/1.5, score 60/75 | trend measure, transitions | 0.4/1.5 | NEUTRAL score | thresholds |
| Fundamental | surprise ×15, clamp 15–92, deadband | live calendar, weights | static surprise | importance (unused) | surprise mapping |
| Macro | rate_diff ×6 ±8, DXY 103.5/104.5, TNX 4.45 | real yields, 2s10s, fetched rates | ^IRX as 2Y, stale rates | dxy_bias (unused) | thresholds |
| Sentiment | VIX 19/23, fixed bins | correlation windows | hardcoded fallbacks | fixed bins | all rules |
| Risk | SL 1.2·ATR, TP 1.5R/3R | spread/slippage/concentration | — | RR constant 3.0 | SL/TP multiples |
| Aggregator | penalty 4.0, floor 30 | per-engine weights, min-count | penalty semantics | score/100 confidence | weighting scheme |

---

# PIPELINE SCORECARD

| Stage | Score (0–100) |
|---|---:|
| Market Data | 50 |
| Data Quality | 45 |
| Snapshot | 45 |
| Parallel Execution | 55 |
| Technical | 52 |
| Candle | 42 |
| Market Structure | 45 |
| Currency Strength | 45 |
| ML | 28 |
| Regime | 34 |
| Fundamental | 29 |
| Macro | 35 |
| Sentiment | 33 |
| Cross-Asset | 33 |
| Risk | 48 |
| Aggregation | 33 |
| Prediction | 28 |
| LLM Context | 34 |

---

# MISSING ANALYTICS

| Missing Capability | Why Needed | Current Gap | Data Required | Expected Benefit | Priority |
|---|---|---|---|---|---|
| Real probability calibration (ML) | EV, sizing, gating all depend on true P(win) | Heuristic sigmoid mislabeled "calibrated" | Labeled trade outcomes | Valid risk decisions | CRITICAL |
| Weighted evidence aggregation | Scores are incomparable | Unweighted mean | Per-engine weights from backtest | Meaningful composite | CRITICAL |
| Forming-candle filter | Prevent mid-bar false signals | Yahoo unfiltered | complete=True filter | Signal stability | CRITICAL |
| Real spread/slippage | Trade costs invalidate EV | Fabricated 1-pip spread | Broker bid/ask | Realistic RR/EV | HIGH |
| Multi-timeframe context | Trend/confirmation/setup alignment | Single 15m only | 1h/4h/daily series | Higher-quality setups | HIGH |
| Live economic calendar + event risk | Avoid trading into news | Static calendar, events=0 | Economic calendar API | Event risk gating | HIGH |
| Statistical regime (z-scores/percentiles/vol percentiles) | Replace arbitrary thresholds | Absent | Historical distribution | Calibrated thresholds | HIGH |
| Concentration & liquidity risk | Portfolio safety | Absent | Exposure/correlation data | Risk control | MEDIUM |
| Session/time-of-day analysis | FX session dynamics | Hardcoded session string | Time logic | Better timing | MEDIUM |
| Benchmark baselines | Prove scores mean anything | Absent | Historical data | Validated predictions | HIGH |

---

# CRITICAL PROBLEMS

### CRITICAL (materially incorrect signals)
1. Heterogeneous engine scores averaged as if comparable (no weighting/confidence).
2. ML "probability" is an untrained, uncalibrated heuristic; 0.72 impossible and meaningless.
3. LLM decision gate rubber-stamps (`approved: True` on all fallbacks; unvalidated JSON).
4. SL/TP direction not reconciled with signal direction → inverted-trade risk.
5. RR is a hardcoded constant 3.0 (not market-derived).
6. `expected_value` hardcoded 1.25; EV never computed in live path.
7. Telegram bot token + chat ID committed in README (compromised).
8. Multi-timeframe architecture advertised but absent (15m only).
9. Static frozen fundamental calendar → identical signals forever; event risk always 0.
10. Fabricated provenance ("LightGBM", "Calibrated", "Quantitative Tree") in evidence/signal/Telegram.

### HIGH (fix before serious paper trading)
- Per-engine confidence ignored; NEUTRAL engines inflate the mean.
- Correlated indicator double-counting across engines.
- Spread fabricated (1 pip); spread gate dead; RR gate bypassed by default 2.0.
- Data-quality gate dead code (DEGRADED passes).
- Risk/EV formulas correct in isolation but never wired; probability source uncalibrated.
- Macro ^IRX mislabeled as 2Y; stale hardcoded rates; silent fallback defaults.
- Sentiment: no news/sentiment; all cross-asset relationships hardcoded.
- Evidence taxonomy absent; WEAK/NEUTRAL mislabeled as contradictions and penalized.
- All statistical analyses (z-scores, distributions, percentiles, analogues) missing.
- Forming candle consumed by all engines.
- Unauthenticated /api/config/* and /api/scan/trigger endpoints; CORS wildcard.
- Currency strength 8-pair USD-centric universe; timeframe mismatch.
- Live signals lack signal_id/trace_id/reasoning_object; paper trading state discarded.

### MEDIUM
- Contradiction penalty counts caveats; missing-data normalization without min-count guard.
- LLM context omits risk/timing; raw metrics blobs; LLM confidence not propagated.
- Funnel counts fabricated; technical_score/risk_reward defaults in payload.
- Recomputations (currency strength 8-pair per instrument; RSI/ADX/EMA 2–3×; uncached macro calls).
- ATR EMA-seeded not Wilder; stop_loss_pips key mismatch.
- Correlation risk ad-hoc; 4h resample anchor; weekend/holiday handling crude.

### LOW
- SMA200 dead; ddof=1; RSI overlap; hardcoded session string; 1D timeframe unused; TIMEFRAMES constant wrong; timezone minor issues; seed demo signals; error-body logging.

---

# EXPERIMENTAL IMPROVEMENTS

Before trusting any signal: (1) build a labeled outcome dataset (SL/TP hit outcomes), (2) fit and cross-validate a real probability model, (3) derive per-engine weights via a hold-out backtest, (4) calibrate probabilities with Platt/isotonic regression, and (5) benchmark every indicator/pattern/regime rule against naive baselines. These are validation experiments, not code changes, and belong in the next phase.

---

# COMPONENTS TO KEEP

- Market Structure fractal detection (fix confirmation, add retest).
- Risk ATR/SL/TP math (correct in isolation — fix direction reconciliation and wiring).
- Technical core indicators (EMA/RSI/ADX/ATR/%B implementations).
- Yahoo/OANDA provider abstraction and cache layer.
- Parallel orchestrator/registry scaffolding.
- Supabase dedup persistence (parameterized, graceful).
- Data validator jump/freshness checks.

---

# COMPONENTS TO IMPROVE

- Technical engine (add missing indicators, remove fake labels, fix RSI overlap).
- Candle engine (correct Engulfing, add context/trend requirement, multiple-pattern output).
- Currency Strength (expand pairs, true normalization, align timeframe).
- Market Structure (add retest/confirmation, full swing topology).
- Macro (fetch live rates, fix ^IRX→2Y, remove silent fallbacks).
- Risk wiring (EV computed, real spread, direction reconciliation).
- Aggregator (weighted, confidence-aware, min-count guard).
- LLM context (include risk/timing levels, validate output, fail-safe).

---

# COMPONENTS TO COMBINE

- Macro + Fundamental → one macro-fundamental layer with live calendar + live rates.
- ML feature computation → share Technical's indicators (compute once).
- Currency Strength + momentum → clarify independence or merge.
- Sentiment cross-asset + Macro DXY/yields → coordinate overlapping proxies.
- Regime → make it a context feature, not a scored engine.

---

# COMPONENTS TO REMOVE (do not remove during audit)

- The hardcoded `strength_diff=2.0` feature and NEUTRAL 0.40 shortcut in ML.
- Regime's NEUTRAL-but-scored contribution to the mean.
- Fake "BREAKOUT_CONTINUATION"/"VOLATILITY_EXPANSION" labels.
- SMA200 (dead, 60<200).
- Fabricated "LightGBM/calibrated/tree" claims.
- Hardcoded `expected_value=1.25` and probability defaults.
- Silent macro/sentiment fallback defaults (or flag them explicitly).

---

# COMPONENTS TO ADD

- Real calibrated probability model (target = hit TP before SL).
- Weighted, confidence-aware evidence aggregation with contradiction detection.
- Forming-candle filter on the Yahoo path.
- Real bid/ask spread + slippage model.
- Multi-timeframe (1h/4h/daily) trend context.
- Live economic calendar with event-risk windows.
- Statistical regime features (z-scores, volatility percentiles, autocorrelation).
- Benchmark baselines for every engine.
- Session/time-of-day analysis.
- Concentration and liquidity risk metrics.

---

# COMPONENTS NOT WORTH ADDING

- Order book / market depth for a 15m-swing system (requires different data provider; low marginal benefit at this horizon).
- Tick-volume intraday microstructure for FX on Yahoo (unavailable and low value at 15m).
- Complex NLP news sentiment before a working calibration/benchmark foundation exists.
- Additional oscillators (Stochastic/CCI) that would just add correlated redundancy without statistical validation.
- Seasonality for currencies (weak evidence; only meaningful for a subset of commodities).
- Elaborate order-flow models before basic spread/slippage/EV correctness is fixed.

---

# STATISTICAL VALIDATION REQUIREMENTS

Must be validated before trust: RSI/ADX/BB/bandwidth thresholds; candle pattern definitions and score weights; fractal window size; currency-strength normalization; regime volatility thresholds; VIX/DXY/TNX thresholds; rate-diff scoring; surprise-to-score mapping; the entire ML model (weights, sigmoid slope, NEUTRAL constant); SL/TP multiples (1.2/1.5/3.0); aggregation weights and contradiction penalty; EV probability source and spread term; every cross-asset correlation assumption; and every benchmark claim.

---

# NEXT-LEVEL ANALYTICAL ARCHITECTURE (proposed, NOT implemented)

```
Market Data (multi-timeframe, complete candles only)
    ↓
Data Quality (freshness, jump, null, forming-candle filter)
    ↓
Market Snapshot (unified timestamp, session, spread)
    ↓
Parallel Evidence
├── Technical (validated indicators)
├── Candle (context-aware patterns)
├── Market Structure (confirmed swings, retest)
├── Momentum / Volatility (statistical)
├── Currency Strength (normalized cross-pair)
├── ML (trained, calibrated win probability)
├── Regime (trend + volatility, contextual)
├── Fundamental + Macro + Rates/Yields (live)
├── Economic Events (live calendar, risk windows)
├── News / Sentiment (real ingestion, not assumed)
├── Cross-Asset (rolling, validated correlations)
├── Liquidity / Microstructure (real spread)
├── Statistics (z-scores, percentiles, analogues)
└── Risk (ATR SL/TP, concentration, correlation)
    ↓
Evidence Normalization (common scale per evidence type)
    ↓
Evidence Quality (STRONG/MODERATE/NEUTRAL/WEAK/STRONG-CONTRADICTION/MISSING/UNRELIABLE)
    ↓
Contradiction Detection (directional, not caveat-count)
    ↓
Weighted Aggregation (confidence-aware, min-engine guard)
    ↓
Prediction / LLM (calibrated probability + full risk/timing context, fail-safe)
    ↓
Deterministic Risk Validation (direction-consistent SL/TP, real costs, EV gate)
    ↓
Signal (trace_id, reasoning_object, benchmarked score)
```

Each layer exists for a specific reason: multi-timeframe for alignment; data-quality for a clean snapshot; per-evidence normalization because heterogeneous scores cannot be averaged raw; evidence-quality taxonomy because WEAK≠CONTRADICTORY and MISSING≠NEGATIVE; contradiction detection to preserve opposing evidence; weighted aggregation to combine calibrated independent evidence; a fail-safe LLM as a checker rather than a rubber stamp; and a deterministic risk gate to enforce direction consistency and realistic costs before any signal is emitted.

---

# TOP 10 REQUIRED IMPROVEMENTS

1. **Replace the "ML" heuristic with a real, trained, cross-validated, calibrated win-probability model** whose target is exactly "TP hit before SL" — and remove all "LightGBM/calibrated" mislabels.
2. **Rebuild aggregation** to normalize heterogeneous evidence, use per-engine weights and confidence, enforce a minimum-engine count, and model contradictions directionally (not as a flat −4 penalty).
3. **Filter the forming candle** on the Yahoo path (or use OANDA's complete=True) so no engine evaluates an incomplete bar.
4. **Reconcile signal direction with SL/TP direction** and compute RR/EV from measured values — eliminate the constant 3.0 RR and hardcoded EV=1.25.
5. **Wire real spread/slippage** (from OANDA or a quote feed) instead of the fabricated 1-pip spread, and make the spread/RR gates actually effective.
6. **Make the LLM gate fail-safe**: validate output schema, default to REJECT (not approve) on failure, and supply stop/target/timing/risk context.
7. **Implement genuine multi-timeframe analysis** (at minimum 15m + 1h + 4h + daily) with defined entry/setup/confirmation/trend roles.
8. **Replace static Fundamental/Macro data with live sources** (economic calendar, current central-bank rates, correct 2Y yield), and flag — not silently default — data outages.
9. **Add the statistical layer** (z-scores, volatility percentiles, distributions, analogues) and benchmark every engine against naive baselines.
10. **Security hardening**: rotate the exposed Telegram token, authenticate all /api/config/* and /api/scan/trigger endpoints, and fix the CORS wildcard.

---

# OVERALL ANALYTICS SCORE

**38 / 100.** Scoring rubric: completeness and correctness of each engine, statistical validity, integration, and the integrity of the aggregation/prediction layer. The strongest sub-score is the Risk math (48) and the technical indicators (52); the weakest are ML (28), Fundamental (29), and the aggregation/prediction layer (33/28).

---

# FINAL VERDICT

1. **Is the current analytical layer genuinely comprehensive?** No. It is *broad* but *shallow*: ~10 engines largely recompute the same indicators over a single 15m series; several are static/hardcoded; the statistical and microstructure layers are absent.
2. **Strongest engines:** Risk (ATR/SL/TP math correct in isolation), Market Structure (genuine fractals), and the core Technical indicators (EMA/RSI/ADX/ATR/%B implementations).
3. **Weakest engines:** ML (not a model), Fundamental (frozen static), Sentiment (no sentiment), Regime (volatility-only).
4. **Redundant engines:** ML features vs Technical; Currency Strength vs momentum; Regime (NEUTRAL-but-counted); Macro vs Fundamental (overlap).
5. **Missing dimensions:** probability calibration, multi-timeframe, real spread/liquidity, live economics, statistical regime, session/time-of-day, benchmarks.
6. **Are predictions measuring trade success?** No. The "probability" is a trend-strength heuristic; nothing models TP-vs-SL outcomes, so no signal's probability reflects trade success.
7. **Is aggregation logically valid?** No — incompatible scores are averaged unweighted with confidence ignored and caveats penalized as contradictions.
8. **Is the LLM receiving sufficient evidence?** No — it lacks risk/timing/price levels, and it cannot veto (failures auto-approve).
9. **Major leakage/look-ahead risks?** Yes — the forming (incomplete) candle is the dominant live-bar integrity risk; no classical train/test leakage exists only because there is no training.
10. **Are scores statistically meaningful?** No — none are benchmarked, calibrated, or validated.
11. **Suitable for continuous Forex + commodity scanning?** Not yet. It runs continuously, but the output quality is insufficient for high-quality opportunity assessment until the top-10 improvements are implemented.
12. **TOP 10 improvements:** listed above — replace the ML layer, rebuild aggregation, filter forming candles, fix direction/EV, wire real spread, make the LLM fail-safe, add multi-timeframe, live macro/fundamental data, a statistical/benchmark layer, and security hardening.

**Bottom line:** the system is a credible *scaffolding* with correctly implemented core indicators and a working parallel execution framework, but its *prediction and aggregation layer* is not yet trustworthy. The ten engines do not currently constitute ten independent, validated sources of evidence. The next development phase must prioritize a real calibrated model, valid aggregation, complete-candle handling, and direction-consistent risk computation before any paper-trading use.

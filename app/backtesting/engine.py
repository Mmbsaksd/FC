"""
Point-In-Time Historical Backtesting and Simulation Engine for FC Trading System.
Executes authentic multi-engine parallel analysis, asset-aware evidence aggregation,
ML probability evaluation, deterministic risk gating, and bar-by-bar trade lifecycle simulation.
Strictly eliminates look-ahead bias and performs empirical stop-loss root-cause attribution.
"""

import logging
import uuid
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import numpy as np

from app.parallel.base_engine import MarketSnapshot, AnalysisResult
from app.parallel.registry import AnalysisEngineRegistry
from app.parallel.engines.technical_engine import ParallelTechnicalEngine
from app.parallel.engines.market_structure_engine import ParallelMarketStructureEngine
from app.parallel.engines.candle_engine import ParallelCandleEngine
from app.parallel.engines.currency_strength_engine import ParallelCurrencyStrengthEngine
from app.parallel.engines.regime_engine import ParallelRegimeEngine
from app.parallel.engines.ml_engine import ParallelMLEngine
from app.parallel.engines.macro_engine import ParallelMacroEngine
from app.parallel.engines.sentiment_engine import ParallelSentimentEngine
from app.parallel.engines.fundamental_engine import ParallelFundamentalEngine
from app.parallel.engines.risk_engine import ParallelRiskEngine
from app.parallel.aggregator import EvidenceAggregator
from app.risk.candidate_qualifier import CandidateQualificationEngine
from app.ml.feature_extractor import feature_extractor
from app.ml.meta_model import central_meta_model
from app.risk.risk_engine import RiskEngine
from app.risk.final_gate import DeterministicFinalRiskGate
from app.engines.outcome_tracker import EmpiricalStopLossAnalyzer
from app.engines.technical_engine import TechnicalAnalysisEngine

logger = logging.getLogger(__name__)

class HistoricalBacktestEngine:
    """
    Simulates the authentic FC trading pipeline over historical bar series.
    Guarantees strict point-in-time feature extraction and trade state isolation.
    """

    def __init__(
        self,
        strategy_params: Optional[Dict[str, Any]] = None,
        spread_slippage_model: bool = True,
        pipeline_mode: str = "CANDIDATE"
    ):
        self.strategy_params = strategy_params or {}
        self.spread_slippage_model = spread_slippage_model
        self.pipeline_mode = self.strategy_params.get("pipeline_mode", pipeline_mode).upper()
        
        # Initialize reusable engine registry and components
        self.registry = self._build_engine_registry()
        self.aggregator = EvidenceAggregator()
        self.final_risk_gate = DeterministicFinalRiskGate(
            min_rr=self.strategy_params.get("min_rr", 2.0),
            max_spread_pips=self.strategy_params.get("max_spread_pips", 10.0)
        )
        self.candidate_qualifier = CandidateQualificationEngine(
            min_consensus=self.strategy_params.get("min_consensus", 0.15),
            min_rr=self.strategy_params.get("min_rr", 2.0),
            min_ev_r=self.strategy_params.get("min_ev_r", 0.0),
            max_contradiction_ratio=self.strategy_params.get("max_contradiction_ratio", 0.50)
        )
        self.min_opportunity_score = self.strategy_params.get("min_opportunity_score", 70.0)
        self.min_ml_probability = self.strategy_params.get("min_ml_probability", 0.40)
        self.max_holding_bars = self.strategy_params.get("max_holding_bars", 24)

    def _build_engine_registry(self) -> AnalysisEngineRegistry:
        registry = AnalysisEngineRegistry()
        registry.register(ParallelTechnicalEngine())
        registry.register(ParallelMarketStructureEngine())
        registry.register(ParallelCandleEngine())
        registry.register(ParallelCurrencyStrengthEngine())
        registry.register(ParallelRegimeEngine())
        registry.register(ParallelMLEngine())
        registry.register(ParallelMacroEngine())
        registry.register(ParallelSentimentEngine())
        registry.register(ParallelFundamentalEngine())
        registry.register(ParallelRiskEngine())
        return registry

    def run_backtest_on_instrument(
        self,
        instrument_config: Dict[str, Any],
        historical_df: pd.DataFrame,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        step_stride: int = 1
    ) -> Dict[str, Any]:
        """
        Executes point-in-time simulation over historical_df for an instrument.
        Returns detailed trade records, rejected candidates, and performance metrics.
        """
        empty_res = {
            "symbol": instrument_config.get("name", instrument_config.get("symbol", "")),
            "asset_class": instrument_config.get("type", "FOREX").upper(),
            "trades": [],
            "rejected_candidates": [],
            "all_candidates": [],
            "funnel": {
                "raw_bars": len(historical_df) if not historical_df.empty else 0,
                "decision_points": 0,
                "neutral_setups": 0,
                "evaluated_candidates": 0,
                "accepted_candidates": 0,
                "rejected_candidates": 0,
                "executed_portfolio_trades": 0,
                "skipped_due_to_open_trade": 0,
                "outcome_classes": {
                    "WIN": 0, "SMALL_WIN": 0, "BREAKEVEN": 0,
                    "SMALL_LOSS": 0, "LOSS": 0, "EXPIRED": 0, "NEUTRAL": 0
                }
            },
            "summary": self.calculate_performance_metrics([])
        }
        if historical_df.empty or len(historical_df) < 30:
            return empty_res

        df = historical_df.copy().reset_index(drop=True)
        if start_date:
            df = df[df["timestamp"] >= pd.to_datetime(start_date, utc=True)].reset_index(drop=True)
        if end_date:
            df = df[df["timestamp"] <= pd.to_datetime(end_date, utc=True)].reset_index(drop=True)

        if len(df) < 30:
            empty_res["funnel"]["raw_bars"] = len(df)
            return empty_res

        # Precompute vectorized technical indicators once on df to accelerate bar simulation
        df = TechnicalAnalysisEngine.calculate_indicators(df)

        symbol = instrument_config["symbol"]
        symbol_name = instrument_config["name"]
        asset_class = instrument_config.get("type", "FOREX").upper()
        pip_size = instrument_config.get("pip_size", 0.0001)
        base_curr = instrument_config.get("base", "USD")
        quote_curr = instrument_config.get("quote", "USD")
        is_crypto = (asset_class == "CRYPTO")

        # Typical spread in pips
        spread_pips = 1.5 if asset_class == "FOREX" else (5.0 if asset_class == "COMMODITY" else 15.0)

        trades: List[Dict[str, Any]] = []
        rejected_candidates: List[Dict[str, Any]] = []
        all_candidates: List[Dict[str, Any]] = []
        active_trade_exit_bar = -1
        n_bars = len(df)
        i = 30  # Start with minimum lookback of 30 bars

        funnel_stats = {
            "raw_bars": n_bars,
            "decision_points": 0,
            "neutral_setups": 0,
            "evaluated_candidates": 0,
            "accepted_candidates": 0,
            "rejected_candidates": 0,
            "executed_portfolio_trades": 0,
            "skipped_due_to_open_trade": 0,
            "outcome_classes": {
                "WIN": 0, "SMALL_WIN": 0, "BREAKEVEN": 0,
                "SMALL_LOSS": 0, "LOSS": 0, "EXPIRED": 0, "NEUTRAL": 0
            }
        }

        while i < n_bars - 2:
            funnel_stats["decision_points"] += 1

            # 1. POINT-IN-TIME CANDLE SLICE (Zero lookahead: strictly up to bar i)
            candles_slice = df.iloc[max(0, i - 60):i + 1].copy().reset_index(drop=True)
            current_bar = df.iloc[i]
            close_price = float(current_bar["close"])
            bar_timestamp = current_bar["timestamp"].isoformat()

            # 2. CONSTRUCT IMMUTABLE MARKET SNAPSHOT
            snapshot = MarketSnapshot(
                timestamp=bar_timestamp,
                symbol=symbol,
                symbol_name=symbol_name,
                asset_class=asset_class,
                price=close_price,
                bid=close_price - (pip_size * spread_pips * 0.5),
                ask=close_price + (pip_size * spread_pips * 0.5),
                spread_pips=spread_pips,
                timeframe="1D",
                candles=candles_slice,
                session="LONDON/NY_OVERLAP",
                pip_size=pip_size,
                base_currency=base_curr,
                quote_currency=quote_curr,
                is_crypto=is_crypto
            )

            # 3. EXECUTE REGISTERED ENGINES SAFELY
            engine_results: Dict[str, AnalysisResult] = {}
            for eng in self.registry.get_all_engines(enabled_only=True):
                try:
                    engine_results[eng.name] = eng.analyze(snapshot)
                except Exception as e:
                    logger.debug(f"Engine {eng.name} failed during backtest: {e}")

            # 4. AGGREGATE EVIDENCE (With Asset-Specific Profiles)
            context = self.aggregator.aggregate_evidence(snapshot, engine_results)

            # 5. FEATURE EXTRACTION & ML PROBABILITY
            named_features, feat_vector = feature_extractor.extract_features(snapshot, engine_results)
            ml_pred = central_meta_model.predict_probability(named_features, direction=context.dominant_direction)
            ml_prob = ml_pred.get("win_probability", 0.50)

            trade_dir = context.dominant_direction

            # Handle NEUTRAL direction setups as valid observation records
            if trade_dir not in ["LONG", "SHORT"]:
                funnel_stats["neutral_setups"] += 1
                funnel_stats["outcome_classes"]["NEUTRAL"] += 1
                neutral_record = {
                    "candidate_id": f"CAND-NEUT-{symbol_name.replace('/', '')}-{i}",
                    "signal_id": f"SIG-BT-{symbol_name.replace('/', '')}-{i}",
                    "decision_time": bar_timestamp,
                    "symbol": symbol_name,
                    "asset": symbol_name,
                    "asset_class": asset_class,
                    "timeframe": "1D",
                    "direction": "NEUTRAL",
                    "features": named_features,
                    "engine_outputs": {k: {"score": v.score, "direction": v.direction, "confidence": v.confidence} for k, v in engine_results.items()},
                    "engine_scores": {k: v.score for k, v in engine_results.items()},
                    "supporting_evidence": context.supporting_evidence,
                    "contradicting_evidence": context.contradicting_evidence,
                    "decision": "NO_TRADE",
                    "accepted": False,
                    "score": context.composite_opportunity_score,
                    "ml_prob": ml_prob,
                    "rejection_reason": "NEUTRAL_DIRECTION",
                    "rejection_stage": "DIRECTION_FILTER",
                    "rejection_score": context.composite_opportunity_score,
                    "future_outcome": "NEUTRAL_DIRECTION",
                    "realized_r": 0.0,
                    "mfe_r": 0.0,
                    "mae_r": 0.0,
                    "holding_bars": 0,
                    "outcome_class": "NEUTRAL",
                    "exit_time": None,
                    "exit_price": None,
                    "root_cause": None,
                    "root_cause_evidence": None,
                    "sl_hit": False,
                    "t1_hit": False,
                    "t2_hit": False
                }
                all_candidates.append(neutral_record)
                rejected_candidates.append(neutral_record)
                i += step_stride
                continue

            funnel_stats["evaluated_candidates"] += 1

            # 6. TRADE PARAMETER CALCULATION
            risk_res = engine_results.get("RiskMetrics")
            atr_val = (risk_res.metrics.get("atr") if risk_res and risk_res.metrics else None) or (pip_size * 20.0)

            calc_params = RiskEngine.calculate_trade_parameters(
                symbol=symbol,
                direction=trade_dir,
                current_price=close_price,
                atr=atr_val,
                pip_size=pip_size,
                min_rr=self.strategy_params.get("min_rr", 2.0),
                asset_class=asset_class
            )

            # 7. RISK GATE & CANDIDATE EVALUATION
            if self.pipeline_mode == "CANDIDATE":
                stage1_ok, stage1_reason, q_metrics = self.candidate_qualifier.evaluate_qualification(
                    context, calc_params, ml_probability=ml_prob
                )
                ev_r = q_metrics.get("expected_value_r", 0.0)
                context.expected_value_r = ev_r
                context.candidate_qualified = stage1_ok
                context.qualification_reason = stage1_reason

                llm_decision, llm_reason, llm_sup, llm_con = self._evaluate_historical_llm_surrogate(
                    context, engine_results, calc_params, ev_r
                )

                decision_candidate = {
                    "symbol_name": symbol_name,
                    "direction": trade_dir,
                    "opportunity_score": context.composite_opportunity_score,
                    "ml_probability": ml_prob,
                    "expected_value_r": ev_r,
                    "decision": llm_decision if stage1_ok else "REJECT"
                }
                passed_gate, gate_reason = self.final_risk_gate.validate_candidate(
                    decision_candidate,
                    context.snapshot_meta,
                    calc_params,
                    mode="CANDIDATE"
                )

                is_accepted = (stage1_ok and (llm_decision == "TRADE") and passed_gate)
                if not is_accepted:
                    if not stage1_ok:
                        rejection_stage = "STAGE_1_QUALIFICATION"
                        rejection_reason = stage1_reason
                    elif llm_decision != "TRADE":
                        rejection_stage = "STAGE_2_LLM"
                        rejection_reason = llm_reason
                    else:
                        rejection_stage = "STAGE_3_RISK_GATE"
                        rejection_reason = gate_reason
                else:
                    rejection_stage = "NONE"
                    rejection_reason = None
            else:  # CHAMPION mode baseline
                ev_r = (ml_prob * float(calc_params.get("risk_reward", 2.0))) - ((1.0 - ml_prob) * 1.0)
                stage1_ok = (context.composite_opportunity_score >= self.min_opportunity_score)
                llm_decision = "TRADE" if stage1_ok else "WATCH"
                llm_reason = "Champion threshold gate"
                decision_candidate = {
                    "symbol_name": symbol_name,
                    "direction": trade_dir,
                    "opportunity_score": context.composite_opportunity_score,
                    "ml_probability": ml_prob,
                    "decision": "TRADE"
                }
                passed_gate, gate_reason = self.final_risk_gate.validate_candidate(
                    decision_candidate,
                    context.snapshot_meta,
                    calc_params,
                    mode="CHAMPION"
                )
                meets_score = (context.composite_opportunity_score >= self.min_opportunity_score)
                meets_ml = (ml_prob >= self.min_ml_probability)
                is_accepted = (passed_gate and meets_score and meets_ml)
                rejection_reason = None if is_accepted else (gate_reason if not passed_gate else ("Below ML threshold" if not meets_ml else "Below score threshold"))
                rejection_stage = "NONE" if is_accepted else ("RISK_GATE" if not passed_gate else ("ML_THRESHOLD" if not meets_ml else "SCORE_THRESHOLD"))

            # 8. PREPARE EXECUTION BRACKET (Fills at next candle open + slippage friction)
            next_bar = df.iloc[i + 1]
            entry_price = float(next_bar["open"])
            
            # Apply execution friction (half spread + slippage)
            slippage = pip_size * (0.5 if not is_crypto else 2.0) if self.spread_slippage_model else 0.0
            if trade_dir == "LONG":
                fill_price = entry_price + (spread_pips * pip_size * 0.5) + slippage
            else:
                fill_price = entry_price - (spread_pips * pip_size * 0.5) - slippage

            # Re-bracket SL and TP from authentic fill price
            trade_bracket = RiskEngine.calculate_trade_parameters(
                symbol=symbol,
                direction=trade_dir,
                current_price=fill_price,
                atr=atr_val,
                pip_size=pip_size,
                asset_class=asset_class
            )
            stop_loss = trade_bracket["stop_loss"]
            take_profit_1 = trade_bracket["take_profit_1"]
            take_profit_2 = trade_bracket["take_profit_2"]
            risk_dist = abs(fill_price - stop_loss)
            if risk_dist <= 0:
                i += step_stride
                continue

            # 9. SIMULATE FORWARD OUTCOME (FOR ALL CANDIDATES AS OUTCOME LABEL)
            signal_id = f"SIG-BT-{symbol_name.replace('/', '')}-{i}"
            base_sig = {
                "signal_id": signal_id,
                "symbol": symbol_name,
                "direction": trade_dir,
                "entry_price": fill_price,
                "stop_loss": stop_loss,
                "features_at_entry": named_features
            }

            sim_res = self.simulate_candidate_forward_outcome(
                df=df,
                entry_bar_idx=i + 1,
                fill_price=fill_price,
                stop_loss=stop_loss,
                take_profit_1=take_profit_1,
                take_profit_2=take_profit_2,
                trade_dir=trade_dir,
                risk_dist=risk_dist,
                max_holding_bars=self.max_holding_bars,
                signal_base_record=base_sig
            )

            # Record outcome class distribution
            oclass = sim_res["outcome_class"]
            if oclass in funnel_stats["outcome_classes"]:
                funnel_stats["outcome_classes"][oclass] += 1

            candidate_record = {
                "candidate_id": f"CAND-{symbol_name.replace('/', '')}-{i}",
                "signal_id": signal_id,
                "decision_time": bar_timestamp,
                "symbol": symbol_name,
                "asset": symbol_name,
                "asset_class": asset_class,
                "timeframe": "1D",
                "direction": trade_dir,
                "features": named_features,  # Point-in-time decision features ONLY (Zero Lookahead)
                "engine_outputs": {k: {"score": v.score, "direction": v.direction, "confidence": v.confidence} for k, v in engine_results.items()},
                "engine_scores": {k: v.score for k, v in engine_results.items()},
                "supporting_evidence": context.supporting_evidence,
                "contradicting_evidence": context.contradicting_evidence,
                "long_evidence": getattr(context, "long_evidence", 0.0),
                "short_evidence": getattr(context, "short_evidence", 0.0),
                "neutral_evidence": getattr(context, "neutral_evidence", 0.0),
                "directional_consensus": getattr(context, "directional_consensus", 0.0),
                "expected_value_r": ev_r,
                "risk_reward": float(calc_params.get("risk_reward", 2.0)),
                "candidate_qualified": stage1_ok,
                "qualification_reason": rejection_reason if not stage1_ok else "Passed Stage-1 qualification",
                "llm_decision": llm_decision,
                "llm_reason": llm_reason,
                "llm_surrogate_type": "APPROXIMATED_DETERMINISTIC_SURROGATE",
                "pipeline_mode": self.pipeline_mode,
                "decision": "TRADE" if is_accepted else "REJECT",
                "accepted": is_accepted,
                "score": context.composite_opportunity_score,
                "ml_prob": ml_prob,
                "rejection_reason": rejection_reason,
                "rejection_stage": rejection_stage,
                "rejection_score": context.composite_opportunity_score if not is_accepted else 0.0,
                "strategy_version": self.strategy_params.get("candidate_version", "v2.0-candidate-opt" if self.pipeline_mode == "CANDIDATE" else "v1.0-champion"),
                "model_version": self.strategy_params.get("model_version", "v2.0"),
                "feature_version": self.strategy_params.get("feature_version", "v2.0"),
                "parameter_version": self.strategy_params.get("parameter_version", "p1.0"),
                
                # Counterfactual / Actual Outcome Labels (Strictly future labels)
                "future_outcome": sim_res["exit_reason"],
                "realized_r": sim_res["realized_r"],
                "mfe_r": sim_res["mfe_r"],
                "mae_r": sim_res["mae_r"],
                "holding_bars": sim_res["holding_bars"],
                "outcome_class": sim_res["outcome_class"],
                "exit_time": sim_res["exit_time"],
                "exit_price": sim_res["exit_price"],
                "root_cause": sim_res["root_cause"],
                "root_cause_evidence": sim_res["root_cause_evidence"],
                "sl_hit": sim_res["sl_hit"],
                "t1_hit": sim_res["t1_hit"],
                "t2_hit": sim_res["t2_hit"]
            }

            all_candidates.append(candidate_record)

            if is_accepted:
                funnel_stats["accepted_candidates"] += 1

                # 10. PORTFOLIO POSITION STATE SEPARATION
                # Execute in portfolio only if no concurrent active trade exists for this symbol
                if i >= active_trade_exit_bar:
                    funnel_stats["executed_portfolio_trades"] += 1
                    active_trade_exit_bar = sim_res["exit_bar_idx"]

                    trade_record = {
                        "signal_id": signal_id,
                        "symbol": symbol_name,
                        "asset_class": asset_class,
                        "direction": trade_dir,
                        "decision_time": bar_timestamp,
                        "entry_time": next_bar["timestamp"].isoformat(),
                        "entry_price": fill_price,
                        "stop_loss": stop_loss,
                        "take_profit_1": take_profit_1,
                        "take_profit_2": take_profit_2,
                        "opportunity_score": context.composite_opportunity_score,
                        "ml_probability": ml_prob,
                        "features_at_entry": named_features,
                        "supporting_evidence": context.supporting_evidence,
                        "contradicting_evidence": context.contradicting_evidence,
                        "t1_hit": sim_res["t1_hit"],
                        "t2_hit": sim_res["t2_hit"],
                        "sl_hit": sim_res["sl_hit"],
                        "realized_r": sim_res["realized_r"],
                        "mfe_r": sim_res["mfe_r"],
                        "mae_r": sim_res["mae_r"],
                        "holding_bars": sim_res["holding_bars"],
                        "exit_time": sim_res["exit_time"],
                        "exit_price": sim_res["exit_price"],
                        "exit_reason": sim_res["exit_reason"],
                        "root_cause": sim_res["root_cause"],
                        "root_cause_evidence": sim_res["root_cause_evidence"],
                        "outcome_class": sim_res["outcome_class"]
                    }
                    trades.append(trade_record)
                else:
                    funnel_stats["skipped_due_to_open_trade"] += 1
            else:
                funnel_stats["rejected_candidates"] += 1
                rejected_candidates.append(candidate_record)

            # ADVANCE STEP STRIDE (Evaluate every valid decision bar without skipping history)
            i += step_stride

        # Compute summary metrics for instrument
        summary = self.calculate_performance_metrics(trades)
        return {
            "symbol": symbol_name,
            "asset_class": asset_class,
            "trades": trades,
            "rejected_candidates": rejected_candidates,
            "all_candidates": all_candidates,
            "funnel": funnel_stats,
            "summary": summary
        }

    @staticmethod
    def evaluate_candidates_against_params(
        candidates: List[Dict[str, Any]],
        params: Dict[str, Any],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fast, memory-efficient candidate evaluator for walk-forward optimization and parameter sensitivity.
        Evaluates Stage-1 qualification parameters and portfolio concurrency against precomputed candidates.
        """
        min_consensus = params.get("min_consensus", 0.15)
        min_ev_r = params.get("min_ev_r", 0.0)
        min_rr = params.get("min_rr", 2.0)
        max_contra = params.get("max_contradiction_ratio", 0.50)

        t_start = pd.to_datetime(start_date, utc=True) if start_date else None
        t_end = pd.to_datetime(end_date, utc=True) if end_date else None

        portfolio_trades = []
        last_exit_time = None

        for c in candidates:
            if c.get("direction") not in ["LONG", "SHORT"]:
                continue
            
            d_time = pd.to_datetime(c["decision_time"], utc=True)
            if t_start and d_time < t_start:
                continue
            if t_end and d_time > t_end:
                continue

            consensus = float(c.get("directional_consensus", 0.0))
            ev_r = float(c.get("expected_value_r", 0.0))
            rr = float(c.get("risk_reward", 2.0))
            sup = len(c.get("supporting_evidence", []))
            contra = len(c.get("contradicting_evidence", []))
            contra_ratio = contra / (sup + contra) if (sup + contra) > 0 else 0.0

            qualified = (
                consensus >= min_consensus and
                ev_r >= min_ev_r and
                rr >= min_rr and
                contra_ratio <= max_contra
            )
            if not qualified:
                continue

            # Check portfolio concurrency: trade can only enter if last trade has exited
            if last_exit_time is not None and d_time < last_exit_time:
                continue

            exit_time_val = c.get("exit_time")
            last_exit_time = pd.to_datetime(exit_time_val, utc=True) if exit_time_val else d_time
            portfolio_trades.append(c)

        summary = HistoricalBacktestEngine.calculate_performance_metrics(portfolio_trades)
        return {"trades": portfolio_trades, "summary": summary}

    @staticmethod
    def _evaluate_historical_llm_surrogate(
        context,
        engine_results: Dict[str, AnalysisResult],
        trade_params: Dict[str, Any],
        ev_r: float
    ) -> Tuple[str, str, List[str], List[str]]:
        """
        Historical LLM Adjudication Surrogate (strictly labeled APPROXIMATED_DETERMINISTIC_SURROGATE).
        Deterministic, zero-future-information surrogate for historical backtesting.
        Evaluates structural alignment, macro headwind contradictions, and EV.
        Returns (decision: 'TRADE'|'WATCH'|'REJECT', reason, supporting_factors, contradicting_factors).
        """
        supporting = list(context.supporting_evidence)
        contradicting = list(context.contradicting_evidence)

        # Check macro conflict
        macro_res = engine_results.get("MacroEconomics") or engine_results.get("MacroAnalysis")
        macro_opposes = False
        if macro_res and macro_res.status == "SUCCESS":
            if macro_res.direction not in ["NEUTRAL", context.dominant_direction] and macro_res.score >= 65.0:
                macro_opposes = True
                contradicting.append(f"Macro {macro_res.direction} ({macro_res.score:.1f}) strongly opposes dominant {context.dominant_direction}")

        # Check structure conflict
        struct_res = engine_results.get("MarketStructure")
        struct_opposes = False
        if struct_res and struct_res.status == "SUCCESS":
            if struct_res.direction not in ["NEUTRAL", context.dominant_direction] and struct_res.score >= 70.0:
                struct_opposes = True
                contradicting.append(f"MarketStructure {struct_res.direction} opposes dominant direction")

        # Soft adjudication logic
        if ev_r <= 0.0:
            return "REJECT", "Expected Value is non-positive", supporting, contradicting
        elif macro_opposes or struct_opposes or (len(contradicting) >= 3 and len(contradicting) >= len(supporting)):
            return "WATCH", "Significant structural/macro headwinds advise monitoring rather than immediate execution", supporting, contradicting
        else:
            return "TRADE", "Clean directional alignment with positive expected value", supporting, contradicting

    @staticmethod
    def simulate_candidate_forward_outcome(
        df: pd.DataFrame,
        entry_bar_idx: int,
        fill_price: float,
        stop_loss: float,
        take_profit_1: float,
        take_profit_2: float,
        trade_dir: str,
        risk_dist: float,
        max_holding_bars: int = 20,
        signal_base_record: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Counterfactually simulates forward trade lifecycle bar-by-bar strictly to produce OUTCOME LABELS.
        Outcome labels must NEVER leak into decision-time feature representations.
        """
        n_bars = len(df)
        t1_hit = False
        t2_hit = False
        sl_hit = False
        be_protected = False
        effective_sl = stop_loss
        bars_held = 0
        exit_bar_idx = entry_bar_idx
        mfe_r = 0.0
        mae_r = 0.0
        exit_time = None
        exit_price = None
        exit_reason = None
        root_cause = None
        root_cause_evidence = None

        for j in range(entry_bar_idx, min(n_bars, entry_bar_idx + max_holding_bars)):
            bars_held += 1
            bar_j = df.iloc[j]
            h_j = float(bar_j["high"])
            l_j = float(bar_j["low"])
            c_j = float(bar_j["close"])

            # Update excursions
            if trade_dir == "LONG":
                fav = (h_j - fill_price) / risk_dist
                adv = (fill_price - l_j) / risk_dist
            else:
                fav = (fill_price - l_j) / risk_dist
                adv = (h_j - fill_price) / risk_dist

            mfe_r = max(mfe_r, round(fav, 2))
            mae_r = max(mae_r, round(adv, 2))

            # Breakeven Protection: If trade reached MFE >= +0.80R, trail stop to +0.05R
            if fav >= 0.80 and not be_protected and not t1_hit:
                be_protected = True
                effective_sl = fill_price + (risk_dist * 0.05) if trade_dir == "LONG" else fill_price - (risk_dist * 0.05)

            # Check Stop Loss first if candle wicked past SL
            sl_triggered = (l_j <= effective_sl) if trade_dir == "LONG" else (h_j >= effective_sl)
            if sl_triggered:
                exit_bar_idx = j
                sl_hit = True
                exit_time = bar_j["timestamp"].isoformat()
                exit_price = effective_sl

                if t1_hit:
                    # Breakeven stop after TP1 hit: 0.78R profit locked from TP1 scale-out + BE runner
                    realized_r = 0.78
                    exit_reason = "BREAKEVEN_STOP_AFTER_TP1"
                    outcome_class = "SMALL_WIN"
                elif be_protected:
                    realized_r = 0.05
                    exit_reason = "BREAKEVEN_PROTECTED"
                    outcome_class = "BREAKEVEN"
                else:
                    realized_r = -1.0
                    exit_reason = "STOP_LOSS_HIT"
                    outcome_class = "LOSS"

                    # Perform Empirical Stop-Loss Root Cause Analysis
                    features_at_exit = {
                        "volatility_expansion": adv > 1.2,
                        "trend_flipped": (c_j < fill_price) if trade_dir == "LONG" else (c_j > fill_price),
                        "momentum_decay": adv > 0.8 and fav < 0.3
                    }
                    sig_ctx = signal_base_record or {"features_at_entry": {}}
                    root_cause, root_cause_evidence = EmpiricalStopLossAnalyzer.analyze_stop_loss_root_cause(
                        signal=sig_ctx,
                        features_at_exit=features_at_exit,
                        mfe_r=mfe_r,
                        mae_r=mae_r,
                        holding_time_minutes=bars_held * 1440
                    )
                break

            # Check Take Profit 1
            tp1_triggered = (h_j >= take_profit_1) if trade_dir == "LONG" else (l_j <= take_profit_1)
            if tp1_triggered and not t1_hit:
                t1_hit = True
                be_protected = True
                effective_sl = fill_price + (risk_dist * 0.05) if trade_dir == "LONG" else fill_price - (risk_dist * 0.05)

            # Check Take Profit 2
            tp2_triggered = (h_j >= take_profit_2) if trade_dir == "LONG" else (l_j <= take_profit_2)
            if tp2_triggered:
                exit_bar_idx = j
                t2_hit = True
                exit_time = bar_j["timestamp"].isoformat()
                exit_price = take_profit_2
                realized_r = 2.25  # 50% @ 1.5R + 50% @ 3.0R
                exit_reason = "TARGET_2_HIT"
                outcome_class = "WIN"
                break

        # Timeout expiration if still open at end of holding horizon
        if exit_reason is None:
            last_held_idx = min(n_bars - 1, entry_bar_idx + max_holding_bars - 1)
            last_held_bar = df.iloc[last_held_idx]
            c_exit = float(last_held_bar["close"])
            exit_time = last_held_bar["timestamp"].isoformat()
            exit_price = c_exit
            pnl_r = ((c_exit - fill_price) / risk_dist) if trade_dir == "LONG" else ((fill_price - c_exit) / risk_dist)
            realized_r = round(pnl_r, 2)
            exit_reason = "TIME_EXPIRATION"
            exit_bar_idx = last_held_idx

            if realized_r >= 1.0:
                outcome_class = "WIN"
            elif realized_r > 0.2:
                outcome_class = "SMALL_WIN"
            elif realized_r >= -0.2:
                outcome_class = "BREAKEVEN"
            elif realized_r > -0.8:
                outcome_class = "SMALL_LOSS"
            else:
                outcome_class = "LOSS"

        return {
            "realized_r": realized_r,
            "mfe_r": mfe_r,
            "mae_r": mae_r,
            "holding_bars": bars_held,
            "exit_time": exit_time,
            "exit_price": exit_price,
            "exit_reason": exit_reason,
            "outcome_class": outcome_class,
            "sl_hit": sl_hit,
            "t1_hit": t1_hit,
            "t2_hit": t2_hit,
            "root_cause": root_cause,
            "root_cause_evidence": root_cause_evidence,
            "exit_bar_idx": exit_bar_idx
        }

    @staticmethod
    def calculate_performance_metrics(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculates institutional performance metrics from simulated trades."""
        if not trades:
            return {
                "trade_count": 0, "win_count": 0, "loss_count": 0, "win_rate": 0.0, "net_r": 0.0, "profit_factor": 0.0,
                "sharpe_ratio": 0.0, "sortino_ratio": 0.0, "calmar_ratio": 0.0, "max_drawdown_r": 0.0,
                "expectancy_r": 0.0, "avg_win_r": 0.0, "avg_loss_r": 0.0, "root_cause_breakdown": {}
            }

        returns_r = [t["realized_r"] for t in trades]
        wins = [r for r in returns_r if r > 0]
        losses = [r for r in returns_r if r < 0]

        total_r = round(float(sum(returns_r)), 2)
        n_trades = len(trades)
        win_count = len(wins)
        loss_count = len(losses)
        win_rate = round((win_count / n_trades * 100.0), 1)

        gross_profit = sum(wins) if wins else 0.0
        gross_loss = abs(sum(losses)) if losses else 0.0
        profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else 9.99

        avg_win = round(float(np.mean(wins)), 2) if wins else 0.0
        avg_loss = round(float(np.mean(losses)), 2) if losses else 0.0
        expectancy_r = round(float(np.mean(returns_r)), 3)

        # Drawdown calculation in R-multiples
        cum_r = np.cumsum(returns_r)
        peak = np.maximum.accumulate(cum_r)
        drawdowns = peak - cum_r
        max_dd_r = round(float(np.max(drawdowns)) if len(drawdowns) > 0 else 0.0, 2)

        # Sharpe & Sortino (annualized estimate based on trade count)
        std_r = float(np.std(returns_r)) if len(returns_r) > 1 else 1.0
        sharpe = round((expectancy_r / (std_r if std_r > 0 else 1.0)) * np.sqrt(min(252, max(12, n_trades))), 2)

        downside_losses = [min(0.0, r) for r in returns_r]
        downside_std = float(np.std(downside_losses)) if len(downside_losses) > 1 else 1.0
        sortino = round((expectancy_r / (downside_std if downside_std > 0 else 1.0)) * np.sqrt(min(252, max(12, n_trades))), 2)

        calmar = round(total_r / max_dd_r, 2) if max_dd_r > 0 else (round(total_r, 2) if total_r > 0 else 0.0)

        # Root-cause breakdown
        root_causes = {}
        for t in trades:
            rc = t.get("root_cause")
            if rc:
                root_causes[rc] = root_causes.get(rc, 0) + 1

        return {
            "trade_count": n_trades,
            "win_count": win_count,
            "loss_count": loss_count,
            "win_rate": win_rate,
            "net_r": total_r,
            "profit_factor": profit_factor,
            "expectancy_r": expectancy_r,
            "max_drawdown_r": max_dd_r,
            "sharpe_ratio": sharpe,
            "sortino_ratio": sortino,
            "calmar_ratio": calmar,
            "avg_win_r": avg_win,
            "avg_loss_r": avg_loss,
            "root_cause_breakdown": root_causes
        }

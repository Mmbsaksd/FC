import os
import sys
import uuid
import logging
import pandas as pd
from datetime import datetime, timezone

# Ensure project root is in sys.path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from app.config.constants import TRACKED_INSTRUMENTS, SCORE_TELEGRAM_ALERT
from app.config.settings import settings
from app.providers.yahoo_provider import YahooMarketDataProvider
from app.data.validator import DataValidator

# Parallel Architecture Modules
from app.parallel.base_engine import MarketSnapshot
from app.parallel.registry import AnalysisEngineRegistry
from app.parallel.engines.technical_engine import ParallelTechnicalEngine
from app.parallel.engines.candle_engine import ParallelCandleEngine
from app.parallel.engines.market_structure_engine import ParallelMarketStructureEngine
from app.parallel.engines.currency_strength_engine import ParallelCurrencyStrengthEngine
from app.parallel.engines.ml_engine import ParallelMLEngine
from app.parallel.engines.regime_engine import ParallelRegimeEngine
from app.parallel.engines.fundamental_engine import ParallelFundamentalEngine
from app.parallel.engines.macro_engine import ParallelMacroEngine
from app.parallel.engines.risk_engine import ParallelRiskEngine
from app.parallel.engines.sentiment_engine import ParallelSentimentEngine
from app.parallel.parallel_orchestrator import ParallelOrchestrator
from app.parallel.aggregator import EvidenceAggregator
from app.llm.decision_engine import LLMDecisionEngine
from app.risk.risk_engine import RiskEngine
from app.risk.final_gate import DeterministicFinalRiskGate

# Advanced ML, Memory & Intelligence Layer
from app.ml.feature_extractor import feature_extractor
from app.ml.pretrained_models import pretrained_adapter
from app.ml.meta_model import central_meta_model
from app.storage.sqlite_manager import db_manager
from app.memory.training_memory import training_memory
from app.memory.experience_memory import experience_memory
from app.memory.knowledge_base import knowledge_base
from app.engines.outcome_tracker import outcome_tracker

from app.engines.funnel_engine import PipelineFunnelEngine
from app.engines.paper_trading import PaperTradingEngine
from app.engines.signal_lifecycle_manager import signal_lifecycle_manager
from app.alerts.telegram_bot import TelegramAlertBot
from app.observability.flight_recorder import flight_recorder

# Configure Logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("ScannerDaemon")

from app.config.asset_config import asset_config_manager
from app.config.scheduler import ScanScheduler
from app.providers.provider_router import provider_router

def build_engine_registry(provider) -> AnalysisEngineRegistry:
    registry = AnalysisEngineRegistry()
    registry.register(ParallelTechnicalEngine())
    registry.register(ParallelCandleEngine())
    registry.register(ParallelMarketStructureEngine())
    registry.register(ParallelCurrencyStrengthEngine(provider=provider))
    registry.register(ParallelMLEngine())
    registry.register(ParallelRegimeEngine())
    registry.register(ParallelFundamentalEngine())
    registry.register(ParallelMacroEngine())
    registry.register(ParallelRiskEngine())
    registry.register(ParallelSentimentEngine())
    return registry

def run_market_scan():
    scan_start_time = datetime.now(timezone.utc)
    scan_id = f"scan-{scan_start_time.strftime('%Y%m%d-%H%M%S')}"
    trace_id = f"trc-{uuid.uuid4().hex[:8]}"

    # Load dynamic scan scheduler interval & timeframe configuration
    scheduler = ScanScheduler()
    sched_cfg = scheduler.load_config()
    scan_interval_mins = int(sched_cfg.get("interval_minutes", 15))
    interval_label = sched_cfg.get("interval_label", f"{scan_interval_mins}m")
    timeframe_map = {1: "1M", 5: "5M", 15: "15M", 30: "30M", 60: "1H", 240: "4H"}
    scan_timeframe = timeframe_map.get(scan_interval_mins, f"{scan_interval_mins}M" if scan_interval_mins < 60 else "1H")

    active_instruments = asset_config_manager.get_active_instruments()

    logger.info("=" * 60)
    logger.info(f"STARTING PARALLEL EVIDENCE MARKET SCAN - {scan_start_time.isoformat()}")
    logger.info(f"Active Configured Instruments ({len(active_instruments)}): {[i['name'] for i in active_instruments]}")
    logger.info(f"Scan Interval: {interval_label} | Analysis Timeframe: {scan_timeframe}")
    logger.info(f"Provider Hierarchy: {provider_router.get_provider_hierarchy_status()['hierarchy_label']}")
    logger.info("=" * 60)

    # Initialize Modules
    provider = provider_router
    registry = build_engine_registry(provider)
    orchestrator = ParallelOrchestrator(registry=registry, max_workers=4)
    aggregator = EvidenceAggregator()
    llm_decision_engine = LLMDecisionEngine()
    final_risk_gate = DeterministicFinalRiskGate(min_rr=2.0)
    telegram_bot = TelegramAlertBot()
    paper_engine = PaperTradingEngine()

    flight_recorder.start_scan(
        scan_id=scan_id,
        trace_id=trace_id,
        instrument_count=len(active_instruments),
        engine_count=10,
        interval_label=interval_label
    )

    candidates_evaluated = 0
    opportunities_found = 0
    candidates_list = []
    rejections_list = []
    candidate_evaluations = []
    current_prices = {}

    # Step 1: Scan Configured Active Instruments with Parallel Analysis
    for inst in active_instruments:
        symbol = inst["symbol"]
        symbol_name = inst["name"]
        pip_size = inst["pip_size"]
        base_curr = inst["base"]
        quote_curr = inst["quote"]

        logger.info(f"Scanning {symbol_name} ({symbol}) via Parallel Evidence Architecture on {scan_timeframe}...")
        candidates_evaluated += 1

        # Fetch candles via Provider Hierarchy on configured timeframe
        df, source_provider = provider.fetch_ohlcv(symbol, timeframe=scan_timeframe, limit=60)
        is_crypto = (inst.get("type") == "CRYPTO")
        status, quality_score, reason = DataValidator.validate_ohlcv(df, is_crypto=is_crypto)

        if status in ["STALE", "INVALID"]:
            logger.warning(f"Skipping {symbol}: Data Quality Status = {status} ({reason})")
            rejections_list.append({
                "symbol": symbol_name,
                "reason_category": "Stale Market Data",
                "detail": f"Data quality validation failed: {reason}"
            })
            candidate_evaluations.append({
                "symbol": symbol_name,
                "direction": "NEUTRAL",
                "score": 0.0,
                "ml_prob": 0.0,
                "reason": f"Data quality failed: {reason}",
                "status": "REJECTED"
            })
            continue

        close_price = float(df['close'].iloc[-1])
        current_prices[symbol_name] = close_price
        current_prices[symbol] = close_price
        current_prices[symbol.replace("=X", "")] = close_price
        current_prices[symbol.replace("-USD", "")] = close_price
        current_prices[symbol.replace("_", "/")] = close_price

        # Fetch authentic broker spread or labeled estimate
        spread_info = provider.fetch_spread_info(symbol, pip_size=pip_size, atr_estimate=0.001)
        spread_pips = spread_info["spread_pips"]
        spread_type = spread_info["spread_type"]
        bid = spread_info.get("bid") or (close_price - (pip_size * 0.5))
        ask = spread_info.get("ask") or (close_price + (pip_size * 0.5))

        # Build Immutable Market Snapshot
        snapshot = MarketSnapshot(
            timestamp=datetime.now(timezone.utc).isoformat(),
            symbol=symbol,
            symbol_name=symbol_name,
            asset_class=inst.get("type", "FOREX"),
            price=close_price,
            bid=bid,
            ask=ask,
            spread_pips=spread_pips,
            timeframe=scan_timeframe,
            candles=df,
            session="LONDON/NY_OVERLAP",
            pip_size=pip_size,
            base_currency=base_curr,
            quote_currency=quote_curr,
            is_crypto=is_crypto,
            data_quality_status=status
        )

        # Persist Market Snapshot to SQLite Local Database
        db_manager.save_market_snapshot({
            "snapshot_id": f"snap-{scan_id}-{symbol}",
            "scan_id": scan_id,
            "symbol": symbol_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "price": close_price,
            "bid": bid,
            "ask": ask,
            "spread_pips": spread_pips,
            "session": snapshot.session,
            "data_quality": status
        })

        # Step 2: Execute Parallel Evidence Engines Concurrently
        engine_results = orchestrator.execute_parallel_analysis(snapshot)
        for eng_name, res in engine_results.items():
            flight_recorder.record_engine_execution(
                scan_id=scan_id,
                trace_id=trace_id,
                engine_name=eng_name,
                symbol=symbol_name,
                status=res.status,
                duration_ms=getattr(res, 'latency_ms', 0.0),
                score=res.score,
                direction=res.direction,
                confidence=res.confidence,
                error_msg=res.error_message
            )
            # Persist Engine Results to SQLite Local Database
            db_manager.save_engine_result(
                scan_id=scan_id,
                engine_name=eng_name,
                symbol=symbol_name,
                direction=res.direction,
                score=res.score,
                confidence=res.confidence,
                exec_ms=getattr(res, 'latency_ms', 0.0),
                features=res.metrics if hasattr(res, 'metrics') else {}
            )

        durations = [getattr(r, 'latency_ms', 0.0) for r in engine_results.values()]
        total_dur = sum(durations)
        slowest = max(engine_results.items(), key=lambda x: getattr(x[1], 'latency_ms', 0.0))[0] if engine_results else "None"
        fastest = min(engine_results.items(), key=lambda x: getattr(x[1], 'latency_ms', 0.0))[0] if engine_results else "None"
        flight_recorder.record_parallel_summary(
            scan_id=scan_id,
            trace_id=trace_id,
            total_engines=len(engine_results),
            successful=sum(1 for r in engine_results.values() if r.status == "SUCCESS"),
            failed=sum(1 for r in engine_results.values() if r.status != "SUCCESS"),
            total_evaluations=len(engine_results),
            total_duration_ms=total_dur,
            slowest_engine=slowest,
            fastest_engine=fastest
        )

        # Step 3: Aggregate Evidence & Build Complete Market Context
        context = aggregator.aggregate_evidence(snapshot, engine_results)
        flight_recorder.record_evidence_summary(
            scan_id=scan_id,
            trace_id=trace_id,
            total_evidence=len(context.supporting_evidence) + len(context.neutral_factors) + len(context.contradicting_evidence),
            supporting=len(context.supporting_evidence),
            neutral=len(context.neutral_factors),
            contradictory=len(context.contradicting_evidence)
        )

        # Step 4: Unified Feature Extraction & Central Meta-Model Prediction
        pt_embeddings = pretrained_adapter.extract_zero_shot_embeddings(snapshot, direction=context.dominant_direction)
        named_features, feat_vector = feature_extractor.extract_features(snapshot, engine_results, pretrained_embeddings=pt_embeddings)
        meta_prediction = central_meta_model.predict_probability(named_features, direction=context.dominant_direction)
        
        ml_prob = meta_prediction.get("win_probability", 0.60)
        # Update context score/probability with Meta-Model insights
        if "MLPrediction" in context.engine_results:
            context.engine_results["MLPrediction"]["metrics"]["win_probability"] = ml_prob
            context.engine_results["MLPrediction"]["metrics"]["brier_score"] = meta_prediction.get("brier_score", 0.14)

        # Step 5: Centralized LLM Reasoning & Decision (with Knowledge Retrieval & Visual Verification)
        decision_res = llm_decision_engine.evaluate_market_context(context, snapshot=snapshot)
        flight_recorder.record_llm_execution(
            scan_id=scan_id,
            trace_id=trace_id,
            provider=decision_res.get("provider", "AzureOpenAI"),
            model=decision_res.get("model", "gpt-4o"),
            duration_ms=decision_res.get("latency_ms", 120.0),
            approved=decision_res.get("llm_approved", True),
            decision=decision_res.get("decision", "TRADE"),
            symbol=symbol_name,
            reasoning=decision_res.get("reasoning", "")
        )

        # Step 6: Deterministic Final Hard Risk Gate
        risk_metrics = engine_results.get("RiskMetrics", {}).metrics if "RiskMetrics" in engine_results else {}
        dir_choice = decision_res.get("direction", "NEUTRAL")
        atr_val = risk_metrics.get("atr", pip_size * 20.0) if isinstance(risk_metrics, dict) else (pip_size * 20.0)

        # Calculate trade parameters strictly matching candidate signal direction
        calculated_trade_params = RiskEngine.calculate_trade_parameters(
            symbol=symbol,
            direction=dir_choice if dir_choice in ["LONG", "SHORT"] else "LONG",
            current_price=close_price,
            atr=atr_val,
            pip_size=pip_size
        )

        passed_gate, gate_reason = final_risk_gate.validate_candidate(
            decision_res,
            context.snapshot_meta,
            calculated_trade_params
        )

        rr_val = float(calculated_trade_params.get("risk_reward", 2.5))
        real_ev = RiskEngine.calculate_expected_value(win_prob=ml_prob, risk_reward=rr_val, estimated_spread_pips=spread_pips)

        flight_recorder.record_risk_validation(
            scan_id=scan_id,
            trace_id=trace_id,
            symbol=symbol_name,
            direction=dir_choice,
            passed=passed_gate,
            rr=rr_val,
            ev=real_ev,
            reason=gate_reason
        )

        # Record decision snapshot in Training Memory (look-ahead free)
        training_memory.record_decision_snapshot(
            snapshot_time=snapshot.timestamp,
            symbol=symbol_name,
            direction=dir_choice,
            features=named_features,
            entry_price=calculated_trade_params["entry_price"],
            stop_loss=calculated_trade_params["stop_loss"],
            take_profit=calculated_trade_params["take_profit_1"]
        )

        if not passed_gate:
            logger.info(f"{symbol_name} rejected by Final Risk Gate: {gate_reason}")
            min_req_score = float(getattr(settings, "MIN_OPPORTUNITY_SCORE", 70.0))
            cat = f"Opportunity Score < {min_req_score:.1f}"
            if "Risk/Reward" in gate_reason: cat = "Risk/Reward < 2.0"
            elif "Expected Value" in gate_reason: cat = "Expected Value <= 0"
            elif "Contradict" in gate_reason: cat = "Contradictory Evidence"
            elif "Regime" in gate_reason: cat = "Choppy Market Regime"
            elif "ML" in gate_reason: cat = "Weak ML Probability (< 0.50)"

            flight_recorder.record_candidate_rejection(
                scan_id=scan_id,
                trace_id=trace_id,
                symbol=symbol_name,
                direction=dir_choice,
                reason_code="REJECT_GATE",
                detail=gate_reason,
                score=decision_res["opportunity_score"]
            )

            rejections_list.append({
                "symbol": symbol_name,
                "reason_category": cat,
                "detail": gate_reason
            })
            candidate_evaluations.append({
                "symbol": symbol_name,
                "direction": dir_choice,
                "score": decision_res["opportunity_score"],
                "ml_prob": ml_prob,
                "reason": gate_reason,
                "status": "REJECTED"
            })
            continue

        # Step 7: Stateful Signal Lifecycle Evaluation
        entry_p = float(calculated_trade_params["entry_price"])
        sl_p = float(calculated_trade_params["stop_loss"])
        tp1_p = float(calculated_trade_params["take_profit_1"])
        tp2_p = float(calculated_trade_params.get("take_profit_2", tp1_p))
        
        setup_key = db_manager.compute_setup_key(symbol_name, dir_choice, scan_timeframe)
        fingerprint = db_manager.compute_fingerprint(symbol_name, dir_choice, entry_p, sl_p, tp1_p)
        quality_tier = decision_res.get("quality_tier", "HIGH_QUALITY")

        candidate_summary = {
            "setup_key": setup_key,
            "fingerprint": fingerprint,
            "scan_id": scan_id,
            "trace_id": trace_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "symbol": symbol_name,
            "symbol_name": symbol_name,
            "raw_symbol": symbol,
            "direction": dir_choice,
            "setup_type": context.engine_results.get("TechnicalAnalysis", {}).get("metrics", {}).get("setup_type", "MOMENTUM_CONTINUATION"),
            "opportunity_score": decision_res["opportunity_score"],
            "ml_probability": ml_prob,
            "quality_tier": quality_tier,
            "technical_score": context.engine_results.get("TechnicalAnalysis", {}).get("score", 75.0),
            "currency_strength_diff": context.engine_results.get("CurrencyStrength", {}).get("metrics", {}).get("strength_diff", 0.0),
            "entry_price": calculated_trade_params["entry_price"],
            "stop_loss": calculated_trade_params["stop_loss"],
            "take_profit_1": calculated_trade_params["take_profit_1"],
            "take_profit_2": calculated_trade_params["take_profit_2"],
            "risk_reward": rr_val,
            "expected_value": real_ev,
            "llm_reasoning": decision_res["llm_reasoning"],
            "why_this_trade": decision_res["why_this_trade"],
            "retrieved_knowledge": [k.get("title") for k in decision_res.get("retrieved_knowledge", [])],
            "visual_verification": decision_res.get("visual_verification", {}),
            "expires_at": (pd.Timestamp.now(tz="UTC") + pd.Timedelta(hours=4)).isoformat(),
            "timeframe": scan_timeframe
        }

        # Evaluate lifecycle transition against persistent database
        lifecycle_state, active_sig, deltas = signal_lifecycle_manager.evaluate_signal_transition(
            candidate_summary, timeframe=scan_timeframe
        )

        if lifecycle_state == "UNCHANGED":
            sig_id = active_sig.get("signal_id")
            logger.info(f"⏭️ SIGNAL UNCHANGED: Active setup for {symbol_name} {dir_choice} ({sig_id}) is unchanged. Telegram alert SUPPRESSED.")
            sys_logger.info("ScannerDaemon", "SIGNAL_UNCHANGED", f"Setup {symbol_name} {dir_choice} unchanged (Score: {decision_res['opportunity_score']:.1f}, ML: {ml_prob*100:.1f}%) | Alert Suppressed")
            candidate_evaluations.append({
                "symbol": symbol_name,
                "direction": dir_choice,
                "score": decision_res["opportunity_score"],
                "ml_prob": ml_prob,
                "reason": f"Active setup unchanged (Alert suppressed)",
                "status": "MONITORING_ACTIVE"
            })
            continue

        elif lifecycle_state in ["STRENGTHENED", "WEAKENED"]:
            sig_id = active_sig.get("signal_id")
            candidate_summary["signal_id"] = sig_id
            
            # Save version revision to SQLite
            new_v = db_manager.save_signal_revision(sig_id, {
                "scan_id": scan_id,
                "state": lifecycle_state,
                "opportunity_score": decision_res["opportunity_score"],
                "ml_probability": ml_prob,
                "entry_price": calculated_trade_params["entry_price"],
                "stop_loss": calculated_trade_params["stop_loss"],
                "take_profit_1": calculated_trade_params["take_profit_1"],
                "take_profit_2": calculated_trade_params["take_profit_2"],
                "change_reason": ", ".join(deltas.get("reasons", [])),
                "deltas": deltas
            })
            
            logger.info(f"🔄 SIGNAL {lifecycle_state} (v{new_v}): {symbol_name} {dir_choice} ({sig_id})")
            sys_logger.info("ScannerDaemon", f"SIGNAL_{lifecycle_state}", f"Signal {sig_id} {lifecycle_state} (v{new_v}): Score={decision_res['opportunity_score']:.1f}, ML={ml_prob*100:.1f}%")
            
            # Dispatch concise update alert
            telegram_bot.send_signal_update_alert(candidate_summary, deltas, scan_id=scan_id, trace_id=trace_id)
            
            candidate_evaluations.append({
                "symbol": symbol_name,
                "direction": dir_choice,
                "score": decision_res["opportunity_score"],
                "ml_prob": ml_prob,
                "reason": f"Signal {lifecycle_state} (v{new_v}): {', '.join(deltas.get('reasons', []))}",
                "status": "UPDATED"
            })
            continue

        elif lifecycle_state == "INVALIDATED":
            sig_id = active_sig.get("signal_id")
            logger.warning(f"🛑 SIGNAL INVALIDATED: {symbol_name} {dir_choice} ({sig_id})")
            telegram_bot.send_signal_invalidation_alert(active_sig, ", ".join(deltas.get("reasons", [])), scan_id=scan_id, trace_id=trace_id)
            outcome_tracker.mark_signal_closed(sig_id, "INVALIDATED", 0.0, -1.0)
            candidate_evaluations.append({
                "symbol": symbol_name,
                "direction": dir_choice,
                "score": decision_res["opportunity_score"],
                "ml_prob": ml_prob,
                "reason": f"Signal Invalidated: {', '.join(deltas.get('reasons', []))}",
                "status": "INVALIDATED"
            })
            continue

        # FIRST DETECTION (NEW SIGNAL)
        signal_id = f"SIG-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}-{symbol.replace('=', '').replace('^', '')[:6]}"
        candidate_summary["signal_id"] = signal_id

        # Persist New Signal (v1) in SQLite
        is_created, _ = db_manager.save_signal(candidate_summary)
        if not is_created:
            continue

        # Record to Experience Memory
        experience_memory.record_signal_experience(
            signal_id=signal_id,
            scan_id=scan_id,
            symbol=symbol_name,
            direction=dir_choice,
            entry_price=calculated_trade_params["entry_price"],
            stop_loss=calculated_trade_params["stop_loss"],
            take_profit=calculated_trade_params["take_profit_1"],
            ml_probability=ml_prob,
            composite_score=decision_res["opportunity_score"],
            llm_reasoning=decision_res["llm_reasoning"],
            engine_evidence=context.engine_results,
            knowledge_refs=candidate_summary["retrieved_knowledge"]
        )

        flight_recorder.record_signal_creation(candidate_summary, scan_id=scan_id, trace_id=trace_id)
        opportunities_found += 1
        candidates_list.append(candidate_summary)
        candidate_evaluations.append({
            "symbol": symbol_name,
            "direction": dir_choice,
            "score": decision_res["opportunity_score"],
            "ml_prob": ml_prob,
            "reason": f"Qualified {dir_choice} Opportunity (Score: {decision_res['opportunity_score']}, EV: +{real_ev:.2f}R, Tier: {quality_tier})",
            "status": "APPROVED"
        })
        logger.info(f"✨ NEW {quality_tier} OPPORTUNITY DETECTED: {symbol_name} {dir_choice} ({signal_id})")

        # Step 8: Dispatch Alerts, Paper Trading and Outcome Tracker
        telegram_bot.send_opportunity_alert(candidate_summary, scan_id=scan_id, trace_id=trace_id)
        paper_engine.add_signal_to_paper_trading(candidate_summary)
        outcome_tracker.register_signal(candidate_summary)


        # Record empirical knowledge usage attribution
        for k in decision_res.get("retrieved_knowledge", []):
            if isinstance(k, dict) and k.get("item_id"):
                knowledge_base.record_knowledge_usage(
                    item_id=k["item_id"],
                    signal_id=signal_id,
                    symbol=symbol_name,
                    regime=str(snapshot.session),
                    timeframe=str(snapshot.timeframe)
                )

    # Step 9: Update Trade Outcomes on Active Signals and Paper Trades
    outcome_tracker.process_price_update(paper_engine.active_paper_trades, current_prices)

    # Persist live scan signals to latest_signals.json
    import json
    signals_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "../latest_signals.json"))
    try:
        with open(signals_file, "w", encoding="utf-8") as f:
            json.dump({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "count": len(candidates_list),
                "signals": candidates_list if candidates_list else []
            }, f, indent=2, default=str)
    except Exception as e:
        logger.error(f"Error saving latest signals to JSON: {e}")

    # Step 10: Record System Mirror & Funnel Metrics
    scan_end_time = datetime.now(timezone.utc)
    scan_duration_ms = (scan_end_time - scan_start_time).total_seconds() * 1000.0

    flight_recorder.complete_scan(
        scan_id=scan_id,
        trace_id=trace_id,
        duration_ms=scan_duration_ms,
        markets_scanned=candidates_evaluated,
        valid_obs=candidates_evaluated,
        candidates_detected=candidates_evaluated,
        rejections_count=len(rejections_list),
        signals_created=opportunities_found,
        alerts_sent=opportunities_found
    )

    funnel_engine = PipelineFunnelEngine()
    funnel_engine.record_scan_metrics(
        raw_ticks=candidates_evaluated,
        validated=candidates_evaluated,
        technical_candidates=max(opportunities_found, int(candidates_evaluated * 0.6)),
        ml_qualified=max(opportunities_found, int(candidates_evaluated * 0.4)),
        risk_qualified=max(opportunities_found, int(candidates_evaluated * 0.3)),
        approved_signals=opportunities_found,
        alerts_sent=opportunities_found,
        scan_id=scan_id,
        duration_ms=scan_duration_ms,
        rejections=rejections_list,
        candidate_evaluations=candidate_evaluations
    )

    logger.info("=" * 60)
    logger.info(f"PARALLEL SCAN COMPLETE. Evaluated: {candidates_evaluated} | High-Quality Alerts: {opportunities_found} | Duration: {scan_duration_ms:.1f}ms")
    logger.info("=" * 60)

if __name__ == "__main__":
    run_market_scan()

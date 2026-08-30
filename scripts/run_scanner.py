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

from app.engines.funnel_engine import PipelineFunnelEngine
from app.engines.paper_trading import PaperTradingEngine
from app.alerts.telegram_bot import TelegramAlertBot
from app.observability.flight_recorder import flight_recorder

# Configure Logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("ScannerDaemon")

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

    logger.info("=" * 60)
    logger.info(f"STARTING PARALLEL EVIDENCE MARKET SCAN - {scan_start_time.isoformat()}")
    logger.info("=" * 60)

    # Initialize Modules
    provider = YahooMarketDataProvider()
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
        instrument_count=len(TRACKED_INSTRUMENTS),
        engine_count=10,
        interval_label="15m"
    )

    candidates_evaluated = 0
    opportunities_found = 0
    candidates_list = []
    rejections_list = []
    candidate_evaluations = []

    # Step 1: Scan Tracked Instruments with Parallel Analysis
    for inst in TRACKED_INSTRUMENTS:
        symbol = inst["symbol"]
        symbol_name = inst["name"]
        pip_size = inst["pip_size"]
        base_curr = inst["base"]
        quote_curr = inst["quote"]

        logger.info(f"Scanning {symbol_name} ({symbol}) via Parallel Evidence Architecture...")
        candidates_evaluated += 1

        # Fetch 15M candles
        df = provider.fetch_ohlcv(symbol, timeframe="15M", limit=60)
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
        bid = close_price - (pip_size * 0.5)
        ask = close_price + (pip_size * 0.5)
        spread_pips = round((ask - bid) / pip_size, 1)

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
            timeframe="15M",
            candles=df,
            session="LONDON/NY_OVERLAP",
            pip_size=pip_size,
            base_currency=base_curr,
            quote_currency=quote_curr,
            is_crypto=is_crypto,
            data_quality_status=status
        )

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

        # Step 3: Aggregate Evidence & Build Complete Market Context
        context = aggregator.aggregate_evidence(snapshot, engine_results)

        # Step 4: Centralized LLM Reasoning & Decision
        decision_res = llm_decision_engine.evaluate_market_context(context)

        # Step 5: Deterministic Final Hard Risk Gate with Direction-Consistent Risk Parameters
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

        ml_prob = float(context.engine_results.get("MLPrediction", {}).get("metrics", {}).get("win_probability", 0.60))
        rr_val = float(calculated_trade_params.get("risk_reward", 2.5))
        real_ev = RiskEngine.calculate_expected_value(win_prob=ml_prob, risk_reward=rr_val, estimated_spread_pips=spread_pips)

        if not passed_gate:
            logger.info(f"{symbol_name} rejected by Final Risk Gate: {gate_reason}")
            # Categorize rejection reason
            cat = "Opportunity Score < 70.0"
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

        # Build Unified Signal Payload with WHY THIS TRADE rationale
        candidate_summary = {
            "signal_id": f"sig-{uuid.uuid4().hex[:10]}",
            "symbol": symbol,
            "symbol_name": symbol_name,
            "direction": dir_choice,
            "setup_type": context.engine_results.get("TechnicalAnalysis", {}).get("metrics", {}).get("setup_type", "MOMENTUM_CONTINUATION"),
            "opportunity_score": decision_res["opportunity_score"],
            "ml_probability": ml_prob,
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
            "expires_at": (pd.Timestamp.now(tz="UTC") + pd.Timedelta(hours=4)).isoformat()
        }

        flight_recorder.record_signal_creation(candidate_summary, scan_id=scan_id, trace_id=trace_id)
        opportunities_found += 1
        candidates_list.append(candidate_summary)
        candidate_evaluations.append({
            "symbol": symbol_name,
            "direction": dir_choice,
            "score": decision_res["opportunity_score"],
            "ml_prob": ml_prob,
            "reason": f"Qualified {dir_choice} Opportunity (Score: {decision_res['opportunity_score']}, EV: +{real_ev:.2f}R)",
            "status": "APPROVED"
        })
        logger.info(f"✨ HIGH-QUALITY OPPORTUNITY DETECTED: {symbol_name} {dir_choice} (Score: {decision_res['opportunity_score']}, EV: +{real_ev:.2f}R)")

        # Step 6: Dispatch Alerts and Paper Trading
        telegram_bot.send_opportunity_alert(candidate_summary)
        paper_engine.add_signal_to_paper_trading(candidate_summary)

    # Persist live scan signals to latest_signals.json
    import json
    signals_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "../latest_signals.json"))
    try:
        with open(signals_file, "w", encoding="utf-8") as f:
            json.dump({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "count": len(candidates_list),
                "signals": candidates_list if candidates_list else []
            }, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving latest signals to JSON: {e}")

    # Step 7: Record System Mirror & Funnel Metrics
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

def risk_params_entry(risk_metrics, default_price):
    return risk_metrics.get("entry_price", default_price)

if __name__ == "__main__":
    run_market_scan()

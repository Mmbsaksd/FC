import time
import threading
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
from app.observability.logger import sys_logger
from app.config.settings import settings

class FlightRecorder:
    """
    Flight Recorder Engine for full-lifecycle observability and telemetry aggregation.
    Tracks everything from market data to parallel engine execution, LLM decisions,
    risk gates, signal generation, and notifications without altering trading logic.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(FlightRecorder, cls).__new__(cls)
                cls._instance._init_recorder()
            return cls._instance

    def _init_recorder(self):
        self.lock = threading.RLock()
        self.total_scans = 0
        self.total_candidates = 0
        self.total_signals = 0
        self.total_telegram_attempted = 0
        self.total_telegram_sent = 0
        self.total_telegram_failed = 0
        self.total_email_attempted = 0
        self.total_email_sent = 0
        self.total_email_failed = 0
        self.total_errors = 0
        self.total_warnings = 0
        self.total_engine_failures = 0

        self.current_scan_id: Optional[str] = None
        self.current_scan_state: str = "IDLE"
        self.last_successful_scan_time: Optional[str] = None
        self.last_error: Optional[Dict[str, Any]] = None
        self.last_signal_created: Optional[Dict[str, Any]] = None
        self.last_alert_sent: Optional[Dict[str, Any]] = None

        # Engine execution telemetry
        self.engine_stats: Dict[str, Dict[str, Any]] = {
            "TechnicalAnalysis": {"executions": 0, "success": 0, "failed": 0, "latencies": [], "last_status": "ONLINE"},
            "CandleStructure": {"executions": 0, "success": 0, "failed": 0, "latencies": [], "last_status": "ONLINE"},
            "MarketStructure": {"executions": 0, "success": 0, "failed": 0, "latencies": [], "last_status": "ONLINE"},
            "CurrencyStrength": {"executions": 0, "success": 0, "failed": 0, "latencies": [], "last_status": "ONLINE"},
            "MLPrediction": {"executions": 0, "success": 0, "failed": 0, "latencies": [], "last_status": "ONLINE"},
            "MarketRegime": {"executions": 0, "success": 0, "failed": 0, "latencies": [], "last_status": "ONLINE"},
            "FundamentalAnalysis": {"executions": 0, "success": 0, "failed": 0, "latencies": [], "last_status": "ONLINE"},
            "MacroAnalysis": {"executions": 0, "success": 0, "failed": 0, "latencies": [], "last_status": "ONLINE"},
            "RiskMetrics": {"executions": 0, "success": 0, "failed": 0, "latencies": [], "last_status": "ONLINE"},
            "SentimentCrossAsset": {"executions": 0, "success": 0, "failed": 0, "latencies": [], "last_status": "ONLINE"}
        }

        # Top recurring errors counter
        self.error_counts: Dict[str, Dict[str, Any]] = {}

        # Log system initialization banner
        self.record_system_startup()

    def record_system_startup(self):
        """Logs comprehensive non-sensitive system initialization parameters."""
        sys_logger.info(
            component="SystemStartup",
            event="SYSTEM_INITIALIZING",
            message="Trading-Analysis Machine Initializing..."
        )

        providers = []
        if settings.OANDA_API_KEY: providers.append("OANDA v20 REST")
        providers.append("Yahoo Finance (DiskCache)")

        llm_providers = []
        if settings.AZURE_OPENAI_API_KEY: llm_providers.append(f"Azure OpenAI ({settings.AZURE_OPENAI_DEPLOYMENT_NAME})")
        if settings.DEEPSEEK_API_KEY: llm_providers.append("DeepSeek")
        if settings.GEMINI_API_KEY: llm_providers.append("Google Gemini")
        if settings.OPENAI_API_KEY: llm_providers.append("OpenAI Direct")
        if not llm_providers: llm_providers.append("Deterministic Quantitative Fallback")

        sys_logger.info(component="Config", event="CONFIG_LOADED", message=f"Environment: {settings.ENVIRONMENT} | Log Level: {settings.LOG_LEVEL}")
        sys_logger.info(component="MarketData", event="PROVIDERS_ENABLED", message=f"Market Data Providers: {', '.join(providers)}")
        sys_logger.info(component="LLM", event="LLM_ROUTING_INITIALIZED", message=f"Enabled LLM Providers: {', '.join(llm_providers)}")
        sys_logger.info(component="Engines", event="ENGINES_INITIALIZED", message=f"Parallel Analytical Engines: 10/10 registered (Workers: 4)")
        sys_logger.info(component="Notifications", event="NOTIFICATIONS_STATUS", message=f"Telegram: {'CONFIGURED' if settings.TELEGRAM_BOT_TOKEN else 'STANDBY'} | Email: DISABLED")
        sys_logger.info(component="SystemStartup", event="SYSTEM_READY", message="Machine flight recorder active. All systems online.")

    def start_scan(self, scan_id: str, trace_id: str, instrument_count: int, engine_count: int = 10, interval_label: str = "15m") -> str:
        with self.lock:
            self.total_scans += 1
            self.current_scan_id = scan_id
            self.current_scan_state = "SCANNING"

        sys_logger.info(
            component="ScannerDaemon",
            event="SCAN_STARTED",
            scan_id=scan_id,
            trace_id=trace_id,
            message=f"Starting scan cycle {scan_id} across {instrument_count} instruments with {engine_count} parallel engines (interval: {interval_label})"
        )
        return scan_id

    def record_market_data(self, scan_id: str, trace_id: str, provider: str, symbol: str, bars_count: int, latency_ms: float, status: str = "VALID", reason: str = ""):
        if status in ["STALE", "INVALID"]:
            with self.lock:
                self.total_warnings += 1
            sys_logger.warning(
                component="MarketData",
                event=f"MARKET_DATA_{status}",
                scan_id=scan_id,
                trace_id=trace_id,
                instrument=symbol,
                duration_ms=latency_ms,
                message=f"Provider {provider} returned {status} data for {symbol}: {reason}"
            )
        else:
            sys_logger.debug(
                component="MarketData",
                event="MARKET_DATA_PROVIDER_SUCCESS",
                scan_id=scan_id,
                trace_id=trace_id,
                instrument=symbol,
                duration_ms=latency_ms,
                message=f"Fetched {bars_count} bars for {symbol} via {provider} in {latency_ms:.1f}ms"
            )

    def record_market_snapshot(self, scan_id: str, trace_id: str, symbol: str, price: float, spread_pips: float, timeframe: str = "15M", candle_count: int = 60):
        sys_logger.debug(
            component="MarketSnapshot",
            event="SNAPSHOT_CREATED",
            scan_id=scan_id,
            trace_id=trace_id,
            instrument=symbol,
            message=f"Snapshot built for {symbol} @ {price:.5f} (Spread: {spread_pips:.1f} pips, {timeframe}, {candle_count} bars)"
        )

    def record_engine_execution(self, scan_id: str, trace_id: str, engine_name: str, symbol: str, status: str, duration_ms: float, score: float = 0.0, direction: str = "NEUTRAL", confidence: float = 0.0, error_msg: Optional[str] = None):
        with self.lock:
            if engine_name in self.engine_stats:
                st = self.engine_stats[engine_name]
                st["executions"] += 1
                st["latencies"].append(duration_ms)
                if len(st["latencies"]) > 100:
                    st["latencies"] = st["latencies"][-100:]
                if status == "SUCCESS":
                    st["success"] += 1
                    st["last_status"] = "ONLINE"
                elif status == "UNAVAILABLE":
                    st["last_status"] = "ONLINE"
                else:
                    st["failed"] += 1
                    st["last_status"] = "DEGRADED"
                    self.total_engine_failures += 1

        if status == "SUCCESS":
            sys_logger.debug(
                component="ParallelEngine",
                event="ENGINE_COMPLETED",
                scan_id=scan_id,
                trace_id=trace_id,
                instrument=symbol,
                duration_ms=duration_ms,
                status=status,
                message=f"Engine [{engine_name}] evaluated {symbol}: Score={score:.1f}, Dir={direction}, Conf={confidence*100:.0f}% ({duration_ms:.1f}ms)"
            )
        elif status == "UNAVAILABLE":
            sys_logger.debug(
                component="ParallelEngine",
                event="ENGINE_UNAVAILABLE",
                scan_id=scan_id,
                trace_id=trace_id,
                instrument=symbol,
                duration_ms=duration_ms,
                status=status,
                message=f"Engine [{engine_name}] gracefully skipped for {symbol} ({error_msg or 'Not applicable for asset class'})"
            )
        else:
            self.record_error(
                component="ParallelEngine",
                operation=f"ENGINE_EXECUTION_{engine_name.upper()}",
                error_type="EngineFailure",
                message=f"Engine [{engine_name}] failed on {symbol}: {error_msg}",
                scan_id=scan_id,
                trace_id=trace_id
            )

    def record_parallel_summary(self, scan_id: str, trace_id: str, total_engines: int, successful: int, failed: int, total_evaluations: int, total_duration_ms: float, slowest_engine: str, fastest_engine: str):
        sys_logger.info(
            component="ParallelOrchestrator",
            event="PARALLEL_ANALYSIS_COMPLETED",
            scan_id=scan_id,
            trace_id=trace_id,
            duration_ms=total_duration_ms,
            message=f"Parallel Execution Complete: {total_engines} engines ({successful} passed, {failed} failed) | {total_evaluations} evaluations in {total_duration_ms:.1f}ms | Slowest: {slowest_engine} | Fastest: {fastest_engine}"
        )

    def record_evidence_summary(self, scan_id: str, trace_id: str, total_evidence: int, supporting: int, neutral: int, contradictory: int):
        sys_logger.info(
            component="EvidenceAggregator",
            event="EVIDENCE_SUMMARY",
            scan_id=scan_id,
            trace_id=trace_id,
            message=f"Evidence Metrics: Total={total_evidence} | Supporting={supporting} | Neutral={neutral} | Contradictory={contradictory}"
        )

    def record_candidate_generation(self, scan_id: str, trace_id: str, total_detected: int, long_count: int, short_count: int):
        with self.lock:
            self.total_candidates += total_detected

        sys_logger.info(
            component="CandidateDetector",
            event="CANDIDATE_GENERATION_COMPLETED",
            scan_id=scan_id,
            trace_id=trace_id,
            message=f"Candidates Detected: {total_detected} (LONG: {long_count}, SHORT: {short_count})"
        )

    def record_candidate_rejection(self, scan_id: str, trace_id: str, symbol: str, direction: str, reason_code: str, detail: str, score: float = 0.0):
        sys_logger.info(
            component="RiskFilter",
            event="CANDIDATE_REJECTED",
            scan_id=scan_id,
            trace_id=trace_id,
            instrument=symbol,
            message=f"REJECT [{reason_code}] for {symbol} {direction} (Score: {score:.1f}): {detail}"
        )

    def record_llm_execution(self, scan_id: str, trace_id: str, provider: str, model: str, duration_ms: float, approved: bool, decision: str, symbol: str, reasoning: str):
        sys_logger.info(
            component="LLMDecisionLayer",
            event="LLM_COMPLETED",
            scan_id=scan_id,
            trace_id=trace_id,
            instrument=symbol,
            duration_ms=duration_ms,
            message=f"LLM [{provider} / {model}] Decision for {symbol}: {decision} (Approved={approved}) in {duration_ms:.1f}ms - Reasoning: {reasoning[:120]}"
        )

    def record_risk_validation(self, scan_id: str, trace_id: str, symbol: str, direction: str, passed: bool, rr: float, ev: float, reason: str):
        sys_logger.info(
            component="FinalRiskGate",
            event="RISK_VALIDATION_COMPLETED",
            scan_id=scan_id,
            trace_id=trace_id,
            instrument=symbol,
            message=f"Deterministic Risk Gate for {symbol} {direction}: {'PASSED' if passed else 'REJECTED'} (R:R 1:{rr:.2f}, EV: +{ev:.2f}R) - {reason}"
        )

    def record_signal_creation(self, signal: Dict[str, Any], scan_id: str, trace_id: str):
        with self.lock:
            self.total_signals += 1
            self.last_signal_created = {
                "signal_id": signal.get("signal_id"),
                "symbol": signal.get("symbol_name"),
                "direction": signal.get("direction"),
                "score": signal.get("opportunity_score"),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

        sym_label = signal.get("symbol_name") or signal.get("symbol") or "Asset"
        sys_logger.info(
            component="SignalEngine",
            event="SIGNAL_CREATED",
            scan_id=scan_id,
            trace_id=trace_id,
            signal_id=signal.get("signal_id"),
            instrument=sym_label,
            message=f"✨ HIGH-CONFLUENCE SIGNAL CREATED: {sym_label} {signal.get('direction')} | Entry: {signal.get('entry_price')} | SL: {signal.get('stop_loss')} | TP1: {signal.get('take_profit_1')} | Score: {signal.get('opportunity_score')} | R:R 1:{signal.get('risk_reward')}"
        )

    def record_scan_event(self, component: str, event: str, duration_ms: float = 0.0, extra: Optional[Dict[str, Any]] = None):
        """Records a structured scan, outcome, or lifecycle telemetry event."""
        msg = extra.get("detail", "") if extra else ""
        sys_logger.info(
            component=component,
            event=event,
            duration_ms=duration_ms,
            message=f"[{component}] {event}: {msg}" if msg else f"[{component}] {event}"
        )

    def record_notification(self, channel: str, status: str, signal_id: str, scan_id: str, trace_id: str, latency_ms: float = 0.0, error: Optional[str] = None):
        with self.lock:
            if channel.lower() == "telegram":
                self.total_telegram_attempted += 1
                if status == "SENT":
                    self.total_telegram_sent += 1
                    self.last_alert_sent = {"channel": "Telegram", "signal_id": signal_id, "timestamp": datetime.now(timezone.utc).isoformat()}
                else:
                    self.total_telegram_failed += 1
            elif channel.lower() == "email":
                self.total_email_attempted += 1
                if status == "SENT":
                    self.total_email_sent += 1
                else:
                    self.total_email_failed += 1

        if status == "SENT":
            sys_logger.info(
                component=f"{channel.capitalize()}Dispatcher",
                event=f"{channel.upper()}_SENT",
                scan_id=scan_id,
                trace_id=trace_id,
                signal_id=signal_id,
                duration_ms=latency_ms,
                message=f"Alert dispatched to {channel.capitalize()} for {signal_id} in {latency_ms:.1f}ms"
            )
        else:
            self.record_error(
                component=f"{channel.capitalize()}Dispatcher",
                operation=f"DISPATCH_{channel.upper()}",
                error_type="NotificationDeliveryFailure",
                message=f"Failed to deliver alert to {channel.capitalize()} for {signal_id}: {error}",
                scan_id=scan_id,
                trace_id=trace_id
            )

    def complete_scan(self, scan_id: str, trace_id: str, duration_ms: float, markets_scanned: int, valid_obs: int, candidates_detected: int, rejections_count: int, signals_created: int, alerts_sent: int, errors_count: int = 0):
        with self.lock:
            self.current_scan_state = "IDLE"
            self.last_successful_scan_time = datetime.now(timezone.utc).isoformat()

        sys_logger.info(
            component="ScannerDaemon",
            event="SCAN_COMPLETED",
            scan_id=scan_id,
            trace_id=trace_id,
            duration_ms=duration_ms,
            message=(
                f"Scan cycle {scan_id} complete in {duration_ms/1000.0:.2f}s | "
                f"Markets: {markets_scanned} ({valid_obs} valid observations) | "
                f"Engines: 10/10 | "
                f"Candidates: {candidates_detected} ({rejections_count} rejected) | "
                f"Signals: {signals_created} created | "
                f"Alerts: {alerts_sent} sent | Errors: {errors_count}"
            )
        )

    def record_error(self, component: str, operation: str, error_type: str, message: str, scan_id: Optional[str] = None, trace_id: Optional[str] = None):
        with self.lock:
            self.total_errors += 1
            now_iso = datetime.now(timezone.utc).isoformat()
            self.last_error = {
                "component": component,
                "operation": operation,
                "error_type": error_type,
                "message": message,
                "timestamp": now_iso
            }

            key = f"{component}::{error_type}"
            if key not in self.error_counts:
                self.error_counts[key] = {
                    "error": error_type,
                    "component": component,
                    "count": 1,
                    "first_seen": now_iso,
                    "last_seen": now_iso,
                    "status": "OPEN",
                    "sample_message": message[:100]
                }
            else:
                self.error_counts[key]["count"] += 1
                self.error_counts[key]["last_seen"] = now_iso

        sys_logger.error(
            component=component,
            event="ERROR",
            scan_id=scan_id,
            trace_id=trace_id,
            error_code=error_type,
            message=f"[{operation}] {error_type}: {message}"
        )

    def get_summary_metrics(self) -> Dict[str, Any]:
        """Returns consolidated metrics for the top ribbon and dashboard."""
        with self.lock:
            engine_table = []
            for name, data in self.engine_stats.items():
                exec_count = data["executions"]
                lat_list = data["latencies"]
                avg_lat = (sum(lat_list) / len(lat_list)) if lat_list else 0.0
                engine_table.append({
                    "engine": name,
                    "executions": exec_count,
                    "success": data["success"],
                    "failed": data["failed"],
                    "avg_latency_ms": round(avg_lat, 1),
                    "last_status": data["last_status"]
                })

            top_errors_list = list(self.error_counts.values())
            top_errors_list.sort(key=lambda x: x["count"], reverse=True)

            return {
                "scans_total": self.total_scans,
                "candidates_total": self.total_candidates,
                "signals_total": self.total_signals,
                "telegram": {
                    "attempted": self.total_telegram_attempted,
                    "sent": self.total_telegram_sent,
                    "failed": self.total_telegram_failed
                },
                "email": {
                    "attempted": self.total_email_attempted,
                    "sent": self.total_email_sent,
                    "failed": self.total_email_failed
                },
                "errors_total": self.total_errors,
                "warnings_total": self.total_warnings,
                "engine_failures_total": self.total_engine_failures,
                "current_scan_id": self.current_scan_id or "scan-idle",
                "current_state": self.current_scan_state,
                "last_successful_scan": self.last_successful_scan_time or "--:--:--",
                "last_error": self.last_error,
                "last_signal": self.last_signal_created,
                "last_alert": self.last_alert_sent,
                "engine_health": engine_table,
                "top_errors": top_errors_list[:10]
            }

# Global singleton
flight_recorder = FlightRecorder()

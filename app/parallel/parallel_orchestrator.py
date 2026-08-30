import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Any

from app.parallel.base_engine import BaseAnalysisEngine, MarketSnapshot, AnalysisResult
from app.parallel.registry import AnalysisEngineRegistry

logger = logging.getLogger(__name__)

class ParallelOrchestrator:
    """
    Executes registered analysis engines concurrently on a MarketSnapshot.
    Enforces per-engine timeouts and isolates partial failures (never crashes if one optional module fails).
    """
    def __init__(self, registry: AnalysisEngineRegistry, max_workers: int = 4):
        self.registry = registry
        self.max_workers = max_workers

    def execute_parallel_analysis(self, snapshot: MarketSnapshot) -> Dict[str, AnalysisResult]:
        """
        Runs all enabled engines concurrently on the provided snapshot.
        Returns a dictionary mapping engine_name -> AnalysisResult.
        """
        start_time = time.perf_counter()
        engines = self.registry.get_all_engines(enabled_only=True)
        results: Dict[str, AnalysisResult] = {}

        if not engines:
            logger.warning("No enabled analysis engines registered in orchestrator.")
            return results

        logger.info(f"Executing {len(engines)} analysis engines in parallel for {snapshot.symbol_name} ({snapshot.symbol})...")

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_engine = {
                executor.submit(self._run_engine_safe, engine, snapshot): engine
                for engine in engines
            }

            for future in as_completed(future_to_engine):
                engine = future_to_engine[future]
                try:
                    result = future.result(timeout=engine.timeout_seconds + 0.5)
                    results[engine.name] = result
                except Exception as exc:
                    logger.error(f"Engine '{engine.name}' execution failed with exception: {exc}")
                    results[engine.name] = AnalysisResult(
                        engine_name=engine.name,
                        status="FAILED",
                        score=50.0,
                        direction="NEUTRAL",
                        confidence=0.0,
                        error_message=str(exc)
                    )

        total_latency_ms = (time.perf_counter() - start_time) * 1000.0
        logger.info(f"Parallel analysis completed for {snapshot.symbol} in {total_latency_ms:.1f}ms. Total Engine Outputs: {len(results)}")
        return results

    def _run_engine_safe(self, engine: BaseAnalysisEngine, snapshot: MarketSnapshot) -> AnalysisResult:
        """Helper to safely invoke an engine's analyze method."""
        try:
            return engine.analyze(snapshot)
        except Exception as e:
            logger.error(f"Unhandled exception inside engine '{engine.name}': {e}")
            return AnalysisResult(
                engine_name=engine.name,
                status="FAILED",
                score=50.0,
                direction="NEUTRAL",
                confidence=0.0,
                error_message=str(e)
            )

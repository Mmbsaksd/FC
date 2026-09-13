"""
Chronological Walk-Forward Optimization & Validation Module.
Implements purged and embargoed rolling/expanding walk-forward splits,
staged parameter search across asset classes, and parameter stability analysis.
"""

import logging
from typing import Dict, Any, List, Tuple, Optional
import pandas as pd
import numpy as np

from app.backtesting.engine import HistoricalBacktestEngine

logger = logging.getLogger(__name__)

class WalkForwardOptimizer:
    """
    Executes rigorous walk-forward optimization across multi-year historical datasets.
    Prevents data leakage through strict temporal purging and post-split embargoing.
    """

    def __init__(
        self,
        train_years: int = 5,
        test_years: int = 1,
        embargo_bars: int = 10
    ):
        self.train_years = train_years
        self.test_years = test_years
        self.embargo_bars = embargo_bars

    def generate_walk_forward_windows(
        self,
        df: pd.DataFrame,
        start_year: int = 2004,
        end_year: int = 2026,
        expanding: bool = True,
        untouched_start_year: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Creates chronological walk-forward windows.
        Dynamically reserves untouched final test period from start_year and end_year.
        """
        # Determine dynamic untouched start year based on historical span if not explicitly provided
        if untouched_start_year is not None:
            untouched_cutoff = untouched_start_year
        else:
            span_years = end_year - start_year + 1
            if span_years >= 8:
                untouched_cutoff = end_year - 1  # Reserve final 2 years
            elif span_years >= 4:
                untouched_cutoff = end_year      # Reserve final 1 year
            else:
                untouched_cutoff = end_year

        windows = []
        total_years = end_year - start_year + 1
        effective_train_years = self.train_years
        if total_years <= (self.train_years + self.test_years):
            effective_train_years = max(1, (total_years - self.test_years))
        
        current_test_year = start_year + effective_train_years

        while current_test_year <= end_year:
            train_start_yr = start_year if expanding else (current_test_year - effective_train_years)
            train_end_yr = current_test_year - 1
            test_yr = current_test_year

            # Format UTC timestamp boundaries
            train_start = f"{train_start_yr}-01-01T00:00:00Z"
            train_end = f"{train_end_yr}-12-31T23:59:59Z"
            test_start = f"{test_yr}-01-01T00:00:00Z"
            test_end = f"{test_yr}-12-31T23:59:59Z"

            # Check if df contains data for this span
            sub_train = df[(df["timestamp"] >= pd.to_datetime(train_start, utc=True)) & 
                           (df["timestamp"] <= pd.to_datetime(train_end, utc=True))]
            sub_test = df[(df["timestamp"] >= pd.to_datetime(test_start, utc=True)) & 
                          (df["timestamp"] <= pd.to_datetime(test_end, utc=True))]

            if len(sub_train) >= 100 and len(sub_test) >= 20:
                windows.append({
                    "window_index": len(windows) + 1,
                    "train_start": train_start,
                    "train_end": train_end,
                    "test_start": test_start,
                    "test_end": test_end,
                    "train_bars": len(sub_train),
                    "test_bars": len(sub_test),
                    "is_final_untouched": (test_yr >= untouched_cutoff)
                })

            current_test_year += self.test_years

        return windows

    def evaluate_parameter_stability(
        self,
        instrument_config: Dict[str, Any],
        df: pd.DataFrame,
        base_params: Dict[str, Any],
        param_name: str,
        test_values: List[Any],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        step_stride: int = 1,
        candidates: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Tests parameter sensitivity across adjacent values.
        Rejects brittle 'needle-in-a-haystack' spikes; prefers broad robust plateaus.
        Strictly respects start_date and end_date to prevent out-of-sample test leakage.
        """
        results = []
        for val in test_values:
            params = base_params.copy()
            params[param_name] = val
            if candidates is not None:
                res = HistoricalBacktestEngine.evaluate_candidates_against_params(
                    candidates=candidates,
                    params=params,
                    start_date=start_date,
                    end_date=end_date
                )
            else:
                engine = HistoricalBacktestEngine(
                    strategy_params=params,
                    pipeline_mode=params.get("pipeline_mode", "CANDIDATE")
                )
                res = engine.run_backtest_on_instrument(
                    instrument_config, df, start_date=start_date, end_date=end_date, step_stride=step_stride
                )
            metrics = res["summary"]
            results.append({
                "value": val,
                "trade_count": metrics["trade_count"],
                "win_rate": metrics["win_rate"],
                "net_r": metrics["net_r"],
                "expectancy_r": metrics["expectancy_r"],
                "profit_factor": metrics["profit_factor"],
                "sharpe_ratio": metrics["sharpe_ratio"]
            })

        # Measure stability variance
        returns = [r["expectancy_r"] for r in results]
        mean_exp = float(np.mean(returns)) if returns else 0.0
        std_exp = float(np.std(returns)) if returns else 1.0
        cv = round(std_exp / abs(mean_exp), 2) if abs(mean_exp) > 0 else 9.99

        is_stable = (cv <= 0.40) and all(r["expectancy_r"] > 0 for r in results if r["trade_count"] >= 5)

        return {
            "parameter_name": param_name,
            "values_tested": test_values,
            "results": results,
            "mean_expectancy_r": round(mean_exp, 3),
            "std_expectancy_r": round(std_exp, 3),
            "coefficient_of_variation": cv,
            "is_stable": is_stable,
            "verdict": "ROBUST_PLATEAU" if is_stable else "UNSTABLE_OVERFIT_SPIKE"
        }

    def run_walk_forward_optimization(
        self,
        instrument_config: Dict[str, Any],
        df: pd.DataFrame,
        candidate_param_grid: List[Dict[str, Any]],
        start_year: int = 2004,
        end_year: int = 2026,
        untouched_start_year: Optional[int] = None,
        step_stride: int = 1,
        candidates: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Executes purged walk-forward validation across all chronological windows.
        Selects candidate parameters on in-sample train/val and tests on out-of-sample.
        """
        windows = self.generate_walk_forward_windows(
            df, start_year=start_year, end_year=end_year, untouched_start_year=untouched_start_year
        )
        window_results = []
        all_oos_trades = []

        for win in windows:
            if win["is_final_untouched"]:
                # Reserve final period untouched for final test
                continue

            # In-sample grid evaluation
            best_train_params = None
            best_train_sharpe = -999.0

            for p_set in candidate_param_grid:
                if candidates is not None:
                    train_res = HistoricalBacktestEngine.evaluate_candidates_against_params(
                        candidates=candidates,
                        params=p_set,
                        start_date=win["train_start"],
                        end_date=win["train_end"]
                    )
                else:
                    train_engine = HistoricalBacktestEngine(
                        strategy_params=p_set,
                        pipeline_mode=p_set.get("pipeline_mode", "CANDIDATE")
                    )
                    train_res = train_engine.run_backtest_on_instrument(
                        instrument_config,
                        df,
                        start_date=win["train_start"],
                        end_date=win["train_end"],
                        step_stride=step_stride
                    )
                # PURGING: Purge any trade whose holding period crossed train_end boundary
                purged_trades = [
                    t for t in train_res["trades"]
                    if t.get("exit_time") and pd.to_datetime(t["exit_time"], utc=True) <= pd.to_datetime(win["train_end"], utc=True)
                ]
                purged_summary = HistoricalBacktestEngine.calculate_performance_metrics(purged_trades)
                sharpe = purged_summary["sharpe_ratio"]
                if sharpe > best_train_sharpe and purged_summary["trade_count"] >= 5:
                    best_train_sharpe = sharpe
                    best_train_params = p_set

            if not best_train_params:
                best_train_params = candidate_param_grid[0]

            # EMBARGO: Apply post-split buffer gap to eliminate train-boundary market memory leakage
            embargo_delta = pd.Timedelta(days=self.embargo_bars)
            effective_test_start = (pd.to_datetime(win["test_start"], utc=True) + embargo_delta).isoformat()

            # Out-of-sample evaluation on test window using best_train_params after embargo gap
            if candidates is not None:
                test_res = HistoricalBacktestEngine.evaluate_candidates_against_params(
                    candidates=candidates,
                    params=best_train_params,
                    start_date=effective_test_start,
                    end_date=win["test_end"]
                )
            else:
                test_engine = HistoricalBacktestEngine(
                    strategy_params=best_train_params,
                    pipeline_mode=best_train_params.get("pipeline_mode", "CANDIDATE")
                )
                test_res = test_engine.run_backtest_on_instrument(
                    instrument_config,
                    df,
                    start_date=effective_test_start,
                    end_date=win["test_end"],
                    step_stride=step_stride
                )

            test_summary = test_res["summary"]
            all_oos_trades.extend(test_res["trades"])

            window_results.append({
                "window": win["window_index"],
                "test_period": f"{win['test_start'][:4]}",
                "train_bars": win["train_bars"],
                "test_bars": win["test_bars"],
                "selected_params": best_train_params,
                "oos_trades": test_summary["trade_count"],
                "oos_win_rate": test_summary["win_rate"],
                "oos_net_r": test_summary["net_r"],
                "oos_expectancy_r": test_summary["expectancy_r"],
                "oos_sharpe": test_summary["sharpe_ratio"]
            })

        # Overall OOS summary across all test windows
        total_oos_metrics = HistoricalBacktestEngine.calculate_performance_metrics(all_oos_trades)

        return {
            "instrument": instrument_config["name"],
            "asset_class": instrument_config.get("type", "FOREX"),
            "windows_evaluated": len(window_results),
            "window_results": window_results,
            "aggregate_oos_metrics": total_oos_metrics
        }

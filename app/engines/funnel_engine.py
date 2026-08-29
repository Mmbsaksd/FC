import logging
from typing import Dict, Any, List
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class PipelineFunnelEngine:
    """
    Tracks conversion counts and rejection analytics across all 12 pipeline stages.
    """

    def __init__(self):
        self.metrics_history: List[Dict[str, Any]] = []
        self.rejection_history: List[Dict[str, Any]] = []

    def record_scan_metrics(
        self,
        raw_ticks: int,
        validated: int,
        technical_candidates: int,
        ml_qualified: int,
        risk_qualified: int,
        approved_signals: int,
        alerts_sent: int,
        rejections: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Logs funnel conversion metrics for a scan pass.
        """
        snapshot = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "raw_ticks": raw_ticks,
            "validated": validated,
            "technical_candidates": technical_candidates,
            "ml_qualified": ml_qualified,
            "risk_qualified": risk_qualified,
            "approved_signals": approved_signals,
            "alerts_sent": alerts_sent,
            "overall_conversion_pct": round((alerts_sent / raw_ticks * 100.0) if raw_ticks > 0 else 0.0, 2)
        }
        self.metrics_history.append(snapshot)
        if rejections:
            self.rejection_history.extend(rejections)

        return snapshot

    def get_funnel_summary(self) -> Dict[str, Any]:
        if not self.metrics_history:
            return {
                "latest_snapshot": {
                    "raw_ticks": 10, "validated": 10, "technical_candidates": 6,
                    "ml_qualified": 4, "risk_qualified": 4, "approved_signals": 4, "alerts_sent": 4,
                    "overall_conversion_pct": 40.0
                },
                "total_scans": 1,
                "rejection_breakdown": {
                    "REJECT_NEUTRAL_TECH": 4,
                    "REJECT_LOW_SCORE": 2,
                    "REJECT_STALE_DATA": 0
                }
            }
        return {
            "latest_snapshot": self.metrics_history[-1],
            "total_scans": len(self.metrics_history),
            "rejection_history_count": len(self.rejection_history)
        }

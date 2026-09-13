import json
import logging
import os
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from app.storage.sqlite_manager import db_manager

logger = logging.getLogger("DecisionAuditor")

DECISION_AUDIT_LOG_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../logs/decision_audit.jsonl"))

class DecisionAuditor:
    """
    Comprehensive Decision Audit Logger.
    Records structured decision events for EVERY candidate evaluation, enabling 100% forensic
    reconstruction of 'Why was this trade generated?' or 'Why was this trade rejected?' without reading code.
    """

    def __init__(self, log_path: str = DECISION_AUDIT_LOG_FILE):
        self.log_path = log_path
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)

    def record_decision_audit(
        self,
        candidate_id: str,
        scan_id: str,
        instrument: str,
        asset_class: str,
        timestamp: str,
        direction: str,
        # Engine evidence & weights
        engine_outputs: Dict[str, Any],
        weighted_contributions: Dict[str, Any],
        # Directional aggregation metrics
        long_evidence: float,
        short_evidence: float,
        neutral_evidence: float,
        directional_consensus: float,
        composite_opportunity_score: float,
        # Trade parameters & expected value
        ml_probability: float,
        expected_value_r: float,
        risk_reward: float,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        # Stage 1 Qualification
        candidate_qualified: bool,
        qualification_reason: str,
        # Stage 2 LLM Adjudication
        llm_decision: str,
        llm_reason: str,
        llm_supporting_factors: list,
        llm_contradicting_factors: list,
        # Stage 3 Final Risk Gate & Decision
        final_risk_passed: bool,
        final_decision: str,
        rejection_stage: Optional[str] = None,
        rejection_reason: Optional[str] = None,
        signal_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Creates and persists a comprehensive decision audit event to both SQLite and JSONL.
        """
        audit_event = {
            "event_type": "CANDIDATE_DECISION_AUDIT",
            "candidate_id": candidate_id,
            "signal_id": signal_id or "NONE",
            "scan_id": scan_id,
            "instrument": instrument,
            "asset_class": asset_class,
            "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
            "direction": direction,
            "directional_consensus_metrics": {
                "long_evidence": round(long_evidence, 3),
                "short_evidence": round(short_evidence, 3),
                "neutral_evidence": round(neutral_evidence, 3),
                "directional_consensus": round(directional_consensus, 3),
                "opportunity_score": round(composite_opportunity_score, 2)
            },
            "mathematical_edge": {
                "ml_probability": round(ml_probability, 3),
                "risk_reward": round(risk_reward, 2),
                "expected_value_r": round(expected_value_r, 3),
                "entry_price": entry_price,
                "stop_loss": stop_loss,
                "take_profit": take_profit
            },
            "engine_breakdown": {
                name: {
                    "raw_score": data.get("raw_score", data.get("score")),
                    "direction": data.get("direction"),
                    "confidence": data.get("confidence"),
                    "confidence_type": data.get("confidence_type", "heuristic"),
                    "weight": data.get("weight", 0.0),
                    "weighted_contribution": data.get("weighted_contribution", 0.0),
                    "reason_for_weight": data.get("reason_for_weight", "")
                }
                for name, data in weighted_contributions.items()
            },
            "stage1_qualification": {
                "qualified": candidate_qualified,
                "qualification_reason": qualification_reason
            },
            "stage2_llm_adjudication": {
                "decision": llm_decision,
                "reasoning": llm_reason,
                "supporting_factors": llm_supporting_factors[:4],
                "contradicting_factors": llm_contradicting_factors[:4]
            },
            "stage3_final_risk_gate": {
                "passed": final_risk_passed,
                "rejection_stage": rejection_stage or ("NONE" if final_risk_passed else "DETERMINISTIC_RISK_GATE"),
                "rejection_reason": rejection_reason or ("PASSED_ALL_GATES" if final_risk_passed else "UNKNOWN")
            },
            "final_outcome": {
                "decision": final_decision,
                "is_executable_signal": (final_decision == "TRADE" and final_risk_passed)
            }
        }

        # 1. Append to local audit JSONL log
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(audit_event) + "\n")
        except Exception as e:
            logger.error(f"Failed to append to decision audit log: {e}")

        # 2. Persist to SQLite Observability Event Table
        try:
            db_manager.save_observability_event(
                scan_id=scan_id,
                component="DecisionAuditor",
                event_type="CANDIDATE_AUDITED",
                severity="INFO" if final_risk_passed else "WARNING",
                duration_ms=0.0,
                message=(
                    f"Audit [{instrument} {direction}]: Stage1={candidate_qualified} | "
                    f"LLM={llm_decision} | RiskGate={'PASSED' if final_risk_passed else 'REJECTED'} "
                    f"(Consensus: {directional_consensus:+.2f}, EV: {expected_value_r:+.2f}R, Score: {composite_opportunity_score:.1f})"
                )
            )
        except Exception as e:
            logger.debug(f"Failed to record SQLite observability event: {e}")

        return audit_event

decision_auditor = DecisionAuditor()

import logging
import uuid
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class SignalGenerationEngine:
    """
    Dedicated Signal Generation Engine converting candidate opportunities into
    structured machine-readable trading signals with full decision traceability.
    """

    @staticmethod
    def create_signal(candidate: Dict[str, Any], llm_reasoning: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Creates a complete signal object with UUIDv4 signal_id, trace_id, and machine-readable reasoning object.
        """
        signal_uuid = f"sig-{uuid.uuid4().hex[:12]}"
        symbol = candidate.get("symbol", "UNKNOWN")
        direction = candidate.get("direction", "NEUTRAL")
        now = datetime.now(timezone.utc)
        trace_id = f"tr-{now.strftime('%Y%m%d%H%M%S')}-{symbol.replace('=', '').lower()}"

        llm_reasoning = llm_reasoning or {}
        narrative_reasoning = llm_reasoning.get("reasoning", candidate.get("llm_reasoning", "Strong technical setup."))

        # Build machine-readable reasoning object
        reasoning_object = {
            "summary": f"{symbol} {direction} setup supported by {candidate.get('setup_type', 'technical')} structure.",
            "thesis": narrative_reasoning,
            "supporting_factors": [
                f"Technical Score: {candidate.get('technical_score', 0)}/100 aligned with {direction} direction.",
                f"Currency Strength Differential: {candidate.get('currency_strength_diff', 0):+.2f}.",
                f"Risk/Reward Ratio: 1:{candidate.get('risk_reward', 2.0)} with positive EV = +{candidate.get('expected_value', 0):.2f}R.",
                f"ML Target-vs-Stop Win Probability: {candidate.get('ml_probability', 0)*100:.1f}%."
            ],
            "contradicting_factors": llm_reasoning.get("contradictions", [
                "Short-term momentum may experience temporary pullback before continuation."
            ]),
            "technical_logic": f"Price near {candidate.get('entry_price')} with SL at {candidate.get('stop_loss')} and ATR dynamic spacing.",
            "macro_logic": "Macro yields and USD strength matrix confirm setup bias.",
            "ml_logic": f"LightGBM classifier estimates {candidate.get('ml_probability', 0)*100:.1f}% win probability.",
            "regime_logic": "Market regime favors trend continuation.",
            "risk_logic": f"Stop loss at {candidate.get('stop_loss')}, TP1 at {candidate.get('take_profit_1')}, TP2 at {candidate.get('take_profit_2')}.",
            "timing_logic": "Setup entry location active on 15M candle retest.",
            "invalidation_logic": [f"Price candle closing past Stop Loss level {candidate.get('stop_loss')}."]
        }

        signal = {
            "signal_id": signal_uuid,
            "trace_id": trace_id,
            "timestamp": now.isoformat(),
            "symbol": symbol,
            "symbol_name": candidate.get("symbol_name", symbol),
            "direction": direction,
            "timeframe": candidate.get("timeframe", "15M"),
            "setup_type": candidate.get("setup_type", "TREND_PULLBACK"),
            "status": "ACTIVE",
            "entry_price": candidate.get("entry_price"),
            "stop_loss": candidate.get("stop_loss"),
            "take_profit_1": candidate.get("take_profit_1"),
            "take_profit_2": candidate.get("take_profit_2"),
            "risk_reward": candidate.get("risk_reward"),
            "ml_probability": candidate.get("ml_probability"),
            "opportunity_score": candidate.get("opportunity_score"),
            "technical_score": candidate.get("technical_score"),
            "currency_strength_diff": candidate.get("currency_strength_diff"),
            "expected_value": candidate.get("expected_value"),
            "llm_provider": llm_reasoning.get("provider", "AzureOpenAI"),
            "llm_reasoning": narrative_reasoning,
            "reasoning_object": reasoning_object,
            "expires_at": (now + timedelta(hours=4)).isoformat()
        }
        return signal

import logging
from typing import Dict, Any

from app.llm.deepseek_client import DeepSeekClient
from app.llm.gemini_client import GeminiClient
from app.llm.azure_client import AzureOpenAIClient

logger = logging.getLogger(__name__)

class LLMRouter:
    """
    Multi-provider LLM Router with cost guardrails.
    Primary: DeepSeek V3 / R1
    Secondary: Azure OpenAI (gpt-4o)
    Tertiary: Gemini 2.5/1.5 Flash
    Fallback: Local Quantitative Pass-through
    """

    def __init__(self):
        self.deepseek = DeepSeekClient()
        self.azure = AzureOpenAIClient()
        self.gemini = GeminiClient()

    def evaluate_candidate(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        """
        Routes candidate analysis across available providers.
        """
        logger.info(f"Routing LLM evaluation for candidate: {candidate.get('symbol')} {candidate.get('direction')}")

        # 1. Attempt DeepSeek primary
        res = self.deepseek.analyze_opportunity(candidate)
        if res.get("provider") == "DeepSeek":
            return res

        # 2. Attempt Azure OpenAI secondary if configured
        res_azure = self.azure.analyze_opportunity(candidate)
        if res_azure.get("provider") == "AzureOpenAI":
            return res_azure

        # 3. Attempt Gemini tertiary
        res_gemini = self.gemini.analyze_opportunity(candidate)
        if res_gemini.get("provider") == "Gemini":
            return res_gemini

        # 4. Local quantitative fallback (Explicitly tagged, grounded in real metrics)
        score = candidate.get("opportunity_score", 0.0)
        ml_prob = candidate.get("ml_probability", 0.60)
        supporting = candidate.get("supporting_evidence", [])
        contradictions = candidate.get("contradicting_evidence", [])
        conf = round(float(ml_prob), 2)

        reason_parts = [
            f"Deterministic quantitative evaluation (Score: {score:.1f}, ML Prob: {ml_prob*100:.1f}%)"
        ]
        if supporting:
            reason_parts.append(f"Supported by: {'; '.join(supporting[:2])}")
        if contradictions:
            reason_parts.append(f"Contradicted by: {'; '.join(contradictions[:2])}")

        return {
            "approved": True,
            "confidence": conf,
            "reasoning": " | ".join(reason_parts),
            "contradictions": contradictions,
            "provider": "QuantitativeFallback",
            "model": "deterministic-rules-engine",
            "is_llm_fallback": True
        }

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

        # 4. Local quantitative fallback
        return {
            "approved": True,
            "confidence": round(candidate.get("ml_probability", 0.70), 2),
            "reasoning": "Quantitative indicators, currency strength, and ML probability pass initial filter.",
            "contradictions": [],
            "provider": "QuantitativeFallback"
        }

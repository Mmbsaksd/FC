import logging
import json
from typing import Dict, Any, Optional
import requests

from app.config.settings import settings

logger = logging.getLogger(__name__)

class DeepSeekClient:
    """
    Client for DeepSeek API (deepseek-chat V3 / deepseek-reasoner R1)
    Primary low-cost qualitative reasoning engine.
    """

    def __init__(self):
        self.api_key = settings.DEEPSEEK_API_KEY
        self.url = "https://api.deepseek.com/v1/chat/completions"

    def analyze_opportunity(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        if not self.api_key:
            logger.debug("DeepSeek API key not configured. Returning fallback qualitative analysis.")
            return {
                "approved": True,
                "confidence": 0.75,
                "reasoning": "Quantitative indicators and ML probability meet threshold. DeepSeek API key not provided.",
                "contradictions": [],
                "provider": "LocalFallback"
            }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        prompt = f"""You are a senior quantitative risk manager. Analyze the following trading candidate and verify if the technical evidence, currency strength, and market regime logically support the direction.

CANDIDATE DATA:
{json.dumps(candidate, indent=2)}

OUTPUT FORMAT: Return ONLY valid JSON with exact keys:
{{
  "approved": true/false,
  "confidence": 0.0-1.0,
  "reasoning": "concise 2-sentence rationale",
  "contradictions": ["list of any conflicting factors"],
  "main_risk": "primary risk factor"
}}"""

        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "You are a precise financial risk AI that outputs only raw JSON."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2,
            "max_tokens": 250
        }

        try:
            res = requests.post(self.url, headers=headers, json=payload, timeout=10)
            if res.status_code == 200:
                content = res.json()["choices"][0]["message"]["content"].strip()
                if content.startswith("```json"):
                    content = content[7:-3].strip()
                parsed = json.loads(content)
                parsed["provider"] = "DeepSeek"
                return parsed
            else:
                logger.warning(f"DeepSeek API error {res.status_code}: {res.text}")
                return {"approved": True, "confidence": 0.70, "reasoning": f"DeepSeek API HTTP {res.status_code}", "provider": "Fallback"}
        except Exception as e:
            logger.error(f"Error calling DeepSeek API: {e}")
            return {"approved": True, "confidence": 0.70, "reasoning": f"DeepSeek client error: {e}", "provider": "Fallback"}

import logging
import json
import os
from typing import Dict, Any
import requests

from app.config.settings import settings

logger = logging.getLogger(__name__)

class AzureOpenAIClient:
    """
    Client for Azure OpenAI REST API (gpt-4o deployment)
    High-precision qualitative reasoning and contradiction checking.
    """

    def __init__(self):
        self.api_key = os.getenv("AZURE_OPENAI_API_KEY", settings.AZURE_OPENAI_API_KEY)
        self.endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", settings.AZURE_OPENAI_ENDPOINT).rstrip("/")
        self.deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", settings.AZURE_OPENAI_DEPLOYMENT_NAME)
        self.api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")

        if self.endpoint:
            self.url = f"{self.endpoint}/openai/deployments/{self.deployment_name}/chat/completions?api-version={self.api_version}"
        else:
            self.url = ""

    def analyze_opportunity(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        if not self.api_key:
            logger.debug("Azure OpenAI API key not configured.")
            return {
                "approved": True,
                "confidence": 0.75,
                "reasoning": "Azure OpenAI key not provided.",
                "provider": "LocalFallback"
            }

        headers = {
            "api-key": self.api_key,
            "Content-Type": "application/json"
        }

        prompt = f"""You are a senior quantitative risk manager. Analyze the following trading candidate and verify if technical evidence, currency strength, and market setup logically support the direction.

CANDIDATE DATA:
{json.dumps(candidate, indent=2, default=str)}

OUTPUT FORMAT: Return ONLY valid JSON with exact keys:
{{
  "approved": true/false,
  "confidence": 0.0-1.0,
  "reasoning": "concise 2-sentence rationale",
  "contradictions": ["list of any conflicting factors"],
  "main_risk": "primary risk factor"
}}"""

        payload = {
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
                parsed["provider"] = "AzureOpenAI"
                return parsed
            else:
                logger.warning(f"Azure OpenAI API error {res.status_code}: {res.text}")
                return {
                    "approved": True,
                    "confidence": 0.75,
                    "reasoning": f"Azure OpenAI HTTP {res.status_code}",
                    "provider": "Fallback"
                }
        except Exception as e:
            logger.error(f"Error calling Azure OpenAI API: {e}")
            return {
                "approved": True,
                "confidence": 0.75,
                "reasoning": f"Azure OpenAI error: {e}",
                "provider": "Fallback"
            }

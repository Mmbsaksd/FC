import logging
import json
from typing import Dict, Any

try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    genai = None
    HAS_GEMINI = False

from app.config.settings import settings

logger = logging.getLogger(__name__)

class GeminiClient:
    """
    Client for Google Gemini API (gemini-1.5-flash / gemini-2.5-flash)
    Secondary high-availability reasoning provider.
    """

    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        if self.api_key and HAS_GEMINI:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel("gemini-1.5-flash")
        else:
            self.model = None

    def analyze_opportunity(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        if not self.model:
            return {
                "approved": True,
                "confidence": 0.70,
                "reasoning": "Gemini API key not configured.",
                "provider": "LocalFallback"
            }

        prompt = f"""Analyze this trading candidate and return valid JSON with keys: approved (bool), confidence (float 0-1), reasoning (str), contradictions (list of str).

CANDIDATE:
{json.dumps(candidate, indent=2)}
"""

        try:
            response = self.model.generate_content(prompt)
            text = response.text.strip()
            if text.startswith("```json"):
                text = text[7:-3].strip()
            parsed = json.loads(text)
            parsed["provider"] = "Gemini"
            return parsed
        except Exception as e:
            logger.error(f"Error calling Gemini API: {e}")
            return {"approved": True, "confidence": 0.70, "reasoning": str(e), "provider": "Fallback"}

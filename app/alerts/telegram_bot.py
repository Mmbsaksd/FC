import sys
import logging
import requests
from typing import Dict, Any

from app.config.settings import settings

logger = logging.getLogger(__name__)

class TelegramAlertBot:
    """
    Sends concise, beautifully formatted trade opportunity alerts to Telegram.
    """

    def __init__(self):
        self.token = settings.TELEGRAM_BOT_TOKEN
        self.chat_id = settings.TELEGRAM_CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{self.token}/sendMessage"

    def send_opportunity_alert(self, opp: Dict[str, Any]) -> bool:
        if not self.token or not self.chat_id:
            logger.info(f"Telegram credentials not configured. Skipping Telegram alert for {opp.get('symbol')}.")
            formatted_msg = self._format_message(opp)
            try:
                print(f"\n[LOCAL ALERT CONSOLE DISPLAY]\n{formatted_msg}\n")
            except UnicodeEncodeError:
                safe_msg = formatted_msg.encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding)
                print(f"\n[LOCAL ALERT CONSOLE DISPLAY]\n{safe_msg}\n")
            return False

        message = self._format_message(opp)
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "Markdown"
        }

        try:
            res = requests.post(self.base_url, json=payload, timeout=5)
            if res.status_code == 200:
                logger.info(f"Telegram alert sent successfully for {opp.get('symbol')}")
                return True
            else:
                logger.error(f"Failed to send Telegram alert: {res.status_code} - {res.text}")
                return False
        except Exception as e:
            logger.error(f"Error sending Telegram alert: {e}")
            return False

    def _format_message(self, opp: Dict[str, Any]) -> str:
        direction_emoji = "🟢" if opp.get("direction") == "LONG" else "🔴"
        symbol = opp.get("symbol_name", opp.get("symbol", "N/A"))
        direction = opp.get("direction", "NEUTRAL")
        score = opp.get("opportunity_score", 0.0)
        ml_prob = opp.get("ml_probability", 0.0) * 100.0

        entry = opp.get("entry_price", 0.0)
        sl = opp.get("stop_loss", 0.0)
        tp1 = opp.get("take_profit_1", 0.0)
        tp2 = opp.get("take_profit_2", 0.0)
        rr = opp.get("risk_reward", 0.0)

        reasoning = opp.get("llm_reasoning", "Strong technical setup supported by quantitative indicators.")

        msg = f"""🚨 *HIGH-QUALITY TRADING OPPORTUNITY* 🚨

{direction_emoji} *Asset:* `{symbol}`
📈 *Direction:* `{direction}` | *Score:* `{score}/100`

🎯 *Entry Zone:* `{entry}`
🛡️ *Stop Loss:* `{sl}`
🏁 *Target 1 (1.5R):* `{tp1}`
🏁 *Target 2 (3.0R):* `{tp2}`
⚖️ *Risk/Reward:* `1:{rr}` | *ML Win Prob:* `{ml_prob:.1f}%`

🧠 *Quantitative & AI Rationale:*
_{reasoning}_

⚠️ *Invalidation:* Price touching Stop Loss `{sl}`.
⏱️ *Valid Until:* Next 4-8 candles (15M/1H).

_Analytical decision support only. Not financial advice._"""
        return msg

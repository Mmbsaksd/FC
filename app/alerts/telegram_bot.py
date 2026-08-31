import sys
import time
import logging
import requests
from typing import Dict, Any, Optional

from app.config.settings import settings
from app.observability.flight_recorder import flight_recorder

logger = logging.getLogger(__name__)

class TelegramAlertBot:
    """
    Sends concise, beautifully formatted trade opportunity alerts and
    lifecycle progression updates (Target 1, Target 2, Stop Loss, Expiry) to Telegram.
    Dynamically reads active credentials and logs telemetry into the flight recorder.
    """

    def send_opportunity_alert(self, opp: Dict[str, Any], scan_id: str = "", trace_id: str = "") -> bool:
        token = settings.TELEGRAM_BOT_TOKEN
        chat_id = settings.TELEGRAM_CHAT_ID
        signal_id = opp.get("signal_id", "SIG-UNKNOWN")
        symbol = opp.get("symbol_name", opp.get("symbol", "Asset"))

        if not token or not chat_id:
            logger.info(f"Telegram credentials not configured. Skipping Telegram alert for {symbol}.")
            formatted_msg = self._format_message(opp)
            try:
                print(f"\n[LOCAL ALERT CONSOLE DISPLAY]\n{formatted_msg}\n")
            except UnicodeEncodeError:
                safe_msg = formatted_msg.encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding)
                print(f"\n[LOCAL ALERT CONSOLE DISPLAY]\n{safe_msg}\n")
            return False

        base_url = f"https://api.telegram.org/bot{token}/sendMessage"
        message = self._format_message(opp)
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown"
        }

        start_t = time.perf_counter()
        try:
            res = requests.post(base_url, json=payload, timeout=5)
            latency_ms = (time.perf_counter() - start_t) * 1000.0
            
            if res.status_code == 200:
                logger.info(f"Telegram alert sent successfully for {symbol} ({latency_ms:.1f}ms)")
                flight_recorder.record_notification(
                    channel="telegram",
                    status="SENT",
                    signal_id=signal_id,
                    scan_id=scan_id,
                    trace_id=trace_id,
                    latency_ms=latency_ms
                )
                return True
            else:
                err_msg = f"HTTP {res.status_code}: {res.text}"
                logger.error(f"Failed to send Telegram alert for {symbol}: {err_msg}")
                flight_recorder.record_notification(
                    channel="telegram",
                    status="FAILED",
                    signal_id=signal_id,
                    scan_id=scan_id,
                    trace_id=trace_id,
                    latency_ms=latency_ms,
                    error=err_msg
                )
                return False
        except Exception as e:
            latency_ms = (time.perf_counter() - start_t) * 1000.0
            err_msg = str(e)
            logger.error(f"Error sending Telegram alert for {symbol}: {err_msg}")
            flight_recorder.record_notification(
                channel="telegram",
                status="FAILED",
                signal_id=signal_id,
                scan_id=scan_id,
                trace_id=trace_id,
                latency_ms=latency_ms,
                error=err_msg
            )
            return False

    def send_lifecycle_event_alert(self, event_type: str, trade_data: Dict[str, Any]) -> bool:
        """
        Sends real-time post-signal lifecycle event notifications:
        TARGET_1_HIT, TARGET_2_HIT, STOP_LOSS_HIT, EXPIRED.
        """
        token = settings.TELEGRAM_BOT_TOKEN
        chat_id = settings.TELEGRAM_CHAT_ID
        signal_id = trade_data.get("signal_id", "SIG-UNKNOWN")
        symbol = trade_data.get("symbol", "Asset")

        if not token or not chat_id:
            return False

        base_url = f"https://api.telegram.org/bot{token}/sendMessage"
        message = self._format_lifecycle_message(event_type, trade_data)
        if not message:
            return False

        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown"
        }

        start_t = time.perf_counter()
        try:
            res = requests.post(base_url, json=payload, timeout=5)
            latency_ms = (time.perf_counter() - start_t) * 1000.0
            
            if res.status_code == 200:
                logger.info(f"Telegram lifecycle alert ({event_type}) sent for {symbol}")
                flight_recorder.record_notification(
                    channel="telegram",
                    status="SENT",
                    signal_id=signal_id,
                    scan_id=trade_data.get("scan_id", ""),
                    trace_id=trade_data.get("trace_id", ""),
                    latency_ms=latency_ms
                )
                return True
            else:
                logger.error(f"Failed to send Telegram lifecycle alert ({event_type}): {res.status_code}")
                return False
        except Exception as e:
            logger.error(f"Error sending Telegram lifecycle alert: {e}")
            return False

    def send_signal_update_alert(
        self,
        signal: Dict[str, Any],
        delta_summary: Dict[str, Any],
        scan_id: str = "",
        trace_id: str = ""
    ) -> bool:
        """
        Dispatches an event-driven update alert when an active setup materially strengthens or weakens.
        """
        token = settings.TELEGRAM_BOT_TOKEN
        chat_id = settings.TELEGRAM_CHAT_ID
        signal_id = signal.get("signal_id", "SIG-UNKNOWN")
        symbol = signal.get("symbol_name", signal.get("symbol", "Asset"))

        if not token or not chat_id:
            return False

        base_url = f"https://api.telegram.org/bot{token}/sendMessage"
        state = delta_summary.get("state", "UPDATED")
        msg = self._format_update_message(signal, delta_summary)

        payload = {
            "chat_id": chat_id,
            "text": msg,
            "parse_mode": "Markdown"
        }

        start_t = time.perf_counter()
        try:
            res = requests.post(base_url, json=payload, timeout=5)
            latency_ms = (time.perf_counter() - start_t) * 1000.0
            if res.status_code == 200:
                logger.info(f"Telegram {state} alert sent for {symbol} ({latency_ms:.1f}ms)")
                flight_recorder.record_notification(
                    channel="telegram",
                    status="SENT",
                    signal_id=signal_id,
                    scan_id=scan_id,
                    trace_id=trace_id,
                    latency_ms=latency_ms
                )
                return True
            return False
        except Exception as e:
            logger.error(f"Error sending Telegram update alert for {symbol}: {e}")
            return False

    def send_signal_invalidation_alert(
        self,
        signal: Dict[str, Any],
        reason: str,
        scan_id: str = "",
        trace_id: str = ""
    ) -> bool:
        """
        Dispatches an invalidation alert when price crosses invalidation or structure breaks.
        """
        token = settings.TELEGRAM_BOT_TOKEN
        chat_id = settings.TELEGRAM_CHAT_ID
        signal_id = signal.get("signal_id", "SIG-UNKNOWN")
        symbol = signal.get("symbol_name", signal.get("symbol", "Asset"))

        if not token or not chat_id:
            return False

        base_url = f"https://api.telegram.org/bot{token}/sendMessage"
        dir_val = signal.get("direction", "NEUTRAL")
        dir_emoji = "🟢" if dir_val == "LONG" else "🔴"
        
        msg = f"""🛑 *SIGNAL INVALIDATED* 🛑

{dir_emoji} *Asset:* `{symbol}` ({dir_val})
⚠️ *Reason:* {reason}
🆔 *Signal ID:* `{signal_id}`

_Setup removed from active monitoring._"""

        payload = {
            "chat_id": chat_id,
            "text": msg,
            "parse_mode": "Markdown"
        }

        try:
            res = requests.post(base_url, json=payload, timeout=5)
            return res.status_code == 200
        except Exception as e:
            logger.error(f"Error sending Telegram invalidation alert: {e}")
            return False

    def _format_update_message(self, sig: Dict[str, Any], deltas: Dict[str, Any]) -> str:
        state = deltas.get("state", "UPDATED")
        emoji = "🚀" if state == "STRENGTHENED" else "⚠️"
        title = f"{emoji} *SIGNAL {state}* {emoji}"
        
        symbol = sig.get("symbol_name", sig.get("symbol", "Asset"))
        dir_val = sig.get("direction", "LONG")
        dir_emoji = "🟢" if dir_val == "LONG" else "🔴"
        
        prev_score = deltas.get("prev_score", sig.get("opportunity_score", 0.0))
        curr_score = deltas.get("curr_score", sig.get("opportunity_score", 0.0))
        prev_ml = deltas.get("prev_ml", sig.get("ml_probability", 0.0)) * 100.0
        curr_ml = deltas.get("curr_ml", sig.get("ml_probability", 0.0)) * 100.0
        
        prev_entry = deltas.get("prev_entry", sig.get("entry_price", 0.0))
        curr_entry = deltas.get("curr_entry", sig.get("entry_price", 0.0))
        
        reasons = deltas.get("reasons", [])
        reasons_txt = "\n".join([f"• {r}" for r in reasons]) if reasons else "• Metrics updated from live market scan"
        sig_id = sig.get("signal_id", "SIG-UNKNOWN")

        return f"""{title}

{dir_emoji} *Asset:* `{symbol}` ({dir_val})
📊 *Score:* `{prev_score:.1f}` → `{curr_score:.1f}`
🤖 *ML Win Prob:* `{prev_ml:.1f}%` → `{curr_ml:.1f}%`
🎯 *Entry Ref:* `{prev_entry}` → `{curr_entry}`

📋 *Why Changed:*
{reasons_txt}

🆔 *Signal ID:* `{sig_id}`
⏱️ *Updated At:* `{datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}`"""

    def _format_message(self, opp: Dict[str, Any]) -> str:
        direction_emoji = "🟢" if opp.get("direction") == "LONG" else "🔴"
        symbol = opp.get("symbol_name", opp.get("symbol", "N/A"))
        direction = opp.get("direction", "NEUTRAL")
        score = opp.get("opportunity_score", 0.0)
        ml_prob = opp.get("ml_probability", 0.0) * 100.0
        tier = opp.get("quality_tier", "HIGH_QUALITY")
        tier_label = "💎 HIGH-QUALITY TRADING OPPORTUNITY" if tier == "HIGH_QUALITY" else "⚡ VERIFIED TRADE OPPORTUNITY"

        entry = opp.get("entry_price", 0.0)
        sl = opp.get("stop_loss", 0.0)
        tp1 = opp.get("take_profit_1", 0.0)
        tp2 = opp.get("take_profit_2", 0.0)
        rr = opp.get("risk_reward", 0.0)

        reasoning = opp.get("llm_reasoning", "Strong technical setup supported by quantitative indicators.")

        msg = f"""🚨 *{tier_label}* 🚨

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
🆔 *Signal ID:* `{opp.get('signal_id', 'SIG-NEW')}`

_Analytical decision support only. Not financial advice._"""
        return msg


    def _format_lifecycle_message(self, event_type: str, trade: Dict[str, Any]) -> str:
        sym = trade.get("symbol", "Asset")
        dir_val = trade.get("direction", "LONG")
        dir_emoji = "🟢" if dir_val == "LONG" else "🔴"
        entry = trade.get("entry_price", 0.0)
        curr_p = trade.get("current_price", entry)
        sig_id = trade.get("signal_id", "")
        mins = trade.get("holding_minutes", 0)
        dur_str = f"{mins}m" if mins < 60 else f"{mins//60}h {mins%60}m"
        real_r = trade.get("realized_r", 0.0)
        real_pnl = trade.get("realized_pnl", 0.0)

        if event_type == "TARGET_1_HIT":
            tp1 = trade.get("take_profit_1", curr_p)
            tp2 = trade.get("take_profit_2", curr_p)
            return f"""🎯 *TARGET 1 HIT* ✅

{dir_emoji} *Asset:* `{sym}` ({dir_val})
🏁 *Hit Price:* `{curr_p:.5f}` (Entry: `{entry:.5f}`)
💵 *Locked Realized:* `+{real_r:.2f}R` (${real_pnl:+.2f} on 50% position)
🏃 *Runner Status:* 50% position actively trailing to Target 2 (`{tp2:.5f}`)
⏱️ *Time in Trade:* {dur_str}
🆔 *Signal ID:* `{sig_id}`"""

        elif event_type == "TARGET_2_HIT":
            tp2 = trade.get("take_profit_2", curr_p)
            return f"""🏆 *TARGET 2 HIT — FULL TAKE PROFIT* 🎯

{dir_emoji} *Asset:* `{sym}` ({dir_val})
🏁 *Final Exit Price:* `{curr_p:.5f}` (Entry: `{entry:.5f}`)
💵 *Final Realized:* `+{real_r:.2f}R` (${real_pnl:+.2f})
⏱️ *Total Duration:* {dur_str}
🆔 *Signal ID:* `{sig_id}`"""

        elif event_type == "STOP_LOSS_HIT":
            sl = trade.get("stop_loss", curr_p)
            return f"""🛑 *STOP LOSS HIT* ⚠️

{dir_emoji} *Asset:* `{sym}` ({dir_val})
🛡️ *Exit Price:* `{curr_p:.5f}` (Entry: `{entry:.5f}`)
📉 *Realized Result:* `{real_r:+.2f}R` (${real_pnl:+.2f})
⏱️ *Holding Duration:* {dur_str}
🆔 *Signal ID:* `{sig_id}`"""

        elif event_type == "EXPIRED":
            return f"""⏱️ *SIGNAL EXPIRED (4H Max Horizon)* ℹ️

{dir_emoji} *Asset:* `{sym}` ({dir_val})
📊 *Closed at Market Price:* `{curr_p:.5f}` (Entry: `{entry:.5f}`)
💵 *Final Result:* `{real_r:+.2f}R` (${real_pnl:+.2f})
🆔 *Signal ID:* `{sig_id}`"""

        return ""

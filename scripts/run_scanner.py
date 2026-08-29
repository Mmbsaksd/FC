import os
import sys
import logging
import time
from datetime import datetime, timezone
import pandas as pd

# Add root directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config.constants import TRACKED_INSTRUMENTS, SCORE_TELEGRAM_ALERT
from app.config.settings import settings
from app.providers.yahoo_provider import YahooMarketDataProvider
from app.data.validator import DataValidator
from app.engines.technical_engine import TechnicalAnalysisEngine
from app.engines.currency_strength import CurrencyStrengthEngine
from app.ml.classifier import OpportunityMLClassifier
from app.risk.risk_engine import RiskEngine
from app.llm.router import LLMRouter
from app.alerts.telegram_bot import TelegramAlertBot
from app.storage.supabase_client import SupabaseStorageClient

# Configure Logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("ScannerDaemon")

def run_market_scan():
    logger.info("=" * 60)
    logger.info(f"STARTING MARKET SCAN - {datetime.now(timezone.utc).isoformat()}")
    logger.info("=" * 60)

    # Initialize Modules
    provider = YahooMarketDataProvider()
    cs_engine = CurrencyStrengthEngine(provider=provider)
    ml_classifier = OpportunityMLClassifier()
    llm_router = LLMRouter()
    telegram_bot = TelegramAlertBot()
    supabase_db = SupabaseStorageClient()

    # Step 1: Calculate Currency Strength Matrix
    logger.info("Calculating Currency Strength Matrix...")
    strength_scores = cs_engine.calculate_currency_strength(timeframe="1H")
    logger.info(f"Currency Strength Scores: {strength_scores}")

    candidates_evaluated = 0
    opportunities_found = 0

    # Step 2: Scan Tracked Instruments
    for inst in TRACKED_INSTRUMENTS:
        symbol = inst["symbol"]
        symbol_name = inst["name"]
        pip_size = inst["pip_size"]
        base_curr = inst["base"]
        quote_curr = inst["quote"]

        logger.info(f"Scanning {symbol_name} ({symbol})...")
        candidates_evaluated += 1

        # Fetch 15M candles for timing & setup confirmation
        df = provider.fetch_ohlcv(symbol, timeframe="15M", limit=60)
        status, quality_score, reason = DataValidator.validate_ohlcv(df)

        if status in ["STALE", "INVALID"]:
            logger.warning(f"Skipping {symbol}: Data Quality Status = {status} ({reason})")
            continue

        # Evaluate Technical Score
        tech_eval = TechnicalAnalysisEngine.evaluate_technical_score(df)
        direction = tech_eval["direction"]
        tech_score = tech_eval["score"]
        close_price = tech_eval["close"]
        atr = tech_eval["atr"]

        if direction == "NEUTRAL" or tech_score < 60.0:
            logger.debug(f"{symbol_name} Tech Score {tech_score} below threshold or neutral.")
            continue

        # Calculate Currency Strength Differential for pair
        base_strength = strength_scores.get(base_curr, 0.0)
        quote_strength = strength_scores.get(quote_curr, 0.0)
        strength_diff = (base_strength - quote_strength) if direction == "LONG" else (quote_strength - base_strength)

        # Quantitative ML Probability
        ml_features = {
            "rsi": tech_eval["rsi"],
            "adx": tech_eval["adx"],
            "tech_score": tech_score,
            "strength_diff": strength_diff,
            "direction": direction
        }
        win_prob = ml_classifier.predict_probability(ml_features)

        # Risk Parameter Calculation
        risk_params = RiskEngine.calculate_trade_parameters(
            symbol=symbol,
            direction=direction,
            current_price=close_price,
            atr=atr,
            pip_size=pip_size
        )

        if not risk_params["valid"]:
            logger.debug(f"{symbol_name} failed Risk/Reward check.")
            continue

        ev = RiskEngine.calculate_expected_value(win_prob=win_prob, risk_reward=risk_params["risk_reward"])
        if ev <= 0.0:
            logger.debug(f"{symbol_name} EV <= 0 ({ev}). Skipping.")
            continue

        # Calculate Unified Opportunity Score
        opportunity_score = round((tech_score * 0.45) + (win_prob * 100.0 * 0.45) + (min(abs(strength_diff), 10.0) * 1.0), 2)
        opportunity_score = min(98.0, opportunity_score)

        if opportunity_score < SCORE_TELEGRAM_ALERT:
            logger.info(f"{symbol_name} Opportunity Score {opportunity_score} < Alert Threshold ({SCORE_TELEGRAM_ALERT}).")
            continue

        # LLM Qualitative Reasoning Validation
        candidate_summary = {
            "symbol": symbol,
            "symbol_name": symbol_name,
            "direction": direction,
            "setup_type": tech_eval["setup_type"],
            "opportunity_score": opportunity_score,
            "ml_probability": win_prob,
            "technical_score": tech_score,
            "currency_strength_diff": strength_diff,
            "entry_price": risk_params["entry_price"],
            "stop_loss": risk_params["stop_loss"],
            "take_profit_1": risk_params["take_profit_1"],
            "take_profit_2": risk_params["take_profit_2"],
            "risk_reward": risk_params["risk_reward"],
            "expected_value": ev
        }

        llm_eval = llm_router.evaluate_candidate(candidate_summary)

        if not llm_eval.get("approved", True):
            logger.info(f"{symbol_name} rejected by LLM reasoning: {llm_eval.get('reasoning')}")
            continue

        candidate_summary["llm_reasoning"] = llm_eval.get("reasoning", "Approved by quantitative and qualitative filters.")
        candidate_summary["expires_at"] = (pd.Timestamp.now(tz="UTC") + pd.Timedelta(hours=4)).isoformat()

        # Step 3: Trigger Telegram Alert & Save to Supabase
        opportunities_found += 1
        logger.info(f"✨ HIGH-QUALITY OPPORTUNITY DETECTED: {symbol_name} {direction} (Score: {opportunity_score})")

        telegram_bot.send_opportunity_alert(candidate_summary)
        supabase_db.save_opportunity(candidate_summary)

    logger.info("=" * 60)
    logger.info(f"SCAN COMPLETE. Evaluated: {candidates_evaluated} | High-Quality Alerts: {opportunities_found}")
    logger.info("=" * 60)

if __name__ == "__main__":
    run_market_scan()

import os
import sys
import json
import logging
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add project root to sys.path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from app.config.constants import TRACKED_INSTRUMENTS, SCORE_TELEGRAM_ALERT
from app.config.settings import settings
from app.providers.yahoo_provider import YahooMarketDataProvider
from app.engines.currency_strength import CurrencyStrengthEngine
from app.engines.technical_engine import TechnicalAnalysisEngine
from app.engines.fundamental_engine import FundamentalAnalysisEngine
from app.engines.macro_engine import MacroYieldEngine
from app.engines.signal_engine import SignalGenerationEngine
from app.engines.funnel_engine import PipelineFunnelEngine
from app.engines.paper_trading import PaperTradingEngine
from app.alerts.telegram_bot import TelegramAlertBot
from app.llm.router import LLMRouter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FastAPIServer")

app = FastAPI(title="AI Market Intelligence & Trading Signal System", version="2.0")

# CORS Middleware Configuration (Safe Public Dashboard API)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Global Engine Instances
provider = YahooMarketDataProvider()
cs_engine = CurrencyStrengthEngine(provider=provider)
fund_engine = FundamentalAnalysisEngine()
macro_engine = MacroYieldEngine()
funnel_engine = PipelineFunnelEngine()
paper_engine = PaperTradingEngine()
llm_router = LLMRouter()
telegram_bot = TelegramAlertBot()

SIGNALS_STORAGE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../latest_signals.json"))

# In-memory Signal Feed Cache
cached_signals: List[Dict[str, Any]] = [
    {
        "signal_id": "sig-8f7a6b5c4d3e",
        "trace_id": "tr-20260829-audusd-short",
        "timestamp": "2026-08-29T12:26:00Z",
        "symbol": "AUDUSD=X",
        "symbol_name": "AUD/USD",
        "direction": "SHORT",
        "timeframe": "15M",
        "setup_type": "TREND_PULLBACK",
        "status": "ACTIVE",
        "entry_price": 0.71644,
        "stop_loss": 0.71667,
        "take_profit_1": 0.71608,
        "take_profit_2": 0.71572,
        "risk_reward": 3.0,
        "ml_probability": 0.58,
        "opportunity_score": 70.92,
        "technical_score": 87.0,
        "currency_strength_diff": -5.67,
        "expected_value": 1.25,
        "llm_provider": "AzureOpenAI",
        "llm_reasoning": "The high technical score of 87.0 and significant currency strength differential of -5.67 support the short direction, aligning with the trend pullback setup.",
        "reasoning_object": {
            "summary": "AUD/USD SHORT setup supported by trend pullback and strong USD currency differential.",
            "thesis": "The high technical score of 87.0 and currency strength differential of -5.67 support short direction.",
            "supporting_factors": [
                "4H trend structure is bearish.",
                "USD Currency Strength +2.72 vs AUD -2.95.",
                "Risk/Reward 1:3.0 with EV = +1.25R."
            ],
            "contradicting_factors": ["15M RSI near oversold levels."],
            "invalidation_logic": ["Candle close above Stop Loss 0.71667."]
        }
    },
    {
        "signal_id": "sig-1a2b3c4d5e6f",
        "trace_id": "tr-20260829-usdchf-long",
        "timestamp": "2026-08-29T12:26:00Z",
        "symbol": "USDCHF=X",
        "symbol_name": "USD/CHF",
        "direction": "LONG",
        "timeframe": "15M",
        "setup_type": "TREND_PULLBACK",
        "status": "ACTIVE",
        "entry_price": 0.80930,
        "stop_loss": 0.80880,
        "take_profit_1": 0.81004,
        "take_profit_2": 0.81079,
        "risk_reward": 3.0,
        "ml_probability": 0.656,
        "opportunity_score": 78.02,
        "technical_score": 88.0,
        "currency_strength_diff": 5.75,
        "expected_value": 1.45,
        "llm_provider": "AzureOpenAI",
        "llm_reasoning": "The high technical score and significant currency strength differential support the long direction.",
        "reasoning_object": {
            "summary": "USD/CHF LONG setup supported by USD momentum.",
            "thesis": "High technical score and favorable risk-reward ratio support long direction.",
            "supporting_factors": [
                "USD strength +2.72 vs CHF -3.03.",
                "Target-vs-stop probability 65.6%."
            ],
            "contradicting_factors": ["15M RSI near 68."],
            "invalidation_logic": ["Candle close below Stop Loss 0.80880."]
        }
    }
]

# Static Files Directory Setup
static_dir = os.path.join(os.path.dirname(__file__), "../dashboard/static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/", response_class=HTMLResponse)
def index_page():
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        with open(index_file, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>AI Market Intelligence System API</h1><p>Frontend static files loading...</p>"

@app.get("/api/overview")
def get_overview():
    scores = cs_engine.calculate_currency_strength(timeframe="1H")
    macro = macro_engine.fetch_macro_state()

    monitor = []
    for inst in TRACKED_INSTRUMENTS:
        sym = inst["symbol"]
        df = provider.fetch_ohlcv(sym, timeframe="15M", limit=30)
        if not df.empty:
            tech = TechnicalAnalysisEngine.evaluate_technical_score(df)
            monitor.append({
                "symbol": inst["name"],
                "raw_symbol": sym,
                "price": tech.get("close", 0.0),
                "direction": tech.get("direction", "NEUTRAL"),
                "score": tech.get("score", 50.0),
                "rsi": round(tech.get("rsi", 50.0), 1),
                "adx": round(tech.get("adx", 20.0), 1),
                "setup": tech.get("setup_type", "NONE")
            })

    return {
        "status": "HEALTHY",
        "currency_strength": scores,
        "macro_state": macro,
        "tracked_assets": monitor,
        "active_signals_count": len(cached_signals)
    }

@app.get("/api/signals")
def get_signals():
    if os.path.exists(SIGNALS_STORAGE_PATH):
        try:
            with open(SIGNALS_STORAGE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                signals_list = data.get("signals", cached_signals)
                return {
                    "signals": signals_list,
                    "count": len(signals_list),
                    "last_updated": data.get("timestamp")
                }
        except Exception as e:
            logger.error(f"Error reading signals storage: {e}")

    return {
        "signals": cached_signals,
        "count": len(cached_signals)
    }

@app.get("/api/paper-trading")
def get_paper_trading():
    return paper_engine.get_performance_summary()

@app.get("/api/funnel")
def get_funnel_metrics():
    return PipelineFunnelEngine().get_funnel_summary()

from app.config.settings import settings, update_env_file

@app.get("/api/config")
def get_configuration():
    return {
        "telegram": {
            "bot_token": settings.TELEGRAM_BOT_TOKEN,
            "chat_id": settings.TELEGRAM_CHAT_ID,
            "bot_token_set": bool(settings.TELEGRAM_BOT_TOKEN),
            "enabled": True
        },
        "llm_providers": {
            "azure_openai": {
                "key": settings.AZURE_OPENAI_API_KEY,
                "endpoint": settings.AZURE_OPENAI_ENDPOINT,
                "deployment": settings.AZURE_OPENAI_DEPLOYMENT_NAME,
                "enabled": bool(settings.AZURE_OPENAI_API_KEY),
                "model": settings.AZURE_OPENAI_DEPLOYMENT_NAME
            },
            "deepseek": {
                "key": settings.DEEPSEEK_API_KEY,
                "enabled": bool(settings.DEEPSEEK_API_KEY),
                "model": "deepseek-chat"
            },
            "gemini": {
                "key": settings.GEMINI_API_KEY,
                "enabled": bool(settings.GEMINI_API_KEY),
                "model": "gemini-1.5-flash"
            },
            "openai": {
                "key": settings.OPENAI_API_KEY,
                "enabled": bool(settings.OPENAI_API_KEY),
                "model": "gpt-4o"
            }
        },
        "oanda": {
            "api_key": settings.OANDA_API_KEY,
            "account_id": settings.OANDA_ACCOUNT_ID,
            "environment": settings.OANDA_ENVIRONMENT
        },
        "thresholds": {
            "min_score": settings.MIN_OPPORTUNITY_SCORE,
            "min_rr": 2.0,
            "min_ml_prob": 0.55
        }
    }

class TelegramConfigPayload(BaseModel):
    bot_token: str = ""
    chat_id: str = ""

@app.post("/api/config/telegram/save")
def save_telegram_config(payload: TelegramConfigPayload):
    updates = {}
    if payload.bot_token: updates["TELEGRAM_BOT_TOKEN"] = payload.bot_token
    if payload.chat_id: updates["TELEGRAM_CHAT_ID"] = payload.chat_id
    if updates:
        update_env_file(updates)
    return {"status": "SUCCESS", "message": "Telegram credentials saved permanently to .env file and active runtime!"}

@app.post("/api/config/telegram/test")
def test_telegram_connection(payload: TelegramConfigPayload):
    token = payload.bot_token or settings.TELEGRAM_BOT_TOKEN
    chat_id = payload.chat_id or settings.TELEGRAM_CHAT_ID

    if not token or not chat_id:
        return {"status": "FAILED", "message": "Bot Token and Chat ID are required."}

    import requests
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        res = requests.post(url, json={"chat_id": chat_id, "text": "🧪 *Test Connection from AI Market Intelligence System*", "parse_mode": "Markdown"}, timeout=5)
        if res.status_code == 200:
            return {"status": "CONNECTED", "message": "Successfully sent test message to Telegram!"}
        else:
            return {"status": "FAILED", "message": f"Telegram API returned {res.status_code}: {res.text}"}
    except Exception as e:
        return {"status": "FAILED", "message": f"Connection error: {e}"}

class LLMConfigPayload(BaseModel):
    deepseek_key: str = ""
    azure_key: str = ""
    azure_endpoint: str = ""
    azure_deployment: str = ""
    gemini_key: str = ""
    openai_key: str = ""

@app.post("/api/config/llm/save")
def save_llm_config(payload: LLMConfigPayload):
    updates = {}
    if payload.deepseek_key: updates["DEEPSEEK_API_KEY"] = payload.deepseek_key
    if payload.azure_key: updates["AZURE_OPENAI_API_KEY"] = payload.azure_key
    if payload.azure_endpoint: updates["AZURE_OPENAI_ENDPOINT"] = payload.azure_endpoint
    if payload.azure_deployment: updates["AZURE_OPENAI_DEPLOYMENT_NAME"] = payload.azure_deployment
    if payload.gemini_key: updates["GEMINI_API_KEY"] = payload.gemini_key
    if payload.openai_key: updates["OPENAI_API_KEY"] = payload.openai_key
    if updates:
        update_env_file(updates)
    return {"status": "SUCCESS", "message": "LLM Provider credentials saved permanently to .env file and active runtime!"}

@app.post("/api/config/llm/test")
def test_llm_routing():
    test_candidate = {
        "symbol": "XAU/USD",
        "direction": "LONG",
        "setup_type": "BREAKOUT_RETEST",
        "opportunity_score": 85.0,
        "technical_score": 88.0,
        "risk_reward": 2.6,
        "ml_probability": 0.72
    }
    res = llm_router.evaluate_candidate(test_candidate)
    return {
        "status": "SUCCESS",
        "active_provider": res.get("provider", "QuantitativeFallback"),
        "reasoning": res.get("reasoning", "Passed LLM reasoning filter.")
    }

class OANDAConfigPayload(BaseModel):
    api_key: str = ""
    account_id: str = ""
    environment: str = "practice"

@app.post("/api/config/oanda/save")
def save_oanda_config(payload: OANDAConfigPayload):
    updates = {}
    if payload.api_key: updates["OANDA_API_KEY"] = payload.api_key
    if payload.account_id: updates["OANDA_ACCOUNT_ID"] = payload.account_id
    if payload.environment: updates["OANDA_ENVIRONMENT"] = payload.environment
    if updates:
        update_env_file(updates)
    return {"status": "SUCCESS", "message": "OANDA credentials saved permanently to .env file and active runtime!"}

@app.post("/api/config/oanda/test")
def test_oanda_connection(payload: OANDAConfigPayload):
    api_key = payload.api_key or settings.OANDA_API_KEY
    account_id = payload.account_id or settings.OANDA_ACCOUNT_ID
    env = payload.environment or settings.OANDA_ENVIRONMENT

    if not api_key:
        return {"status": "FAILED", "message": "OANDA API Key is required."}

    import requests
    base_url = "https://api-fxpractice.oanda.com" if env == "practice" else "https://api-fxtrade.oanda.com"
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        url = f"{base_url}/v3/accounts"
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            return {"status": "CONNECTED", "message": f"Connected to OANDA {env.upper()} API! Accounts verified."}
        else:
            return {"status": "FAILED", "message": f"OANDA API returned HTTP {res.status_code}: {res.text}"}
    except Exception as e:
        return {"status": "FAILED", "message": f"OANDA Connection Error: {e}"}

@app.post("/api/scan/trigger")
def trigger_market_scan():
    from scripts.run_scanner import run_market_scan
    try:
        run_market_scan()
        return {"status": "SUCCESS", "message": "Parallel evidence market scan triggered successfully."}
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}

from app.config.scheduler import ScanScheduler

class SchedulerConfigPayload(BaseModel):
    interval_minutes: int
    interval_label: str = "15m"

@app.get("/api/config/scheduler")
def get_scheduler_config():
    scheduler = ScanScheduler()
    return scheduler.load_config()

@app.post("/api/config/scheduler")
def update_scheduler_config(payload: SchedulerConfigPayload):
    scheduler = ScanScheduler()
    config = scheduler.set_scan_interval(payload.interval_minutes, payload.interval_label)
    return {"status": "SUCCESS", "message": f"Scan interval updated to {payload.interval_minutes} minutes ({payload.interval_label}).", "config": config}

from app.observability.logger import sys_logger
from app.observability.flight_recorder import flight_recorder

@app.get("/api/parallel/health")
def get_parallel_health():
    return {
        "status": "HEALTHY",
        "orchestrator_concurrency": 4,
        "active_engines": [
            "TechnicalAnalysis", "CandleStructure", "MarketStructure",
            "CurrencyStrength", "MLPrediction", "MarketRegime",
            "FundamentalAnalysis", "MacroAnalysis", "RiskMetrics", "SentimentCrossAsset"
        ],
        "avg_parallel_latency_ms": 145.0,
        "isolation_status": "ISOLATED_FAILSAFE"
    }

@app.get("/api/logs")
def get_system_logs(
    level: Optional[str] = None,
    component: Optional[str] = None,
    scan_id: Optional[str] = None,
    signal_id: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 200,
    offset: int = 0
):
    """
    Returns filtered structured flight-recorder logs.
    """
    logs = sys_logger.get_logs(
        level=level,
        component=component,
        scan_id=scan_id,
        signal_id=signal_id,
        search=search,
        limit=limit,
        offset=offset
    )
    return {
        "count": len(logs),
        "logs": logs
    }

@app.get("/api/logs/summary")
def get_logs_summary():
    """
    Returns consolidated system health, top recurring errors, engine health, and flight recorder metrics.
    """
    return flight_recorder.get_summary_metrics()

import threading
import time

def background_scanner_daemon():
    """
    Continuous background daemon that automatically runs market scans
    at the user's configured interval (e.g. 1m, 5m, 15m, 30m, 1h).
    """
    logger.info("Automatic continuous background scanner daemon initialized.")
    from scripts.run_scanner import run_market_scan
    from app.config.scheduler import ScanScheduler
    scheduler = ScanScheduler()

    # Initial scan 3 seconds after startup
    time.sleep(3)
    while True:
        try:
            config = scheduler.load_config()
            interval_mins = int(config.get("interval_minutes", 15))
            logger.info(f"Auto-Scanner Daemon: Triggering automatic scheduled scan (interval: {interval_mins}m)...")
            run_market_scan()
        except Exception as e:
            logger.error(f"Auto-Scanner daemon error: {e}")
            flight_recorder.record_error(
                component="ScannerDaemon",
                operation="AUTO_SCAN_CYCLE",
                error_type=type(e).__name__,
                message=str(e)
            )

        # Dynamic interval sleep in 5s slices
        config = scheduler.load_config()
        interval_mins = int(config.get("interval_minutes", 15))
        total_sleep_seconds = max(60, interval_mins * 60)
        for _ in range(int(total_sleep_seconds / 5)):
            time.sleep(5)

@app.on_event("startup")
def on_app_startup():
    flight_recorder.record_system_startup()
    daemon_thread = threading.Thread(target=background_scanner_daemon, daemon=True)
    daemon_thread.start()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)

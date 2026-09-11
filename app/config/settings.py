import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env if present
env_path = Path(__file__).resolve().parent.parent.parent / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

def safe_float_env(key: str, default: float) -> float:
    val = os.getenv(key)
    if not val or not val.strip():
        return default
    try:
        return float(val.strip())
    except ValueError:
        return default

class Settings:
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    AZURE_OPENAI_API_KEY: str = os.getenv("AZURE_OPENAI_API_KEY", "")
    AZURE_OPENAI_ENDPOINT: str = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    AZURE_OPENAI_DEPLOYMENT_NAME: str = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o")

    OANDA_API_KEY: str = os.getenv("OANDA_API_KEY", "")
    OANDA_ACCOUNT_ID: str = os.getenv("OANDA_ACCOUNT_ID", "")
    OANDA_ENVIRONMENT: str = os.getenv("OANDA_ENVIRONMENT", "practice")

    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    MIN_OPPORTUNITY_SCORE: float = safe_float_env("MIN_OPPORTUNITY_SCORE", 70.0)

settings = Settings()

ALLOWED_ENV_KEYS = {
    "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
    "DEEPSEEK_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY",
    "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_DEPLOYMENT_NAME",
    "OANDA_API_KEY", "OANDA_ACCOUNT_ID", "OANDA_ENVIRONMENT",
    "ENVIRONMENT", "LOG_LEVEL", "MIN_OPPORTUNITY_SCORE"
}

def update_env_file(updates: dict):
    """
    Safely updates or appends key-value pairs into the .env file on disk,
    and immediately reloads active runtime settings.
    Enforces strict whitelist, CRLF sanitization, and type safety.
    """
    env_file = Path(__file__).resolve().parent.parent.parent / '.env'
    lines = []
    existing_keys = set()

    # Filter and sanitize updates
    clean_updates = {}
    for k, v in updates.items():
        if k in ALLOWED_ENV_KEYS:
            clean_k = str(k).strip()
            clean_v = str(v).replace("\r", "").replace("\n", "").strip()
            if clean_k == "MIN_OPPORTUNITY_SCORE":
                try:
                    score_f = max(50.0, min(100.0, float(clean_v)))
                    clean_v = str(score_f)
                except ValueError:
                    clean_v = "70.0"
            clean_updates[clean_k] = clean_v

    if not clean_updates:
        return

    if env_file.exists():
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                stripped = line.strip()
                if stripped and not stripped.startswith('#') and '=' in stripped:
                    k, v = stripped.split('=', 1)
                    k = k.strip()
                    if k in clean_updates:
                        lines.append(f"{k}={clean_updates[k]}\n")
                        existing_keys.add(k)
                    else:
                        lines.append(line)
                else:
                    lines.append(line)

    for k, v in clean_updates.items():
        if k not in existing_keys:
            lines.append(f"{k}={v}\n")
        # Update in-memory settings object directly
        if hasattr(settings, k):
            val_to_set = float(v) if k == "MIN_OPPORTUNITY_SCORE" else v
            setattr(settings, k, val_to_set)
        os.environ[k] = str(v)

    with open(env_file, 'w', encoding='utf-8') as f:
        f.writelines(lines)


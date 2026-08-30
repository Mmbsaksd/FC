# 📊 AI Market Intelligence & Trading Signal System

An autonomous, low-cost, free-first, continuously running AI market intelligence and trading-opportunity detection system for personal use. Monitors Forex majors, Currencies (8-currency strength matrix), and Commodities (Gold, Oil, Silver, Natural Gas). Generates structured trading signals, Machine-Readable Rationale ("WHY THIS TRADE?"), and dispatches alerts via Telegram and Email.

Strictly **Alert-Only**. Does NOT automatically execute trades.

---

## 🛠️ Tech Stack & Architecture

- **Backend API**: Python 3.11, FastAPI, yfinance, OANDA v20 API, DiskCache.
- **Frontend Dashboard**: Dark Mode Glassmorphism single-page app (Inter & Outfit Google Fonts, Chart.js, Lucide Icons).
- **AI & LLM Routing**: DeepSeek V3/R1 (Primary), Azure OpenAI `gpt-4o` (Secondary), Google Gemini 1.5/2.5 Flash (Tertiary).
- **Alerting**: Telegram Bot API (`python-telegram-bot`) & Free SMTP Email.

---

## 🚀 Local Execution

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Credentials
Copy `.env.example` to `.env` and enter your keys:
```ini
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
TELEGRAM_CHAT_ID=your-telegram-chat-id
AZURE_OPENAI_API_KEY=your-azure-key
AZURE_OPENAI_ENDPOINT=https://your-endpoint.cognitiveservices.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
```

### 3. Launch Local Server & Dashboard
```bash
python app/api/server.py
```
Open **`http://127.0.0.1:8000/`** in your browser!

### 4. Run 15-Minute Continuous Background Scanner
```bash
python scripts/run_continuous.py
```

### 5. Run Test Suite
```bash
python -m unittest discover tests
```

---

## ☁️ $0/Month 24/7 Cloud Deployment Guide

### Part A: Deploy Web Dashboard to Vercel (Free)

1. Install Vercel CLI or connect your GitHub repository to [Vercel.com](https://vercel.com).
2. Deploy using the included [`vercel.json`](file:///f:/FC/vercel.json):
   ```bash
   vercel
   ```
3. Set your environment variables (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `AZURE_OPENAI_API_KEY`, etc.) under Vercel Project Settings $\rightarrow$ Environment Variables.
4. Your dashboard is now live at `https://your-project.vercel.app`!

### Part B: Enable 24/7 Cloud Background Scanning via GitHub Actions (Free)

1. Push your repository to **GitHub**.
2. Go to **Settings $\rightarrow$ Secrets and variables $\rightarrow$ Actions** in your GitHub repo.
3. Add the following repository secrets:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
   - `AZURE_OPENAI_API_KEY`
   - `AZURE_OPENAI_ENDPOINT`
   - `AZURE_OPENAI_DEPLOYMENT_NAME`
   - `AZURE_OPENAI_API_VERSION`
   - `SUPABASE_URL`
   - `SUPABASE_KEY`
4. The included workflow [`.github/workflows/scanner.yml`](file:///f:/FC/.github/workflows/scanner.yml) will automatically run a scan pass every **15 minutes 24/7 for $0/month**!

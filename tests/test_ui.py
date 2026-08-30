import unittest
from unittest.mock import patch
import os
import sys
import ast
from fastapi.testclient import TestClient

# Add project root to sys.path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from app.api.server import app

class TestUIDashboard(unittest.TestCase):
    """
    Comprehensive UI and Frontend validation test suite for the Web Dashboard and Streamlit apps.
    """

    @classmethod
    def setUpClass(cls):
        cls.patcher = patch("app.api.server.SIGNALS_STORAGE_PATH", "non_existent_file.json")
        cls.patcher.start()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.patcher.stop()

    def setUp(self):
        self.response = self.client.get("/")
        self.html = self.response.text

    def test_root_html_document_structure(self):
        """Verify HTML document tags, meta viewport, title, stylesheets, and scripts."""
        self.assertEqual(self.response.status_code, 200)
        self.assertIn("<!DOCTYPE html>", self.html)
        self.assertIn("<meta name=\"viewport\"", self.html)
        self.assertIn("<title>AI Market Intelligence & Trading Signal System</title>", self.html)
        self.assertIn("href=\"/static/styles.css\"", self.html)
        self.assertIn("src=\"https://cdn.jsdelivr.net/npm/chart.js\"", self.html)
        self.assertIn("src=\"/static/app.js", self.html)

    def test_tabs_and_navigation_elements(self):
        """Verify navigation bar and all 6 tab view containers."""
        tab_ids = [
            "tab-overview",
            "tab-signals",
            "tab-paper",
            "tab-funnel",
            "tab-settings",
            "tab-health"
        ]
        for tab_id in tab_ids:
            self.assertIn(f'id="{tab_id}"', self.html, f"Missing tab container: {tab_id}")
            self.assertIn(f"switchTab('{tab_id}')", self.html, f"Missing tab button onclick: switchTab('{tab_id}')")

    def test_dashboard_interactive_components_and_containers(self):
        """Verify dynamic DOM containers and canvas elements."""
        critical_element_ids = [
            "currency-strength-grid",
            "market-monitor-body",
            "signals-container",
            "pt-balance",
            "pt-pnl",
            "pt-winrate",
            "pt-profit-factor",
            "equityChart",
            "mirror-scan-id",
            "mirror-scan-time",
            "mirror-latency",
            "lifecycle-flow-grid",
            "engine-matrix-container",
            "rejection-reasons-list",
            "candidate-eval-body",
            "tg-token",
            "tg-chatid",
            "llm-deepseek-key",
            "llm-azure-key",
            "llm-azure-endpoint",
            "llm-gemini-key",
            "llm-openai-key",
            "oanda-key",
            "oanda-account",
            "oanda-env",
            "scan-interval-select",
            "flight-recorder-terminal",
            "engine-health-body",
            "top-errors-body",
            "rationale-modal",
            "modal-title",
            "modal-body"
        ]
        for elem_id in critical_element_ids:
            self.assertIn(f'id="{elem_id}"', self.html, f"Missing UI DOM element with id: {elem_id}")

    def test_static_css_assets_delivery(self):
        """Verify /static/styles.css is served and contains glassmorphism rules."""
        res = self.client.get("/static/styles.css")
        self.assertEqual(res.status_code, 200)
        css_text = res.text
        self.assertIn("--bg-dark", css_text)
        self.assertIn(".glass-card", css_text)
        self.assertIn(".btn-primary", css_text)
        self.assertIn(".modal-overlay", css_text)
        self.assertIn(".direction-tag", css_text)

    def test_static_js_assets_delivery(self):
        """Verify /static/app.js is served and defines required frontend functions."""
        res = self.client.get("/static/app.js")
        self.assertEqual(res.status_code, 200)
        js_text = res.text
        self.assertIn("function switchTab", js_text)
        self.assertIn("async function loadOverview", js_text)
        self.assertIn("async function loadSignals", js_text)
        self.assertIn("async function loadPaperTrading", js_text)
        self.assertIn("function openModal", js_text)
        self.assertIn("async function triggerScan", js_text)
        self.assertIn("async function saveTelegramConfig", js_text)
        self.assertIn("async function saveLLMConfig", js_text)
        self.assertIn("async function saveOANDAConfig", js_text)
        self.assertIn("async function saveSchedulerInterval", js_text)

    def test_ui_api_contract_overview(self):
        """Verify overview endpoint schema matches app.js loadOverview expectations."""
        res = self.client.get("/api/overview")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("currency_strength", data)
        self.assertIn("tracked_assets", data)
        if data["tracked_assets"]:
            asset = data["tracked_assets"][0]
            self.assertIn("symbol", asset)
            self.assertIn("price", asset)
            self.assertIn("direction", asset)
            self.assertIn("score", asset)
            self.assertIn("rsi", asset)
            self.assertIn("adx", asset)
            self.assertIn("setup", asset)

    def test_ui_api_contract_signals(self):
        """Verify signals endpoint schema matches app.js loadSignals & openModal expectations."""
        res = self.client.get("/api/signals")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("signals", data)
        self.assertGreater(len(data["signals"]), 0)
        sig = data["signals"][0]
        self.assertIn("symbol_name", sig)
        self.assertIn("direction", sig)
        self.assertIn("opportunity_score", sig)
        self.assertIn("entry_price", sig)
        self.assertIn("stop_loss", sig)
        self.assertIn("take_profit_1", sig)
        self.assertIn("risk_reward", sig)
        self.assertIn("llm_reasoning", sig)
        self.assertIn("reasoning_object", sig)

    def test_ui_api_contract_paper_trading(self):
        """Verify paper trading endpoint schema matches app.js loadPaperTrading expectations."""
        res = self.client.get("/api/paper-trading")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("current_balance", data)
        self.assertIn("net_pnl", data)
        self.assertIn("win_rate_pct", data)
        self.assertIn("profit_factor", data)

    def test_ui_api_contract_parallel_health(self):
        """Verify parallel health endpoint schema matches app.js loadParallelHealth expectations."""
        res = self.client.get("/api/parallel/health")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("status", data)
        self.assertIn("active_engines", data)
        self.assertIn("orchestrator_concurrency", data)

    def test_streamlit_dashboard_scripts_syntax(self):
        """Verify Streamlit dashboard scripts are syntactically valid and parse cleanly."""
        dashboard_files = [
            os.path.join(root_dir, "app", "dashboard", "app.py"),
            os.path.join(root_dir, "app", "dashboard", "dashboard.py")
        ]
        for script_path in dashboard_files:
            self.assertTrue(os.path.exists(script_path), f"Dashboard script missing: {script_path}")
            with open(script_path, "r", encoding="utf-8") as f:
                code = f.read()
                # Parse AST to ensure no syntax errors
                tree = ast.parse(code)
                self.assertIsNotNone(tree)

if __name__ == '__main__':
    unittest.main()

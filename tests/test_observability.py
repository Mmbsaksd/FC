import unittest
from app.observability.logger import sanitize_message, sys_logger
from app.observability.flight_recorder import flight_recorder
from fastapi.testclient import TestClient
from app.api.server import app

class TestObservabilitySubsystem(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_credential_sanitizer(self):
        """Verify API keys, Telegram tokens, and secrets are redacted from logs."""
        raw_msg1 = "Loaded TELEGRAM_BOT_TOKEN=8815174821:AAEVVwaPfglouNg2AHCQ0ZeLVIXtyndxbvo successfully."
        sanitized1 = sanitize_message(raw_msg1)
        self.assertNotIn("8815174821:AAEVVwaPfglouNg2AHCQ0ZeLVIXtyndxbvo", sanitized1)
        self.assertIn("[REDACTED]", sanitized1)

        raw_standalone_tg = "Sending to Telegram with token 8815174821:AAEVVwaPfglouNg2AHCQ0ZeLVIXtyndxbvo"
        sanitized_tg = sanitize_message(raw_standalone_tg)
        self.assertNotIn("8815174821:AAEVVwaPfglouNg2AHCQ0ZeLVIXtyndxbvo", sanitized_tg)
        self.assertIn("[TELEGRAM_BOT_TOKEN_REDACTED]", sanitized_tg)

        raw_msg2 = "Using Authorization: Bearer sk-proj-1234567890abcdef1234567890 for OpenAI."
        sanitized2 = sanitize_message(raw_msg2)
        self.assertNotIn("sk-proj-1234567890abcdef1234567890", sanitized2)
        self.assertIn("[REDACTED]", sanitized2)

        raw_bearer = "Passed token Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9 for authentication"
        sanitized_bearer = sanitize_message(raw_bearer)
        self.assertIn("Bearer [REDACTED]", sanitized_bearer)

        raw_msg3 = "Connecting with api_key=3d33f3caa5607a16c0441c76a240eb34 to OANDA."
        sanitized3 = sanitize_message(raw_msg3)
        self.assertNotIn("3d33f3caa5607a16c0441c76a240eb34", sanitized3)
        self.assertIn("[REDACTED]", sanitized3)

    def test_structured_logger_ring_buffer(self):
        """Verify ring buffer stores records and filters properly."""
        sys_logger.info(
            component="TestComponent",
            event="TEST_EVENT_A",
            message="Test informational message for observability",
            scan_id="scan-test-101"
        )
        sys_logger.warning(
            component="TestComponent",
            event="TEST_EVENT_B",
            message="Test warning event",
            scan_id="scan-test-101"
        )
        sys_logger.error(
            component="TestComponent",
            event="TEST_EVENT_C",
            message="Test error event",
            scan_id="scan-test-101"
        )

        all_logs = sys_logger.get_logs(scan_id="scan-test-101")
        self.assertGreaterEqual(len(all_logs), 3)

        error_logs = sys_logger.get_logs(scan_id="scan-test-101", level="ERROR")
        self.assertTrue(any(l["event"] == "TEST_EVENT_C" for l in error_logs))

    def test_flight_recorder_lifecycle_aggregation(self):
        """Verify flight recorder lifecycle counters and summary outputs."""
        scan_id = "scan-test-lifecycle-999"
        trace_id = "trc-test-999"

        flight_recorder.start_scan(scan_id, trace_id, instrument_count=14, engine_count=10)
        flight_recorder.record_market_data(scan_id, trace_id, "YahooFinance", "EUR/USD", 60, 25.0)
        flight_recorder.record_engine_execution(scan_id, trace_id, "TechnicalAnalysis", "EUR/USD", "SUCCESS", 12.5, 80.0, "LONG", 0.85)
        flight_recorder.record_candidate_rejection(scan_id, trace_id, "EUR/USD", "LONG", "REJECT_POOR_RR", "R:R 1.5 < 2.0", 65.0)
        flight_recorder.complete_scan(scan_id, trace_id, 120.0, 14, 14, 1, 1, 0, 0)

        summary = flight_recorder.get_summary_metrics()
        self.assertIn("scans_total", summary)
        self.assertGreaterEqual(summary["scans_total"], 1)
        self.assertIn("engine_health", summary)
        self.assertEqual(len(summary["engine_health"]), 10)
        self.assertIn("top_errors", summary)

    def test_api_logs_endpoints(self):
        """Verify /api/logs and /api/logs/summary return HTTP 200 with structured data."""
        res = self.client.get("/api/logs?limit=50")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("logs", data)
        self.assertIn("count", data)

        res_sum = self.client.get("/api/logs/summary")
        self.assertEqual(res_sum.status_code, 200)
        sum_data = res_sum.json()
        self.assertIn("scans_total", sum_data)
        self.assertIn("engine_health", sum_data)
        self.assertIn("current_state", sum_data)

if __name__ == "__main__":
    unittest.main()

import os
import re
import sys
import json
import logging
import threading
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from collections import deque

# Credential patterns to sanitize from all logs
SENSITIVE_PATTERNS = [
    (re.compile(r'Bearer\s+[A-Za-z0-9_\-\.]{10,}', re.IGNORECASE), 'Bearer [REDACTED]'),
    (re.compile(r'sk-[A-Za-z0-9_\-\.]{20,}', re.IGNORECASE), 'sk-[REDACTED]'),
    (re.compile(r'\b[0-9]{9,11}:[A-Za-z0-9_\-]{30,45}\b'), '[TELEGRAM_BOT_TOKEN_REDACTED]'),
    (re.compile(r'(?i)(api[-_]?key|token|password|secret|authorization)\s*[:=]\s*["\']?([^"\'\s,;]+)["\']?'), r'\1="[REDACTED]"'),
    (re.compile(r'\b[0-9a-f]{32,64}\b', re.IGNORECASE), '[SECRET_KEY_REDACTED]')
]

def sanitize_message(msg: str) -> str:
    """Scrub any sensitive credentials or tokens from string."""
    if not isinstance(msg, str):
        msg = str(msg)
    for pattern, replacement in SENSITIVE_PATTERNS:
        msg = pattern.sub(replacement, msg)
    return msg

class StructuredLogRecord:
    """Structured Event model for telemetry and flight-recorder records."""
    def __init__(
        self,
        level: str,
        event: str,
        component: str,
        message: str,
        scan_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        signal_id: Optional[str] = None,
        instrument: Optional[str] = None,
        duration_ms: Optional[float] = None,
        status: Optional[str] = None,
        error_code: Optional[str] = None,
        metrics: Optional[Dict[str, Any]] = None,
        timestamp: Optional[str] = None
    ):
        self.timestamp = timestamp or datetime.now(timezone.utc).isoformat()
        self.level = level.upper()
        self.event = event
        self.component = component
        self.message = sanitize_message(message)
        self.scan_id = scan_id
        self.trace_id = trace_id
        self.signal_id = signal_id
        self.instrument = instrument
        self.duration_ms = round(duration_ms, 2) if duration_ms is not None else None
        self.status = status
        self.error_code = error_code
        self.metrics = metrics or {}

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "timestamp": self.timestamp,
            "level": self.level,
            "event": self.event,
            "component": self.component,
            "message": self.message,
        }
        if self.scan_id: d["scan_id"] = self.scan_id
        if self.trace_id: d["trace_id"] = self.trace_id
        if self.signal_id: d["signal_id"] = self.signal_id
        if self.instrument: d["instrument"] = self.instrument
        if self.duration_ms is not None: d["duration_ms"] = self.duration_ms
        if self.status: d["status"] = self.status
        if self.error_code: d["error_code"] = self.error_code
        if self.metrics: d["metrics"] = self.metrics
        return d

    def to_formatted_line(self) -> str:
        time_part = self.timestamp.split("T")[-1][:8] if "T" in self.timestamp else self.timestamp
        scan_part = f" [{self.scan_id}]" if self.scan_id else ""
        comp_part = f" [{self.component}]"
        evt_part = f" [{self.event}]" if self.event else ""
        return f"[{time_part}] [{self.level:<5}]{scan_part}{comp_part}{evt_part} {self.message}"

class SystemLogger:
    """
    Central thread-safe structured logger with in-memory ring buffer
    and rolling file rotation.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(SystemLogger, cls).__new__(cls)
                cls._instance._init_logger()
            return cls._instance

    def _init_logger(self):
        self.max_buffer_size = 10000
        self.ring_buffer: deque = deque(maxlen=self.max_buffer_size)
        self.lock = threading.RLock()

        # Create logs directory
        log_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../logs"))
        os.makedirs(log_dir, exist_ok=True)
        self.log_file = os.path.join(log_dir, "system.log")

        # Configure root python logger
        self.py_logger = logging.getLogger("FC_SYSTEM")
        self.py_logger.setLevel(logging.DEBUG)

        # File Handler (10MB max, 5 backups)
        file_handler = RotatingFileHandler(
            self.log_file,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_fmt = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_fmt)

        # Console Handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(file_fmt)

        self.py_logger.handlers = []
        self.py_logger.addHandler(file_handler)
        self.py_logger.addHandler(console_handler)

    def log(
        self,
        level: str,
        event: str,
        component: str,
        message: str,
        scan_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        signal_id: Optional[str] = None,
        instrument: Optional[str] = None,
        duration_ms: Optional[float] = None,
        status: Optional[str] = None,
        error_code: Optional[str] = None,
        metrics: Optional[Dict[str, Any]] = None
    ) -> StructuredLogRecord:
        record = StructuredLogRecord(
            level=level,
            event=event,
            component=component,
            message=message,
            scan_id=scan_id,
            trace_id=trace_id,
            signal_id=signal_id,
            instrument=instrument,
            duration_ms=duration_ms,
            status=status,
            error_code=error_code,
            metrics=metrics
        )

        with self.lock:
            self.ring_buffer.append(record)

        # Log through Python logging system safely
        log_method = getattr(self.py_logger, level.lower(), self.py_logger.info)
        log_method(f"[{event}] {record.message}")

        return record

    def debug(self, component: str, event: str, message: str, **kwargs):
        return self.log("DEBUG", event, component, message, **kwargs)

    def info(self, component: str, event: str, message: str, **kwargs):
        return self.log("INFO", event, component, message, **kwargs)

    def warning(self, component: str, event: str, message: str, **kwargs):
        return self.log("WARNING", event, component, message, **kwargs)

    def error(self, component: str, event: str, message: str, **kwargs):
        return self.log("ERROR", event, component, message, **kwargs)

    def critical(self, component: str, event: str, message: str, **kwargs):
        return self.log("CRITICAL", event, component, message, **kwargs)

    def get_logs(
        self,
        level: Optional[str] = None,
        component: Optional[str] = None,
        scan_id: Optional[str] = None,
        signal_id: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 200,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        with self.lock:
            filtered = list(self.ring_buffer)

        # Apply filters in reverse chronological order
        filtered.reverse()

        if level and level.upper() != "ALL":
            target_level = level.upper()
            if target_level == "ERROR":
                filtered = [r for r in filtered if r.level in ["ERROR", "CRITICAL"]]
            else:
                filtered = [r for r in filtered if r.level == target_level]

        if component and component.upper() != "ALL":
            filtered = [r for r in filtered if r.component.lower() == component.lower()]

        if scan_id:
            filtered = [r for r in filtered if r.scan_id == scan_id]

        if signal_id:
            filtered = [r for r in filtered if r.signal_id == signal_id]

        if search:
            s_lower = search.lower()
            filtered = [r for r in filtered if s_lower in r.message.lower() or s_lower in r.event.lower() or s_lower in r.component.lower()]

        paginated = filtered[offset: offset + limit]
        return [r.to_dict() for r in paginated]

# Global singleton instance
sys_logger = SystemLogger()

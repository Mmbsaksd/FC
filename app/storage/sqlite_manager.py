"""
SQLite Local Persistent Storage Module for AI Trading System.
Authoritative source of truth for all operational, analytical, signal, outcome, ML-training,
and observability data across application restarts, dashboard refreshes, and machine reboots.
"""

import os
import json
import sqlite3
import hashlib
import logging
from contextlib import contextmanager
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

DB_DIRECTORY = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data"))
DB_PATH = os.path.join(DB_DIRECTORY, "trading_system.db")

class SQLiteManager:
    """
    Thread-safe, WAL-enabled SQLite Database Manager.
    Serves as the local source of truth for all system data.
    """

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=30.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        try:
            yield conn
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def _init_db(self):
        """Initializes database schema with required tables and indexes."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 1. SIGNALS TABLE
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                signal_id TEXT PRIMARY KEY,
                fingerprint TEXT UNIQUE NOT NULL,
                setup_key TEXT,
                scan_id TEXT,
                trace_id TEXT,
                symbol TEXT NOT NULL,
                raw_symbol TEXT,
                asset_class TEXT,
                direction TEXT NOT NULL,
                entry_price REAL NOT NULL,
                stop_loss REAL NOT NULL,
                take_profit_1 REAL NOT NULL,
                take_profit_2 REAL,
                tp1_r REAL DEFAULT 1.5,
                tp2_r REAL DEFAULT 3.0,
                risk_reward REAL DEFAULT 2.0,
                opportunity_score REAL NOT NULL,
                ml_probability REAL NOT NULL,
                quality_tier TEXT DEFAULT 'HIGH_QUALITY',
                version INTEGER DEFAULT 1,
                status TEXT NOT NULL DEFAULT 'MONITORING',
                t1_hit INTEGER DEFAULT 0,
                t1_hit_time TEXT,
                t1_hit_price REAL,
                t2_hit INTEGER DEFAULT 0,
                t2_hit_time TEXT,
                t2_hit_price REAL,
                sl_hit INTEGER DEFAULT 0,
                sl_hit_time TEXT,
                sl_hit_price REAL,
                expired INTEGER DEFAULT 0,
                current_price REAL,
                unrealized_r REAL DEFAULT 0.0,
                unrealized_pnl REAL DEFAULT 0.0,
                realized_r REAL DEFAULT 0.0,
                realized_pnl REAL DEFAULT 0.0,
                mfe_r REAL DEFAULT 0.0,
                mae_r REAL DEFAULT 0.0,
                holding_minutes INTEGER DEFAULT 0,
                outcome TEXT,
                llm_reasoning TEXT,
                evidence_json TEXT,
                why_this_trade_json TEXT,
                supporting_evidence_json TEXT,
                contradicting_evidence_json TEXT,
                neutral_evidence_json TEXT,
                features_json TEXT,
                exit_reason TEXT,
                root_cause TEXT,
                root_cause_evidence TEXT,
                features_at_exit_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """)

            # 2. SIGNAL LIFECYCLE EVENTS TABLE (Idempotent by event_id)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS signal_lifecycle_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT UNIQUE NOT NULL,
                signal_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                price REAL,
                detail TEXT,
                FOREIGN KEY (signal_id) REFERENCES signals(signal_id) ON DELETE CASCADE
            );
            """)

            # 3. MARKET SNAPSHOTS TABLE
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS market_snapshots (
                snapshot_id TEXT PRIMARY KEY,
                scan_id TEXT,
                symbol TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                price REAL NOT NULL,
                bid REAL,
                ask REAL,
                spread_pips REAL,
                session TEXT,
                data_quality TEXT,
                indicators_json TEXT
            );
            """)

            # 4. ENGINE ANALYTICAL RESULTS TABLE
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS engine_analytical_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_id TEXT NOT NULL,
                engine_name TEXT NOT NULL,
                engine_version TEXT,
                symbol TEXT NOT NULL,
                direction TEXT,
                score REAL,
                confidence REAL,
                execution_ms REAL,
                features_json TEXT,
                timestamp TEXT NOT NULL
            );
            """)

            # 5. ML TRAINING RECORDS TABLE (Zero future data leakage)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS ml_training_records (
                record_id TEXT PRIMARY KEY,
                signal_id TEXT UNIQUE NOT NULL,
                model_version TEXT,
                signal_time_features_json TEXT NOT NULL,
                ml_prediction REAL,
                ml_probability REAL,
                composite_score REAL,
                realized_r REAL,
                realized_pnl REAL,
                mfe_r REAL,
                mae_r REAL,
                outcome_class TEXT,
                holding_period_mins INTEGER,
                regime TEXT,
                exit_reason TEXT,
                root_cause TEXT,
                root_cause_evidence TEXT,
                created_at TEXT NOT NULL,
                resolved_at TEXT,
                FOREIGN KEY (signal_id) REFERENCES signals(signal_id) ON DELETE CASCADE
            );
            """)

            # 6. SIGNAL REVISIONS TABLE (Full Stateful Lifecycle Audit Trail)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS signal_revisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_id TEXT NOT NULL,
                version_number INTEGER NOT NULL,
                scan_id TEXT,
                timestamp TEXT NOT NULL,
                state TEXT NOT NULL,
                opportunity_score REAL,
                ml_probability REAL,
                entry_price REAL,
                stop_loss REAL,
                take_profit_1 REAL,
                take_profit_2 REAL,
                change_reason TEXT,
                delta_summary_json TEXT,
                FOREIGN KEY (signal_id) REFERENCES signals(signal_id) ON DELETE CASCADE
            );
            """)

            # 7. NOTIFICATION LOGS TABLE
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS notification_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel TEXT NOT NULL,
                event_type TEXT NOT NULL,
                signal_id TEXT,
                status TEXT NOT NULL,
                latency_ms REAL,
                error_message TEXT,
                timestamp TEXT NOT NULL
            );
            """)

            # 8. SYSTEM OBSERVABILITY EVENTS TABLE
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_observability_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_id TEXT,
                component TEXT NOT NULL,
                event_type TEXT NOT NULL,
                severity TEXT DEFAULT 'INFO',
                duration_ms REAL,
                message TEXT,
                timestamp TEXT NOT NULL
            );
            """)

            # Run column migrations if upgrading existing database
            cursor.execute("PRAGMA table_info(signals)")
            cols = [col["name"] for col in cursor.fetchall()]
            new_signal_cols = {
                "setup_key": "TEXT",
                "version": "INTEGER DEFAULT 1",
                "quality_tier": "TEXT DEFAULT 'HIGH_QUALITY'",
                "why_this_trade_json": "TEXT",
                "supporting_evidence_json": "TEXT",
                "contradicting_evidence_json": "TEXT",
                "neutral_evidence_json": "TEXT",
                "features_json": "TEXT",
                "exit_reason": "TEXT",
                "root_cause": "TEXT",
                "root_cause_evidence": "TEXT",
                "features_at_exit_json": "TEXT"
            }
            for col_name, col_type in new_signal_cols.items():
                if col_name not in cols:
                    cursor.execute(f"ALTER TABLE signals ADD COLUMN {col_name} {col_type}")

            cursor.execute("PRAGMA table_info(ml_training_records)")
            ml_cols = [col["name"] for col in cursor.fetchall()]
            new_ml_cols = {
                "exit_reason": "TEXT",
                "root_cause": "TEXT",
                "root_cause_evidence": "TEXT"
            }
            for col_name, col_type in new_ml_cols.items():
                if col_name not in ml_cols:
                    cursor.execute(f"ALTER TABLE ml_training_records ADD COLUMN {col_name} {col_type}")

            # INDEXES FOR OPTIMAL QUERY PERFORMANCE
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_signals_status ON signals(status);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_signals_symbol ON signals(symbol);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_signals_created ON signals(created_at);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_signals_fingerprint ON signals(fingerprint);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_signals_setup_key ON signals(setup_key);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_revisions_signal ON signal_revisions(signal_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_signal ON signal_lifecycle_events(signal_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_engine_scan ON engine_analytical_results(scan_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ml_signal ON ml_training_records(signal_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_obs_time ON system_observability_events(timestamp);")

            conn.commit()
            logger.info("SQLite local persistent schema initialized and verified.")

    # -------------------------------------------------------------
    # SIGNAL FINGERPRINT & DEDUPLICATION METHODS
    # -------------------------------------------------------------
    @staticmethod
    def compute_setup_key(symbol: str, direction: str, timeframe: str = "5M") -> str:
        """
        Generates a robust semantic setup key identifying the continuous opportunity.
        Format: EURUSD:SHORT:5M
        """
        clean_sym = symbol.replace("/", "").replace("_", "").replace("-USD", "").replace("=X", "").replace("=F", "").upper()
        return f"{clean_sym}:{direction.upper()}:{timeframe.upper()}"

    @staticmethod
    def compute_fingerprint(symbol: str, direction: str, entry_price: float, sl: float, tp1: float) -> str:
        """
        Generates a deterministic setup fingerprint.
        Rounds price levels into discrete pip buckets so identical setups produce the same fingerprint.
        """
        bucket_entry = round(entry_price, 3 if entry_price > 50 else 4)
        bucket_sl = round(sl, 3 if sl > 50 else 4)
        bucket_tp = round(tp1, 3 if tp1 > 50 else 4)

        raw = f"{symbol.upper()}:{direction.upper()}:{bucket_entry}:{bucket_sl}:{bucket_tp}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]

    def is_duplicate_active_signal(self, fingerprint: str) -> bool:
        """
        Checks if an active, non-closed signal with this fingerprint already exists.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT signal_id FROM signals
                WHERE (fingerprint = ? OR setup_key = ?) AND status IN ('NEW', 'MONITORING', 'TARGET_1_HIT')
            """, (fingerprint, fingerprint))
            row = cursor.fetchone()
            return row is not None

    def get_active_signal_by_setup_key(self, setup_key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves the current active signal record matching a semantic setup key.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM signals
                WHERE setup_key = ? AND status IN ('NEW', 'MONITORING', 'TARGET_1_HIT')
                ORDER BY created_at DESC LIMIT 1
            """, (setup_key,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def save_signal_revision(self, signal_id: str, revision: Dict[str, Any]) -> int:
        """
        Records a state transition / update revision for an existing active signal.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(version_number) as v FROM signal_revisions WHERE signal_id = ?", (signal_id,))
            r = cursor.fetchone()
            next_v = (r["v"] or 1) + 1 if r and r["v"] else 2
            
            now_iso = datetime.now(timezone.utc).isoformat()
            cursor.execute("""
            INSERT INTO signal_revisions (
                signal_id, version_number, scan_id, timestamp, state,
                opportunity_score, ml_probability, entry_price, stop_loss,
                take_profit_1, take_profit_2, change_reason, delta_summary_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                signal_id, next_v, revision.get("scan_id", ""),
                now_iso, revision.get("state", "UPDATED"),
                float(revision.get("opportunity_score", 0.0)),
                float(revision.get("ml_probability", 0.0)),
                float(revision.get("entry_price", 0.0)),
                float(revision.get("stop_loss", 0.0)),
                float(revision.get("take_profit_1", 0.0)),
                float(revision.get("take_profit_2", 0.0)),
                revision.get("change_reason", ""),
                json.dumps(revision.get("deltas", {}), default=str)
            ))
            
            # Update parent signal latest state atomically
            cursor.execute("""
            UPDATE signals
            SET version = ?,
                opportunity_score = ?,
                ml_probability = ?,
                entry_price = ?,
                stop_loss = ?,
                take_profit_1 = ?,
                updated_at = ?
            WHERE signal_id = ?
            """, (
                next_v,
                float(revision.get("opportunity_score", 0.0)),
                float(revision.get("ml_probability", 0.0)),
                float(revision.get("entry_price", 0.0)),
                float(revision.get("stop_loss", 0.0)),
                float(revision.get("take_profit_1", 0.0)),
                now_iso,
                signal_id
            ))
            conn.commit()
            return next_v

    def get_signal_revisions(self, signal_id: str) -> List[Dict[str, Any]]:
        """
        Returns full revision history for a signal.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM signal_revisions WHERE signal_id = ? ORDER BY version_number ASC", (signal_id,))
            return [dict(r) for r in cursor.fetchall()]

    # -------------------------------------------------------------
    # SIGNAL CRUD & LIFECYCLE MANAGEMENT
    # -------------------------------------------------------------
    def save_signal(self, signal: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Persists a new signal. Enforces persistent deduplication via setup fingerprint.
        Returns (is_created, signal_id).
        """
        sig_id = signal.get("signal_id")
        symbol = signal.get("symbol_name", signal.get("symbol", "Asset"))
        direction = signal.get("direction", "LONG")
        entry = float(signal.get("entry_price", 0.0))
        sl = float(signal.get("stop_loss", 0.0))
        tp1 = float(signal.get("take_profit_1", 0.0))
        tp2 = float(signal.get("take_profit_2")) if signal.get("take_profit_2") is not None else tp1
        tf = signal.get("timeframe", "5M")

        setup_key = signal.get("setup_key") or self.compute_setup_key(symbol, direction, tf)
        fingerprint = signal.get("fingerprint") or self.compute_fingerprint(symbol, direction, entry, sl, tp1)

        # Check if identical active signal exists
        if self.get_active_signal_by_setup_key(setup_key) is not None:
            logger.info(f"Duplicate signal rejected: Active setup already monitored for {symbol} {direction} (Key: {setup_key})")
            return False, sig_id

        now_iso = datetime.now(timezone.utc).isoformat()
        risk_dist = abs(entry - sl) if abs(entry - sl) > 0 else 0.0001
        tp1_r = round(abs(tp1 - entry) / risk_dist, 2)
        tp2_r = round(abs(tp2 - entry) / risk_dist, 2) if tp2 != tp1 else tp1_r

        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                features = signal.get("features", signal.get("feature_vector", {}))
                engine_evidence = signal.get("engine_evidence", signal.get("evidence", {}))
                why_this_trade = signal.get("why_this_trade", {})
                supporting_evidence = signal.get("supporting_evidence", [])
                contradicting_evidence = signal.get("contradicting_evidence", [])
                neutral_evidence = signal.get("neutral_evidence", [])

                cursor.execute("""
                INSERT INTO signals (
                    signal_id, fingerprint, setup_key, scan_id, trace_id, symbol, raw_symbol, asset_class,
                    direction, entry_price, stop_loss, take_profit_1, take_profit_2,
                    tp1_r, tp2_r, risk_reward, opportunity_score, ml_probability, quality_tier,
                    status, version, current_price, created_at, updated_at, llm_reasoning, evidence_json,
                    why_this_trade_json, supporting_evidence_json, contradicting_evidence_json, neutral_evidence_json, features_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    sig_id, fingerprint, setup_key, signal.get("scan_id", "scan-unknown"), signal.get("trace_id", "trace-unknown"),
                    symbol, signal.get("raw_symbol", signal.get("symbol", "")),
                    signal.get("asset_class") or ("CRYPTO" if any(c in symbol.upper() for c in ["BTC", "ETH"]) else ("FOREX" if "/" in symbol else "COMMODITY")),
                    direction, entry, sl, tp1, tp2, tp1_r, tp2_r,
                    float(signal.get("risk_reward", 2.0)),
                    float(signal.get("opportunity_score", 70.0)),
                    float(signal.get("ml_probability", 0.60)),
                    signal.get("quality_tier", "HIGH_QUALITY"),
                    "MONITORING", 1, entry, now_iso, now_iso,
                    signal.get("llm_reasoning", ""),
                    json.dumps(engine_evidence, default=str),
                    json.dumps(why_this_trade, default=str),
                    json.dumps(supporting_evidence, default=str),
                    json.dumps(contradicting_evidence, default=str),
                    json.dumps(neutral_evidence, default=str),
                    json.dumps(features, default=str)
                ))

                # Record Initial Version 1 in signal_revisions
                cursor.execute("""
                INSERT INTO signal_revisions (
                    signal_id, version_number, scan_id, timestamp, state,
                    opportunity_score, ml_probability, entry_price, stop_loss,
                    take_profit_1, take_profit_2, change_reason, delta_summary_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    sig_id, 1, signal.get("scan_id", "scan-initial"),
                    now_iso, "NEW",
                    float(signal.get("opportunity_score", 70.0)),
                    float(signal.get("ml_probability", 0.60)),
                    entry, sl, tp1, tp2,
                    "Initial Signal Detection",
                    json.dumps({"state": "NEW"}, default=str)
                ))

                # Record Initial Lifecycle Event atomically
                event_id = f"{sig_id}_SIGNAL_CREATED"
                cursor.execute("""
                INSERT OR IGNORE INTO signal_lifecycle_events (event_id, signal_id, event_type, timestamp, price, detail)
                VALUES (?, ?, ?, ?, ?, ?)
                """, (event_id, sig_id, "SIGNAL_CREATED", now_iso, entry, f"Signal created @ {entry:.5f} (SL: {sl:.5f}, TP1: {tp1:.5f}, TP2: {tp2:.5f})"))

                # Initialize ML Training Record atomically
                features = signal.get("features", signal.get("feature_vector", {}))
                cursor.execute("""
                INSERT OR REPLACE INTO ml_training_records (
                    record_id, signal_id, model_version, signal_time_features_json,
                    ml_prediction, ml_probability, composite_score,
                    regime, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    f"mlrec-{sig_id}", sig_id, signal.get("model_version", "v2.1.0"),
                    json.dumps(features, default=str),
                    float(signal.get("ml_prediction", 1.0)),
                    float(signal.get("ml_probability", 0.60)),
                    float(signal.get("opportunity_score", 70.0)),
                    signal.get("regime", "NORMAL"),
                    now_iso
                ))

                conn.commit()
                logger.info(f"Signal persisted into SQLite database: {sig_id} ({symbol} {direction})")
                return True, sig_id
            except sqlite3.IntegrityError as e:
                logger.warning(f"Integrity check in save_signal: {e}")
                return False, sig_id

    def update_signal_progress(self, sig_id: str, updates: Dict[str, Any]):
        """Updates live excursions, prices, and status for an active signal."""
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        fields = []
        values = []
        for k, v in updates.items():
            fields.append(f"{k} = ?")
            values.append(v)
        values.append(sig_id)

        sql = f"UPDATE signals SET {', '.join(fields)} WHERE signal_id = ?"
        with self._get_connection() as conn:
            conn.execute(sql, values)
            conn.commit()

    def record_event(self, signal_id: str, event_type: str, price: float, detail: str, conn: Optional[sqlite3.Connection] = None) -> bool:
        """
        Idempotently logs a lifecycle event.
        Uses deterministic event_id (e.g. 'SIG-123_TARGET_1_HIT') to guarantee no duplicate event records.
        """
        event_id = f"{signal_id}_{event_type}"
        now_iso = datetime.now(timezone.utc).isoformat()

        if conn is not None:
            try:
                conn.execute("""
                INSERT INTO signal_lifecycle_events (event_id, signal_id, event_type, timestamp, price, detail)
                VALUES (?, ?, ?, ?, ?, ?)
                """, (event_id, signal_id, event_type, now_iso, price, detail))
                return True
            except sqlite3.IntegrityError:
                return False
        else:
            with self._get_connection() as new_conn:
                try:
                    new_conn.execute("""
                    INSERT INTO signal_lifecycle_events (event_id, signal_id, event_type, timestamp, price, detail)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """, (event_id, signal_id, event_type, now_iso, price, detail))
                    new_conn.commit()
                    return True
                except sqlite3.IntegrityError:
                    return False

    def get_active_signals(self) -> List[Dict[str, Any]]:
        """Retrieves all non-terminal signals from the database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM signals
                WHERE status IN ('NEW', 'MONITORING', 'TARGET_1_HIT')
                ORDER BY created_at DESC
            """)
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def get_closed_signals(self, limit: int = 200) -> List[Dict[str, Any]]:
        """Retrieves completed signals from the database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM signals
                WHERE status IN ('CLOSED', 'TARGET_2_HIT', 'STOPPED_OUT', 'EXPIRED', 'INVALIDATED')
                ORDER BY updated_at DESC
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def get_signal_by_id(self, signal_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single signal and its full chronological event timeline."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM signals WHERE signal_id = ?", (signal_id,))
            row = cursor.fetchone()
            if not row:
                return None
            res = dict(row)

            # Fetch lifecycle events
            cursor.execute("""
                SELECT event_type as event, timestamp, price, detail
                FROM signal_lifecycle_events
                WHERE signal_id = ?
                ORDER BY id ASC
            """, (signal_id,))
            res["events"] = [dict(e) for e in cursor.fetchall()]
            return res

    def get_recent_lifecycle_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves real-time event feed across all signals."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT e.event_type, e.timestamp, e.signal_id, s.symbol, s.direction, e.price, e.detail
                FROM signal_lifecycle_events e
                LEFT JOIN signals s ON e.signal_id = s.signal_id
                ORDER BY e.id DESC
                LIMIT ?
            """, (limit,))
            return [dict(r) for r in cursor.fetchall()]

    # -------------------------------------------------------------
    # ML & RETRAINING RECORD PERSISTENCE
    # -------------------------------------------------------------
    def save_ml_training_record(self, signal: Dict[str, Any], conn: Optional[sqlite3.Connection] = None):
        """Saves decision-time features without data leakage."""
        sig_id = signal.get("signal_id")
        rec_id = f"mlrec-{sig_id}"
        now_iso = datetime.now(timezone.utc).isoformat()

        features = signal.get("features", signal.get("feature_vector", {}))
        sql = """
        INSERT OR REPLACE INTO ml_training_records (
            record_id, signal_id, model_version, signal_time_features_json,
            ml_prediction, ml_probability, composite_score,
            regime, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            rec_id, sig_id, signal.get("model_version", "v2.1.0"),
            json.dumps(features, default=str),
            float(signal.get("ml_prediction", 1.0)),
            float(signal.get("ml_probability", 0.60)),
            float(signal.get("opportunity_score", 70.0)),
            signal.get("regime", "NORMAL"),
            now_iso
        )

        if conn is not None:
            try:
                conn.execute(sql, params)
            except Exception as e:
                logger.error(f"Error saving ML training record: {e}")
        else:
            with self._get_connection() as new_conn:
                try:
                    new_conn.execute(sql, params)
                    new_conn.commit()
                except Exception as e:
                    logger.error(f"Error saving ML training record: {e}")

    def update_ml_training_outcome(
        self,
        signal_id: str,
        outcome_class: str,
        realized_r: float,
        realized_pnl: float,
        mfe_r: float,
        mae_r: float,
        holding_mins: int,
        exit_reason: Optional[str] = None,
        root_cause: Optional[str] = None,
        root_cause_evidence: Optional[str] = None
    ):
        """Updates ground-truth outcome label when a trade closes."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            try:
                conn.execute("""
                UPDATE ml_training_records
                SET outcome_class = ?, realized_r = ?, realized_pnl = ?,
                    mfe_r = ?, mae_r = ?, holding_period_mins = ?, resolved_at = ?,
                    exit_reason = COALESCE(?, exit_reason),
                    root_cause = COALESCE(?, root_cause),
                    root_cause_evidence = COALESCE(?, root_cause_evidence)
                WHERE signal_id = ?
                """, (outcome_class, realized_r, realized_pnl, mfe_r, mae_r, holding_mins, now_iso, exit_reason, root_cause, root_cause_evidence, signal_id))
                conn.commit()
            except Exception as e:
                logger.error(f"Error updating ML training outcome: {e}")

    # -------------------------------------------------------------
    # MARKET SNAPSHOTS & ANALYTICAL EVIDENCE
    # -------------------------------------------------------------
    def save_market_snapshot(self, snapshot: Dict[str, Any]):
        """Persists market state at scan time."""
        snap_id = snapshot.get("snapshot_id", f"snap-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{snapshot.get('symbol')}")
        with self._get_connection() as conn:
            try:
                conn.execute("""
                INSERT OR REPLACE INTO market_snapshots (
                    snapshot_id, scan_id, symbol, timestamp, price, bid, ask, spread_pips, session, data_quality, indicators_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    snap_id, snapshot.get("scan_id"), snapshot.get("symbol"),
                    snapshot.get("timestamp", datetime.now(timezone.utc).isoformat()),
                    float(snapshot.get("price", 0.0)),
                    float(snapshot.get("bid", 0.0)),
                    float(snapshot.get("ask", 0.0)),
                    float(snapshot.get("spread_pips", 0.0)),
                    snapshot.get("session", "UNKNOWN"),
                    snapshot.get("data_quality", "GOOD"),
                    json.dumps(snapshot.get("indicators", {}), default=str)
                ))
                conn.commit()
                return snap_id
            except Exception as e:
                logger.error(f"Error saving market snapshot: {e}")
                return None

    def save_engine_result(self, scan_id: str, engine_name: str, symbol: str, direction: str, score: float, confidence: float, exec_ms: float, features: Dict[str, Any]):
        """Persists individual engine evaluation."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            try:
                conn.execute("""
                INSERT INTO engine_analytical_results (
                    scan_id, engine_name, engine_version, symbol, direction, score, confidence, execution_ms, features_json, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    scan_id, engine_name, "2.0", symbol, direction, score, confidence, exec_ms, json.dumps(features, default=str), now_iso
                ))
                conn.commit()
            except Exception as e:
                logger.error(f"Error saving engine analytical result: {e}")

    # -------------------------------------------------------------
    # TELEMETRY & OBSERVABILITY
    # -------------------------------------------------------------
    def save_notification_log(self, channel: str, event_type: str, signal_id: str, status: str, latency_ms: float, error_msg: str = ""):
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            try:
                conn.execute("""
                INSERT INTO notification_logs (channel, event_type, signal_id, status, latency_ms, error_message, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (channel, event_type, signal_id, status, latency_ms, error_msg, now_iso))
                conn.commit()
            except Exception as e:
                logger.error(f"Error saving notification log: {e}")

    def save_observability_event(self, scan_id: str, component: str, event_type: str, severity: str, duration_ms: float, message: str):
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            try:
                conn.execute("""
                INSERT INTO system_observability_events (scan_id, component, event_type, severity, duration_ms, message, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (scan_id, component, event_type, severity, duration_ms, message, now_iso))
                conn.commit()
            except Exception as e:
                logger.error(f"Error saving observability event: {e}")

    # -------------------------------------------------------------
    # AGGREGATED STATISTICAL METRICS FROM PERSISTENT DATABASE
    # -------------------------------------------------------------
    def get_database_analytics(self) -> Dict[str, Any]:
        """Calculates accurate analytics from persistent SQLite records."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Signals Summary
            cursor.execute("SELECT COUNT(*) as total FROM signals")
            total_signals = cursor.fetchone()["total"]

            cursor.execute("SELECT COUNT(*) as active FROM signals WHERE status IN ('NEW', 'MONITORING', 'TARGET_1_HIT')")
            active_signals = cursor.fetchone()["active"]

            cursor.execute("SELECT COUNT(*) as closed FROM signals WHERE status IN ('CLOSED', 'TARGET_2_HIT', 'STOPPED_OUT', 'EXPIRED', 'INVALIDATED')")
            closed_signals = cursor.fetchone()["closed"]

            cursor.execute("SELECT COUNT(*) as t1 FROM signals WHERE t1_hit = 1")
            t1_hits = cursor.fetchone()["t1"]

            cursor.execute("SELECT COUNT(*) as t2 FROM signals WHERE t2_hit = 1")
            t2_hits = cursor.fetchone()["t2"]

            cursor.execute("SELECT COUNT(*) as sl FROM signals WHERE sl_hit = 1")
            sl_hits = cursor.fetchone()["sl"]

            cursor.execute("SELECT COUNT(*) as exp FROM signals WHERE expired = 1")
            expired_hits = cursor.fetchone()["exp"]

            cursor.execute("SELECT COUNT(*) as wins, SUM(realized_r) as win_r, SUM(realized_pnl) as win_pnl FROM signals WHERE status NOT IN ('NEW', 'MONITORING', 'TARGET_1_HIT') AND realized_r > 0")
            win_row = cursor.fetchone()
            winning_signals = win_row["wins"] or 0
            gross_profit = win_row["win_pnl"] or 0.0

            cursor.execute("SELECT COUNT(*) as losses, SUM(realized_r) as loss_r, SUM(realized_pnl) as loss_pnl FROM signals WHERE status NOT IN ('NEW', 'MONITORING', 'TARGET_1_HIT') AND realized_r <= 0")
            loss_row = cursor.fetchone()
            losing_signals = loss_row["losses"] or 0
            gross_loss = abs(loss_row["loss_pnl"] or 0.0)

            cursor.execute("SELECT SUM(realized_r) as tot_r, SUM(realized_pnl) as tot_pnl FROM signals WHERE status NOT IN ('NEW', 'MONITORING', 'TARGET_1_HIT')")
            tot_row = cursor.fetchone()
            total_r = round(tot_row["tot_r"] or 0.0, 2)
            total_pnl = round(tot_row["tot_pnl"] or 0.0, 2)

            win_rate = round((winning_signals / closed_signals * 100.0) if closed_signals > 0 else 0.0, 1)
            loss_rate = round((losing_signals / closed_signals * 100.0) if closed_signals > 0 else 0.0, 1)
            t1_rate = round((t1_hits / total_signals * 100.0) if total_signals > 0 else 0.0, 1)
            t2_rate = round((t2_hits / total_signals * 100.0) if total_signals > 0 else 0.0, 1)
            sl_rate = round((sl_hits / total_signals * 100.0) if total_signals > 0 else 0.0, 1)
            avg_r = round((total_r / closed_signals) if closed_signals > 0 else 0.0, 2)

            avg_win_r = ((win_row["win_r"] or 0.0) / winning_signals) if winning_signals > 0 else 0.0
            avg_loss_r = (abs(loss_row["loss_r"] or 0.0) / losing_signals) if losing_signals > 0 else 0.0
            expectancy_r = round(((win_rate / 100.0) * avg_win_r) - ((loss_rate / 100.0) * avg_loss_r), 2)
            profit_factor = round((gross_profit / gross_loss) if gross_loss > 0 else (2.5 if gross_profit > 0 else 1.0), 2)

            # Asset Breakdown
            cursor.execute("""
                SELECT symbol, COUNT(*) as total,
                       SUM(CASE WHEN t1_hit = 1 THEN 1 ELSE 0 END) as t1_hits,
                       SUM(CASE WHEN t2_hit = 1 THEN 1 ELSE 0 END) as t2_hits,
                       SUM(CASE WHEN status NOT IN ('NEW', 'MONITORING', 'TARGET_1_HIT') AND realized_r > 0 THEN 1 ELSE 0 END) as wins,
                       SUM(CASE WHEN status NOT IN ('NEW', 'MONITORING', 'TARGET_1_HIT') THEN 1 ELSE 0 END) as completed,
                       SUM(CASE WHEN status NOT IN ('NEW', 'MONITORING', 'TARGET_1_HIT') THEN realized_r ELSE 0 END) as total_r
                FROM signals
                GROUP BY symbol
                ORDER BY total DESC
            """)
            asset_breakdown = []
            for r in cursor.fetchall():
                comp = r["completed"] or 0
                w_pct = round(((r["wins"] or 0) / comp * 100.0) if comp > 0 else 0.0, 1)
                asset_breakdown.append({
                    "symbol": r["symbol"],
                    "total_signals": r["total"],
                    "completed": comp,
                    "win_rate_pct": w_pct,
                    "t1_rate_pct": round(((r["t1_hits"] or 0) / r["total"] * 100.0) if r["total"] > 0 else 0.0, 1),
                    "t2_rate_pct": round(((r["t2_hits"] or 0) / r["total"] * 100.0) if r["total"] > 0 else 0.0, 1),
                    "total_r": round(r["total_r"] or 0.0, 2),
                    "avg_r": round(((r["total_r"] or 0.0) / comp) if comp > 0 else 0.0, 2)
                })

            return {
                "total_alerts": total_signals,
                "active_alerts": active_signals,
                "closed_alerts": closed_signals,
                "target_1_hits": t1_hits,
                "target_1_rate_pct": t1_rate,
                "target_2_hits": t2_hits,
                "target_2_rate_pct": t2_rate,
                "stop_loss_hits": sl_hits,
                "stop_loss_rate_pct": sl_rate,
                "expired_count": expired_hits,
                "winning_signals": winning_signals,
                "losing_signals": losing_signals,
                "win_rate_pct": win_rate,
                "loss_rate_pct": loss_rate,
                "average_r": avg_r,
                "total_r": total_r,
                "total_pnl_usd": total_pnl,
                "expectancy_r": expectancy_r,
                "profit_factor": profit_factor,
                "asset_breakdown": asset_breakdown
            }

# Global singleton SQLite Manager
db_manager = SQLiteManager()

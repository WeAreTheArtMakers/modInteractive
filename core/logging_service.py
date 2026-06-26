"""Logging and telemetry service for modInteractive.

SQLite-based event logging with log rotation and system metrics tracking.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.event_bus import Event, EventBus, SystemEvents

logger = logging.getLogger(__name__)


class LoggingService:
    """Centralized logging service with SQLite storage.

    Handles event logs, error logs, and system metrics collection.
    """

    def __init__(
        self,
        event_bus: EventBus,
        db_path: str = "logs/modinteractive.db",
        retention_days: int = 30,
    ) -> None:
        """Initialize logging service.

        Args:
            event_bus: System event bus
            db_path: Path to SQLite database file
            retention_days: Number of days to retain logs
        """
        self._event_bus = event_bus
        self._db_path = Path(db_path)
        self._retention_days = retention_days
        self._conn: Optional[sqlite3.Connection] = None
        self._metrics_task: Optional[asyncio.Task[None]] = None
        self._running = False
        self._lock = asyncio.Lock()

        self._db_path.parent.mkdir(parents=True, exist_ok=True)

    async def start(self) -> None:
        """Start logging service and initialize database."""
        self._init_db()
        self._running = True
        self._metrics_task = asyncio.create_task(self._collect_metrics())
        self._event_bus.subscribe(SystemEvents.SYSTEM_ERROR, self._log_system_error)
        self._event_bus.subscribe(SystemEvents.STATE_CHANGED, self._log_state_change)
        logger.info("Logging service started")

    async def stop(self) -> None:
        """Stop logging service."""
        self._running = False
        if self._metrics_task:
            self._metrics_task.cancel()
            try:
                await self._metrics_task
            except asyncio.CancelledError:
                pass
        if self._conn:
            self._conn.close()
        logger.info("Logging service stopped")

    def _init_db(self) -> None:
        """Initialize SQLite database and create tables."""
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")

        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS event_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                event_type TEXT NOT NULL,
                source TEXT NOT NULL,
                data TEXT,
                priority TEXT
            );

            CREATE TABLE IF NOT EXISTS system_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                cpu_percent REAL,
                memory_percent REAL,
                fps REAL,
                state TEXT,
                temperature REAL
            );

            CREATE TABLE IF NOT EXISTS error_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                error_type TEXT NOT NULL,
                message TEXT NOT NULL,
                traceback TEXT,
                source TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_event_logs_timestamp ON event_logs(timestamp);
            CREATE INDEX IF NOT EXISTS idx_event_logs_type ON event_logs(event_type);
            CREATE INDEX IF NOT EXISTS idx_error_logs_timestamp ON error_logs(timestamp);
            CREATE INDEX IF NOT EXISTS idx_system_metrics_timestamp ON system_metrics(timestamp);
        """)
        self._conn.commit()

    async def log_event(self, event: Event) -> None:
        """Log an event to the database.

        Args:
            event: Event to log
        """
        async with self._lock:
            try:
                self._conn.execute(
                    """INSERT INTO event_logs (timestamp, event_type, source, data, priority)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        event.timestamp,
                        event.event_type.name,
                        event.source,
                        str(event.data),
                        event.priority.name,
                    ),
                )
                self._conn.commit()
            except sqlite3.Error as e:
                logger.error(f"Failed to log event: {e}")

    async def log_error(
        self,
        error_type: str,
        message: str,
        traceback: Optional[str] = None,
        source: Optional[str] = None,
    ) -> None:
        """Log an error to the database.

        Args:
            error_type: Type of error
            message: Error message
            traceback: Optional traceback string
            source: Optional source component name
        """
        async with self._lock:
            try:
                self._conn.execute(
                    """INSERT INTO error_logs (timestamp, error_type, message, traceback, source)
                       VALUES (?, ?, ?, ?, ?)""",
                    (time.time(), error_type, message, traceback, source),
                )
                self._conn.commit()
            except sqlite3.Error as e:
                logger.error(f"Failed to log error: {e}")

    async def get_event_logs(
        self,
        limit: int = 100,
        event_type: Optional[str] = None,
        since: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Get event logs from database.

        Args:
            limit: Maximum number of logs to return
            event_type: Optional filter by event type
            since: Optional timestamp to filter from

        Returns:
            List of event log dictionaries
        """
        query = "SELECT * FROM event_logs WHERE 1=1"
        params: List[Any] = []

        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)
        if since:
            query += " AND timestamp >= ?"
            params.append(since)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        try:
            cursor = self._conn.execute(query, params)
            rows = cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "timestamp": row[1],
                    "event_type": row[2],
                    "source": row[3],
                    "data": row[4],
                    "priority": row[5],
                }
                for row in rows
            ]
        except sqlite3.Error as e:
            logger.error(f"Failed to query event logs: {e}")
            return []

    async def get_error_logs(
        self,
        limit: int = 50,
        since: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Get error logs from database.

        Args:
            limit: Maximum number of logs to return
            since: Optional timestamp to filter from

        Returns:
            List of error log dictionaries
        """
        query = "SELECT * FROM error_logs WHERE 1=1"
        params: List[Any] = []

        if since:
            query += " AND timestamp >= ?"
            params.append(since)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        try:
            cursor = self._conn.execute(query, params)
            rows = cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "timestamp": row[1],
                    "error_type": row[2],
                    "message": row[3],
                    "traceback": row[4],
                    "source": row[5],
                }
                for row in rows
            ]
        except sqlite3.Error as e:
            logger.error(f"Failed to query error logs: {e}")
            return []

    async def get_metrics(
        self,
        limit: int = 100,
        since: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Get system metrics from database.

        Args:
            limit: Maximum number of metrics to return
            since: Optional timestamp to filter from

        Returns:
            List of metric dictionaries
        """
        query = "SELECT * FROM system_metrics WHERE 1=1"
        params: List[Any] = []

        if since:
            query += " AND timestamp >= ?"
            params.append(since)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        try:
            cursor = self._conn.execute(query, params)
            rows = cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "timestamp": row[1],
                    "cpu_percent": row[2],
                    "memory_percent": row[3],
                    "fps": row[4],
                    "state": row[5],
                    "temperature": row[6],
                }
                for row in rows
            ]
        except sqlite3.Error as e:
            logger.error(f"Failed to query metrics: {e}")
            return []

    async def cleanup_old_logs(self) -> None:
        """Remove logs older than retention period."""
        cutoff = time.time() - (self._retention_days * 86400)
        async with self._lock:
            try:
                self._conn.execute("DELETE FROM event_logs WHERE timestamp < ?", (cutoff,))
                self._conn.execute("DELETE FROM error_logs WHERE timestamp < ?", (cutoff,))
                self._conn.execute("DELETE FROM system_metrics WHERE timestamp < ?", (cutoff,))
                self._conn.commit()
                logger.info(f"Cleaned up logs older than {self._retention_days} days")
            except sqlite3.Error as e:
                logger.error(f"Failed to cleanup logs: {e}")

    async def _collect_metrics(self) -> None:
        """Periodically collect and store system metrics."""
        while self._running:
            try:
                import psutil
                cpu = psutil.cpu_percent(interval=0.5)
                memory = psutil.virtual_memory().percent

                # Try to get temperature
                temp = None
                try:
                    with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                        temp = float(f.read().strip()) / 1000.0
                except (IOError, FileNotFoundError, ValueError):
                    pass

                async with self._lock:
                    self._conn.execute(
                        """INSERT INTO system_metrics (timestamp, cpu_percent, memory_percent, temperature)
                           VALUES (?, ?, ?, ?)""",
                        (time.time(), cpu, memory, temp),
                    )
                    self._conn.commit()

                await asyncio.sleep(30)
            except asyncio.CancelledError:
                break
            except ImportError:
                await asyncio.sleep(60)
            except Exception as e:
                logger.error(f"Metrics collection error: {e}")
                await asyncio.sleep(30)

    async def _log_system_error(self, event: Event) -> None:
        """Log system error events.

        Args:
            event: Error event from event bus
        """
        await self.log_error(
            error_type=event.data.get("error_type", "UNKNOWN"),
            message=str(event.data.get("message", "No message")),
            source=event.source,
        )

    async def _log_state_change(self, event: Event) -> None:
        """Log state change events.

        Args:
            event: State change event from event bus
        """
        await self.log_event(event)

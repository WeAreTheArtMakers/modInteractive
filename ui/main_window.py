"""Main window UI for modInteractive kiosk system.

Provides the primary graphical interface with dark/light theme support,
system status monitoring, and touch-friendly controls.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from PySide6.QtCore import (
    Qt,
    QTimer,
    QSize,
    QPoint,
    Signal,
    Slot,
    QPropertyAnimation,
    QEasingCurve,
)
from PySide6.QtGui import (
    QAction,
    QColor,
    QFont,
    QIcon,
    QKeySequence,
    QPalette,
    QPixmap,
    QCloseEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QStatusBar,
    QSystemTrayIcon,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.event_bus import Event, EventBus, EventPriority, SystemEvents
from core.state_machine import SystemState
from core.config_service import ConfigService

if TYPE_CHECKING:
    from core.state_machine import StateMachine

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────

TOUCH_MIN_SIZE = 48  # Minimum touch target size in pixels
ANIMATION_DURATION = 200  # UI animation duration in ms
STATUS_POLL_INTERVAL = 500  # Status update polling interval in ms

DARK_THEME_STYLESHEET = """
/* ── modInteractive Dark Theme ── */

QMainWindow {
    background-color: #1E1E2E;
}

QWidget {
    background-color: #1E1E2E;
    color: #FFFFFF;
    font-family: "Segoe UI", "SF Pro Display", "DejaVu Sans", "Noto Sans", -apple-system, sans-serif;
    font-size: 13px;
}

/* ── Tab Widget ── */
QTabWidget::pane {
    border: none;
    background-color: #1E1E2E;
}

QTabWidget::tab-bar {
    alignment: center;
}

QTabBar::tab {
    background-color: #2D2D3F;
    color: #AAAAAA;
    border: none;
    min-width: 100px;
    min-height: 44px;
    padding: 8px 16px;
    margin: 2px;
    border-radius: 8px;
    font-size: 13px;
}

QTabBar::tab:selected {
    background-color: #4A90D9;
    color: #FFFFFF;
    font-weight: bold;
}

QTabBar::tab:hover:!selected {
    background-color: #3A3A4F;
    color: #FFFFFF;
}

/* ── Buttons ── */
QPushButton {
    background-color: #4A90D9;
    color: #FFFFFF;
    border: none;
    border-radius: 8px;
    min-width: 48px;
    min-height: 48px;
    padding: 8px 20px;
    font-size: 14px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #5BA0E9;
}

QPushButton:pressed {
    background-color: #3A80C9;
}

QPushButton:disabled {
    background-color: #3A3A4F;
    color: #666666;
}

QPushButton#dangerButton {
    background-color: #E74C3C;
}

QPushButton#dangerButton:hover {
    background-color: #F05A4A;
}

QPushButton#successButton {
    background-color: #2ECC71;
}

QPushButton#successButton:hover {
    background-color: #3DDC81;
}

QPushButton#warningButton {
    background-color: #F39C12;
    color: #1E1E2E;
}

QPushButton#warningButton:hover {
    background-color: #F4A92A;
}

/* ── Cards / Group Boxes ── */
QGroupBox {
    background-color: #2D2D3F;
    border: 1px solid #3A3A4F;
    border-radius: 12px;
    padding: 20px 16px 16px 16px;
    margin-top: 8px;
    font-size: 14px;
    font-weight: 600;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 2px 10px;
    color: #AAAAAA;
    font-weight: 600;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 1px;
}

/* ── Status Indicators ── */
QLabel#statusOk {
    color: #2ECC71;
    font-weight: bold;
}

QLabel#statusWarning {
    color: #F39C12;
    font-weight: bold;
}

QLabel#statusError {
    color: #E74C3C;
    font-weight: bold;
}

QLabel#statusInactive {
    color: #666666;
}

/* ── Labels ── */
QLabel {
    background: transparent;
    color: #FFFFFF;
}

QLabel#cardTitle {
    font-size: 16px;
    font-weight: 700;
    color: #FFFFFF;
}

QLabel#cardValue {
    font-size: 24px;
    font-weight: 300;
    color: #4A90D9;
}

QLabel#sectionHeader {
    font-size: 18px;
    font-weight: 700;
    color: #FFFFFF;
    padding: 8px 0;
}

/* ── Sliders ── */
QSlider::groove:horizontal {
    background: #3A3A4F;
    height: 6px;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background: #4A90D9;
    width: 24px;
    height: 24px;
    margin: -9px 0;
    border-radius: 12px;
}

QSlider::sub-page:horizontal {
    background: #4A90D9;
    border-radius: 3px;
}

/* ── Spin Boxes ── */
QSpinBox, QDoubleSpinBox {
    background-color: #2D2D3F;
    border: 1px solid #3A3A4F;
    border-radius: 6px;
    padding: 6px 10px;
    min-height: 32px;
    color: #FFFFFF;
    font-size: 14px;
}

QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: #4A90D9;
}

/* ── Combo Box ── */
QComboBox {
    background-color: #2D2D3F;
    border: 1px solid #3A3A4F;
    border-radius: 6px;
    padding: 6px 10px;
    min-height: 32px;
    color: #FFFFFF;
    font-size: 14px;
}

QComboBox:focus {
    border-color: #4A90D9;
}

QComboBox::drop-down {
    border: none;
    width: 30px;
}

QComboBox QAbstractItemView {
    background-color: #2D2D3F;
    border: 1px solid #3A3A4F;
    selection-background-color: #4A90D9;
    color: #FFFFFF;
}

/* ── Check Box ── */
QCheckBox {
    spacing: 8px;
    min-height: 24px;
    font-size: 14px;
}

QCheckBox::indicator {
    width: 20px;
    height: 20px;
    border-radius: 4px;
    border: 2px solid #4A90D9;
    background-color: #2D2D3F;
}

QCheckBox::indicator:checked {
    background-color: #4A90D9;
}

/* ── Scroll Area ── */
QScrollArea {
    border: none;
    background-color: transparent;
}

QScrollBar:vertical {
    background: #2D2D3F;
    width: 10px;
    border-radius: 5px;
}

QScrollBar::handle:vertical {
    background: #4A90D9;
    min-height: 40px;
    border-radius: 5px;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

/* ── Status Bar ── */
QStatusBar {
    background-color: #2D2D3F;
    color: #AAAAAA;
    border-top: 1px solid #3A3A4F;
    font-size: 12px;
    padding: 4px 12px;
}

/* ── Frames ── */
QFrame#separator {
    background-color: #3A3A4F;
    max-height: 1px;
}

/* ── Tool Tips ── */
QToolTip {
    background-color: #2D2D3F;
    color: #FFFFFF;
    border: 1px solid #4A90D9;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
}
"""

LIGHT_THEME_STYLESHEET = """
/* ── modInteractive Light Theme ── */

QMainWindow {
    background-color: #F5F5F5;
}

QWidget {
    background-color: #F5F5F5;
    color: #2C3E50;
    font-family: "Segoe UI", "SF Pro Display", "DejaVu Sans", "Noto Sans", -apple-system, sans-serif;
    font-size: 13px;
}

QTabWidget::pane {
    border: none;
    background-color: #F5F5F5;
}

QTabWidget::tab-bar {
    alignment: center;
}

QTabBar::tab {
    background-color: #E0E0E0;
    color: #555555;
    border: none;
    min-width: 100px;
    min-height: 44px;
    padding: 8px 16px;
    margin: 2px;
    border-radius: 8px;
    font-size: 13px;
}

QTabBar::tab:selected {
    background-color: #4A90D9;
    color: #FFFFFF;
    font-weight: bold;
}

QTabBar::tab:hover:!selected {
    background-color: #D0D0D0;
    color: #2C3E50;
}

QPushButton {
    background-color: #4A90D9;
    color: #FFFFFF;
    border: none;
    border-radius: 8px;
    min-width: 48px;
    min-height: 48px;
    padding: 8px 20px;
    font-size: 14px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #5BA0E9;
}

QPushButton:pressed {
    background-color: #3A80C9;
}

QPushButton:disabled {
    background-color: #CCCCCC;
    color: #888888;
}

QPushButton#dangerButton {
    background-color: #E74C3C;
}

QPushButton#successButton {
    background-color: #2ECC71;
}

QPushButton#warningButton {
    background-color: #F39C12;
    color: #FFFFFF;
}

QGroupBox {
    background-color: #FFFFFF;
    border: 1px solid #E0E0E0;
    border-radius: 12px;
    padding: 20px 16px 16px 16px;
    margin-top: 8px;
    font-size: 14px;
    font-weight: 600;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 2px 10px;
    color: #888888;
    font-weight: 600;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 1px;
}

QLabel#statusOk {
    color: #2ECC71;
    font-weight: bold;
}

QLabel#statusWarning {
    color: #F39C12;
    font-weight: bold;
}

QLabel#statusError {
    color: #E74C3C;
    font-weight: bold;
}

QLabel#statusInactive {
    color: #AAAAAA;
}

QLabel {
    background: transparent;
    color: #2C3E50;
}

QLabel#cardTitle {
    font-size: 16px;
    font-weight: 700;
    color: #2C3E50;
}

QLabel#cardValue {
    font-size: 24px;
    font-weight: 300;
    color: #4A90D9;
}

QLabel#sectionHeader {
    font-size: 18px;
    font-weight: 700;
    color: #2C3E50;
    padding: 8px 0;
}

QSlider::groove:horizontal {
    background: #E0E0E0;
    height: 6px;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background: #4A90D9;
    width: 24px;
    height: 24px;
    margin: -9px 0;
    border-radius: 12px;
}

QSlider::sub-page:horizontal {
    background: #4A90D9;
    border-radius: 3px;
}

QSpinBox, QDoubleSpinBox {
    background-color: #FFFFFF;
    border: 1px solid #E0E0E0;
    border-radius: 6px;
    padding: 6px 10px;
    min-height: 32px;
    color: #2C3E50;
    font-size: 14px;
}

QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: #4A90D9;
}

QComboBox {
    background-color: #FFFFFF;
    border: 1px solid #E0E0E0;
    border-radius: 6px;
    padding: 6px 10px;
    min-height: 32px;
    color: #2C3E50;
    font-size: 14px;
}

QComboBox:focus {
    border-color: #4A90D9;
}

QComboBox::drop-down {
    border: none;
    width: 30px;
}

QComboBox QAbstractItemView {
    background-color: #FFFFFF;
    border: 1px solid #E0E0E0;
    selection-background-color: #4A90D9;
    color: #2C3E50;
}

QCheckBox {
    spacing: 8px;
    min-height: 24px;
    font-size: 14px;
}

QCheckBox::indicator {
    width: 20px;
    height: 20px;
    border-radius: 4px;
    border: 2px solid #4A90D9;
    background-color: #FFFFFF;
}

QCheckBox::indicator:checked {
    background-color: #4A90D9;
}

QScrollArea {
    border: none;
    background-color: transparent;
}

QScrollBar:vertical {
    background: #E0E0E0;
    width: 10px;
    border-radius: 5px;
}

QScrollBar::handle:vertical {
    background: #4A90D9;
    min-height: 40px;
    border-radius: 5px;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QStatusBar {
    background-color: #FFFFFF;
    color: #888888;
    border-top: 1px solid #E0E0E0;
    font-size: 12px;
    padding: 4px 12px;
}

QFrame#separator {
    background-color: #E0E0E0;
    max-height: 1px;
}

QToolTip {
    background-color: #FFFFFF;
    color: #2C3E50;
    border: 1px solid #4A90D9;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
}
"""


# ──────────────────────────────────────────────
# Status Widget
# ──────────────────────────────────────────────

class StatusIndicator(QLabel):
    """A colored status indicator dot with label for system status displays.

    Shows a colored circle indicator and status text for a system component.
    """

    def __init__(self, label: str, parent: Optional[QWidget] = None) -> None:
        """Initialize status indicator.

        Args:
            label: Display label for this indicator
            parent: Parent widget
        """
        super().__init__(parent)
        self._status_label = label
        self._status: str = "inactive"
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Build the indicator layout."""
        layout = QHBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(12)

        # Indicator dot
        self._dot = QLabel()
        self._dot.setFixedSize(14, 14)
        self._dot.setObjectName("statusInactive")
        self._dot.setStyleSheet(
            "background-color: #666666; border-radius: 7px;"
        )
        layout.addWidget(self._dot, alignment=Qt.AlignVCenter)

        # Label text
        self._label_widget = QLabel(self._status_label)
        self._label_widget.setObjectName("cardTitle")
        layout.addWidget(self._label_widget, alignment=Qt.AlignVCenter)

        # Status text
        self._status_text = QLabel("Inactive")
        self._status_text.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addStretch()
        layout.addWidget(self._status_text)

        self.setLayout(layout)

    def set_status(self, status: str) -> None:
        """Update the indicator status.

        Args:
            status: One of 'ok', 'warning', 'error', 'inactive'
        """
        self._status = status
        colors = {
            "ok": "#2ECC71",
            "warning": "#F39C12",
            "error": "#E74C3C",
            "inactive": "#666666",
        }
        labels = {
            "ok": "OK",
            "warning": "Warning",
            "error": "Error",
            "inactive": "Inactive",
        }

        color = colors.get(status, "#666666")
        self._dot.setStyleSheet(
            f"background-color: {color}; border-radius: 7px;"
        )
        self._status_text.setText(labels.get(status, "Unknown"))
        self._status_text.setObjectName(f"status{status.capitalize()}")

        # Force style refresh
        self._status_text.style().unpolish(self._status_text)
        self._status_text.style().polish(self._status_text)


# ──────────────────────────────────────────────
# Stat Card Widget
# ──────────────────────────────────────────────

class StatCard(QFrame):
    """A styled card widget for displaying a labeled statistic value.

    Used in the dashboard to show metrics like frame rate, uptime, etc.
    """

    def __init__(
        self,
        title: str,
        value: str = "--",
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initialize stat card.

        Args:
            title: Card title/label
            value: Initial display value
            parent: Parent widget
        """
        super().__init__(parent)
        self._title = title
        self._value = value
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Build the card layout."""
        self.setObjectName("statCard")
        self.setStyleSheet("""
            StatCard {
                background-color: #2D2D3F;
                border: 1px solid #3A3A4F;
                border-radius: 12px;
                padding: 16px;
            }
        """)
        self.setMinimumSize(140, 80)

        layout = QVBoxLayout()
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        # Title
        title_label = QLabel(self._title.upper())
        title_label.setStyleSheet(
            "font-size: 11px; font-weight: 600; letter-spacing: 1px;"
            "color: #AAAAAA; background: transparent;"
        )
        layout.addWidget(title_label)

        # Value
        self._value_label = QLabel(self._value)
        self._value_label.setObjectName("cardValue")
        self._value_label.setStyleSheet(
            "font-size: 28px; font-weight: 300; color: #4A90D9;"
            "background: transparent;"
        )
        layout.addWidget(self._value_label)

        self.setLayout(layout)

    def set_value(self, value: str) -> None:
        """Update the displayed value.

        Args:
            value: New value string
        """
        self._value = value
        self._value_label.setText(value)


# ──────────────────────────────────────────────
# Dashboard Tab
# ──────────────────────────────────────────────

class DashboardTab(QWidget):
    """Dashboard tab showing system status and controls.

    Displays status indicators for core services (Camera, GPU, Video,
    Detection), Start/Stop buttons, and the last trigger timestamp.
    """

    def __init__(
        self,
        event_bus: EventBus,
        state_machine: StateMachine,
        config_service: ConfigService,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initialize dashboard tab.

        Args:
            event_bus: System event bus
            state_machine: System state machine
            config_service: Configuration service
            parent: Parent widget
        """
        super().__init__(parent)
        self._event_bus = event_bus
        self._state_machine = state_machine
        self._config_service = config_service

        self._status_indicators: Dict[str, StatusIndicator] = {}
        self._system_running = False
        self._last_trigger_time: Optional[float] = None

        self._setup_ui()
        self._connect_signals()
        self._start_polling()

    def _setup_ui(self) -> None:
        """Build the dashboard layout."""
        layout = QVBoxLayout()
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        # ── Header ──
        header = QLabel("System Dashboard")
        header.setObjectName("sectionHeader")
        layout.addWidget(header)

        # ── Status Grid ──
        status_grid = QHBoxLayout()
        status_grid.setSpacing(16)

        components = [
            ("Camera Feed", "camera"),
            ("GPU Status", "gpu"),
            ("Video Engine", "video"),
            ("Detection", "detection"),
        ]

        for label, key in components:
            group = QGroupBox(label)
            group.setStyleSheet("""
                QGroupBox {
                    background-color: #2D2D3F;
                    border: 1px solid #3A3A4F;
                    border-radius: 12px;
                    font-size: 13px;
                    font-weight: 600;
                }
            """)
            group.setMinimumSize(200, 80)

            inner = QVBoxLayout(group)
            inner.setContentsMargins(12, 20, 12, 12)

            indicator = StatusIndicator(label)
            self._status_indicators[key] = indicator
            inner.addWidget(indicator)

            group.setLayout(inner)
            status_grid.addWidget(group)

        layout.addLayout(status_grid)

        # ── Stats Row ──
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(16)

        self._stat_cards: Dict[str, StatCard] = {}

        stat_defs = [
            ("Uptime", "0m"),
            ("Frame Rate", "0 FPS"),
            ("Trigger Count", "0"),
            ("Video Queue", "0"),
        ]

        for title, default_val in stat_defs:
            card = StatCard(title, default_val)
            key = title.lower().replace(" ", "_")
            self._stat_cards[key] = card
            stats_layout.addWidget(card)

        layout.addLayout(stats_layout)

        # ── Last Trigger ──
        trigger_card = QGroupBox("Last Trigger")
        trigger_card.setStyleSheet("""
            QGroupBox {
                background-color: #2D2D3F;
                border: 1px solid #3A3A4F;
                border-radius: 12px;
                font-size: 13px;
                font-weight: 600;
            }
        """)
        trigger_layout = QHBoxLayout(trigger_card)

        self._trigger_label = QLabel("No trigger recorded")
        self._trigger_label.setObjectName("cardTitle")
        self._trigger_label.setStyleSheet(
            "font-size: 16px; background: transparent;"
        )
        trigger_layout.addWidget(self._trigger_label)

        trigger_layout.addStretch()

        trigger_time_label = QLabel("--")
        trigger_time_label.setObjectName("cardValue")
        trigger_time_label.setStyleSheet(
            "font-size: 16px; background: transparent;"
        )
        self._trigger_time_label = trigger_time_label
        trigger_layout.addWidget(trigger_time_label)

        layout.addWidget(trigger_card)

        # ── Control Buttons ──
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(16)

        self._start_btn = QPushButton("▶  Start System")
        self._start_btn.setObjectName("successButton")
        self._start_btn.setMinimumSize(180, 56)
        self._start_btn.setIconSize(QSize(24, 24))
        btn_layout.addWidget(self._start_btn)

        self._stop_btn = QPushButton("■  Stop System")
        self._stop_btn.setObjectName("dangerButton")
        self._stop_btn.setMinimumSize(180, 56)
        self._stop_btn.setEnabled(False)
        btn_layout.addWidget(self._stop_btn)

        btn_layout.addStretch()

        self._restart_btn = QPushButton("↻  Restart Services")
        self._restart_btn.setObjectName("warningButton")
        self._restart_btn.setMinimumSize(180, 56)
        btn_layout.addWidget(self._restart_btn)

        layout.addLayout(btn_layout)
        layout.addStretch()

        self.setLayout(layout)

    def _connect_signals(self) -> None:
        """Connect button signals and event bus subscriptions."""
        self._start_btn.clicked.connect(self._on_start_clicked)
        self._stop_btn.clicked.connect(self._on_stop_clicked)
        self._restart_btn.clicked.connect(self._on_restart_clicked)

        # Subscribe to system events for status updates
        self._event_bus.subscribe(
            SystemEvents.CAMERA_CONNECTED,
            self._on_event_callback,
        )
        self._event_bus.subscribe(
            SystemEvents.CAMERA_DISCONNECTED,
            self._on_event_callback,
        )
        self._event_bus.subscribe(
            SystemEvents.CAMERA_ERROR,
            self._on_event_callback,
        )
        self._event_bus.subscribe(
            SystemEvents.PERSON_DETECTED,
            self._on_event_callback,
        )
        self._event_bus.subscribe(
            SystemEvents.PLAYBACK_STARTED,
            self._on_event_callback,
        )
        self._event_bus.subscribe(
            SystemEvents.PLAYBACK_ERROR,
            self._on_event_callback,
        )
        self._event_bus.subscribe(
            SystemEvents.SYSTEM_ERROR,
            self._on_event_callback,
        )

    def _start_polling(self) -> None:
        """Start a timer to periodically refresh status."""
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._refresh_status)
        self._poll_timer.start(STATUS_POLL_INTERVAL)

    @Slot()
    def _refresh_status(self) -> None:
        """Poll system state and update UI indicators."""
        state = self._state_machine.current_state

        # Update camera status
        camera_ok = state in (
            SystemState.IDLE,
            SystemState.DETECTING,
            SystemState.PERSON_CONFIRMED,
            SystemState.FADE_IN,
            SystemState.PLAYING,
        )
        self._status_indicators["camera"].set_status(
            "ok" if camera_ok else "inactive"
        )

        # GPU status (always ok for now, real GPU check would go here)
        self._status_indicators["gpu"].set_status("ok")

        # Video engine status
        video_ok = state in (
            SystemState.PLAYING,
            SystemState.FADE_IN,
            SystemState.FADE_OUT,
        )
        self._status_indicators["video"].set_status(
            "ok" if video_ok else "inactive"
        )

        # Detection status
        detection_ok = state in (
            SystemState.DETECTING,
            SystemState.PERSON_CONFIRMED,
        )
        self._status_indicators["detection"].set_status(
            "ok" if detection_ok else "inactive"
        )

        # Error state
        if state == SystemState.ERROR:
            for key in self._status_indicators:
                self._status_indicators[key].set_status("error")

        # Update stat cards
        uptime_seconds = self._state_machine.state_duration
        minutes = int(uptime_seconds // 60)
        seconds = int(uptime_seconds % 60)
        self._stat_cards["uptime"].set_value(f"{minutes}m {seconds}s")

        # Simulated values - in production these would come from services
        self._stat_cards["frame_rate"].set_value("30 FPS")
        self._stat_cards["video_queue"].set_value("12")

        # Update last trigger display
        if self._last_trigger_time is not None:
            elapsed = time.time() - self._last_trigger_time
            if elapsed < 60:
                self._trigger_time_label.setText(f"{int(elapsed)}s ago")
            elif elapsed < 3600:
                self._trigger_time_label.setText(f"{int(elapsed / 60)}m ago")
            else:
                self._trigger_time_label.setText(
                    f"{int(elapsed / 3600)}h ago"
                )

    async def _on_event_callback(self, event: Event) -> None:
        """Handle event bus events for status updates.

        Args:
            event: The received event
        """
        if event.event_type == SystemEvents.PERSON_DETECTED:
            self._last_trigger_time = time.time()
            self._trigger_label.setText("Person Detected")
            # Update trigger count
            current = self._stat_cards["trigger_count"]._value
            try:
                new_count = int(current) + 1
            except (ValueError, TypeError):
                new_count = 1
            self._stat_cards["trigger_count"].set_value(str(new_count))

    @Slot()
    def _on_start_clicked(self) -> None:
        """Handle Start System button click."""
        self._system_running = True
        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        logger.info("System start requested from UI")

    @Slot()
    def _on_stop_clicked(self) -> None:
        """Handle Stop System button click."""
        self._system_running = False
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        logger.info("System stop requested from UI")

    @Slot()
    def _on_restart_clicked(self) -> None:
        """Handle Restart Services button click."""
        logger.info("Service restart requested from UI")


# ──────────────────────────────────────────────
# Video Manager Tab
# ──────────────────────────────────────────────

class VideoManagerTab(QWidget):
    """Tab for managing video playlists and playback settings."""

    def __init__(
        self,
        event_bus: EventBus,
        config_service: ConfigService,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initialize video manager tab.

        Args:
            event_bus: System event bus
            config_service: Configuration service
            parent: Parent widget
        """
        super().__init__(parent)
        self._event_bus = event_bus
        self._config_service = config_service
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Build the video manager layout."""
        layout = QVBoxLayout()
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        header = QLabel("Video Manager")
        header.setObjectName("sectionHeader")
        layout.addWidget(header)

        # ── Playlist Controls ──
        playlist_group = QGroupBox("Playlist Controls")
        playlist_layout = QVBoxLayout(playlist_group)
        playlist_layout.setSpacing(12)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        add_video_btn = QPushButton("+  Add Videos")
        add_video_btn.setMinimumSize(160, 48)
        btn_row.addWidget(add_video_btn)

        remove_btn = QPushButton("−  Remove Selected")
        remove_btn.setMinimumSize(160, 48)
        btn_row.addWidget(remove_btn)

        clear_btn = QPushButton("✕  Clear Playlist")
        clear_btn.setMinimumSize(160, 48)
        btn_row.addWidget(clear_btn)

        btn_row.addStretch()
        playlist_layout.addLayout(btn_row)

        controls_row = QHBoxLayout()
        controls_row.setSpacing(12)

        shuffle_btn = QPushButton("🔀  Shuffle")
        shuffle_btn.setMinimumSize(120, 48)
        controls_row.addWidget(shuffle_btn)

        loop_cb = QCheckBox("Loop Videos")
        loop_cb.setChecked(
            self._config_service.get("video.loop_videos", False)
        )
        controls_row.addWidget(loop_cb)

        controls_row.addStretch()
        playlist_layout.addLayout(controls_row)

        layout.addWidget(playlist_group)

        # ── Playback Mode ──
        mode_group = QGroupBox("Playback Mode")
        mode_layout = QHBoxLayout(mode_group)
        mode_layout.setSpacing(12)

        mode_label = QLabel("Mode:")
        mode_layout.addWidget(mode_label)

        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["sequential", "random", "single"])
        current_mode = self._config_service.get("video.playback_mode", "random")
        self._mode_combo.setCurrentText(current_mode)
        self._mode_combo.setMinimumSize(160, 40)
        mode_layout.addWidget(self._mode_combo)

        mode_layout.addStretch()
        layout.addWidget(mode_group)

        # ── Video Preview ──
        preview_group = QGroupBox("Video Preview")
        preview_layout = QVBoxLayout(preview_group)
        self._preview_label = QLabel("🎬 Video Preview\n\nSelect a video to preview")
        self._preview_label.setAlignment(Qt.AlignCenter)
        self._preview_label.setMinimumSize(480, 270)
        self._preview_label.setStyleSheet(
            "background-color: #1A1A2E; border: 2px solid #3A3A4F; "
            "border-radius: 8px; color: #666666; font-size: 14px;"
        )
        preview_layout.addWidget(self._preview_label)
        layout.addWidget(preview_group)

        # ── Playback Settings ──
        settings_group = QGroupBox("Video Settings")
        settings_layout = QFormLayout(settings_group)
        settings_layout.setSpacing(12)
        settings_layout.setLabelAlignment(Qt.AlignRight)

        self._fade_in_spin = QDoubleSpinBox()
        self._fade_in_spin.setRange(0.0, 5.0)
        self._fade_in_spin.setSingleStep(0.1)
        self._fade_in_spin.setValue(
            self._config_service.get("video.fade_in_duration", 1.0)
        )
        self._fade_in_spin.setSuffix(" s")
        self._fade_in_spin.setMinimumSize(120, 40)
        settings_layout.addRow("Fade In:", self._fade_in_spin)

        self._fade_out_spin = QDoubleSpinBox()
        self._fade_out_spin.setRange(0.0, 5.0)
        self._fade_out_spin.setSingleStep(0.1)
        self._fade_out_spin.setValue(
            self._config_service.get("video.fade_out_duration", 1.0)
        )
        self._fade_out_spin.setSuffix(" s")
        self._fade_out_spin.setMinimumSize(120, 40)
        settings_layout.addRow("Fade Out:", self._fade_out_spin)

        self._volume_slider = QSlider(Qt.Horizontal)
        self._volume_slider.setRange(0, 100)
        self._volume_slider.setValue(
            self._config_service.get("video.volume", 80)
        )
        self._volume_slider.setMinimumSize(200, 40)
        settings_layout.addRow("Volume:", self._volume_slider)

        volume_val = QLabel(f"{self._volume_slider.value()}%")
        volume_val.setObjectName("cardValue")
        volume_val.setStyleSheet("font-size: 16px; background: transparent;")
        self._volume_slider.valueChanged.connect(
            lambda v: volume_val.setText(f"{v}%")
        )
        settings_layout.addRow("", volume_val)

        # ── Video Rotation ──
        rotation_label = QLabel("Rotation:")
        settings_layout.addRow(rotation_label)

        rotation_btn_layout = QHBoxLayout()
        rotation_btn_layout.setSpacing(8)
        self._rotation_btns = {}
        for angle in [0, 90, 180, 270]:
            btn = QPushButton(f"{angle}°")
            btn.setCheckable(True)
            btn.setMinimumSize(60, 40)
            btn.setChecked(angle == 0)
            self._rotation_btns[angle] = btn
            rotation_btn_layout.addWidget(btn)

        rotation_btn_layout.addStretch()
        settings_layout.addRow("", rotation_btn_layout)

        layout.addWidget(settings_group)

        apply_btn = QPushButton("✓  Apply Settings")
        apply_btn.setObjectName("successButton")
        apply_btn.setMinimumSize(180, 52)
        layout.addWidget(apply_btn, alignment=Qt.AlignLeft)

        layout.addStretch()
        self.setLayout(layout)


# ──────────────────────────────────────────────
# Camera Panel Tab
# ──────────────────────────────────────────────

class CameraPanelTab(QWidget):
    """Tab for camera configuration and preview."""

    def __init__(
        self,
        event_bus: EventBus,
        config_service: ConfigService,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initialize camera panel tab.

        Args:
            event_bus: System event bus
            config_service: Configuration service
            parent: Parent widget
        """
        super().__init__(parent)
        self._event_bus = event_bus
        self._config_service = config_service
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Build the camera panel layout."""
        layout = QVBoxLayout()
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        header = QLabel("Camera Panel")
        header.setObjectName("sectionHeader")
        layout.addWidget(header)

        # ── Camera Preview ──
        preview_group = QGroupBox("Live Preview")
        preview_layout = QVBoxLayout(preview_group)

        self._preview_label = QLabel("Camera Preview")
        self._preview_label.setAlignment(Qt.AlignCenter)
        self._preview_label.setMinimumSize(480, 320)
        self._preview_label.setStyleSheet("""
            background-color: #1A1A2E;
            border: 2px solid #3A3A4F;
            border-radius: 8px;
            color: #666666;
            font-size: 16px;
        """)
        preview_layout.addWidget(self._preview_label)

        layout.addWidget(preview_group)

        # ── Camera Settings ──
        settings_group = QGroupBox("Camera Settings")
        settings_layout = QFormLayout(settings_group)
        settings_layout.setSpacing(12)
        settings_layout.setLabelAlignment(Qt.AlignRight)

        self._device_spin = QSpinBox()
        self._device_spin.setRange(0, 10)
        self._device_spin.setValue(
            self._config_service.get("camera.device_id", 0)
        )
        self._device_spin.setMinimumSize(120, 40)
        settings_layout.addRow("Device ID:", self._device_spin)

        res_layout = QHBoxLayout()
        self._width_spin = QSpinBox()
        self._width_spin.setRange(320, 3840)
        self._width_spin.setSingleStep(160)
        self._width_spin.setValue(
            self._config_service.get("camera.resolution.width", 640)
        )
        self._width_spin.setMinimumSize(100, 40)
        res_layout.addWidget(self._width_spin)

        res_layout.addWidget(QLabel("×"))

        self._height_spin = QSpinBox()
        self._height_spin.setRange(240, 2160)
        self._height_spin.setSingleStep(120)
        self._height_spin.setValue(
            self._config_service.get("camera.resolution.height", 480)
        )
        self._height_spin.setMinimumSize(100, 40)
        res_layout.addWidget(self._height_spin)

        settings_layout.addRow("Resolution:", res_layout)

        self._fps_spin = QSpinBox()
        self._fps_spin.setRange(1, 60)
        self._fps_spin.setValue(
            self._config_service.get("camera.fps", 15)
        )
        self._fps_spin.setMinimumSize(120, 40)
        settings_layout.addRow("FPS:", self._fps_spin)

        self._auto_reconnect_cb = QCheckBox("Auto Reconnect")
        self._auto_reconnect_cb.setChecked(
            self._config_service.get("camera.auto_reconnect", True)
        )
        settings_layout.addRow("", self._auto_reconnect_cb)

        layout.addWidget(settings_group)

        # ── Control Buttons ──
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        apply_btn = QPushButton("✓  Apply Camera Settings")
        apply_btn.setObjectName("successButton")
        apply_btn.setMinimumSize(200, 52)
        btn_layout.addWidget(apply_btn)

        restart_btn = QPushButton("↻  Restart Camera")
        restart_btn.setMinimumSize(180, 52)
        btn_layout.addWidget(restart_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        layout.addStretch()
        self.setLayout(layout)


# ──────────────────────────────────────────────
# Detection Settings Tab
# ──────────────────────────────────────────────

class DetectionSettingsTab(QWidget):
    """Tab for configuring detection parameters."""

    def __init__(
        self,
        event_bus: EventBus,
        config_service: ConfigService,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initialize detection settings tab.

        Args:
            event_bus: System event bus
            config_service: Configuration service
            parent: Parent widget
        """
        super().__init__(parent)
        self._event_bus = event_bus
        self._config_service = config_service
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Build the detection settings layout."""
        layout = QVBoxLayout()
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        header = QLabel("Detection Settings")
        header.setObjectName("sectionHeader")
        layout.addWidget(header)

        # ── Detection Parameters ──
        params_group = QGroupBox("Detection Parameters")
        params_layout = QFormLayout(params_group)
        params_layout.setSpacing(16)
        params_layout.setLabelAlignment(Qt.AlignRight)

        self._confidence_spin = QDoubleSpinBox()
        self._confidence_spin.setRange(0.01, 0.99)
        self._confidence_spin.setSingleStep(0.05)
        self._confidence_spin.setDecimals(2)
        self._confidence_spin.setValue(
            self._config_service.get("detection.confidence_threshold", 0.65)
        )
        self._confidence_spin.setMinimumSize(140, 40)
        params_layout.addRow("Confidence Threshold:", self._confidence_spin)

        self._motion_spin = QDoubleSpinBox()
        self._motion_spin.setRange(0.001, 0.1)
        self._motion_spin.setSingleStep(0.005)
        self._motion_spin.setDecimals(3)
        self._motion_spin.setValue(
            self._config_service.get("detection.motion_sensitivity", 0.02)
        )
        self._motion_spin.setMinimumSize(140, 40)
        params_layout.addRow("Motion Sensitivity:", self._motion_spin)

        self._cooldown_spin = QSpinBox()
        self._cooldown_spin.setRange(0, 300)
        self._cooldown_spin.setSuffix(" s")
        self._cooldown_spin.setValue(
            self._config_service.get("detection.cooldown_seconds", 10)
        )
        self._cooldown_spin.setMinimumSize(140, 40)
        params_layout.addRow("Cooldown Duration:", self._cooldown_spin)

        self._frame_skip_spin = QSpinBox()
        self._frame_skip_spin.setRange(0, 10)
        self._frame_skip_spin.setValue(
            self._config_service.get("detection.frame_skip", 2)
        )
        self._frame_skip_spin.setMinimumSize(140, 40)
        params_layout.addRow("Frame Skip:", self._frame_skip_spin)

        self._enable_roi_cb = QCheckBox("Enable Region of Interest (ROI)")
        self._enable_roi_cb.setChecked(
            self._config_service.get("detection.enable_roi", False)
        )
        params_layout.addRow("", self._enable_roi_cb)

        mode_label = QLabel("Detection Mode:")
        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["hybrid", "motion", "ai"])
        self._mode_combo.setCurrentText(
            self._config_service.get("detection.mode", "hybrid")
        )
        self._mode_combo.setMinimumSize(140, 40)
        params_layout.addRow(mode_label, self._mode_combo)

        layout.addWidget(params_group)

        # ── Model Configuration ──
        model_group = QGroupBox("AI Model Configuration")
        model_layout = QFormLayout(model_group)
        model_layout.setSpacing(12)
        model_layout.setLabelAlignment(Qt.AlignRight)

        self._model_path_label = QLabel(
            self._config_service.get(
                "detection.model_path", "models/yolov8n.pt"
            )
        )
        self._model_path_label.setStyleSheet(
            "background-color: #1A1A2E; padding: 8px 12px;"
            "border-radius: 6px; font-family: monospace;"
        )
        model_layout.addRow("Model Path:", self._model_path_label)

        browse_btn = QPushButton("Browse...")
        browse_btn.setMinimumSize(120, 40)
        model_layout.addRow("", browse_btn)

        layout.addWidget(model_group)

        # ── Apply Button ──
        apply_btn = QPushButton("✓  Apply Detection Settings")
        apply_btn.setObjectName("successButton")
        apply_btn.setMinimumSize(220, 52)
        layout.addWidget(apply_btn, alignment=Qt.AlignLeft)

        layout.addStretch()
        self.setLayout(layout)


# ──────────────────────────────────────────────
# Playback Settings Tab
# ──────────────────────────────────────────────

class PlaybackSettingsTab(QWidget):
    """Tab for configuring video playback behavior."""

    def __init__(
        self,
        event_bus: EventBus,
        config_service: ConfigService,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initialize playback settings tab.

        Args:
            event_bus: System event bus
            config_service: Configuration service
            parent: Parent widget
        """
        super().__init__(parent)
        self._event_bus = event_bus
        self._config_service = config_service
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Build the playback settings layout."""
        layout = QVBoxLayout()
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        header = QLabel("Playback Settings")
        header.setObjectName("sectionHeader")
        layout.addWidget(header)

        # ── Playback Mode ──
        mode_group = QGroupBox("Playback Mode")
        mode_layout = QFormLayout(mode_group)
        mode_layout.setSpacing(12)
        mode_layout.setLabelAlignment(Qt.AlignRight)

        self._playback_mode_combo = QComboBox()
        self._playback_mode_combo.addItems(["random", "sequential", "single"])
        self._playback_mode_combo.setCurrentText(
            self._config_service.get("video.playback_mode", "random")
        )
        self._playback_mode_combo.setMinimumSize(160, 40)
        mode_layout.addRow("Mode:", self._playback_mode_combo)

        self._loop_cb = QCheckBox("Loop Videos Continuously")
        self._loop_cb.setChecked(
            self._config_service.get("video.loop_videos", False)
        )
        mode_layout.addRow("", self._loop_cb)

        self._fullscreen_cb = QCheckBox("Fullscreen Playback")
        self._fullscreen_cb.setChecked(
            self._config_service.get("video.fullscreen", True)
        )
        mode_layout.addRow("", self._fullscreen_cb)

        layout.addWidget(mode_group)

        # ── Transition Settings ──
        transition_group = QGroupBox("Transition Settings")
        transition_layout = QFormLayout(transition_group)
        transition_layout.setSpacing(12)
        transition_layout.setLabelAlignment(Qt.AlignRight)

        self._fade_in_spin = QDoubleSpinBox()
        self._fade_in_spin.setRange(0.0, 5.0)
        self._fade_in_spin.setSingleStep(0.1)
        self._fade_in_spin.setValue(
            self._config_service.get("video.fade_in_duration", 1.0)
        )
        self._fade_in_spin.setSuffix(" s")
        self._fade_in_spin.setMinimumSize(120, 40)
        transition_layout.addRow("Fade In Duration:", self._fade_in_spin)

        self._fade_out_spin = QDoubleSpinBox()
        self._fade_out_spin.setRange(0.0, 5.0)
        self._fade_out_spin.setSingleStep(0.1)
        self._fade_out_spin.setValue(
            self._config_service.get("video.fade_out_duration", 1.0)
        )
        self._fade_out_spin.setSuffix(" s")
        self._fade_out_spin.setMinimumSize(120, 40)
        transition_layout.addRow("Fade Out Duration:", self._fade_out_spin)

        layout.addWidget(transition_group)

        # ── Volume ──
        volume_group = QGroupBox("Audio Settings")
        volume_layout = QVBoxLayout(volume_group)
        volume_layout.setSpacing(12)

        vol_row = QHBoxLayout()
        vol_label = QLabel("Volume:")
        vol_label.setMinimumWidth(120)
        vol_row.addWidget(vol_label)

        self._volume_slider = QSlider(Qt.Horizontal)
        self._volume_slider.setRange(0, 100)
        self._volume_slider.setValue(
            self._config_service.get("video.volume", 80)
        )
        self._volume_slider.setMinimumSize(300, 40)
        vol_row.addWidget(self._volume_slider)

        self._volume_value = QLabel(f"{self._volume_slider.value()}%")
        self._volume_value.setObjectName("cardValue")
        self._volume_value.setStyleSheet("font-size: 16px; background: transparent;")
        self._volume_value.setMinimumWidth(50)
        vol_row.addWidget(self._volume_value)

        self._volume_slider.valueChanged.connect(
            lambda v: self._volume_value.setText(f"{v}%")
        )

        volume_layout.addLayout(vol_row)

        mute_btn = QPushButton("🔇  Mute")
        mute_btn.setMinimumSize(120, 44)
        volume_layout.addWidget(mute_btn)

        layout.addWidget(volume_group)

        # ── Apply Button ──
        apply_btn = QPushButton("✓  Apply Playback Settings")
        apply_btn.setObjectName("successButton")
        apply_btn.setMinimumSize(220, 52)
        layout.addWidget(apply_btn, alignment=Qt.AlignLeft)

        layout.addStretch()
        self.setLayout(layout)


# ──────────────────────────────────────────────
# Logs Panel Tab
# ──────────────────────────────────────────────

class LogsPanelTab(QWidget):
    """Tab for viewing system logs in real-time."""

    def __init__(
        self,
        event_bus: EventBus,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initialize logs panel tab.

        Args:
            event_bus: System event bus
            parent: Parent widget
        """
        super().__init__(parent)
        self._event_bus = event_bus
        self._log_entries: List[str] = []
        self._max_entries = 1000
        self._setup_ui()
        self._subscribe_events()

    def _setup_ui(self) -> None:
        """Build the logs panel layout."""
        layout = QVBoxLayout()
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        header = QLabel("System Logs")
        header.setObjectName("sectionHeader")
        layout.addWidget(header)

        # ── Filter Controls ──
        filter_row = QHBoxLayout()
        filter_row.setSpacing(12)

        filter_label = QLabel("Filter Level:")
        filter_row.addWidget(filter_label)

        self._level_combo = QComboBox()
        self._level_combo.addItems(["ALL", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self._level_combo.setCurrentText("INFO")
        self._level_combo.setMinimumSize(140, 40)
        filter_row.addWidget(self._level_combo)

        filter_row.addWidget(QLabel("Search:"))

        self._search_input = QComboBox()
        self._search_input.setEditable(True)
        self._search_input.setPlaceholderText("Search logs...")
        self._search_input.setMinimumSize(250, 40)
        filter_row.addWidget(self._search_input)

        filter_row.addStretch()

        clear_btn = QPushButton("✕  Clear Logs")
        clear_btn.setMinimumSize(140, 44)
        filter_row.addWidget(clear_btn)

        layout.addLayout(filter_row)

        # ── Log Display ──
        self._log_display = QLabel()
        self._log_display.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self._log_display.setWordWrap(True)
        self._log_display.setStyleSheet("""
            background-color: #1A1A2E;
            color: #CCCCCC;
            border: 1px solid #3A3A4F;
            border-radius: 8px;
            padding: 12px;
            font-family: "SF Mono", "Fira Code", "Consolas", monospace;
            font-size: 12px;
        """)
        self._log_display.setText("No log entries...")
        self._log_display.setTextInteractionFlags(
            Qt.TextSelectableByMouse
        )

        # Scrollable container for logs
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._log_display)
        scroll.setMinimumHeight(300)
        layout.addWidget(scroll)

        # ── Status Bar for Logs ──
        status_row = QHBoxLayout()
        self._log_count_label = QLabel("Entries: 0")
        self._log_count_label.setObjectName("cardTitle")
        self._log_count_label.setStyleSheet("font-size: 12px; background: transparent;")
        status_row.addWidget(self._log_count_label)

        status_row.addStretch()

        auto_scroll_cb = QCheckBox("Auto-scroll")
        auto_scroll_cb.setChecked(True)
        status_row.addWidget(auto_scroll_cb)

        layout.addLayout(status_row)

        self.setLayout(layout)

    def _subscribe_events(self) -> None:
        """Subscribe to log-relevant events."""
        self._event_bus.subscribe_all(self._on_any_event)

    async def _on_any_event(self, event: Event) -> None:
        """Capture events and append to log display.

        Args:
            event: Any system event
        """
        timestamp = time.strftime(
            "%H:%M:%S", time.localtime(event.timestamp)
        )
        entry = (
            f"[{timestamp}] [{event.event_type.name}] "
            f"[{event.source}] {event.data}"
        )
        self._log_entries.append(entry)

        # Trim to max entries
        if len(self._log_entries) > self._max_entries:
            self._log_entries = self._log_entries[-self._max_entries:]

        # Update display
        display_text = "\n".join(self._log_entries[-100:])
        self._log_display.setText(display_text)
        self._log_count_label.setText(f"Entries: {len(self._log_entries)}")


# ──────────────────────────────────────────────
# Main Window
# ──────────────────────────────────────────────

class MainWindow(QMainWindow):
    """Primary application window for modInteractive kiosk system.

    Provides a tabbed interface with a modern flat design, dark/light theme
    support, system tray integration, and touch-friendly controls.

    Subscribes to EventBus events for real-time state updates and
    communicates with the StateMachine and ConfigService for system control.

    Attributes:
        MIN_WIDTH: Minimum window width (1024px)
        MIN_HEIGHT: Minimum window height (600px)
        WINDOW_TITLE: Default window title
    """

    MIN_WIDTH: int = 1024
    MIN_HEIGHT: int = 600
    WINDOW_TITLE: str = "modInteractive - AI Kiosk System"

    # Signal emitted when the UI requests a system state change
    state_change_requested = Signal(str)

    def __init__(
        self,
        event_bus: EventBus,
        state_machine: StateMachine,
        config_service: ConfigService,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initialize the main window.

        Args:
            event_bus: System event bus for pub/sub communication
            state_machine: System state machine instance
            config_service: Configuration service for reading/writing settings
            parent: Optional parent widget
        """
        super().__init__(parent)

        # Core references
        self._event_bus = event_bus
        self._state_machine = state_machine
        self._config_service = config_service

        # Internal state
        self._current_theme: str = "dark"
        self._unsubscribe_fns: List[callable] = []
        self._is_fullscreen: bool = False
        self._start_time: float = time.time()

        # ── Window configuration ──
        self.setWindowTitle(self.WINDOW_TITLE)
        self.setMinimumSize(self.MIN_WIDTH, self.MIN_HEIGHT)
        self.resize(1280, 800)

        # Enable touch events
        self.setAttribute(Qt.WA_AcceptTouchEvents, True)

        # ── Build UI ──
        self._setup_ui()
        self._setup_menu_bar()
        self._setup_status_bar()
        self._setup_system_tray()

        # ── Apply default theme ──
        theme_config = self._config_service.get("ui.theme", "dark")
        self._apply_theme(theme_config)

        # ── Subscribe to events ──
        self._subscribe_to_events()

        # ── Start UI state polling ──
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._update_status_bar)
        self._poll_timer.start(STATUS_POLL_INTERVAL)

        logger.info("MainWindow initialized")

    # ──────────────────────────────────────────
    # UI Setup
    # ──────────────────────────────────────────

    def _setup_ui(self) -> None:
        """Build the complete user interface layout."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── Tab Widget ──
        self._tab_widget = QTabWidget()
        self._tab_widget.setDocumentMode(True)
        self._tab_widget.setElideMode(Qt.ElideRight)
        self._tab_widget.setMovable(True)
        self._tab_widget.setTabBarAutoHide(False)

        # Create tabs
        self._dashboard_tab = DashboardTab(
            self._event_bus, self._state_machine, self._config_service
        )
        self._video_tab = VideoManagerTab(self._event_bus, self._config_service)
        self._camera_tab = CameraPanelTab(self._event_bus, self._config_service)
        self._detection_tab = DetectionSettingsTab(
            self._event_bus, self._config_service
        )
        self._playback_tab = PlaybackSettingsTab(
            self._event_bus, self._config_service
        )
        self._logs_tab = LogsPanelTab(self._event_bus)

        # Add tabs with icons (using unicode as placeholder icons)
        self._tab_widget.addTab(self._dashboard_tab, "📊  Dashboard")
        self._tab_widget.addTab(self._video_tab, "🎬  Video Manager")
        self._tab_widget.addTab(self._camera_tab, "📷  Camera Panel")
        self._tab_widget.addTab(self._detection_tab, "🔍  Detection Settings")
        self._tab_widget.addTab(self._playback_tab, "▶  Playback Settings")
        self._tab_widget.addTab(self._logs_tab, "📋  Logs Panel")

        # Style the tab widget to be touch-friendly
        self._tab_widget.setStyleSheet("""
            QTabWidget::tab-bar {
                alignment: center;
            }
            QTabBar::tab {
                min-height: 44px;
                padding: 8px 20px;
                margin: 2px;
            }
        """)

        main_layout.addWidget(self._tab_widget)

    def _setup_menu_bar(self) -> None:
        """Configure the application menu bar."""
        menu_bar = self.menuBar()

        # ── File Menu ──
        file_menu = menu_bar.addMenu("&File")
        file_menu.setToolTipsVisible(True)

        toggle_theme_action = QAction("Toggle Theme", self)
        toggle_theme_action.setShortcut(QKeySequence("Ctrl+T"))
        toggle_theme_action.triggered.connect(self._toggle_theme)
        file_menu.addAction(toggle_theme_action)

        file_menu.addSeparator()

        fullscreen_action = QAction("Toggle Fullscreen", self)
        fullscreen_action.setShortcut(QKeySequence("F11"))
        fullscreen_action.triggered.connect(self._toggle_fullscreen)
        file_menu.addAction(fullscreen_action)

        file_menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.setShortcut(QKeySequence("Ctrl+Q"))
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # ── View Menu ──
        view_menu = menu_bar.addMenu("&View")

        for i in range(self._tab_widget.count()):
            tab_action = QAction(
                f"Switch to {self._tab_widget.tabText(i)}", self
            )
            tab_index = i
            tab_action.triggered.connect(
                lambda checked, idx=tab_index: self._tab_widget.setCurrentIndex(idx)
            )
            view_menu.addAction(tab_action)

        # ── Help Menu ──
        help_menu = menu_bar.addMenu("&Help")

        about_action = QAction("About modInteractive", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _setup_status_bar(self) -> None:
        """Configure the status bar with system info."""
        status_bar = self.statusBar()
        status_bar.setStyleSheet("""
            QStatusBar {
                background-color: #2D2D3F;
                color: #AAAAAA;
                border-top: 1px solid #3A3A4F;
                font-size: 12px;
                padding: 4px 12px;
            }
        """)

        # Status labels
        self._state_label = QLabel("State: --")
        self._state_label.setMinimumWidth(160)
        status_bar.addPermanentWidget(self._state_label)

        self._uptime_label = QLabel("Uptime: 0m")
        self._uptime_label.setMinimumWidth(140)
        status_bar.addPermanentWidget(self._uptime_label)

        self._theme_label = QLabel("Theme: Dark")
        self._theme_label.setMinimumWidth(100)
        status_bar.addPermanentWidget(self._theme_label)

    def _setup_system_tray(self) -> None:
        """Configure the system tray icon and context menu."""
        # Create a simple icon using a pixmap (16x16)
        icon_pixmap = QPixmap(16, 16)
        icon_pixmap.fill(QColor("#4A90D9"))
        self._tray_icon = QSystemTrayIcon(QIcon(icon_pixmap), self)
        self._tray_icon.setToolTip("modInteractive - AI Kiosk System")

        # Tray context menu
        tray_menu = QMenu()

        show_action = QAction("Show Window", self)
        show_action.triggered.connect(self.show_normal)
        tray_menu.addAction(show_action)

        start_action = QAction("▶ Start System", self)
        start_action.triggered.connect(self._tray_start_system)
        tray_menu.addAction(start_action)

        stop_action = QAction("■ Stop System", self)
        stop_action.triggered.connect(self._tray_stop_system)
        tray_menu.addAction(stop_action)

        tray_menu.addSeparator()

        toggle_theme_action = QAction("Toggle Theme", self)
        toggle_theme_action.triggered.connect(self._toggle_theme)
        tray_menu.addAction(toggle_theme_action)

        tray_menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(QApplication.quit)
        tray_menu.addAction(quit_action)

        self._tray_icon.setContextMenu(tray_menu)

        # Double-click to restore
        self._tray_icon.activated.connect(self._on_tray_activated)

        self._tray_icon.show()
        logger.info("System tray icon created")

    # ──────────────────────────────────────────
    # Event Bus Subscriptions
    # ──────────────────────────────────────────

    def _subscribe_to_events(self) -> None:
        """Subscribe to relevant EventBus events for UI updates."""
        events_of_interest = [
            SystemEvents.STATE_CHANGED,
            SystemEvents.UI_THEME_CHANGED,
            SystemEvents.CONFIG_CHANGED,
            SystemEvents.SYSTEM_ERROR,
            SystemEvents.CAMERA_CONNECTED,
            SystemEvents.CAMERA_DISCONNECTED,
        ]

        for event_type in events_of_interest:
            unsub = self._event_bus.subscribe(
                event_type, self._handle_system_event
            )
            self._unsubscribe_fns.append(unsub)

    async def _handle_system_event(self, event: Event) -> None:
        """Process incoming system events for UI state updates.

        Args:
            event: The received system event
        """
        if event.event_type == SystemEvents.STATE_CHANGED:
            new_state = event.data.get("to", "UNKNOWN")
            self._state_label.setText(f"State: {new_state}")

        elif event.event_type == SystemEvents.UI_THEME_CHANGED:
            new_theme = event.data.get("theme", "dark")
            self._apply_theme(new_theme)

        elif event.event_type == SystemEvents.SYSTEM_ERROR:
            error_msg = event.data.get("error", "Unknown error")
            logger.error(f"System error received in UI: {error_msg}")
            # Update status bar with error
            self._state_label.setText("State: ERROR")
            self._state_label.setStyleSheet("color: #E74C3C; font-weight: bold;")

    def unsubscribe_all(self) -> None:
        """Clean up all event bus subscriptions."""
        for unsub in self._unsubscribe_fns:
            try:
                unsub()
            except Exception as e:
                logger.debug(f"Unsubscribe error: {e}")
        self._unsubscribe_fns.clear()
        logger.info("All event bus subscriptions removed")

    # ──────────────────────────────────────────
    # Theme Management
    # ──────────────────────────────────────────

    def _apply_theme(self, theme_name: str) -> None:
        """Apply a named theme to the entire application.

        Args:
            theme_name: One of 'dark' or 'light'
        """
        if theme_name == "light":
            stylesheet = LIGHT_THEME_STYLESHEET
            self._current_theme = "light"
            self._theme_label.setText("Theme: Light")
        else:
            stylesheet = DARK_THEME_STYLESHEET
            self._current_theme = "dark"
            self._theme_label.setText("Theme: Dark")

        self.setStyleSheet(stylesheet)
        logger.info(f"Theme applied: {theme_name}")

        # Propagate to all child widgets
        for widget in self.findChildren(QWidget):
            widget.setStyleSheet(stylesheet)

    def _toggle_theme(self) -> None:
        """Toggle between dark and light themes."""
        new_theme = "light" if self._current_theme == "dark" else "dark"
        self._apply_theme(new_theme)

        # Publish theme change event
        asyncio.create_task(
            self._event_bus.publish(
                Event(
                    event_type=SystemEvents.UI_THEME_CHANGED,
                    source="main_window",
                    data={"theme": new_theme},
                    priority=EventPriority.NORMAL,
                )
            )
        )

    # ──────────────────────────────────────────
    # Window State Management
    # ──────────────────────────────────────────

    def _toggle_fullscreen(self) -> None:
        """Toggle fullscreen mode."""
        if self._is_fullscreen:
            self.showNormal()
            self._is_fullscreen = False
        else:
            self.showFullScreen()
            self._is_fullscreen = True
        logger.info(f"Fullscreen: {self._is_fullscreen}")

    def show_normal(self) -> None:
        """Restore window to normal state and bring to front."""
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def _on_tray_activated(
        self, reason: QSystemTrayIcon.ActivationReason
    ) -> None:
        """Handle system tray icon activation.

        Args:
            reason: Activation reason (double-click, etc.)
        """
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_normal()

    def _tray_start_system(self) -> None:
        """Start system from tray menu."""
        logger.info("System start from tray")

    def _tray_stop_system(self) -> None:
        """Stop system from tray menu."""
        logger.info("System stop from tray")

    # ──────────────────────────────────────────
    # Status Bar Updates
    # ──────────────────────────────────────────

    @Slot()
    def _update_status_bar(self) -> None:
        """Periodically refresh the status bar information."""
        # Update state display
        state_name = self._state_machine.current_state.name
        self._state_label.setText(f"State: {state_name}")

        # Update uptime
        uptime_seconds = time.time() - self._start_time
        minutes = int(uptime_seconds // 60)
        seconds = int(uptime_seconds % 60)
        hours = minutes // 60
        if hours > 0:
            self._uptime_label.setText(
                f"Uptime: {hours}h {minutes % 60}m"
            )
        else:
            self._uptime_label.setText(f"Uptime: {minutes}m {seconds}s")

        # Re-apply state label styling for errors
        if self._state_machine.current_state == SystemState.ERROR:
            self._state_label.setStyleSheet(
                "color: #E74C3C; font-weight: bold;"
            )

    # ──────────────────────────────────────────
    # Dialog Methods
    # ──────────────────────────────────────────

    def _show_about(self) -> None:
        """Display the About dialog."""
        QMessageBox.about(
            self,
            "About modInteractive",
            (
                "<h2>modInteractive v2.0.0</h2>"
                "<p>AI-Powered Interactive Kiosk System</p>"
                "<p>An intelligent kiosk system with AI-based person "
                "detection, video playback, and interactive display "
                "capabilities.</p>"
                "<hr>"
                "<p><b>Features:</b></p>"
                "<ul>"
                "<li>AI Person Detection (YOLOv8)</li>"
                "<li>Motion Detection</li>"
                "<li>Video Playback with Fade Transitions</li>"
                "<li>Touchscreen Optimized UI</li>"
                "<li>Raspberry Pi 5 Optimized</li>"
                "</ul>"
                "<hr>"
                "<p><i>Built with Python, PySide6, and OpenCV</i></p>"
            ),
        )

    # ──────────────────────────────────────────
    # Close Event
    # ──────────────────────────────────────────

    def closeEvent(self, event: QCloseEvent) -> None:
        """Handle window close event - minimize to tray instead of closing.

        Args:
            event: The close event
        """
        if self._tray_icon.isVisible():
            QMessageBox.information(
                self,
                "modInteractive",
                "The application will continue running in the system tray. "
                "Use 'Quit' from the tray menu to exit completely.",
            )
            self.hide()
            event.ignore()
        else:
            self.unsubscribe_all()
            self._poll_timer.stop()
            event.accept()

    # ──────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────

    def set_theme(self, theme_name: str) -> None:
        """Programmatically set the UI theme.

        Args:
            theme_name: 'dark' or 'light'
        """
        self._apply_theme(theme_name)

    def get_current_theme(self) -> str:
        """Get the currently active theme name.

        Returns:
            'dark' or 'light'
        """
        return self._current_theme

    def switch_to_tab(self, tab_index: int) -> None:
        """Switch to a specific tab by index.

        Args:
            tab_index: 0-based tab index
                (0=Dashboard, 1=Video Manager, 2=Camera Panel,
                 3=Detection Settings, 4=Playback Settings, 5=Logs Panel)
        """
        if 0 <= tab_index < self._tab_widget.count():
            self._tab_widget.setCurrentIndex(tab_index)

    def cleanup(self) -> None:
        """Clean up resources before shutdown."""
        self.unsubscribe_all()
        if hasattr(self, "_poll_timer") and self._poll_timer:
            self._poll_timer.stop()
        if hasattr(self, "_tray_icon") and self._tray_icon:
            self._tray_icon.hide()
        logger.info("MainWindow cleanup completed")

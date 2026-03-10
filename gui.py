#!/usr/bin/env python3
"""
Load Test Automation Framework
PyQt5-based GUI for creating load test configurations and running tests.
"""

import csv
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

from PyQt5.QtCore import (
    Qt, QProcess, pyqtSignal, QObject, QSize, QTimer,
    QPropertyAnimation, QEasingCurve, QAbstractAnimation,
)
from PyQt5.QtGui import (
    QFont, QIcon, QColor, QPalette, QFontDatabase, QPixmap, QImage,
    QLinearGradient, QPainter,
)
import qtawesome as qta
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QComboBox, QCheckBox, QSpinBox,
    QDoubleSpinBox, QGroupBox, QScrollArea, QTabWidget, QTextEdit,
    QFileDialog, QMessageBox, QSplitter, QFrame, QTableWidget,
    QTableWidgetItem, QHeaderView, QStackedWidget, QListWidget,
    QListWidgetItem, QFormLayout, QSizePolicy, QDialog, QDialogButtonBox,
    QTreeWidget, QTreeWidgetItem, QProgressBar, QToolBar, QAction,
    QAbstractItemView, QStyle, QGraphicsOpacityEffect, QInputDialog,
)

# ---------------------------------------------------------------------------
# Application colour palette  –  deep black, rich crimson accents
# ---------------------------------------------------------------------------
THEME_COLORS = {
    "bg_dark": "#020204",
    "bg_medium": "#08080c",
    "bg_light": "#101018",
    "bg_card": "#050508",
    "bg_elevated": "#0c0c10",
    "red_primary": "#9e3535",
    "red_hover": "#b84a4a",
    "red_dark": "#6b2525",
    "red_glow": "rgba(158, 53, 53, 0.28)",
    "red_subtle": "rgba(158, 53, 53, 0.07)",
    "text_primary": "#d8d8dc",
    "text_secondary": "#808088",
    "text_muted": "#3a3a42",
    "border": "#141418",
    "border_light": "#1e1e26",
    "success": "#1b8a3e",
    "success_glow": "rgba(27, 138, 62, 0.25)",
    "warning": "#d47800",
    "error": "#b84848",
    "error_glow": "rgba(184, 72, 72, 0.22)",
    "input_bg": "#060608",
    "input_border": "#18181e",
    "input_focus": "#c41e1e",
    "table_header": "#060608",
    "table_alt_row": "#040406",
    "scrollbar_bg": "#040406",
    "scrollbar_handle": "#20202a",
    "accent_blue": "#1a3a5c",
    "gradient_start": "#040408",
    "gradient_end": "#08080c",
}

# Serif font stack
_FONT_FAMILY = "'Libre Baskerville', 'Georgia', 'Times New Roman', serif"

STYLESHEET = f"""
/* ── Global ─────────────────────────────────────────────── */
QMainWindow {{
    background-color: {THEME_COLORS['bg_dark']};
}}
QWidget {{
    color: {THEME_COLORS['text_primary']};
    font-family: {_FONT_FAMILY};
    font-size: 15px;
}}

/* ── Labels ─────────────────────────────────────────────── */
QLabel {{
    color: {THEME_COLORS['text_primary']};
    background: transparent;
    font-weight: 400;
    font-size: 15px;
}}
QLabel[class="heading"] {{
    font-size: 24px;
    font-weight: 700;
    color: {THEME_COLORS['red_primary']};
    letter-spacing: 0.5px;
}}
QLabel[class="subheading"] {{
    font-size: 15px;
    font-weight: 700;
    color: {THEME_COLORS['text_secondary']};
    text-transform: uppercase;
    letter-spacing: 1.5px;
}}

/* ── Buttons – pill-shaped, rich glow on hover ──────────── */
QPushButton {{
    background-color: {THEME_COLORS['red_primary']};
    color: #ffffff;
    border: none;
    padding: 10px 26px;
    border-radius: 18px;
    font-weight: 700;
    font-size: 15px;
    min-height: 22px;
    letter-spacing: 0.4px;
}}
QPushButton:hover {{
    background-color: {THEME_COLORS['red_hover']};
    border: 1px solid {THEME_COLORS['red_glow']};
}}
QPushButton:pressed {{
    background-color: {THEME_COLORS['red_dark']};
}}
QPushButton:disabled {{
    background-color: {THEME_COLORS['bg_light']};
    color: {THEME_COLORS['text_muted']};
}}
QPushButton[class="secondary"] {{
    background-color: {THEME_COLORS['bg_light']};
    color: {THEME_COLORS['text_primary']};
    border: 1px solid {THEME_COLORS['border_light']};
}}
QPushButton[class="secondary"]:hover {{
    background-color: {THEME_COLORS['border_light']};
    border-color: {THEME_COLORS['text_muted']};
}}
QPushButton[class="danger"] {{
    background-color: transparent;
    color: {THEME_COLORS['error']};
    border: 1px solid {THEME_COLORS['error']};
}}
QPushButton[class="danger"]:hover {{
    background-color: {THEME_COLORS['error']};
    color: #ffffff;
}}

/* ── Inputs ─────────────────────────────────────────────── */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background-color: {THEME_COLORS['input_bg']};
    color: {THEME_COLORS['text_primary']};
    border: 1px solid {THEME_COLORS['input_border']};
    border-radius: 10px;
    padding: 8px 14px;
    min-height: 22px;
    selection-background-color: {THEME_COLORS['red_primary']};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border: 1px solid {THEME_COLORS['input_focus']};
    background-color: {THEME_COLORS['bg_elevated']};
}}
QComboBox::drop-down {{
    border: none;
    padding-right: 10px;
}}
QComboBox QAbstractItemView {{
    background-color: {THEME_COLORS['bg_elevated']};
    color: {THEME_COLORS['text_primary']};
    selection-background-color: {THEME_COLORS['red_primary']};
    border: 1px solid {THEME_COLORS['border_light']};
    border-radius: 8px;
    padding: 4px;
}}

/* ── Checkboxes ─────────────────────────────────────────── */
QCheckBox {{
    color: {THEME_COLORS['text_primary']};
    spacing: 10px;
    background: transparent;
}}
QCheckBox::indicator {{
    width: 20px;
    height: 20px;
    border: 2px solid {THEME_COLORS['border_light']};
    border-radius: 6px;
    background: {THEME_COLORS['input_bg']};
}}
QCheckBox::indicator:hover {{
    border-color: {THEME_COLORS['red_primary']};
}}
QCheckBox::indicator:checked {{
    background: {THEME_COLORS['red_primary']};
    border-color: {THEME_COLORS['red_primary']};
}}

/* ── Group Boxes ────────────────────────────────────────── */
QGroupBox {{
    background-color: {THEME_COLORS['bg_card']};
    border: 1px solid {THEME_COLORS['border']};
    border-radius: 14px;
    margin-top: 18px;
    padding: 22px;
    padding-top: 34px;
    font-weight: 700;
    font-size: 15px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 5px 16px;
    color: {THEME_COLORS['red_primary']};
    background-color: {THEME_COLORS['bg_card']};
    border: 1px solid {THEME_COLORS['border']};
    border-radius: 8px;
    font-size: 15px;
    font-weight: 700;
    letter-spacing: 1px;
    text-transform: uppercase;
}}

/* ── Tabs ───────────────────────────────────────────────── */
QTabWidget::pane {{
    border: 1px solid {THEME_COLORS['border']};
    border-top: none;
    border-radius: 0 0 12px 12px;
    background-color: {THEME_COLORS['bg_dark']};
}}
QTabBar {{
    qproperty-expanding: false;
}}
QTabBar::tab {{
    background-color: {THEME_COLORS['bg_medium']};
    color: {THEME_COLORS['text_muted']};
    padding: 14px 24px;
    border: none;
    border-bottom: 3px solid transparent;
    font-weight: 700;
    font-size: 15px;
    min-width: 200px;
    letter-spacing: 0.8px;
}}
QTabBar::tab:selected {{
    color: {THEME_COLORS['text_primary']};
    border-bottom: 3px solid {THEME_COLORS['red_primary']};
    background-color: {THEME_COLORS['bg_dark']};
}}
QTabBar::tab:hover:!selected {{
    background-color: {THEME_COLORS['bg_light']};
    color: {THEME_COLORS['text_secondary']};
    border-bottom: 3px solid {THEME_COLORS['red_subtle']};
}}

/* ── Console / Text Edit ────────────────────────────────── */
QTextEdit {{
    background-color: {THEME_COLORS['bg_card']};
    color: #f0f0f4;
    border: 1px solid {THEME_COLORS['border']};
    border-radius: 12px;
    padding: 14px;
    font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace;
    font-size: 15px;
    line-height: 1.6;
}}

/* ── Tables ─────────────────────────────────────────────── */
QTableWidget {{
    background-color: {THEME_COLORS['bg_card']};
    color: {THEME_COLORS['text_primary']};
    border: 1px solid {THEME_COLORS['border']};
    border-radius: 12px;
    gridline-color: {THEME_COLORS['border']};
    selection-background-color: {THEME_COLORS['red_primary']};
    alternate-background-color: {THEME_COLORS['table_alt_row']};
}}
QTableWidget::item {{
    padding: 9px;
    border: none;
}}
QTableWidget::item:hover {{
    background-color: {THEME_COLORS['bg_light']};
}}
QHeaderView::section {{
    background-color: {THEME_COLORS['table_header']};
    color: {THEME_COLORS['text_secondary']};
    padding: 11px 8px;
    border: none;
    border-right: 1px solid {THEME_COLORS['border']};
    border-bottom: 2px solid {THEME_COLORS['red_primary']};
    font-weight: 700;
    font-size: 13px;
    text-transform: uppercase;
    letter-spacing: 1px;
}}

/* ── List Widget ────────────────────────────────────────── */
QListWidget {{
    background-color: {THEME_COLORS['bg_card']};
    color: {THEME_COLORS['text_primary']};
    border: 1px solid {THEME_COLORS['border']};
    border-radius: 12px;
    outline: none;
    padding: 6px;
}}
QListWidget::item {{
    padding: 12px 18px;
    border-bottom: 1px solid {THEME_COLORS['border']};
    border-radius: 8px;
    margin: 2px 4px;
    font-weight: 600;
}}
QListWidget::item:selected {{
    background-color: {THEME_COLORS['red_primary']};
    color: white;
}}
QListWidget::item:hover:!selected {{
    background-color: {THEME_COLORS['bg_light']};
    border-left: 3px solid {THEME_COLORS['red_primary']};
}}

/* ── Scroll Areas & Bars ────────────────────────────────── */
QScrollArea {{
    border: none;
    background: transparent;
}}
QScrollBar:vertical {{
    background: {THEME_COLORS['scrollbar_bg']};
    width: 7px;
    margin: 0;
    border-radius: 3px;
}}
QScrollBar::handle:vertical {{
    background: {THEME_COLORS['scrollbar_handle']};
    min-height: 40px;
    border-radius: 3px;
}}
QScrollBar::handle:vertical:hover {{
    background: {THEME_COLORS['text_muted']};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: {THEME_COLORS['scrollbar_bg']};
    height: 7px;
    margin: 0;
    border-radius: 3px;
}}
QScrollBar::handle:horizontal {{
    background: {THEME_COLORS['scrollbar_handle']};
    min-width: 40px;
    border-radius: 3px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {THEME_COLORS['text_muted']};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* ── Progress Bar ───────────────────────────────────────── */
QProgressBar {{
    background-color: {THEME_COLORS['bg_medium']};
    border: 1px solid {THEME_COLORS['border']};
    border-radius: 11px;
    text-align: center;
    color: white;
    font-weight: 700;
    min-height: 22px;
}}
QProgressBar::chunk {{
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {THEME_COLORS['red_dark']},
        stop:1 {THEME_COLORS['red_primary']});
    border-radius: 10px;
}}

/* ── Splitter ───────────────────────────────────────────── */
QSplitter::handle {{
    background-color: {THEME_COLORS['border']};
    border-radius: 1px;
}}
QSplitter::handle:horizontal {{
    width: 2px;
}}
QSplitter::handle:vertical {{
    height: 2px;
}}
QSplitter::handle:hover {{
    background-color: {THEME_COLORS['red_primary']};
}}

/* ── Toolbar ────────────────────────────────────────────── */
QToolBar {{
    background-color: {THEME_COLORS['bg_medium']};
    border-bottom: 2px solid {THEME_COLORS['red_primary']};
    padding: 10px 16px;
    spacing: 12px;
}}

/* ── Dialog button box ──────────────────────────────────── */
QDialogButtonBox QPushButton {{
    min-width: 100px;
}}

/* ── Tooltips ───────────────────────────────────────────── */
QToolTip {{
    background-color: {THEME_COLORS['bg_elevated']};
    color: {THEME_COLORS['text_primary']};
    border: 1px solid {THEME_COLORS['border_light']};
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 13px;
}}

/* ── Message Box ────────────────────────────────────────── */
QMessageBox {{
    background-color: {THEME_COLORS['bg_card']};
}}
QMessageBox QLabel {{
    color: {THEME_COLORS['text_primary']};
    font-size: 15px;
}}
"""

# ---------------------------------------------------------------------------
# Protocol definitions (mirrors config_validator.py)
# ---------------------------------------------------------------------------
PROTOCOLS = ["speed_test", "web_browsing", "streaming", "voip_sipp"]

PROTOCOL_PARAMS = {
    "speed_test": {
        "required": {
            "target_url": {"type": "list", "label": "Target URLs (host:port)", "placeholder": "e.g. host:port"},
        },
        "optional": {
            "duration": {"type": "int", "label": "Duration (seconds)", "default": 10, "min": 1},
        },
    },
    "web_browsing": {
        "required": {
            "target_url": {"type": "list", "label": "Target URLs", "placeholder": "e.g. https://www.google.com"},
        },
        "optional": {
            "headless": {"type": "bool", "label": "Headless Mode", "default": True},
            "disable_cache": {"type": "bool", "label": "Disable Cache", "default": True},
        },
    },
    "streaming": {
        "required": {
            "server_url": {"type": "str", "label": "Jellyfin Server URL", "placeholder": "http://host:8096"},
            "api_key": {"type": "str", "label": "API Key", "placeholder": "your-jellyfin-api-key"},
            "item_ids": {"type": "list", "label": "Item IDs", "placeholder": "jellyfin-item-id"},
        },
        "optional": {
            "headless": {"type": "bool", "label": "Headless Mode", "default": True},
            "disable_cache": {"type": "bool", "label": "Disable Cache", "default": True},
            "parallel_browsing": {"type": "bool", "label": "Parallel Browsing", "default": False},
            "aggregate": {"type": "bool", "label": "Aggregate Results", "default": False},
        },
    },
    "voip_sipp": {
        "required": {
            "target_url": {"type": "list", "label": "Target URLs (host/IP)", "placeholder": "e.g. 192.168.1.100"},
        },
        "optional": {
            "number_of_calls": {"type": "int", "label": "Number of Calls", "default": 5, "min": 1},
            "call_duration": {"type": "int", "label": "Call Duration (seconds)", "default": 5, "min": 1},
            "type": {"type": "choice", "label": "Media Type", "choices": ["none", "audio", "video"], "default": "none"},
            "transport": {"type": "choice", "label": "Transport", "choices": ["udp", "tcp"], "default": "udp"},
        },
    },
}

PROTOCOL_METRICS = {
    "speed_test": ["download_speed", "upload_speed", "jitter", "latency"],
    "web_browsing": ["page_load_time", "ttfb", "dom_content_loaded", "http_response_code", "resource_count", "redirect_count"],
    "streaming": [
        "initial_buffer_time", "test_wall_seconds", "startup_latency_sec",
        "playback_seconds", "active_playback_seconds", "rebuffer_events",
        "rebuffer_ratio", "min_buffer", "max_buffer", "avg_buffer",
        "resolution_switches", "segments_fetched", "non_200_segments",
        "avg_segment_latency_sec", "max_segment_latency_sec", "est_bitrate_bps",
        "error_count", "download_speed", "upload_speed", "latency", "jitter",
    ],
    "voip_sipp": [
        # SIP signaling (always available)
        "call_success", "call_setup_time", "failed_calls", "retransmissions",
        "timeout_errors", "avg_rtt", "min_rtt", "max_rtt",
        "sip_response_jitter",
        # Audio RTP (type=audio only)
        "audio_rtp_packets", "audio_rtp_packet_loss",
        "audio_rtp_packet_loss_rate", "audio_rtp_jitter",
        "audio_rtp_bitrate_kbps",
        # Video RTP (type=video only)
        "video_rtp_packets", "video_rtp_packet_loss",
        "video_rtp_packet_loss_rate", "video_rtp_jitter",
        "video_rtp_bitrate_kbps",
        # Aggregate media (type=audio or video)
        "jitter", "media_capture_available", "media_streams_observed",
        "media_packets_sent", "media_packets_received",
        "media_bytes_sent", "media_bytes_received",
        "media_packet_loss", "media_packet_loss_rate",
        "media_tx_bitrate_kbps", "media_rx_bitrate_kbps",
    ],
}

# VoIP metrics grouped by media type — used to filter the metric combo
# in ExpectationDialog and to validate expectations in config_validator.
_VOIP_SIGNALING_METRICS = {
    "call_success", "call_setup_time", "failed_calls", "retransmissions",
    "timeout_errors", "avg_rtt", "min_rtt", "max_rtt", "sip_response_jitter",
}
_VOIP_AUDIO_METRICS = {
    "audio_rtp_packets", "audio_rtp_packet_loss",
    "audio_rtp_packet_loss_rate", "audio_rtp_jitter", "audio_rtp_bitrate_kbps",
}
_VOIP_VIDEO_METRICS = {
    "video_rtp_packets", "video_rtp_packet_loss",
    "video_rtp_packet_loss_rate", "video_rtp_jitter", "video_rtp_bitrate_kbps",
}
_VOIP_MEDIA_AGGREGATE_METRICS = {
    "jitter", "media_capture_available", "media_streams_observed",
    "media_packets_sent", "media_packets_received",
    "media_bytes_sent", "media_bytes_received",
    "media_packet_loss", "media_packet_loss_rate",
    "media_tx_bitrate_kbps", "media_rx_bitrate_kbps",
}

VOIP_METRICS_BY_TYPE = {
    "none": _VOIP_SIGNALING_METRICS,
    "audio": _VOIP_SIGNALING_METRICS | _VOIP_AUDIO_METRICS | _VOIP_MEDIA_AGGREGATE_METRICS,
    "video": _VOIP_SIGNALING_METRICS | _VOIP_VIDEO_METRICS | _VOIP_MEDIA_AGGREGATE_METRICS,
}

VALID_OPERATORS = ["lt", "lte", "gt", "gte", "eq", "neq"]
OPERATOR_LABELS = {
    "lt": "< (less than)",
    "lte": "<= (less or equal)",
    "gt": "> (greater than)",
    "gte": ">= (greater or equal)",
    "eq": "== (equal)",
    "neq": "!= (not equal)",
}

VALID_UNITS = [
    "bps", "kbps", "mbps", "gbps", "Bps", "KBps", "MBps", "GBps",
    "ns", "us", "ms", "s", "sec", "seconds", "min", "minutes",
    "count", "code", "ratio",
]

# Mapping from metric category to compatible units (mirrors config_validator logic)
CATEGORY_VALID_UNITS = {
    "speed": ["bps", "kbps", "mbps", "gbps", "Bps", "KBps", "MBps", "GBps"],
    "time": ["ns", "us", "ms", "s", "sec", "seconds", "min", "minutes"],
    "count": ["count", "code", "ratio"],
}

# Metric to category mapping (mirrors unit_converter.METRIC_CATEGORIES)
METRIC_CATEGORY = {
    "download_speed": "speed", "upload_speed": "speed",
    "est_bitrate_bps": "speed", "media_tx_bitrate_kbps": "speed",
    "media_rx_bitrate_kbps": "speed",
    "latency": "time", "jitter": "time", "page_load_time": "time",
    "ttfb": "time", "dom_content_loaded": "time",
    "initial_buffer_time": "time", "test_wall_seconds": "time",
    "startup_latency_sec": "time", "playback_seconds": "time",
    "active_playback_seconds": "time", "min_buffer": "time",
    "max_buffer": "time", "avg_buffer": "time",
    "avg_segment_latency_sec": "time", "max_segment_latency_sec": "time",
    "call_setup_time": "time", "avg_rtt": "time", "min_rtt": "time",
    "max_rtt": "time", "sip_response_jitter": "time",
    "audio_rtp_jitter": "time", "video_rtp_jitter": "time",
    "audio_rtp_packets": "count", "audio_rtp_packet_loss": "count",
    "audio_rtp_packet_loss_rate": "count",
    "audio_rtp_bitrate_kbps": "speed",
    "video_rtp_packets": "count", "video_rtp_packet_loss": "count",
    "video_rtp_packet_loss_rate": "count",
    "video_rtp_bitrate_kbps": "speed",
    "resource_count": "count", "redirect_count": "count",
    "http_response_code": "count", "rebuffer_events": "count",
    "rebuffer_ratio": "count", "resolution_switches": "count",
    "segments_fetched": "count", "non_200_segments": "count",
    "error_count": "count", "call_success": "count",
    "failed_calls": "count", "retransmissions": "count",
    "timeout_errors": "count",
    "media_capture_available": "count", "media_streams_observed": "count",
    "media_packets_sent": "count", "media_packets_received": "count",
    "media_bytes_sent": "count", "media_bytes_received": "count",
    "media_packet_loss": "count", "media_packet_loss_rate": "count",
}

VALID_AGGREGATIONS = ["avg", "min", "max", "stddev"] + [f"p{i}" for i in range(1, 100)]
VALID_SCOPES = ["per_iteration", "scenario"]


# ---------------------------------------------------------------------------
# Animation helpers
# ---------------------------------------------------------------------------
def pulse_opacity(widget, duration=1200):
    """Create a subtle pulsing opacity animation (for progress indicators)."""
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    anim = QPropertyAnimation(effect, b"opacity")
    anim.setDuration(duration)
    anim.setStartValue(0.6)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.InOutSine)
    anim.setLoopCount(-1)  # infinite loop
    # Reverse each cycle for pulse effect
    anim.finished.connect(lambda: None)
    widget._pulse_anim = anim
    return anim


def build_toolbar_logo_pixmap(path, target_height=28):
    """Remove the logo's baked light matte and crop it for dark-toolbar use."""
    image = QImage(path)
    if image.isNull():
        return QPixmap()

    image = image.convertToFormat(QImage.Format_ARGB32)
    min_x, min_y = image.width(), image.height()
    max_x = max_y = -1

    for y in range(image.height()):
        for x in range(image.width()):
            color = image.pixelColor(x, y)
            red, green, blue = color.red(), color.green(), color.blue()
            spread = max(red, green, blue) - min(red, green, blue)
            brightness = max(red, green, blue)

            if spread <= 22 and brightness >= 210:
                if brightness >= 235:
                    color.setAlpha(0)
                else:
                    fade = (235 - brightness) / 25.0
                    color.setAlpha(int(color.alpha() * max(0.0, min(1.0, fade))))
                image.setPixelColor(x, y, color)

            if color.alpha() > 0:
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)

    if max_x < min_x or max_y < min_y:
        return QPixmap.fromImage(image).scaledToHeight(target_height, Qt.SmoothTransformation)

    padding = 6
    min_x = max(0, min_x - padding)
    min_y = max(0, min_y - padding)
    max_x = min(image.width() - 1, max_x + padding)
    max_y = min(image.height() - 1, max_y + padding)
    cropped = image.copy(min_x, min_y, max_x - min_x + 1, max_y - min_y + 1)
    return QPixmap.fromImage(cropped).scaledToHeight(target_height, Qt.SmoothTransformation)


# ---------------------------------------------------------------------------
# Signals helper
# ---------------------------------------------------------------------------
class ProcessSignals(QObject):
    output = pyqtSignal(str)
    finished = pyqtSignal(int)


# ---------------------------------------------------------------------------
# Expectation Editor Dialog
# ---------------------------------------------------------------------------
class ExpectationDialog(QDialog):
    """Dialog for adding/editing a single expectation."""

    def __init__(self, protocol, expectation=None, media_type=None, parent=None):
        super().__init__(parent)
        self.protocol = protocol
        self.media_type = media_type
        self.setWindowTitle("Edit Expectation" if expectation else "Add Expectation")
        self.setMinimumWidth(450)
        self.setStyleSheet(STYLESHEET)
        self._build_ui(expectation)

    def _build_ui(self, exp):
        layout = QFormLayout(self)
        layout.setSpacing(12)

        metrics = PROTOCOL_METRICS.get(self.protocol, [])
        # For voip_sipp, filter metrics based on the scenario's media type
        if self.protocol == "voip_sipp" and self.media_type is not None:
            allowed = VOIP_METRICS_BY_TYPE.get(self.media_type)
            if allowed is not None:
                metrics = [m for m in metrics if m in allowed]
        self.metric_combo = QComboBox()
        self.metric_combo.addItems(metrics)
        layout.addRow("Metric:", self.metric_combo)

        self.operator_combo = QComboBox()
        for op in VALID_OPERATORS:
            self.operator_combo.addItem(OPERATOR_LABELS[op], op)
        layout.addRow("Operator:", self.operator_combo)

        self.value_spin = QDoubleSpinBox()
        self.value_spin.setRange(-999999, 999999)
        self.value_spin.setDecimals(4)
        layout.addRow("Value:", self.value_spin)

        self.unit_combo = QComboBox()
        layout.addRow("Unit:", self.unit_combo)

        self.agg_combo = QComboBox()
        self.agg_combo.addItems(["avg", "min", "max", "stddev", "percentile"])
        self.agg_combo.currentTextChanged.connect(self._on_aggregation_changed)
        self._percentile_value = None  # stores the chosen p1-p99 value
        layout.addRow("Aggregation:", self.agg_combo)

        self.scope_combo = QComboBox()
        self.scope_combo.addItems(VALID_SCOPES)
        layout.addRow("Evaluation Scope:", self.scope_combo)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        # Wire metric selection to filter compatible units
        self.metric_combo.currentTextChanged.connect(self._update_units)
        self._update_units(self.metric_combo.currentText())

        # Populate if editing
        if exp:
            idx = self.metric_combo.findText(exp.get("metric", ""))
            if idx >= 0:
                self.metric_combo.setCurrentIndex(idx)
            idx = self.operator_combo.findData(exp.get("operator", ""))
            if idx >= 0:
                self.operator_combo.setCurrentIndex(idx)
            self.value_spin.setValue(exp.get("value", 0))
            idx = self.unit_combo.findText(exp.get("unit", ""))
            if idx >= 0:
                self.unit_combo.setCurrentIndex(idx)
            agg = exp.get("aggregation", "")
            if agg.startswith("p") and agg[1:].isdigit():
                self._percentile_value = int(agg[1:])
                self.agg_combo.setCurrentText("percentile")
            else:
                idx = self.agg_combo.findText(agg)
                if idx >= 0:
                    self.agg_combo.setCurrentIndex(idx)
            idx = self.scope_combo.findText(exp.get("evaluation_scope", ""))
            if idx >= 0:
                self.scope_combo.setCurrentIndex(idx)

    def _update_units(self, metric):
        """Filter the unit combo to show only units compatible with the selected metric."""
        category = METRIC_CATEGORY.get(metric, "count")
        compatible = CATEGORY_VALID_UNITS.get(category, VALID_UNITS)
        prev_unit = self.unit_combo.currentText()
        self.unit_combo.blockSignals(True)
        self.unit_combo.clear()
        self.unit_combo.addItems(compatible)
        # Restore previous selection if still compatible
        idx = self.unit_combo.findText(prev_unit)
        if idx >= 0:
            self.unit_combo.setCurrentIndex(idx)
        self.unit_combo.blockSignals(False)

    def _on_aggregation_changed(self, text):
        """Prompt for percentile value when 'percentile' is selected."""
        if text == "percentile":
            val, ok = QInputDialog.getInt(
                self, "Percentile", "Enter percentile (1–99):",
                value=self._percentile_value or 50, min=1, max=99,
            )
            if ok:
                self._percentile_value = val
            else:
                # User cancelled — revert to avg
                self.agg_combo.blockSignals(True)
                self.agg_combo.setCurrentText("avg")
                self.agg_combo.blockSignals(False)
                self._percentile_value = None

    def get_expectation(self):
        agg = self.agg_combo.currentText()
        if agg == "percentile" and self._percentile_value is not None:
            agg = f"p{self._percentile_value}"
        return {
            "metric": self.metric_combo.currentText(),
            "operator": self.operator_combo.currentData(),
            "value": self.value_spin.value(),
            "unit": self.unit_combo.currentText(),
            "aggregation": agg,
            "evaluation_scope": self.scope_combo.currentText(),
        }


# ---------------------------------------------------------------------------
# Scenario Editor Widget
# ---------------------------------------------------------------------------
class ScenarioEditor(QWidget):
    """Editor for a single scenario."""

    changed = pyqtSignal()

    def __init__(self, scenario=None, parent=None):
        super().__init__(parent)
        self._building = True
        self._build_ui()
        if scenario:
            self.load_scenario(scenario)
        self._building = False

    def _emit_changed(self):
        if not self._building:
            self.changed.emit()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Vertical)

        # ── Top: config groups in a scrollable area ──
        top_scroll = QScrollArea()
        top_scroll.setWidgetResizable(True)
        top_scroll.setFrameShape(QFrame.NoFrame)
        top_container = QWidget()
        top_layout = QVBoxLayout(top_container)
        top_layout.setSpacing(12)

        # -- Basic Info & Schedule side-by-side --
        top_row = QHBoxLayout()

        basic_group = QGroupBox("Basic Information")
        basic_layout = QFormLayout()
        basic_layout.setSpacing(10)

        self.id_edit = QLineEdit()
        self.id_edit.setPlaceholderText("unique_scenario_id")
        self.id_edit.textChanged.connect(self._emit_changed)
        basic_layout.addRow("Scenario ID:", self.id_edit)

        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText("Human-readable description")
        self.desc_edit.textChanged.connect(self._emit_changed)
        basic_layout.addRow("Description:", self.desc_edit)

        self.enabled_check = QCheckBox("Enabled")
        self.enabled_check.setChecked(True)
        self.enabled_check.stateChanged.connect(self._emit_changed)
        basic_layout.addRow("", self.enabled_check)

        self.protocol_combo = QComboBox()
        self.protocol_combo.addItems(PROTOCOLS)
        self.protocol_combo.currentTextChanged.connect(self._on_protocol_changed)
        basic_layout.addRow("Protocol:", self.protocol_combo)

        basic_group.setLayout(basic_layout)
        top_row.addWidget(basic_group)

        sched_group = QGroupBox("Schedule")
        sched_layout = QFormLayout()
        sched_layout.setSpacing(10)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["once", "recurring"])
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        sched_layout.addRow("Mode:", self.mode_combo)

        self.start_time_edit = QLineEdit()
        self.start_time_edit.setPlaceholderText("immediate or ISO datetime")
        self.start_time_edit.setText("immediate")
        self.start_time_edit.textChanged.connect(self._emit_changed)
        sched_layout.addRow("Start Time (ISO format in UTC):", self.start_time_edit)

        self.interval_spin = QDoubleSpinBox()
        self.interval_spin.setRange(0.01, 99999)
        self.interval_spin.setValue(1)
        self.interval_spin.valueChanged.connect(self._emit_changed)
        self.interval_label = QLabel("Interval (min):")
        sched_layout.addRow(self.interval_label, self.interval_spin)

        self.duration_spin = QDoubleSpinBox()
        self.duration_spin.setRange(0.001, 99999)
        self.duration_spin.setValue(1)
        self.duration_spin.setDecimals(3)
        self.duration_spin.valueChanged.connect(self._emit_changed)
        self.duration_label = QLabel("Duration (hrs):")
        sched_layout.addRow(self.duration_label, self.duration_spin)

        sched_group.setLayout(sched_layout)
        top_row.addWidget(sched_group)

        top_layout.addLayout(top_row)

        # -- Parameters (dynamic based on protocol) --
        self.params_group = QGroupBox("Parameters")
        self.params_layout = QFormLayout()
        self.params_layout.setSpacing(10)
        self.params_group.setLayout(self.params_layout)
        top_layout.addWidget(self.params_group)
        self.param_widgets = {}

        top_layout.addStretch()
        top_scroll.setWidget(top_container)
        splitter.addWidget(top_scroll)

        # ── Bottom: Expectations with full space ──
        exp_widget = QWidget()
        exp_outer = QVBoxLayout(exp_widget)
        exp_outer.setContentsMargins(0, 0, 0, 0)
        exp_outer.setSpacing(8)

        exp_group = QGroupBox("Expectations")
        exp_layout = QVBoxLayout()
        exp_layout.setSpacing(8)

        self.exp_table = QTableWidget()
        self.exp_table.setColumnCount(6)
        self.exp_table.setHorizontalHeaderLabels(["Metric", "Operator", "Value", "Unit", "Aggregation", "Scope"])
        self.exp_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.exp_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.exp_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.exp_table.setAlternatingRowColors(True)
        self.exp_table.verticalHeader().setVisible(False)
        self.exp_table.setMinimumHeight(160)
        exp_layout.addWidget(self.exp_table, 1)

        btn_row = QHBoxLayout()
        add_exp_btn = QPushButton(qta.icon("fa5s.plus-circle", color=THEME_COLORS['text_primary']), " Add Expectation")
        add_exp_btn.clicked.connect(self._add_expectation)
        btn_row.addWidget(add_exp_btn)

        edit_exp_btn = QPushButton(qta.icon("fa5s.edit", color=THEME_COLORS['text_primary']), " Edit")
        edit_exp_btn.setProperty("class", "secondary")
        edit_exp_btn.clicked.connect(self._edit_expectation)
        btn_row.addWidget(edit_exp_btn)

        del_exp_btn = QPushButton(qta.icon("fa5s.minus-circle", color=THEME_COLORS['error']), " Remove")
        del_exp_btn.setProperty("class", "danger")
        del_exp_btn.clicked.connect(self._remove_expectation)
        btn_row.addWidget(del_exp_btn)

        btn_row.addStretch()
        exp_layout.addLayout(btn_row)
        exp_group.setLayout(exp_layout)
        exp_outer.addWidget(exp_group)
        splitter.addWidget(exp_widget)

        # Give expectations ~45% of vertical space
        splitter.setSizes([550, 450])
        splitter.setChildrenCollapsible(False)
        main_layout.addWidget(splitter)

        # Initialize
        self._on_mode_changed(self.mode_combo.currentText())
        self._on_protocol_changed(self.protocol_combo.currentText())

        # Store expectations data
        self._expectations = []

    def _on_mode_changed(self, mode):
        is_recurring = (mode == "recurring")
        self.interval_spin.setVisible(is_recurring)
        self.interval_label.setVisible(is_recurring)
        self.duration_spin.setVisible(is_recurring)
        self.duration_label.setVisible(is_recurring)
        self._emit_changed()

    def _on_protocol_changed(self, protocol):
        # Clear old param widgets
        while self.params_layout.count():
            item = self.params_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self.param_widgets.clear()

        proto_def = PROTOCOL_PARAMS.get(protocol, {})

        # Required params
        for key, info in proto_def.get("required", {}).items():
            self._add_param_widget(key, info)

        # Optional params
        for key, info in proto_def.get("optional", {}).items():
            self._add_param_widget(key, info)

        self._emit_changed()

    def _add_param_widget(self, key, info):
        ptype = info["type"]
        label = info.get("label", key)

        if ptype == "list":
            w = QLineEdit()
            w.setPlaceholderText(info.get("placeholder", "comma-separated values"))
            w.setToolTip("Enter comma-separated values")
            w.textChanged.connect(self._emit_changed)
        elif ptype == "str":
            w = QLineEdit()
            w.setPlaceholderText(info.get("placeholder", ""))
            w.textChanged.connect(self._emit_changed)
        elif ptype == "int":
            w = QSpinBox()
            w.setRange(info.get("min", 0), info.get("max", 99999))
            w.setValue(info.get("default", 1))
            w.valueChanged.connect(self._emit_changed)
        elif ptype == "bool":
            w = QCheckBox()
            w.setChecked(info.get("default", False))
            w.stateChanged.connect(self._emit_changed)
        elif ptype == "choice":
            w = QComboBox()
            w.addItems(info.get("choices", []))
            default = info.get("default", "")
            idx = w.findText(default)
            if idx >= 0:
                w.setCurrentIndex(idx)
            w.currentTextChanged.connect(self._emit_changed)
        else:
            w = QLineEdit()
            w.textChanged.connect(self._emit_changed)

        self.param_widgets[key] = (info, w)
        self.params_layout.addRow(f"{label}:", w)

    def _get_voip_media_type(self):
        """Return the current voip_sipp media type parameter, or None."""
        if self.protocol_combo.currentText() != "voip_sipp":
            return None
        info_widget = self.param_widgets.get("type")
        if info_widget is None:
            return None
        _, w = info_widget
        if isinstance(w, QComboBox):
            return w.currentText()
        return None

    def _add_expectation(self):
        protocol = self.protocol_combo.currentText()
        dlg = ExpectationDialog(protocol, media_type=self._get_voip_media_type(), parent=self)
        if dlg.exec_() == QDialog.Accepted:
            exp = dlg.get_expectation()
            self._expectations.append(exp)
            self._refresh_exp_table()
            self._emit_changed()

    def _edit_expectation(self):
        row = self.exp_table.currentRow()
        if row < 0 or row >= len(self._expectations):
            return
        protocol = self.protocol_combo.currentText()
        dlg = ExpectationDialog(protocol, self._expectations[row],
                                media_type=self._get_voip_media_type(), parent=self)
        if dlg.exec_() == QDialog.Accepted:
            self._expectations[row] = dlg.get_expectation()
            self._refresh_exp_table()
            self._emit_changed()

    def _remove_expectation(self):
        row = self.exp_table.currentRow()
        if row < 0 or row >= len(self._expectations):
            return
        self._expectations.pop(row)
        self._refresh_exp_table()
        self._emit_changed()

    def _refresh_exp_table(self):
        self.exp_table.setRowCount(len(self._expectations))
        for i, exp in enumerate(self._expectations):
            self.exp_table.setItem(i, 0, QTableWidgetItem(exp.get("metric", "")))
            self.exp_table.setItem(i, 1, QTableWidgetItem(exp.get("operator", "")))
            val = exp.get("value", 0)
            self.exp_table.setItem(i, 2, QTableWidgetItem(str(int(val) if val == int(val) else val)))
            self.exp_table.setItem(i, 3, QTableWidgetItem(exp.get("unit", "")))
            self.exp_table.setItem(i, 4, QTableWidgetItem(exp.get("aggregation", "")))
            self.exp_table.setItem(i, 5, QTableWidgetItem(exp.get("evaluation_scope", "")))

    def get_scenario(self):
        """Build scenario dict from current form values."""
        scenario = {
            "id": self.id_edit.text().strip(),
            "description": self.desc_edit.text().strip(),
            "enabled": self.enabled_check.isChecked(),
            "protocol": self.protocol_combo.currentText(),
            "schedule": {
                "mode": self.mode_combo.currentText(),
                "start_time": self.start_time_edit.text().strip() or "immediate",
            },
            "parameters": {},
            "expectations": list(self._expectations),
        }

        if self.mode_combo.currentText() == "recurring":
            scenario["schedule"]["interval_minutes"] = self.interval_spin.value()
            scenario["schedule"]["duration_hours"] = self.duration_spin.value()

        for key, (info, widget) in self.param_widgets.items():
            ptype = info["type"]
            if ptype == "list":
                text = widget.text().strip()
                scenario["parameters"][key] = [v.strip() for v in text.split(",") if v.strip()] if text else []
            elif ptype == "str":
                scenario["parameters"][key] = widget.text().strip()
            elif ptype == "int":
                scenario["parameters"][key] = widget.value()
            elif ptype == "bool":
                scenario["parameters"][key] = widget.isChecked()
            elif ptype == "choice":
                scenario["parameters"][key] = widget.currentText()

        return scenario

    def load_scenario(self, s):
        """Populate form from scenario dict."""
        self._building = True
        self.id_edit.setText(s.get("id", ""))
        self.desc_edit.setText(s.get("description", ""))
        self.enabled_check.setChecked(s.get("enabled", True))

        protocol = s.get("protocol", "speed_test")
        idx = self.protocol_combo.findText(protocol)
        if idx >= 0:
            self.protocol_combo.setCurrentIndex(idx)

        schedule = s.get("schedule", {})
        mode = schedule.get("mode", "once")
        idx = self.mode_combo.findText(mode)
        if idx >= 0:
            self.mode_combo.setCurrentIndex(idx)
        self.start_time_edit.setText(schedule.get("start_time", "immediate"))
        if mode == "recurring":
            self.interval_spin.setValue(schedule.get("interval_minutes", 1))
            self.duration_spin.setValue(schedule.get("duration_hours", 1))

        # Load parameters
        params = s.get("parameters", {})
        for key, (info, widget) in self.param_widgets.items():
            if key not in params:
                continue
            ptype = info["type"]
            val = params[key]
            if ptype == "list" and isinstance(val, list):
                widget.setText(", ".join(str(v) for v in val))
            elif ptype == "str":
                widget.setText(str(val))
            elif ptype == "int":
                widget.setValue(int(val))
            elif ptype == "bool":
                widget.setChecked(bool(val))
            elif ptype == "choice":
                ci = widget.findText(str(val))
                if ci >= 0:
                    widget.setCurrentIndex(ci)

        # Load expectations
        self._expectations = list(s.get("expectations", []))
        self._refresh_exp_table()
        self._building = False


# ---------------------------------------------------------------------------
# Configuration Tab
# ---------------------------------------------------------------------------
class ConfigurationTab(QWidget):
    """Main configuration editing tab."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # -- Top bar: global settings + actions --
        top_bar = QHBoxLayout()

        # Global settings
        gs_group = QGroupBox("Global Settings")
        gs_layout = QFormLayout()
        self.report_path_edit = QLineEdit("./results/")
        self.report_path_edit.setMinimumWidth(300)
        gs_layout.addRow("Report Path:", self.report_path_edit)
        gs_group.setLayout(gs_layout)
        top_bar.addWidget(gs_group)

        top_bar.addStretch()

        # Action buttons
        btn_col = QVBoxLayout()
        load_btn = QPushButton(qta.icon("fa5s.folder-open", color=THEME_COLORS['text_primary']), " Load Config")
        load_btn.setProperty("class", "secondary")
        load_btn.clicked.connect(self._load_config)
        btn_col.addWidget(load_btn)

        save_btn = QPushButton(qta.icon("fa5s.save", color=THEME_COLORS['text_primary']), " Save Config")
        save_btn.clicked.connect(self._save_config)
        btn_col.addWidget(save_btn)
        top_bar.addLayout(btn_col)

        layout.addLayout(top_bar)

        # -- Scenario list + editor --
        content_row = QHBoxLayout()

        # Left: scenario list (fixed width)
        left_panel = QWidget()
        left_panel.setFixedWidth(420)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        lbl = QLabel("Scenarios")
        lbl.setProperty("class", "subheading")
        left_layout.addWidget(lbl)

        self.scenario_list = QListWidget()
        self.scenario_list.setIconSize(QSize(10, 10))
        self.scenario_list.currentRowChanged.connect(self._on_scenario_selected)
        left_layout.addWidget(self.scenario_list)

        list_btn_row = QHBoxLayout()
        add_btn = QPushButton(qta.icon("fa5s.plus", color=THEME_COLORS['text_primary']), " Add")
        add_btn.clicked.connect(self._add_scenario)
        list_btn_row.addWidget(add_btn)

        dup_btn = QPushButton(qta.icon("fa5s.copy", color=THEME_COLORS['text_primary']), " Duplicate")
        dup_btn.setProperty("class", "secondary")
        dup_btn.clicked.connect(self._duplicate_scenario)
        list_btn_row.addWidget(dup_btn)

        del_btn = QPushButton(qta.icon("fa5s.trash-alt", color=THEME_COLORS['error']), " Delete")
        del_btn.setProperty("class", "danger")
        del_btn.clicked.connect(self._delete_scenario)
        list_btn_row.addWidget(del_btn)

        left_layout.addLayout(list_btn_row)
        content_row.addWidget(left_panel)

        # Right: scenario editor stack
        self.editor_stack = QStackedWidget()
        self.empty_label = QLabel("Select or add a scenario to begin editing.")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet(f"color: {THEME_COLORS['text_muted']}; font-size: 16px;")
        self.editor_stack.addWidget(self.empty_label)
        content_row.addWidget(self.editor_stack, 1)

        layout.addLayout(content_row)

        # Internal state
        self._editors = []  # list of ScenarioEditor
        self._current_index = -1

    def _add_scenario(self):
        editor = ScenarioEditor()
        editor.id_edit.setText(f"new_scenario_{len(self._editors) + 1}")
        editor.changed.connect(self._on_editor_changed)
        self._editors.append(editor)
        self.editor_stack.addWidget(editor)

        item = QListWidgetItem(self._status_icon(True), editor.id_edit.text())
        self.scenario_list.addItem(item)
        self.scenario_list.setCurrentRow(self.scenario_list.count() - 1)

    def _duplicate_scenario(self):
        idx = self.scenario_list.currentRow()
        if idx < 0 or idx >= len(self._editors):
            return
        data = self._editors[idx].get_scenario()
        data["id"] = data["id"] + "_copy"
        editor = ScenarioEditor(data)
        editor.changed.connect(self._on_editor_changed)
        self._editors.append(editor)
        self.editor_stack.addWidget(editor)
        item = QListWidgetItem(self._status_icon(data.get("enabled", True)), data["id"])
        self.scenario_list.addItem(item)
        self.scenario_list.setCurrentRow(self.scenario_list.count() - 1)

    def _delete_scenario(self):
        idx = self.scenario_list.currentRow()
        if idx < 0 or idx >= len(self._editors):
            return
        reply = QMessageBox.question(
            self, "Delete Scenario",
            f"Delete scenario '{self._editors[idx].id_edit.text()}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            editor = self._editors.pop(idx)
            self.editor_stack.removeWidget(editor)
            editor.deleteLater()
            self.scenario_list.takeItem(idx)
            if self.scenario_list.count() > 0:
                self.scenario_list.setCurrentRow(min(idx, self.scenario_list.count() - 1))
            else:
                self.editor_stack.setCurrentWidget(self.empty_label)

    def _on_scenario_selected(self, row):
        self._current_index = row
        if 0 <= row < len(self._editors):
            self.editor_stack.setCurrentWidget(self._editors[row])
        else:
            self.editor_stack.setCurrentWidget(self.empty_label)

    @staticmethod
    def _status_icon(enabled):
        color = THEME_COLORS['success'] if enabled else THEME_COLORS['error']
        return qta.icon("fa5s.circle", color=color)

    def _on_editor_changed(self):
        """Update scenario list label when editor changes."""
        idx = self.scenario_list.currentRow()
        if 0 <= idx < len(self._editors):
            editor = self._editors[idx]
            sid = editor.id_edit.text().strip() or "(unnamed)"
            enabled = editor.enabled_check.isChecked()
            item = self.scenario_list.item(idx)
            item.setText(sid)
            item.setIcon(self._status_icon(enabled))

    def get_config(self):
        """Build full configuration dict."""
        config = {
            "global_settings": {
                "report_path": self.report_path_edit.text().strip() or "./results/"
            },
            "scenarios": [e.get_scenario() for e in self._editors]
        }
        return config

    def load_config_data(self, config):
        """Load a configuration dict into the editor."""
        # Clear existing
        for editor in self._editors:
            self.editor_stack.removeWidget(editor)
            editor.deleteLater()
        self._editors.clear()
        self.scenario_list.clear()

        # Global settings
        gs = config.get("global_settings", {})
        self.report_path_edit.setText(gs.get("report_path", "./results/"))

        # Scenarios
        for s in config.get("scenarios", []):
            editor = ScenarioEditor(s)
            editor.changed.connect(self._on_editor_changed)
            self._editors.append(editor)
            self.editor_stack.addWidget(editor)
            enabled = s.get("enabled", True)
            item = QListWidgetItem(self._status_icon(enabled), s.get("id", "(unnamed)"))
            self.scenario_list.addItem(item)

        if self.scenario_list.count() > 0:
            self.scenario_list.setCurrentRow(0)

    def _load_config(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Configuration", "configurations/", "JSON Files (*.json)"
        )
        if path:
            try:
                with open(path, "r") as f:
                    config = json.load(f)
                self.load_config_data(config)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load config:\n{e}")

    def _save_config(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Configuration", "configurations/main.json", "JSON Files (*.json)"
        )
        if path:
            try:
                config = self.get_config()
                with open(path, "w") as f:
                    json.dump(config, f, indent=2)
                QMessageBox.information(self, "Saved", f"Configuration saved to:\n{path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save config:\n{e}")


# ---------------------------------------------------------------------------
# Test Runner Tab
# ---------------------------------------------------------------------------
class TestRunnerTab(QWidget):
    """Tab for running orchestrate.py and viewing live output."""

    _MAX_CONSOLE_LINES = 5000
    _TRIM_TO = 3000

    def __init__(self, config_tab: ConfigurationTab, parent=None):
        super().__init__(parent)
        self.config_tab = config_tab
        self.process = None
        self._last_console_line = ""
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # -- Controls --
        ctrl_row = QHBoxLayout()

        self.run_btn = QPushButton(qta.icon("fa5s.rocket", color="#ffffff"), "  Run Tests  ")
        self.run_btn.setStyleSheet(
            f"QPushButton {{ font-size: 16px; padding: 14px 44px; border-radius: 24px; "
            f"background: qlineargradient(x1:0, y1:0, x2:1, y2:1, "
            f"stop:0 {THEME_COLORS['red_primary']}, stop:1 {THEME_COLORS['red_dark']}); "
            f"letter-spacing: 1.5px; font-weight: 800; border: 1px solid {THEME_COLORS['red_primary']}; }}"
            f"QPushButton:hover {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, "
            f"stop:0 {THEME_COLORS['red_hover']}, stop:1 {THEME_COLORS['red_primary']}); "
            f"border: 1px solid {THEME_COLORS['red_hover']}; }}"
            f"QPushButton:disabled {{ background: {THEME_COLORS['bg_light']}; "
            f"color: {THEME_COLORS['text_muted']}; border: 1px solid {THEME_COLORS['border']}; }}"
        )
        self.run_btn.clicked.connect(self._run_tests)
        ctrl_row.addWidget(self.run_btn)

        self.stop_btn = QPushButton(qta.icon("fa5s.stop-circle", color=THEME_COLORS['error']), " Stop")
        self.stop_btn.setProperty("class", "danger")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop_tests)
        ctrl_row.addWidget(self.stop_btn)

        ctrl_row.addStretch()

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet(f"color: {THEME_COLORS['text_secondary']}; font-size: 15px;")
        ctrl_row.addWidget(self.status_label)

        layout.addLayout(ctrl_row)

        # -- Spinner --
        self._spin_widget = qta.IconWidget()
        self._spin_widget.setFixedSize(40, 40)
        self._spin_widget.setStyleSheet("background: transparent;")
        self._spin_widget.setVisible(False)
        self._spin_animation = qta.Spin(self._spin_widget, interval=50, step=5)
        self._spin_widget.setIcon(qta.icon("fa5s.circle-notch", color=THEME_COLORS['success'], animation=self._spin_animation))
        self._spin_widget.setIconSize(QSize(34, 34))
        ctrl_row.addWidget(self._spin_widget)

        # -- Output console --
        console_hbox = QHBoxLayout()
        console_icon = QLabel()
        console_icon.setPixmap(qta.icon("fa5s.terminal", color=THEME_COLORS['text_secondary']).pixmap(16, 16))
        console_icon.setStyleSheet("background: transparent;")
        console_hbox.addWidget(console_icon)
        console_label = QLabel("Console Output")
        console_label.setProperty("class", "subheading")
        console_hbox.addWidget(console_label)
        console_hbox.addStretch()
        layout.addLayout(console_hbox)

        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setMinimumHeight(300)
        layout.addWidget(self.console)

    # Lines produced by ``docker service create`` progress reporting that
    # should be hidden from the user – they only care about orchestrate.py's
    # own print statements.
    _DOCKER_NOISE_PATTERNS = (
        "overall progress:",
        "verify: ",
        "converged",
        "image ",
        "its digest",
        "possibly leading to",
        "versions of the image",
    )

    def _run_tests(self):
        # Save config before running
        config = self.config_tab.get_config()
        config_path = os.path.join(os.path.dirname(__file__), "configurations", "main.json")
        try:
            with open(config_path, "w") as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save config:\n{e}")
            return

        self.console.clear()
        self._last_console_line = ""
        self.console.append(f"[INFO] Configuration saved to {config_path}")
        self.console.append("[INFO] Starting orchestrate.py...\n")

        self.run_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self._spin_widget.setVisible(True)
        self._spin_animation.start()
        self.status_label.setText("Running...")
        self.status_label.setStyleSheet(f"color: {THEME_COLORS['red_primary']}; font-size: 15px; font-weight: bold;")

        self.process = QProcess(self)
        self.process.setWorkingDirectory(os.path.dirname(os.path.abspath(__file__)))
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._read_output)
        self.process.finished.connect(self._on_finished)
        # -u = unbuffered so we get live output line-by-line
        self.process.start("python3", ["-u", "orchestrate.py"])

    def _stop_tests(self):
        if self.process and self.process.state() != QProcess.NotRunning:
            self.process.kill()
            self.console.append("\n[INFO] Process killed by user.")

    def _is_docker_noise(self, line: str) -> bool:
        """Return True if the line is Docker service-create progress noise."""
        stripped = line.strip()
        if not stripped:
            return False
        # Docker service IDs are 25-char hex strings on their own line
        if len(stripped) == 25 and all(c in "0123456789abcdef" for c in stripped):
            return True
        # Bare task progress lines like "1/1:  " or "1/1: running"
        if stripped.startswith("1/") and ":" in stripped and len(stripped) < 40:
            return True
        for pattern in self._DOCKER_NOISE_PATTERNS:
            if pattern in stripped:
                return True
        return False

    def _read_output(self):
        data = self.process.readAllStandardOutput().data().decode("utf-8", errors="replace")
        # Filter out docker service create noise and duplicate consecutive lines
        filtered_lines = []
        for line in data.splitlines(keepends=True):
            if self._is_docker_noise(line):
                continue
            stripped = line.rstrip()
            if stripped and stripped == self._last_console_line:
                continue
            if stripped:
                self._last_console_line = stripped
            filtered_lines.append(line)
        if filtered_lines:
            text = "".join(filtered_lines)
            self.console.moveCursor(self.console.textCursor().End)
            self.console.insertPlainText(text)
            self.console.moveCursor(self.console.textCursor().End)

            # Trim console if it exceeds max lines to prevent memory bloat
            doc = self.console.document()
            if doc.blockCount() > self._MAX_CONSOLE_LINES:
                cursor = self.console.textCursor()
                cursor.movePosition(cursor.Start)
                cursor.movePosition(cursor.Down, cursor.KeepAnchor,
                                    doc.blockCount() - self._TRIM_TO)
                cursor.removeSelectedText()

    def _on_finished(self, exit_code, exit_status):
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self._spin_animation.stop()
        self._spin_widget.setVisible(False)

        if exit_code == 0:
            self.status_label.setText("Completed Successfully")
            self.status_label.setStyleSheet(f"color: {THEME_COLORS['success']}; font-size: 15px; font-weight: bold;")
            self.console.append("\n[INFO] Orchestration completed successfully.")
        else:
            self.status_label.setText(f"Failed (exit code {exit_code})")
            self.status_label.setStyleSheet(f"color: {THEME_COLORS['error']}; font-size: 15px; font-weight: bold;")
            self.console.append(f"\n[ERROR] Process exited with code {exit_code}")


# ---------------------------------------------------------------------------
# Results Tab
# ---------------------------------------------------------------------------
class ResultsTab(QWidget):
    """Tab for displaying test results from CSV exports."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Controls
        ctrl = QHBoxLayout()

        self.results_path_edit = QLineEdit("./results/")
        self.results_path_edit.setMinimumWidth(300)
        ctrl.addWidget(QLabel("Results Path:"))
        ctrl.addWidget(self.results_path_edit)

        refresh_btn = QPushButton(qta.icon("fa5s.sync-alt", color=THEME_COLORS['text_primary']), " Load Results")
        refresh_btn.clicked.connect(self._load_results)
        ctrl.addWidget(refresh_btn)

        ctrl.addStretch()

        nuke_btn = QPushButton(qta.icon("fa5s.bomb", color=THEME_COLORS['error']), " Nuke Database")
        nuke_btn.setProperty("class", "danger")
        nuke_btn.clicked.connect(self._nuke_database)
        ctrl.addWidget(nuke_btn)

        layout.addLayout(ctrl)

        # Sub-tabs for different CSV files
        self.result_tabs = QTabWidget()
        self.result_tabs.tabBar().setExpanding(False)
        self.result_tabs.setUsesScrollButtons(True)
        layout.addWidget(self.result_tabs)

        # Summary panel
        self.summary_group = QGroupBox("Test Summary")
        summary_layout = QVBoxLayout()
        self.summary_label = QLabel("Load results to see summary.")
        self.summary_label.setWordWrap(True)
        self.summary_label.setStyleSheet(f"font-size: 15px; color: {THEME_COLORS['text_secondary']};")
        summary_layout.addWidget(self.summary_label)
        self.summary_group.setLayout(summary_layout)
        layout.addWidget(self.summary_group)

    def _load_results(self):
        results_dir = self.results_path_edit.text().strip()
        if not os.path.isdir(results_dir):
            QMessageBox.warning(self, "Warning", f"Results directory not found:\n{results_dir}")
            return

        self.result_tabs.clear()

        _ic = THEME_COLORS['text_secondary']
        csv_files = [
            ("results_log.csv", "Results Log", qta.icon("fa5s.clipboard-list", color=_ic)),
            ("scenario_summary.csv", "Scenario Summary", qta.icon("fa5s.list-alt", color=_ic)),
            ("scenarios.csv", "Scenarios", qta.icon("fa5s.project-diagram", color=_ic)),
            ("test_runs.csv", "Test Runs", qta.icon("fa5s.running", color=_ic)),
            ("raw_metrics.csv", "Raw Metrics", qta.icon("fa5s.database", color=_ic)),
        ]

        pass_count = 0
        fail_count = 0
        results_log_data = []

        for filename, tab_name, tab_icon in csv_files:
            filepath = os.path.join(results_dir, filename)
            if not os.path.exists(filepath):
                continue

            try:
                with open(filepath, "r", newline="") as f:
                    reader = csv.reader(f)
                    rows = list(reader)
            except Exception:
                continue

            if not rows:
                continue

            headers = rows[0]
            data = rows[1:]

            table = QTableWidget()
            table.setColumnCount(len(headers))
            table.setHorizontalHeaderLabels(headers)
            table.setRowCount(len(data))
            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
            table.setAlternatingRowColors(True)
            table.verticalHeader().setVisible(False)
            table.setEditTriggers(QAbstractItemView.NoEditTriggers)

            # Find status column for results_log
            status_col = -1
            if filename == "results_log.csv" and "status" in headers:
                status_col = headers.index("status")

            for r, row in enumerate(data):
                for c, val in enumerate(row):
                    item = QTableWidgetItem(val)
                    # Color-code PASS/FAIL/ERROR
                    if c == status_col:
                        if val.upper() == "PASS":
                            item.setForeground(QColor(THEME_COLORS["success"]))
                            item.setFont(QFont("", -1, QFont.Bold))
                            pass_count += 1
                        elif val.upper() == "FAIL":
                            item.setForeground(QColor(THEME_COLORS["error"]))
                            item.setFont(QFont("", -1, QFont.Bold))
                            fail_count += 1
                        elif val.upper() == "ERROR":
                            item.setForeground(QColor(THEME_COLORS["warning"]))
                            item.setFont(QFont("", -1, QFont.Bold))
                    table.setItem(r, c, item)

            if filename == "results_log.csv":
                results_log_data = data

            self.result_tabs.addTab(table, tab_icon, tab_name)

        # Build Expectation Report tab
        self._build_expectation_report(results_dir, results_log_data)

        # Build Error Log tab
        self._build_error_log_tab(results_dir)

        # Update summary from all results initially
        self._update_summary(self._report_rows if hasattr(self, '_report_rows') else [])

    def _build_expectation_report(self, results_dir, results_log_data):
        """Build a user-friendly Expectation Report tab that resolves UUIDs to
        human-readable scenario/test names using the config_snapshot stored in
        scenarios.csv."""
        if not results_log_data:
            return

        # --- Build lookup maps ---
        # scenario_id -> user-provided id & protocol
        scenario_map = {}
        scenario_id_order = []
        scenarios_path = os.path.join(results_dir, "scenarios.csv")
        if os.path.exists(scenarios_path):
            try:
                with open(scenarios_path, "r", newline="") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        sid = row.get("scenario_id", "")
                        config_raw = row.get("config_snapshot", "{}")
                        try:
                            config = json.loads(config_raw)
                        except json.JSONDecodeError:
                            config = {}
                        scenario_map[sid] = {
                            "name": config.get("id", sid[:8]),
                            "protocol": row.get("protocol", config.get("protocol", "")),
                            "description": config.get("description", ""),
                        }
                        scenario_id_order.append(sid)
            except Exception:
                pass

        # run_id -> {scenario_id, start_time}
        run_map = {}
        runs_path = os.path.join(results_dir, "test_runs.csv")
        if os.path.exists(runs_path):
            try:
                with open(runs_path, "r", newline="") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        run_map[row.get("run_id", "")] = {
                            "scenario_id": row.get("scenario_id", ""),
                            "start_time": row.get("start_time", ""),
                        }
            except Exception:
                pass

        # --- Read results_log.csv with headers ---
        rl_path = os.path.join(results_dir, "results_log.csv")
        if not os.path.exists(rl_path):
            return
        try:
            with open(rl_path, "r", newline="") as f:
                reader = csv.DictReader(f)
                rl_rows = list(reader)
        except Exception:
            return

        if not rl_rows:
            return

        # --- Build report rows ---
        report_headers = [
            "Scenario", "Protocol", "Metric", "Expected", "Measured",
            "Status", "Scope", "Timestamp", "Description",
        ]
        report_rows = []
        for row in rl_rows:
            run_id = row.get("run_id", "")
            run_info = run_map.get(run_id, {})
            scenario_id = run_info.get("scenario_id", "")
            info = scenario_map.get(scenario_id, {})

            report_rows.append({
                "scenario_id": scenario_id,
                "cells": [
                    info.get("name", scenario_id[:8] if scenario_id else "—"),
                    info.get("protocol", ""),
                    row.get("metric_name", ""),
                    row.get("expected_value", ""),
                    row.get("measured_value", ""),
                    row.get("status", ""),
                    row.get("scope", ""),
                    run_info.get("start_time", ""),
                    info.get("description", ""),
                ],
            })

        # --- Store report data for filtering ---
        self._report_headers = report_headers
        self._report_rows = report_rows
        self._scenario_map = scenario_map

        # --- Build wrapper widget with filter + table ---
        wrapper = QWidget()
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.setSpacing(8)

        # Filter row
        filter_row = QHBoxLayout()
        filter_label = QLabel("Filter by Scenario:")
        filter_label.setStyleSheet(f"color: {THEME_COLORS['text_secondary']}; font-weight: 700;")
        filter_row.addWidget(filter_label)

        self._report_filter_combo = QComboBox()
        self._report_filter_combo.setMinimumWidth(360)
        self._report_filter_combo.addItem("All Scenarios", "")
        if scenario_id_order:
            self._report_filter_combo.addItem(f"Latest  ({scenario_id_order[-1]})", "__latest__")
        for sid in scenario_id_order:
            self._report_filter_combo.addItem(sid, sid)
        self._latest_scenario_id = scenario_id_order[-1] if scenario_id_order else ""
        self._report_filter_combo.currentIndexChanged.connect(self._apply_report_filter)
        filter_row.addWidget(self._report_filter_combo)

        # Protocol filter
        proto_label = QLabel("Filter by Protocol:")
        proto_label.setStyleSheet(f"color: {THEME_COLORS['text_secondary']}; font-weight: 700;")
        filter_row.addWidget(proto_label)

        self._report_proto_combo = QComboBox()
        self._report_proto_combo.setMinimumWidth(180)
        self._report_proto_combo.addItem("All Protocols", "")
        for proto in PROTOCOLS:
            self._report_proto_combo.addItem(proto, proto)
        self._report_proto_combo.currentIndexChanged.connect(self._apply_report_filter)
        filter_row.addWidget(self._report_proto_combo)

        filter_row.addStretch()
        wrapper_layout.addLayout(filter_row)

        # Table
        self._report_table = QTableWidget()
        self._report_table.setColumnCount(len(report_headers))
        self._report_table.setHorizontalHeaderLabels(report_headers)
        self._report_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self._report_table.setAlternatingRowColors(True)
        self._report_table.verticalHeader().setVisible(False)
        self._report_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        wrapper_layout.addWidget(self._report_table)

        # Populate table (unfiltered)
        self._populate_report_table(report_rows)

        self.result_tabs.insertTab(0, wrapper, qta.icon("fa5s.check-double", color=THEME_COLORS['text_secondary']), "Expectation Report")
        self.result_tabs.setCurrentIndex(0)

    def _build_error_log_tab(self, results_dir: str):
        """Load error_log.txt from the results directory and display it in a tab."""
        error_log_path = os.path.join(results_dir, "error_log.txt")
        if not os.path.exists(error_log_path):
            return

        try:
            with open(error_log_path, "r") as f:
                content = f.read()
        except Exception:
            return

        if not content.strip():
            return

        log_display = QTextEdit()
        log_display.setReadOnly(True)
        log_display.setPlainText(content)
        log_display.setStyleSheet(
            f"background-color: {THEME_COLORS['bg_card']}; "
            f"color: {THEME_COLORS['error']}; "
            f"font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace; "
            f"font-size: 13px; "
            f"padding: 14px; "
            f"border: 1px solid {THEME_COLORS['border']}; "
            f"border-radius: 12px;"
        )

        self.result_tabs.addTab(
            log_display,
            qta.icon("fa5s.exclamation-triangle", color=THEME_COLORS['warning']),
            "Error Log"
        )

    def _populate_report_table(self, rows):
        """Fill the expectation report table with the given row dicts."""
        table = self._report_table
        table.setRowCount(len(rows))
        status_col = self._report_headers.index("Status")
        for r, entry in enumerate(rows):
            cells = entry["cells"]
            for c, val in enumerate(cells):
                item = QTableWidgetItem(val)
                if c == status_col:
                    if val.upper() == "PASS":
                        item.setForeground(QColor(THEME_COLORS["success"]))
                        item.setFont(QFont("", -1, QFont.Bold))
                    elif val.upper() == "FAIL":
                        item.setForeground(QColor(THEME_COLORS["error"]))
                        item.setFont(QFont("", -1, QFont.Bold))
                    elif val.upper() == "ERROR":
                        item.setForeground(QColor(THEME_COLORS["warning"]))
                        item.setFont(QFont("", -1, QFont.Bold))
                table.setItem(r, c, item)

    def _apply_report_filter(self):
        """Filter the expectation report table by scenario_id and/or protocol."""
        selected_sid = self._report_filter_combo.currentData()
        selected_proto = self._report_proto_combo.currentData()
        filtered = self._report_rows
        if selected_sid:
            sid = self._latest_scenario_id if selected_sid == "__latest__" else selected_sid
            filtered = [row for row in filtered if row["scenario_id"] == sid]
        if selected_proto:
            filtered = [row for row in filtered if row["cells"][1] == selected_proto]
        self._populate_report_table(filtered)
        self._update_summary(filtered)

    def _update_summary(self, rows):
        """Update the Test Summary panel based on the given report rows."""
        status_col = self._report_headers.index("Status") if hasattr(self, '_report_headers') else 5
        pass_count = sum(1 for r in rows if r["cells"][status_col].upper() == "PASS")
        fail_count = sum(1 for r in rows if r["cells"][status_col].upper() == "FAIL")
        error_count = sum(1 for r in rows if r["cells"][status_col].upper() == "ERROR")
        total = pass_count + fail_count + error_count
        if total > 0:
            pass_rate = (pass_count / total) * 100
            if fail_count == 0 and error_count == 0:
                headline = "ALL TESTS PASSED"
                headline_color = THEME_COLORS['success']
            elif error_count > 0 and fail_count == 0:
                headline = f"{error_count} TEST(S) ERRORED"
                headline_color = THEME_COLORS['warning']
            else:
                headline = f"{fail_count} TEST(S) FAILED"
                headline_color = THEME_COLORS['error']
            self.summary_label.setText(
                f"<span style='font-size:22px; font-weight:bold; color:{headline_color};'>"
                f"{headline}</span><br><br>"
                f"<span style='font-size:15px;'>"
                f"Total Expectations: <b>{total}</b> &nbsp;&nbsp;|&nbsp;&nbsp; "
                f"<span style='color:{THEME_COLORS['success']};'>Passed: <b>{pass_count}</b></span> &nbsp;&nbsp;|&nbsp;&nbsp; "
                f"<span style='color:{THEME_COLORS['error']};'>Failed: <b>{fail_count}</b></span> &nbsp;&nbsp;|&nbsp;&nbsp; "
                f"<span style='color:{THEME_COLORS['warning']};'>Errors: <b>{error_count}</b></span> &nbsp;&nbsp;|&nbsp;&nbsp; "
                f"Pass Rate: <b>{pass_rate:.1f}%</b></span>"
            )
        else:
            self.summary_label.setText("No matching results for the selected filters.")

    def _nuke_database(self):
        """Stop and remove the Postgres container and its volume."""
        reply = QMessageBox.warning(
            self, "Nuke Database",
            "This will permanently destroy the Postgres database by stopping "
            "and removing the Docker container and the 'load-test' volume.\n\n"
            "All unsaved results will be lost. Make sure you have exported "
            "the results in a directory before proceeding.\n\n"
            "Are you sure?",
            QMessageBox.Yes | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        if reply != QMessageBox.Yes:
            return

        commands = [
            ["docker", "stop", "db-container"],
            ["docker", "rm", "db-container"],
            ["docker", "volume", "rm", "load-test"],
        ]
        errors = []
        for cmd in commands:
            try:
                subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            except Exception as e:
                errors.append(f"{' '.join(cmd)}: {e}")

        if errors:
            QMessageBox.warning(self, "Nuke Database", "Completed with errors:\n" + "\n".join(errors))
        else:
            QMessageBox.information(self, "Nuke Database", "Database container and volume removed successfully.")


# ---------------------------------------------------------------------------
# Main Window
# ---------------------------------------------------------------------------
class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self.setWindowTitle("Load Test Automation Framework")
        self.setMinimumWidth(1280)
        self.setMinimumHeight(860)
        self._build_ui()
        self._load_default_config()
        self.showMaximized()

    def resizeEvent(self, event):
        if self.width() < 1280 or self.height() < 860:
            self.resize(max(self.width(), 1280), max(self.height(), 860))
        self._bg_cache = None
        super().resizeEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        size = self.size()
        cache = getattr(self, '_bg_cache', None)
        if cache is None or cache.size() != size:
            bg = QPixmap(size)
            p = QPainter(bg)
            gradient = QLinearGradient(0, 0, size.width(), size.height())
            gradient.setColorAt(0.0, QColor("#080812"))
            gradient.setColorAt(0.15, QColor("#06060e"))
            gradient.setColorAt(0.35, QColor("#04040a"))
            gradient.setColorAt(0.5, QColor(THEME_COLORS['bg_dark']))
            gradient.setColorAt(0.65, QColor("#04040a"))
            gradient.setColorAt(0.85, QColor("#07050e"))
            gradient.setColorAt(1.0, QColor("#0a0810"))
            p.fillRect(bg.rect(), gradient)
            p.end()
            self._bg_cache = bg
        painter.drawPixmap(0, 0, self._bg_cache)
        painter.end()

    def _build_ui(self):
        # Title bar / toolbar
        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(20, 20))

        logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo", "honeywell-logo-11530965197um5hebvsd4.png")
        title_label = QLabel()
        title_label.setAttribute(Qt.WA_TranslucentBackground)
        logo_pixmap = build_toolbar_logo_pixmap(logo_path, target_height=28)
        title_label.setPixmap(logo_pixmap)
        title_label.setStyleSheet("background: transparent; border: none; padding: 4px 2px;")
        toolbar.addWidget(title_label)

        # Separator dot
        sep = QLabel("\u2022")
        sep.setStyleSheet(
            f"color: {THEME_COLORS['border_light']}; font-size: 18px; "
            f"background: transparent; padding: 0 4px;"
        )
        toolbar.addWidget(sep)

        subtitle = QLabel("Load Test Automation Framework")
        subtitle.setStyleSheet(
            f"font-size: 20px; color: #f0f0f4; "
            f"background: transparent; padding-left: 4px; letter-spacing: 1.5px;"
            f"font-weight: bold; text-transform: uppercase;"
        )
        toolbar.addWidget(subtitle)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        spacer.setStyleSheet("background: transparent;")
        toolbar.addWidget(spacer)

        self.addToolBar(toolbar)

        # Central widget with tabs
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        _icon_color = THEME_COLORS['text_secondary']

        self.config_tab = ConfigurationTab()
        self.tabs.addTab(self.config_tab, qta.icon("fa5s.cogs", color=_icon_color), "  Configuration  ")

        self.runner_tab = TestRunnerTab(self.config_tab)
        self.tabs.addTab(self.runner_tab, qta.icon("fa5s.play-circle", color=_icon_color), "  Run Tests  ")

        self.results_tab = ResultsTab()
        self.tabs.addTab(self.results_tab, qta.icon("fa5s.chart-bar", color=_icon_color), "  Results  ")

        self.setCentralWidget(self.tabs)

    def _load_default_config(self):
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "configurations", "main.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    config = json.load(f)
                self.config_tab.load_config_data(config)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)

    # Set ultra-dark palette as base
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(THEME_COLORS["bg_dark"]))
    palette.setColor(QPalette.WindowText, QColor(THEME_COLORS["text_primary"]))
    palette.setColor(QPalette.Base, QColor(THEME_COLORS["bg_card"]))
    palette.setColor(QPalette.AlternateBase, QColor(THEME_COLORS["table_alt_row"]))
    palette.setColor(QPalette.Text, QColor(THEME_COLORS["text_primary"]))
    palette.setColor(QPalette.Button, QColor(THEME_COLORS["bg_light"]))
    palette.setColor(QPalette.ButtonText, QColor(THEME_COLORS["text_primary"]))
    palette.setColor(QPalette.Highlight, QColor(THEME_COLORS["red_primary"]))
    palette.setColor(QPalette.HighlightedText, QColor("white"))
    palette.setColor(QPalette.ToolTipBase, QColor(THEME_COLORS["bg_elevated"]))
    palette.setColor(QPalette.ToolTipText, QColor(THEME_COLORS["text_primary"]))
    palette.setColor(QPalette.PlaceholderText, QColor(THEME_COLORS["text_muted"]))
    app.setPalette(palette)

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

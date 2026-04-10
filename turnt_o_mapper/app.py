"""
Main application window (PyQt6 GUI).

The ``App`` class builds the full UI: header, left panel with four tabs
(Generate, DBT Import, Textures, Settings), right panel with 2D / 3D
preview and log.  Event handlers delegate to the generation, import, and
preview modules for the actual work.
"""

import io
import math
import os
import random
import subprocess
import threading
import time
from typing import Dict, List, Optional, Set

from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QSlider, QSpinBox, QDoubleSpinBox,
    QCheckBox, QLineEdit, QTabWidget, QTextEdit, QScrollArea,
    QFileDialog, QFrame, QSizePolicy, QButtonGroup, QStatusBar,
    QPlainTextEdit,
)
from PyQt6.QtCore import Qt, QTimer, QSize, pyqtSignal
from PyQt6.QtGui import (
    QColor, QTextCharFormat, QTextCursor, QFont, QPixmap, QImage,
    QPainter, QPen, QPainterPath,
)

try:
    from PIL import Image
    PIL_OK = True
except ImportError:
    PIL_OK = False

from .constants import (
    ALL_TEXTURES, FLOOR_TEX, WALL_TEX, CEIL_TEX,
    T, DARK_T, LIGHT_T, IMG_EXTS,
)
from .__version__ import __version__
from .models import Room, Bridge
from .config import load_app_cfg, save_app_cfg
from .generation import generate_map
from .viewer3d import Viewer3DWidget
from .preview2d import Preview2DWidget
from . import dbt_import
from .updater import check_for_update, download_and_restart


# ── Stylesheet builder ────────────────────────────────────────────────────────
def build_qss(t: dict) -> str:
    """Generate the application QSS from a theme palette dict *t*."""
    return f"""
* {{
    color: {t['text']};
    font-family: "Segoe UI Variable", "Segoe UI", "Inter", "SF Pro Text", Arial, sans-serif;
    font-size: 10pt;
    outline: none;
}}

QMainWindow, QWidget {{
    background-color: {t['bg']};
}}

QWidget#leftPanel {{
    background-color: {t['bg_panel']};
    border-radius: 10px;
    border: 1px solid {t['card_border']};
}}

QWidget#rightPanel {{
    background-color: {t['bg']};
}}

QWidget#headerWidget {{
    background-color: {t['bg_card']};
    border-bottom: 2px solid {t['accent']};
}}

QLabel#titleAccent {{
    color: {t['accent']};
    font-family: "Cascadia Code", "JetBrains Mono", "Consolas";
    font-size: 17pt;
    font-weight: bold;
    letter-spacing: 1px;
    background: transparent;
}}

QLabel#titleText {{
    color: {t['text']};
    font-family: "Cascadia Code", "JetBrains Mono", "Consolas";
    font-size: 17pt;
    font-weight: bold;
    letter-spacing: 1px;
    background: transparent;
}}

QLabel#titleSub {{
    color: {t['text_dim']};
    font-size: 8pt;
    letter-spacing: 0.5px;
    background: transparent;
}}

QLabel#versionLabel {{
    color: {t['text_dim']};
    font-size: 8pt;
    background: transparent;
    padding: 0 4px;
}}

QFrame#headerSep {{
    background-color: {t['border']};
    max-width: 1px;
    min-width: 1px;
}}

QTabWidget::pane {{
    border: 1px solid {t['card_border']};
    background-color: {t['bg_panel']};
    border-radius: 0px 8px 8px 8px;
}}

QTabBar::tab {{
    background-color: transparent;
    color: {t['text_dim']};
    padding: 8px 16px;
    font-weight: 600;
    font-size: 9pt;
    border: none;
    margin-right: 2px;
    border-radius: 6px 6px 0px 0px;
}}

QTabBar::tab:selected {{
    background-color: {t['bg_card']};
    color: {t['accent']};
    border-bottom: 2px solid {t['accent']};
}}

QTabBar::tab:hover:!selected {{
    background-color: {t['tab_hover']};
    color: {t['text']};
}}

QSlider::groove:horizontal {{
    height: 4px;
    background: {t['bg_input']};
    border-radius: 2px;
}}

QSlider::handle:horizontal {{
    background: {t['accent']};
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}}

QSlider::handle:horizontal:hover {{
    background: {t['accent_bright']};
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 8px;
}}

QSlider::sub-page:horizontal {{
    background: {t['accent']};
    border-radius: 2px;
    height: 4px;
}}

QSpinBox, QDoubleSpinBox, QLineEdit {{
    background-color: {t['bg_input']};
    color: {t['text']};
    border: 1px solid {t['card_border']};
    border-radius: 6px;
    padding: 5px 8px;
    font-family: "Cascadia Code", "Consolas", monospace;
    font-size: 9pt;
    selection-background-color: {t['accent']};
    selection-color: {t['selection_fg']};
}}

QSpinBox:focus, QDoubleSpinBox:focus, QLineEdit:focus {{
    border: 1px solid {t['accent']};
}}

QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    background-color: {t['spin_btn_bg']};
    border: none;
    width: 18px;
    border-radius: 0px 5px 5px 0px;
}}

QSpinBox::up-button:hover, QSpinBox::down-button:hover,
QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {{
    background-color: {t['border']};
}}

QSpinBox:disabled, QDoubleSpinBox:disabled {{
    color: {t['text_dim']};
    border-color: {t['disabled_border']};
}}

QCheckBox {{
    color: {t['text']};
    font-size: 9pt;
    spacing: 8px;
    background: transparent;
}}

QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    background-color: {t['bg_input']};
    border: 1px solid {t['card_border']};
    border-radius: 4px;
}}

QCheckBox::indicator:checked {{
    background-color: {t['accent']};
    border-color: {t['accent']};
    image: none;
}}

QCheckBox::indicator:hover {{
    border-color: {t['accent']};
}}

QCheckBox:disabled {{
    color: {t['text_dim']};
}}

QPushButton {{
    background-color: {t['btn_bg']};
    color: {t['text']};
    border: 1px solid {t['btn_border']};
    border-radius: 6px;
    padding: 6px 14px;
    font-weight: 600;
    font-size: 9pt;
    letter-spacing: 0.3px;
}}

QPushButton:hover {{
    background-color: {t['btn_hover']};
    border-color: {t['border']};
    color: {t['btn_fg']};
}}

QPushButton:pressed {{
    background-color: {t['bg_input']};
}}

QPushButton:checked {{
    background-color: {t['accent']};
    color: #000000;
    border-color: {t['accent']};
}}

QPushButton#btnSave {{
    background-color: {t['save_bg']};
    color: #ffffff;
    border-color: {t['save_border']};
    font-weight: 700;
}}
QPushButton#btnSave:hover {{ background-color: {t['save_hover']}; border-color: {t['success']}; }}

QPushButton#btnFolder {{
    background-color: {t['folder_bg']};
    color: #ffffff;
    border-color: {t['folder_border']};
}}
QPushButton#btnFolder:hover {{ background-color: {t['folder_hover']}; }}

QPushButton#btnLaunch {{
    background-color: {t['launch_bg']};
    color: #ffffff;
    border-color: {t['launch_border']};
}}
QPushButton#btnLaunch:hover {{ background-color: {t['launch_hover']}; border-color: {t['warning']}; }}

QPushButton#btnGenerate {{
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {t['gen_grad_l']}, stop:1 {t['gen_grad_r']});
    color: #ffffff;
    border: none;
    border-radius: 8px;
    font-size: 11pt;
    font-weight: 700;
    padding: 10px 20px;
    letter-spacing: 0.5px;
}}
QPushButton#btnGenerate:hover {{
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {t['gen_grad_r']}, stop:1 {t['gen_grad_rh']});
}}
QPushButton#btnGenerate:pressed {{
    background-color: {t['accent_press']};
}}

QPushButton#btnAuto[active="true"] {{
    background-color: {t['auto_bg']};
    color: {t['auto_text']};
    border-color: {t['auto_border']};
}}
QPushButton#btnAuto[active="false"] {{
    background-color: {t['btn_bg']};
    color: {t['text_dim']};
    border-color: {t['btn_border']};
}}

QPushButton#btnLayout {{
    font-size: 8pt;
    padding: 5px 8px;
    border-radius: 5px;
}}
QPushButton#btnLayout:checked {{
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {t['gen_grad_l']}, stop:1 {t['gen_grad_r']});
    color: #ffffff;
    border-color: {t['accent']};
}}

QPushButton#btnSmall {{
    font-size: 8pt;
    padding: 4px 10px;
    border-radius: 5px;
}}

QScrollArea {{
    border: none;
    background-color: {t['lbx_bg']};
}}

QScrollBar:vertical {{
    background: transparent;
    width: 6px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {t['scrollbar_h']};
    border-radius: 3px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: {t['border']};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

QScrollBar:horizontal {{
    background: transparent;
    height: 6px;
}}
QScrollBar::handle:horizontal {{
    background: {t['scrollbar_h']};
    border-radius: 3px;
    min-width: 24px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

QPlainTextEdit {{
    background-color: {t['bg_input']};
    color: {t['text_dim']};
    font-family: "Cascadia Code", "Consolas", monospace;
    font-size: 9pt;
    border: 1px solid {t['card_border']};
    border-radius: 6px;
    padding: 4px;
}}

QStatusBar {{
    background-color: {t['bg_panel']};
    color: {t['text_dim']};
    font-size: 8pt;
    border-top: 1px solid {t['card_border']};
}}

QFrame#secSep {{
    background-color: {t['sec_sep']};
    max-height: 1px;
    min-height: 1px;
}}

QLabel#secLabel {{
    color: {t['accent']};
    font-size: 8pt;
    font-weight: 700;
    letter-spacing: 1px;
    background: transparent;
}}

QLabel#dimLabel {{
    color: {t['text_dim']};
    font-size: 7pt;
    background: transparent;
}}

QLabel#sliderVal {{
    color: {t['accent']};
    font-family: "Cascadia Code", "Consolas", monospace;
    font-size: 9pt;
    font-weight: bold;
    min-width: 42px;
    background: transparent;
}}

QWidget#texRow {{
    background-color: {t['lbx_bg']};
    border-radius: 3px;
}}

QWidget#texRow:hover {{
    background-color: {t['lbx_sel']};
}}

QWidget#prevCard {{
    background-color: {t['bg_card']};
    border-radius: 8px;
    border: 1px solid {t['card_border']};
}}

QWidget#updateBanner {{
    background-color: {t['update_bg']};
    border-bottom: 1px solid {t['success']};
}}

QWidget#updateBanner QLabel {{
    color: {t['success']};
    font-weight: bold;
    background: transparent;
}}

QLabel#mapPreviewHdr {{
    color: {t['text']};
    font-size: 9pt;
    font-weight: 700;
    letter-spacing: 0.5px;
    background: transparent;
}}

QLabel#statsLabel {{
    color: {t['text_dim']};
    font-size: 8pt;
    font-family: "Cascadia Code", "Consolas", monospace;
    background: transparent;
}}

QLabel#logHdr {{
    color: {t['text']};
    font-size: 9pt;
    font-weight: 700;
    letter-spacing: 0.5px;
    background: transparent;
}}
"""


DARK_QSS = build_qss(DARK_T)  # default dark stylesheet (used by main.py on startup)


# ── Theme colour lerp ─────────────────────────────────────────────────────────
def _lerp_color(a: QColor, b: QColor, t: float) -> QColor:
    t = max(0.0, min(1.0, t))
    return QColor(
        int(a.red()   + (b.red()   - a.red())   * t),
        int(a.green() + (b.green() - a.green()) * t),
        int(a.blue()  + (b.blue()  - a.blue())  * t),
    )


# ── Theme toggle switch (moon / sun) ─────────────────────────────────────────
class ThemeToggle(QWidget):
    """Pill-shaped toggle that slides between 🌙 dark (left) and ☀ light (right)."""

    toggled = pyqtSignal(bool)   # True = dark

    _W, _H = 80, 32

    def __init__(self, dark: bool = True, parent=None):
        super().__init__(parent)
        self._dark   = dark
        self._pos    = 0.0 if dark else 1.0   # 0 = dark/left, 1 = light/right
        self._target = self._pos
        self._timer  = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)
        self.setFixedSize(self._W, self._H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)

    # ── public API ────────────────────────────────────────────────────────
    def is_dark(self) -> bool:
        return self._dark

    def set_dark(self, dark: bool, animate: bool = True):
        self._dark   = dark
        self._target = 0.0 if dark else 1.0
        if animate:
            self._timer.start()
        else:
            self._pos = self._target
            self.update()

    # ── internals ─────────────────────────────────────────────────────────
    def mousePressEvent(self, event):
        self._dark   = not self._dark
        self._target = 0.0 if self._dark else 1.0
        self._timer.start()
        self.toggled.emit(self._dark)

    def _tick(self):
        diff = self._target - self._pos
        if abs(diff) < 0.015:
            self._pos = self._target
            self._timer.stop()
        else:
            self._pos += diff * 0.22
        self.update()

    # ── paint ─────────────────────────────────────────────────────────────
    def paintEvent(self, _event):
        W, H, t = self._W, self._H, self._pos
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # ── Track / pill ──────────────────────────────────────────────────
        track_dark  = QColor(0x1a, 0x20, 0x44)
        track_light = QColor(0x5b, 0xa4, 0xe8)
        p.setBrush(_lerp_color(track_dark, track_light, t))
        p.setPen(Qt.PenStyle.NoPen)
        pill = QPainterPath()
        pill.addRoundedRect(0, 0, W, H, H / 2, H / 2)
        p.drawPath(pill)

        # ── Moon (left side) ──────────────────────────────────────────────
        moon_alpha = int((1.0 - t) * 220 + 35)   # always slightly visible
        cx_m, cy_m, r_m = 18, H // 2, 7
        # Full disc
        disc = QPainterPath()
        disc.addEllipse(cx_m - r_m, cy_m - r_m, r_m * 2, r_m * 2)
        # Subtract offset disc to carve crescent
        bite = QPainterPath()
        bite.addEllipse(cx_m - r_m + 5, cy_m - r_m - 3, r_m * 2 + 1, r_m * 2 + 1)
        crescent = disc.subtracted(bite)
        moon_col = QColor(0xd8, 0xec, 0xff, moon_alpha)
        p.fillPath(crescent, moon_col)

        # ── Sun (right side) ──────────────────────────────────────────────
        sun_alpha = int(t * 220 + 35)             # always slightly visible
        cx_s, cy_s, r_s = W - 18, H // 2, 5
        sun_col  = QColor(0xff, 0xd0, 0x40, sun_alpha)
        ray_col  = QColor(0xff, 0xd0, 0x40, sun_alpha)
        pen = QPen(ray_col, 1.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        for i in range(8):
            ang = i * math.pi / 4
            x1 = cx_s + (r_s + 2) * math.cos(ang)
            y1 = cy_s + (r_s + 2) * math.sin(ang)
            x2 = cx_s + (r_s + 5) * math.cos(ang)
            y2 = cy_s + (r_s + 5) * math.sin(ang)
            p.drawLine(int(x1), int(y1), int(x2), int(y2))
        p.setBrush(sun_col)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(cx_s - r_s, cy_s - r_s, r_s * 2, r_s * 2)

        # ── Thumb ─────────────────────────────────────────────────────────
        margin = 3
        sz     = H - 2 * margin
        travel = W - 2 * margin - sz
        tx     = margin + self._pos * travel
        th_col = _lerp_color(QColor(0xff, 0xff, 0xff),
                             QColor(0xff, 0xe0, 0x6a), t)
        # Subtle shadow ring
        p.setBrush(QColor(0, 0, 0, 30))
        p.drawEllipse(int(tx) - 1, margin - 1, sz + 2, sz + 2)
        p.setBrush(th_col)
        p.drawEllipse(int(tx), margin, sz, sz)

        p.end()


# ── Helper: section header ────────────────────────────────────────────────────
def _sec_widget(title: str) -> QWidget:
    w = QWidget()
    w.setContentsMargins(0, 8, 0, 3)
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(6)
    lbl = QLabel(title)
    lbl.setObjectName("secLabel")
    sep = QFrame()
    sep.setObjectName("secSep")
    sep.setFrameShape(QFrame.Shape.HLine)
    h.addWidget(lbl)
    h.addWidget(sep, stretch=1)
    return w


class App(QMainWindow):
    """Main Turnt-o-mapper application window."""

    # Thread-safe dispatch: emit from any thread, slot runs in main thread
    _dispatch_signal = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self._dispatch_signal.connect(lambda fn: fn())
        self.setWindowTitle("Turnt-o-mapper")
        self.setMinimumSize(900, 640)

        self._dark_mode      = True
        self._map_str        = ""
        self._last_map_path  = ""
        self._rooms:   List[Room]   = []
        self._bridges: List[Bridge] = []
        self._is_rbe_import  = False
        self._tex_paths: Dict[str, str] = {}
        self._tex_pixmaps: Dict[str, QPixmap] = {}
        # texture checkbox references: tex_name -> (floor_cb, wall_cb, ceil_cb)
        self._tex_cbs: Dict[str, tuple] = {}

        self._root_layout: Optional[QVBoxLayout] = None

        # Config save debounce
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(500)
        self._save_timer.timeout.connect(self._flush_settings)

        self._build_ui()
        self._restore_config()

        self._randomize_seed(silent=True)
        self._log("Turnt-o-mapper ready. Configure and hit Generate!", "info")

        # Auto-update check (background, non-blocking)
        check_for_update(self._on_update_available)

    # ── UI construction ───────────────────────────────────────────────────
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        self._root_layout = QVBoxLayout(central)
        self._root_layout.setContentsMargins(0, 0, 0, 0)
        self._root_layout.setSpacing(0)

        self._root_layout.addWidget(self._build_header())

        body = QWidget()
        body_lay = QHBoxLayout(body)
        body_lay.setContentsMargins(10, 8, 10, 8)
        body_lay.setSpacing(8)

        left = self._build_left()
        left.setObjectName("leftPanel")
        left.setMinimumWidth(340)

        right = self._build_right()
        right.setObjectName("rightPanel")

        body_lay.addWidget(left, stretch=2)
        body_lay.addWidget(right, stretch=3)
        self._root_layout.addWidget(body, stretch=1)

        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Ready")

    def _build_header(self) -> QWidget:
        hdr = QWidget()
        hdr.setObjectName("headerWidget")
        hdr.setFixedHeight(52)
        lay = QHBoxLayout(hdr)
        lay.setContentsMargins(18, 8, 18, 8)
        lay.setSpacing(0)

        turnt = QLabel("TURNT")
        turnt.setObjectName("titleAccent")
        mapper = QLabel("-O-MAPPER")
        mapper.setObjectName("titleText")
        sep = QFrame()
        sep.setObjectName("headerSep")
        sep.setFrameShape(QFrame.Shape.VLine)
        sub = QLabel(".map generator + DBT importer")
        sub.setObjectName("titleSub")

        lbl_ver = QLabel(f"v{__version__}")
        lbl_ver.setObjectName("versionLabel")

        lay.addWidget(turnt)
        lay.addWidget(mapper)
        lay.addSpacing(14)
        lay.addWidget(sep)
        lay.addSpacing(14)
        lay.addWidget(sub)
        lay.addStretch()
        lay.addWidget(lbl_ver)
        return hdr

    # ── Left panel ────────────────────────────────────────────────────────
    def _build_left(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(4)

        self._left_tabs = QTabWidget()
        self._left_tabs.addTab(self._tab_generate(),   "Generate")
        self._left_tabs.addTab(self._tab_dbt_import(), "DBT Import")
        self._left_tabs.addTab(self._tab_textures(),   "Textures")
        self._left_tabs.addTab(self._tab_settings(),   "Settings")
        lay.addWidget(self._left_tabs, stretch=1)

        # Separator
        sep = QFrame()
        sep.setObjectName("secSep")
        sep.setFrameShape(QFrame.Shape.HLine)
        lay.addWidget(sep)

        # Shared action buttons
        btn_row = QWidget()
        br_lay = QHBoxLayout(btn_row)
        br_lay.setContentsMargins(0, 4, 0, 4)
        br_lay.setSpacing(6)

        self._btn_save = QPushButton("Save .map")
        self._btn_save.setObjectName("btnSave")
        self._btn_save.clicked.connect(self._on_save)

        self._btn_folder = QPushButton("Open folder")
        self._btn_folder.setObjectName("btnFolder")
        self._btn_folder.clicked.connect(self._on_open_folder)

        self._btn_launch = QPushButton("Launch game")
        self._btn_launch.setObjectName("btnLaunch")
        self._btn_launch.clicked.connect(self._on_launch_game)

        br_lay.addWidget(self._btn_save,   stretch=1)
        br_lay.addWidget(self._btn_folder, stretch=1)
        br_lay.addWidget(self._btn_launch, stretch=1)
        lay.addWidget(btn_row)
        return w

    def _tab_generate(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(4)
        scroll.setWidget(inner)

        # Rooms slider
        lay.addWidget(_sec_widget("Number of rooms"))
        rooms_row = QWidget()
        rr = QHBoxLayout(rooms_row)
        rr.setContentsMargins(0, 0, 0, 0)
        self._spin_rooms = QSpinBox()
        self._spin_rooms.setRange(2, 100)
        self._spin_rooms.setValue(10)
        self._lbl_rooms = QLabel("10")
        self._lbl_rooms.setObjectName("sliderVal")
        self._slider_rooms = QSlider(Qt.Orientation.Horizontal)
        self._slider_rooms.setRange(2, 100)
        self._slider_rooms.setValue(10)
        self._slider_rooms.valueChanged.connect(
            lambda v: (self._lbl_rooms.setText(str(v)),
                       self._spin_rooms.blockSignals(True),
                       self._spin_rooms.setValue(v),
                       self._spin_rooms.blockSignals(False),
                       self._schedule_save()))
        self._spin_rooms.valueChanged.connect(
            lambda v: (self._slider_rooms.setValue(v),
                       self._lbl_rooms.setText(str(v)),
                       self._schedule_save()))
        rr.addWidget(self._slider_rooms, stretch=1)
        rr.addWidget(self._lbl_rooms)
        lay.addWidget(rooms_row)

        # Seed row
        seed_row = QWidget()
        sr = QHBoxLayout(seed_row)
        sr.setContentsMargins(0, 4, 0, 4)
        sr.setSpacing(6)
        self._btn_auto = QPushButton("🎲 Auto")
        self._btn_auto.setObjectName("btnAuto")
        self._btn_auto.setCheckable(True)
        self._btn_auto.setChecked(True)
        self._btn_auto.setProperty("active", "true")
        self._btn_auto.clicked.connect(self._toggle_autorand)
        self._spin_seed = QSpinBox()
        self._spin_seed.setRange(0, 9_999_999)
        self._spin_seed.setValue(0)
        self._spin_seed.setReadOnly(True)
        self._spin_seed.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        sr.addWidget(self._btn_auto)
        sr.addWidget(self._spin_seed, stretch=1)
        lay.addWidget(seed_row)

        # Generate button (full-width)
        self._btn_gen = QPushButton("⚡  Generate")
        self._btn_gen.setObjectName("btnGenerate")
        self._btn_gen.clicked.connect(self._on_generate)
        lay.addWidget(self._btn_gen)

        # Map name
        name_row = QWidget()
        nr = QHBoxLayout(name_row)
        nr.setContentsMargins(0, 6, 0, 0)
        nr.setSpacing(6)
        lbl_n = QLabel("Map name:")
        lbl_n.setObjectName("dimLabel")
        self._edit_map_name_gen = QLineEdit("generated")
        self._edit_map_name_gen.setPlaceholderText("generated")
        suf = QLabel(".map")
        suf.setObjectName("dimLabel")
        nr.addWidget(lbl_n)
        nr.addWidget(self._edit_map_name_gen, stretch=1)
        nr.addWidget(suf)
        lay.addWidget(name_row)

        sep = QFrame(); sep.setObjectName("secSep"); sep.setFrameShape(QFrame.Shape.HLine)
        lay.addWidget(sep)

        # Room sizes grid
        lay.addWidget(_sec_widget("Room settings"))
        sz_grid = QWidget()
        g = QGridLayout(sz_grid)
        g.setContentsMargins(0, 0, 0, 0)
        g.setSpacing(4)
        labels  = ["Min W", "Max W", "Min D", "Max D", "Min H", "Max H"]
        defvals = [384, 2048, 256, 768, 256, 640]
        self._sz: Dict[str, QSpinBox] = {}
        for i, (lbl, val) in enumerate(zip(labels, defvals)):
            r, c = divmod(i, 2)
            cell = QWidget()
            cl = QVBoxLayout(cell)
            cl.setContentsMargins(0, 0, 0, 0)
            cl.setSpacing(1)
            l = QLabel(lbl); l.setObjectName("dimLabel")
            sb = QSpinBox()
            sb.setRange(64, 4096)
            sb.setSingleStep(64)
            sb.setValue(val)
            sb.valueChanged.connect(self._schedule_save)
            self._sz[lbl] = sb
            cl.addWidget(l)
            cl.addWidget(sb)
            g.addWidget(cell, r, c)
            g.setColumnStretch(c, 1)
        lay.addWidget(sz_grid)

        hint = QLabel("Long side = travel axis  |  Short side = lateral sweep")
        hint.setObjectName("dimLabel")
        lay.addWidget(hint)

        # Corridor width + Rooms per segment (side by side)
        lay.addWidget(_sec_widget("Corridor & structure"))
        cw_row = QWidget()
        cwr = QHBoxLayout(cw_row)
        cwr.setContentsMargins(0, 0, 0, 0)
        cwr.setSpacing(8)

        # Corridor width slider
        corr_cell = QWidget()
        corr_lay = QVBoxLayout(corr_cell)
        corr_lay.setContentsMargins(0, 0, 0, 0)
        corr_lay.setSpacing(2)
        corr_hdr = QWidget()
        corr_hdr_lay = QHBoxLayout(corr_hdr)
        corr_hdr_lay.setContentsMargins(0, 0, 0, 0)
        corr_hdr_lay.addWidget(QLabel("Corridor width"))
        self._lbl_corr = QLabel("67%")
        self._lbl_corr.setObjectName("sliderVal")
        corr_hdr_lay.addStretch()
        corr_hdr_lay.addWidget(self._lbl_corr)
        self._slider_corr = QSlider(Qt.Orientation.Horizontal)
        self._slider_corr.setRange(25, 100)
        self._slider_corr.setValue(67)
        self._slider_corr.valueChanged.connect(
            lambda v: (self._lbl_corr.setText("100% (open)" if v >= 98 else f"{v}%"),
                       self._schedule_save()))
        corr_lay.addWidget(corr_hdr)
        corr_lay.addWidget(self._slider_corr)
        cwr.addWidget(corr_cell, stretch=1)

        # Rooms per segment (structural, not physics)
        rpt_cell = QWidget()
        rpt_lay = QVBoxLayout(rpt_cell)
        rpt_lay.setContentsMargins(0, 0, 0, 0)
        rpt_lay.setSpacing(2)
        rpt_lbl = QLabel("Rooms / segment")
        rpt_lbl.setObjectName("dimLabel")
        self._spin_rpt = QSpinBox()
        self._spin_rpt.setRange(1, 10)
        self._spin_rpt.setValue(3)
        self._spin_rpt.setFixedWidth(64)
        self._spin_rpt.valueChanged.connect(self._schedule_save)
        rpt_lay.addWidget(rpt_lbl)
        rpt_lay.addWidget(self._spin_rpt)
        cwr.addWidget(rpt_cell)

        lay.addWidget(cw_row)

        # Checkboxes
        self._chk_height = QCheckBox("Height variation between rooms")
        self._chk_height.setChecked(True)
        self._chk_height.stateChanged.connect(self._schedule_save)
        self._chk_checks = QCheckBox("Add trigger_checkpoint entities")
        self._chk_checks.setChecked(True)
        self._chk_checks.stateChanged.connect(self._schedule_save)
        lay.addWidget(self._chk_height)
        lay.addWidget(self._chk_checks)

        sep2 = QFrame(); sep2.setObjectName("secSep"); sep2.setFrameShape(QFrame.Shape.HLine)
        lay.addWidget(sep2)

        # Physics
        lay.addWidget(_sec_widget("Physics"))
        self._chk_physics = QCheckBox("Use acceleration model")
        self._chk_physics.stateChanged.connect(lambda _: (self._toggle_physics(), self._schedule_save()))
        lay.addWidget(self._chk_physics)

        phy_grid = QWidget()
        pg = QGridLayout(phy_grid)
        pg.setContentsMargins(0, 2, 0, 4)
        pg.setSpacing(4)
        phy_params = [
            ("Base speed (UPS)",       "_spin_u_base",   550, 100, 2000, 10),
            ("Speed gain / room",      "_spin_u_gain",    60,   0,  300,  5),
            ("Air time (×0.01 s)",     "_spin_t_air",     68,  30,  150,  1),
            ("Strafe factor (×0.01)",  "_spin_strafe_f",  20,   5,   40,  1),
        ]
        self._phy_widgets: List[QSpinBox] = []
        for row_i, (lbl, attr, dflt, lo, hi, inc) in enumerate(phy_params):
            r, c = divmod(row_i, 2)
            cell = QWidget()
            cl = QVBoxLayout(cell)
            cl.setContentsMargins(0, 0, 0, 0)
            cl.setSpacing(1)
            l = QLabel(lbl); l.setObjectName("dimLabel")
            sb = QSpinBox()
            sb.setRange(lo, hi)
            sb.setSingleStep(inc)
            sb.setValue(dflt)
            sb.valueChanged.connect(self._schedule_save)
            setattr(self, attr, sb)
            self._phy_widgets.append(sb)
            cl.addWidget(l)
            cl.addWidget(sb)
            pg.addWidget(cell, r, c)
            pg.setColumnStretch(c, 1)
        lay.addWidget(phy_grid)
        self._toggle_physics()

        sep3 = QFrame(); sep3.setObjectName("secSep"); sep3.setFrameShape(QFrame.Shape.HLine)
        lay.addWidget(sep3)

        # Layout style
        lay.addWidget(_sec_widget("Layout style"))
        self._current_layout = "Zigzag"
        layout_names = ["Linear", "Zigzag", "Snake", "Random", "Spiral", "Multilevel"]
        layout_grid = QWidget()
        lg = QGridLayout(layout_grid)
        lg.setContentsMargins(0, 0, 0, 4)
        lg.setSpacing(4)
        self._layout_group = QButtonGroup(self)
        self._layout_group.setExclusive(True)
        self._layout_btns: Dict[str, QPushButton] = {}
        for i, name in enumerate(layout_names):
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setChecked(name == "Zigzag")
            btn.setObjectName("btnLayout")
            btn.clicked.connect(lambda checked, n=name: self._select_layout(n))
            self._layout_group.addButton(btn, i)
            self._layout_btns[name] = btn
            lg.addWidget(btn, i // 3, i % 3)
            lg.setColumnStretch(i % 3, 1)
        lay.addWidget(layout_grid)
        lay.addStretch()
        return scroll

    def _select_layout(self, name: str):
        self._current_layout = name
        self._schedule_save()

    def _tab_dbt_import(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(4)

        lay.addWidget(_sec_widget("Source .rbe file"))
        file_row = QWidget()
        fr = QHBoxLayout(file_row)
        fr.setContentsMargins(0, 0, 0, 8)
        fr.setSpacing(4)
        self._edit_rbe_path = QLineEdit()
        self._edit_rbe_path.setFont(QFont("Consolas", 8))
        self._edit_rbe_path.textChanged.connect(self._schedule_save)
        btn_rbe = QPushButton("…")
        btn_rbe.setFixedWidth(32)
        btn_rbe.clicked.connect(self._browse_rbe)
        fr.addWidget(self._edit_rbe_path)
        fr.addWidget(btn_rbe)
        lay.addWidget(file_row)

        # Map output name (auto-filled from RBE filename on browse)
        rname_row = QWidget()
        rnr = QHBoxLayout(rname_row)
        rnr.setContentsMargins(0, 0, 0, 8)
        rnr.setSpacing(6)
        lbl_rn = QLabel("Map name:")
        lbl_rn.setObjectName("dimLabel")
        self._edit_map_name_rbe = QLineEdit("imported")
        self._edit_map_name_rbe.setPlaceholderText("imported")
        suf_r = QLabel(".map")
        suf_r.setObjectName("dimLabel")
        rnr.addWidget(lbl_rn)
        rnr.addWidget(self._edit_map_name_rbe, stretch=1)
        rnr.addWidget(suf_r)
        lay.addWidget(rname_row)

        lay.addWidget(_sec_widget("Scale (Quake units per block)"))
        sc_row = QWidget()
        sr = QHBoxLayout(sc_row)
        sr.setContentsMargins(0, 0, 0, 8)
        sr.setSpacing(6)
        # 1:1 defaults: DBT block = 40×20×40 (X×Y_height×Z)
        # sx = 40 × 2.4 = 96  (DBT-X  → Q3-X)
        # sy = 40 × 2.4 = 96  (DBT-Z  → Q3-Y)
        # sz = 20 × 2.2 = 44  (DBT-Y height → Q3-Z)
        self._spin_rbe_sx = QSpinBox(); self._spin_rbe_sx.setRange(1, 512); self._spin_rbe_sx.setValue(96)
        self._spin_rbe_sy = QSpinBox(); self._spin_rbe_sy.setRange(1, 512); self._spin_rbe_sy.setValue(96)
        self._spin_rbe_sz = QSpinBox(); self._spin_rbe_sz.setRange(1, 512); self._spin_rbe_sz.setValue(44)
        for lbl_txt, sb in [("X:", self._spin_rbe_sx), ("Y:", self._spin_rbe_sy),
                             ("Z (height):", self._spin_rbe_sz)]:
            sr.addWidget(QLabel(lbl_txt))
            sr.addWidget(sb)
            sb.valueChanged.connect(self._schedule_save)
        lay.addWidget(sc_row)

        hint_scale = QLabel("Defaults — x×2.4  y×2.4  z(height)×2.2  →  96 / 96 / 44  |  angles: degrees")
        hint_scale.setObjectName("dimLabel")
        lay.addWidget(hint_scale)

        lay.addWidget(_sec_widget("Actions"))
        btn_import = QPushButton("Import")
        btn_import.setObjectName("btnGenerate")
        btn_import.clicked.connect(self._on_import_rbe)
        lay.addWidget(btn_import)
        lay.addStretch()
        return w

    def _tab_textures(self) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(6)

        # Left: scrollable texture list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        list_inner = QWidget()
        list_inner.setStyleSheet(f"background-color: {T['lbx_bg']};")
        self._tex_list_lay = QVBoxLayout(list_inner)
        self._tex_list_lay.setContentsMargins(2, 2, 2, 2)
        self._tex_list_lay.setSpacing(1)
        self._tex_list_lay.addStretch()
        scroll.setWidget(list_inner)
        lay.addWidget(scroll, stretch=1)

        hint = QLabel("F = use as Floor\nW = Wall\nC = Ceiling")
        hint.setObjectName("dimLabel")
        hint.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Right: preview panel
        prev_card = QWidget()
        prev_card.setObjectName("prevCard")
        prev_card.setFixedWidth(140)
        pc_lay = QVBoxLayout(prev_card)
        pc_lay.setContentsMargins(8, 8, 8, 8)
        pc_lay.setSpacing(4)
        prev_hdr = QLabel("Preview")
        prev_hdr.setObjectName("secLabel")
        prev_hdr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pc_lay.addWidget(prev_hdr)
        self._prev_lbl = QLabel()
        self._prev_lbl.setFixedSize(120, 120)
        self._prev_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._prev_lbl.setStyleSheet(f"background-color: {T['bg_input']}; color: {T['text_dim']};")
        self._prev_lbl.setText("—")
        pc_lay.addWidget(self._prev_lbl)
        self._prev_name = QLabel("")
        self._prev_name.setObjectName("dimLabel")
        self._prev_name.setWordWrap(True)
        self._prev_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pc_lay.addWidget(self._prev_name)
        pc_lay.addWidget(hint)
        pc_lay.addStretch()

        right_w = QWidget()
        rv = QVBoxLayout(right_w)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.addWidget(prev_card)
        lay.addWidget(right_w)

        self._populate_tex_list()
        return w

    def _populate_tex_list(self):
        # Clear existing rows (keep trailing stretch)
        while self._tex_list_lay.count() > 1:
            item = self._tex_list_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for tex_name in sorted(ALL_TEXTURES.keys()):
            row = QWidget()
            row.setObjectName("texRow")
            row.setFixedHeight(22)
            rh = QHBoxLayout(row)
            rh.setContentsMargins(2, 0, 2, 0)
            rh.setSpacing(2)

            # Thumbnail
            thumb = QLabel()
            thumb.setFixedSize(16, 16)
            thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            rh.addWidget(thumb)
            self._load_thumb_qt(tex_name, thumb, 16)

            # Name button
            name_btn = QPushButton(tex_name)
            name_btn.setFlat(True)
            name_btn.setStyleSheet(
                f"text-align:left; color:{T['text']}; font-family:Consolas; font-size:7pt;"
                f" background:transparent; border:none;")
            name_btn.clicked.connect(lambda _, t=tex_name: self._show_tex_preview(t))
            rh.addWidget(name_btn, stretch=1)

            # F/W/C checkboxes
            floor_cb = QCheckBox("F")
            floor_cb.setStyleSheet(f"color:{T['success']}; font-size:7pt;")
            floor_cb.setChecked(tex_name in FLOOR_TEX)

            wall_cb = QCheckBox("W")
            wall_cb.setStyleSheet(f"color:{T['accent2']}; font-size:7pt;")
            wall_cb.setChecked(tex_name in WALL_TEX)

            ceil_cb = QCheckBox("C")
            ceil_cb.setStyleSheet(f"color:{T['accent']}; font-size:7pt;")
            ceil_cb.setChecked(tex_name in CEIL_TEX)

            for cb in (floor_cb, wall_cb, ceil_cb):
                cb.stateChanged.connect(self._update_tex_lists)
                rh.addWidget(cb)

            self._tex_cbs[tex_name] = (floor_cb, wall_cb, ceil_cb)
            self._tex_list_lay.insertWidget(self._tex_list_lay.count() - 1, row)

    def _load_thumb_qt(self, tex_name: str, lbl: QLabel, size: int = 16):
        if not PIL_OK:
            return
        cached = self._tex_pixmaps.get(f"{tex_name}_{size}")
        if cached:
            lbl.setPixmap(cached)
            return
        path = self._tex_paths.get(tex_name) or self._find_tex_file(tex_name)
        if not path:
            return
        try:
            img = Image.open(path).convert("RGBA")
            img.thumbnail((size, size))
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            qimg = QImage.fromData(buf.getvalue())
            pm = QPixmap.fromImage(qimg)
            self._tex_pixmaps[f"{tex_name}_{size}"] = pm
            lbl.setPixmap(pm)
        except Exception:
            pass

    def _find_tex_file(self, tex_name: str) -> Optional[str]:
        if not hasattr(self, '_edit_tex_folder'):
            return None
        folder = self._edit_tex_folder.text()
        if not folder or not os.path.isdir(folder):
            return None
        base = tex_name.split("/")[-1]
        for root_d, _, files in os.walk(folder):
            for fn in files:
                nm, ext = os.path.splitext(fn)
                if nm.lower() == base.lower() and ext.lower() in IMG_EXTS:
                    fp = os.path.join(root_d, fn)
                    self._tex_paths[tex_name] = fp
                    return fp
        return None

    def _show_tex_preview(self, tex_name: str):
        self._prev_name.setText(tex_name)
        if not PIL_OK:
            self._prev_lbl.setText("pip install\npillow")
            return
        path = self._tex_paths.get(tex_name) or self._find_tex_file(tex_name)
        if not path:
            self._prev_lbl.setText("No image\n(set folder)")
            return
        try:
            img = Image.open(path).convert("RGBA")
            img.thumbnail((120, 120))
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            qimg = QImage.fromData(buf.getvalue())
            pm = QPixmap.fromImage(qimg)
            self._prev_lbl.setPixmap(pm)
            self._prev_lbl.setText("")
        except Exception as ex:
            self._prev_lbl.setText(f"Error:\n{ex}")

    def _update_tex_lists(self):
        FLOOR_TEX.clear()
        WALL_TEX.clear()
        CEIL_TEX.clear()
        for tex_name, (f_cb, w_cb, c_cb) in self._tex_cbs.items():
            if f_cb.isChecked(): FLOOR_TEX.append(tex_name)
            if w_cb.isChecked(): WALL_TEX.append(tex_name)
            if c_cb.isChecked(): CEIL_TEX.append(tex_name)
        if not FLOOR_TEX: FLOOR_TEX.append("turnt/turnt_concrete")
        if not WALL_TEX:  WALL_TEX.append("turnt/turnt_tech")
        if not CEIL_TEX:  CEIL_TEX.append("turnt/turnt_sky")
        self._schedule_save()

    def _tab_settings(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(4)

        def path_row(title, attr, browse_fn):
            lay.addWidget(_sec_widget(title))
            row = QWidget()
            rh = QHBoxLayout(row)
            rh.setContentsMargins(0, 0, 0, 8)
            rh.setSpacing(4)
            edit = QLineEdit()
            edit.setFont(QFont("Consolas", 8))
            edit.textChanged.connect(self._schedule_save)
            setattr(self, attr, edit)
            btn = QPushButton("…")
            btn.setFixedWidth(32)
            btn.clicked.connect(browse_fn)
            rh.addWidget(edit)
            rh.addWidget(btn)
            lay.addWidget(row)

        path_row("Output folder",                "_edit_out_folder",  self._browse_out_folder)
        path_row("Texture folder (for preview)", "_edit_tex_folder", self._browse_tex_folder)
        path_row("Game executable",            "_edit_game_exe",    self._browse_game_exe)

        lay.addWidget(_sec_widget("Preview"))
        self._chk_prev_labels = QCheckBox("Show room numbers")
        self._chk_prev_labels.setChecked(True)
        self._chk_prev_labels.stateChanged.connect(self._schedule_save)
        self._chk_prev_hmap = QCheckBox("Show heightmap bar")
        self._chk_prev_hmap.setChecked(True)
        self._chk_prev_hmap.stateChanged.connect(self._schedule_save)
        self._chk_prev_ramps = QCheckBox("Show ramps in 3D preview")
        self._chk_prev_ramps.setChecked(True)
        self._chk_prev_ramps.stateChanged.connect(self._schedule_save)
        lay.addWidget(self._chk_prev_labels)
        lay.addWidget(self._chk_prev_hmap)
        lay.addWidget(self._chk_prev_ramps)

        lay.addWidget(_sec_widget("Appearance"))
        theme_row = QWidget()
        tr = QHBoxLayout(theme_row)
        tr.setContentsMargins(0, 4, 0, 4)
        tr.setSpacing(8)
        lbl_theme = QLabel("Theme")
        lbl_theme.setObjectName("dimLabel")
        self._theme_toggle = ThemeToggle(dark=True)
        self._theme_toggle.toggled.connect(self._apply_theme)
        tr.addWidget(lbl_theme)
        tr.addStretch()
        tr.addWidget(self._theme_toggle)
        lay.addWidget(theme_row)

        lay.addStretch()

        # Default output folder
        self._edit_out_folder.setText(os.path.join(os.getcwd(), "maps"))
        return w

    # ── Right panel ───────────────────────────────────────────────────────
    def _build_right(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        # Preview card
        preview_card = QWidget()
        pc_lay = QVBoxLayout(preview_card)
        pc_lay.setContentsMargins(0, 0, 0, 0)
        pc_lay.setSpacing(4)

        # Header
        ph = QWidget()
        ph_lay = QHBoxLayout(ph)
        ph_lay.setContentsMargins(8, 4, 8, 4)
        lbl_prev = QLabel("MAP PREVIEW")
        lbl_prev.setObjectName("mapPreviewHdr")
        self._lbl_stats = QLabel("")
        self._lbl_stats.setObjectName("statsLabel")
        ph_lay.addWidget(lbl_prev)
        ph_lay.addStretch()
        ph_lay.addWidget(self._lbl_stats)
        pc_lay.addWidget(ph)

        # Legend
        leg = QWidget()
        leg_lay = QHBoxLayout(leg)
        leg_lay.setContentsMargins(8, 2, 8, 2)
        leg_lay.setSpacing(4)
        for color_key, label in [
            (T["start_col"], "Start"), (T["room_col"], "Room"),
            (T["end_col"],   "End"),   (T["corr_col"], "Corridor"),
        ]:
            swatch = QLabel()
            swatch.setFixedSize(14, 14)
            swatch.setStyleSheet(f"background-color:{color_key}; border-radius:2px;")
            lbl = QLabel(label)
            lbl.setObjectName("dimLabel")
            leg_lay.addWidget(swatch)
            leg_lay.addWidget(lbl)
            leg_lay.addSpacing(6)
        leg_lay.addStretch()
        pc_lay.addWidget(leg)

        # 2D / 3D tabs
        view_tabs = QTabWidget()
        self._view_tabs = view_tabs

        tab2d = QWidget()
        t2_lay = QVBoxLayout(tab2d)
        t2_lay.setContentsMargins(0, 0, 0, 0)
        t2_lay.setSpacing(2)
        bar2d = QWidget()
        b2_lay = QHBoxLayout(bar2d)
        b2_lay.setContentsMargins(4, 2, 4, 2)
        btn_fit = QPushButton("Fit")
        btn_fit.setObjectName("btnSmall")
        btn_fit.clicked.connect(self._2d_fit)
        hint2d = QLabel("  scroll=zoom  drag=pan  dbl-click=fit")
        hint2d.setObjectName("dimLabel")
        b2_lay.addWidget(btn_fit)
        b2_lay.addWidget(hint2d)
        b2_lay.addStretch()
        t2_lay.addWidget(bar2d)
        self._preview2d = Preview2DWidget()
        t2_lay.addWidget(self._preview2d, stretch=1)
        view_tabs.addTab(tab2d, "2D")

        tab3d = QWidget()
        t3_lay = QVBoxLayout(tab3d)
        t3_lay.setContentsMargins(0, 0, 0, 0)
        t3_lay.setSpacing(2)
        bar3d = QWidget()
        b3_lay = QHBoxLayout(bar3d)
        b3_lay.setContentsMargins(4, 2, 4, 2)
        for pname in ("Iso", "Top", "Front", "Side"):
            pb = QPushButton(pname)
            pb.setObjectName("btnSmall")
            pb.clicked.connect(lambda _, n=pname: self._viewer3d.set_preset(n))
            b3_lay.addWidget(pb)
        hint3d = QLabel("  drag=rotate  scroll=zoom  WASD=pan (click 3D first)")
        hint3d.setObjectName("dimLabel")
        b3_lay.addWidget(hint3d)
        b3_lay.addStretch()
        t3_lay.addWidget(bar3d)
        self._viewer3d = Viewer3DWidget()
        t3_lay.addWidget(self._viewer3d, stretch=1)
        view_tabs.addTab(tab3d, "3D")

        view_tabs.currentChanged.connect(self._on_view_tab_changed)
        pc_lay.addWidget(view_tabs, stretch=1)
        lay.addWidget(preview_card, stretch=3)

        # Log section
        log_card = QWidget()
        lc_lay = QVBoxLayout(log_card)
        lc_lay.setContentsMargins(0, 0, 0, 0)
        lc_lay.setSpacing(2)

        log_hdr = QWidget()
        lh_lay = QHBoxLayout(log_hdr)
        lh_lay.setContentsMargins(8, 4, 8, 4)
        log_lbl = QLabel("LOG")
        log_lbl.setObjectName("logHdr")
        btn_clear = QPushButton("Clear")
        btn_clear.setObjectName("btnSmall")
        btn_clear.clicked.connect(self._clear_log)
        lh_lay.addWidget(log_lbl)
        lh_lay.addStretch()
        lh_lay.addWidget(btn_clear)
        lc_lay.addWidget(log_hdr)

        self._logbox = QPlainTextEdit()
        self._logbox.setReadOnly(True)
        self._logbox.setMaximumBlockCount(500)
        lc_lay.addWidget(self._logbox, stretch=1)
        lay.addWidget(log_card, stretch=1)
        return w

    # ── Config ────────────────────────────────────────────────────────────
    def _restore_config(self):
        cfg = load_app_cfg()
        if cfg.get("tex_folder"):
            self._edit_tex_folder.setText(cfg["tex_folder"])
            folder = cfg["tex_folder"]
            if os.path.isdir(folder):
                threading.Thread(
                    target=self._scan_tex_folder, args=(folder,), daemon=True
                ).start()
        if cfg.get("game_exe"):     self._edit_game_exe.setText(cfg["game_exe"])
        if cfg.get("rbe_path"):
            self._edit_rbe_path.setText(cfg["rbe_path"])
            # Restore rbe map name only if explicitly saved; else keep auto-default
            if cfg.get("map_name_rbe"):
                self._edit_map_name_rbe.setText(cfg["map_name_rbe"])
        if cfg.get("map_name_gen"): self._edit_map_name_gen.setText(cfg["map_name_gen"])
        # out_folder (new) with fallback to legacy out_path directory
        if cfg.get("out_folder"):
            self._edit_out_folder.setText(cfg["out_folder"])
        elif cfg.get("out_path"):
            self._edit_out_folder.setText(os.path.dirname(cfg["out_path"]))
        if cfg.get("rbe_sx"):       self._spin_rbe_sx.setValue(cfg["rbe_sx"])
        if cfg.get("rbe_sy"):       self._spin_rbe_sy.setValue(cfg["rbe_sy"])
        # Restore sz only if it looks intentionally set (>= 40); old configs had
        # stale values of 42 or 22 that were wrong defaults — skip those.
        if cfg.get("rbe_sz") and cfg["rbe_sz"] >= 40:
            self._spin_rbe_sz.setValue(cfg["rbe_sz"])
        if cfg.get("n_rooms"):      self._slider_rooms.setValue(cfg["n_rooms"])
        if cfg.get("layout"):
            self._current_layout = cfg["layout"]
            for name, btn in self._layout_btns.items():
                btn.setChecked(name == cfg["layout"])
        if cfg.get("corr_frac") is not None:
            self._slider_corr.setValue(int(cfg["corr_frac"] * 100))
        if cfg.get("height_var") is not None:
            self._chk_height.setChecked(cfg["height_var"])
        if cfg.get("checkpoints") is not None:
            self._chk_checks.setChecked(cfg["checkpoints"])
        if cfg.get("use_physics") is not None:
            self._chk_physics.setChecked(cfg["use_physics"])
        for lbl in ("Min W", "Max W", "Min D", "Max D", "Min H", "Max H"):
            key = f"sz_{lbl}"
            if key in cfg:
                self._sz[lbl].setValue(cfg[key])
        for attr in ("_spin_u_base", "_spin_u_gain", "_spin_t_air",
                     "_spin_strafe_f", "_spin_rpt"):
            if attr in cfg and hasattr(self, attr):
                getattr(self, attr).setValue(cfg[attr])
        if cfg.get("prev_labels") is not None:
            self._chk_prev_labels.setChecked(cfg["prev_labels"])
        if cfg.get("prev_hmap") is not None:
            self._chk_prev_hmap.setChecked(cfg["prev_hmap"])
        if cfg.get("prev_ramps") is not None:
            self._chk_prev_ramps.setChecked(cfg["prev_ramps"])
        if "dark_mode" in cfg:
            dark = bool(cfg["dark_mode"])
            self._theme_toggle.set_dark(dark, animate=False)
            self._apply_theme(dark)

    def _schedule_save(self, *_):
        self._save_timer.start()

    def _flush_settings(self):
        d = {
            "out_folder":   self._edit_out_folder.text(),
            "map_name_gen": self._edit_map_name_gen.text(),
            "map_name_rbe": self._edit_map_name_rbe.text(),
            "tex_folder":   self._edit_tex_folder.text(),
            "game_exe":     self._edit_game_exe.text(),
            "rbe_path":     self._edit_rbe_path.text(),
            "rbe_sx":       self._spin_rbe_sx.value(),
            "rbe_sy":       self._spin_rbe_sy.value(),
            "rbe_sz":       self._spin_rbe_sz.value(),
            "n_rooms":      self._slider_rooms.value(),
            "layout":       self._current_layout,
            "corr_frac":    self._slider_corr.value() / 100.0,
            "height_var":   self._chk_height.isChecked(),
            "checkpoints":  self._chk_checks.isChecked(),
            "use_physics":  self._chk_physics.isChecked(),
            "prev_labels":  self._chk_prev_labels.isChecked(),
            "prev_hmap":    self._chk_prev_hmap.isChecked(),
            "prev_ramps":   self._chk_prev_ramps.isChecked(),
            "dark_mode":    self._theme_toggle.is_dark(),
        }
        for lbl, sb in self._sz.items():
            d[f"sz_{lbl}"] = sb.value()
        for attr in ("_spin_u_base", "_spin_u_gain", "_spin_t_air",
                     "_spin_strafe_f", "_spin_rpt"):
            if hasattr(self, attr):
                d[attr] = getattr(self, attr).value()
        save_app_cfg(d)

    # ── Generation ────────────────────────────────────────────────────────
    def _collect_cfg(self) -> dict:
        self._update_tex_lists()
        return {
            "n_rooms":      self._slider_rooms.value(),
            "min_w": self._sz["Min W"].value(), "max_w": self._sz["Max W"].value(),
            "min_d": self._sz["Min D"].value(), "max_d": self._sz["Max D"].value(),
            "min_h": self._sz["Min H"].value(), "max_h": self._sz["Max H"].value(),
            "use_physics":  self._chk_physics.isChecked(),
            "u_base":       float(self._spin_u_base.value()),
            "u_gain":       float(self._spin_u_gain.value()),
            "t_air":        self._spin_t_air.value() / 100.0,
            "strafe_f":     self._spin_strafe_f.value() / 100.0,
            "rooms_per_turn": self._spin_rpt.value(),
            "layout_style":   self._current_layout,
            "seed":         self._spin_seed.value(),
            "map_name":     "turnt_map",
            "height_var":   self._chk_height.isChecked(),
            "checkpoints":  self._chk_checks.isChecked(),
            "corridor_width_frac": self._slider_corr.value() / 100.0,
        }

    def _on_generate(self):
        def run():
            try:
                cfg = self._collect_cfg()
                errs = []
                if cfg["min_w"] >= cfg["max_w"]: errs.append("Min W must be < Max W")
                if cfg["min_d"] >= cfg["max_d"]: errs.append("Min D must be < Max D")
                if cfg["min_h"] >= cfg["max_h"]: errs.append("Min H must be < Max H")
                if errs:
                    for e in errs: self._log(e, "warn")
                    return

                u_end = cfg["u_base"] + (cfg["n_rooms"] - 1) * cfg["u_gain"]
                self._log(
                    f"Generating {cfg['n_rooms']} rooms | "
                    f"u: {cfg['u_base']:.0f}→{u_end:.0f} UPS | "
                    f"layout: {cfg['layout_style']} | seed {cfg['seed']}…", "info")
                t0 = time.perf_counter()
                ms, rooms, bridges, gen_warnings = generate_map(cfg)
                dt = time.perf_counter() - t0

                self._map_str = ms
                self._rooms   = rooms
                self._bridges = bridges
                self._is_rbe_import = False

                nb = ms.count("// brush")
                kb = len(ms.encode()) / 1024
                n_cp = max(0, (len(rooms) - 2)) // 10
                # Estimate run time: sum(room_len / speed_in) for each room
                t_run = sum(
                    (r.w if r.travel_axis == 'x' else r.d) / max(1.0, r.speed_in)
                    for r in rooms
                )
                t_str = (f"{int(t_run // 60)}m {t_run % 60:.0f}s"
                         if t_run >= 60 else f"{t_run:.0f}s")
                self._log(
                    f"Done in {dt:.2f}s — {len(rooms)} rooms, "
                    f"{len(bridges)} bridges, {nb} brushes, {kb:.1f} KB", "info")
                self._log(
                    f"  Checkpoints: {n_cp}  |  Est. run time: ~{t_str}", "plain")
                for w in gen_warnings:
                    self._log(w, "warn")

                stats = (f"rooms={len(rooms)}  bridges={len(bridges)}"
                         f"  brushes={nb}  ~{t_str}  {kb:.1f} KB")
                self._ui(lambda s=stats: self._lbl_stats.setText(s))
                self._ui(self._redraw)
                self._ui(lambda: self._viewer3d.load(self._rooms, self._bridges))

                if self._btn_auto.isChecked():
                    self._ui(lambda: QTimer.singleShot(200, self._randomize_seed))

            except Exception as ex:
                import traceback; traceback.print_exc()
                self._log(f"Error: {ex}", "error")

        threading.Thread(target=run, daemon=True).start()

    def _on_import_rbe(self):
        def run():
            path = self._edit_rbe_path.text().strip()
            if not path:
                self._log("No file selected.", "error")
                return
            sx = self._spin_rbe_sx.value()
            sy = self._spin_rbe_sy.value()
            sz = self._spin_rbe_sz.value()
            try:
                ms, fake_rooms, _ = dbt_import.run_import(
                    path, sx, sy, sz, log_fn=self._log)
                self._map_str = ms
                self._rooms   = fake_rooms
                self._bridges = []
                self._is_rbe_import = True
                self._ui(self._redraw)
                self._ui(lambda r=fake_rooms:
                         self._viewer3d.load(r, [], show_labels=False))
            except Exception as ex:
                import traceback; traceback.print_exc()
                self._log(f"Error: {ex}", "error")

        threading.Thread(target=run, daemon=True).start()

    # ── Save / open ───────────────────────────────────────────────────────
    def _current_out_path(self) -> str:
        """Build the full output path from folder + current map name field."""
        folder = self._edit_out_folder.text().strip() or os.getcwd()
        name_edit = (self._edit_map_name_rbe
                     if self._is_rbe_import else self._edit_map_name_gen)
        name = name_edit.text().strip()
        if not name:
            name = "imported" if self._is_rbe_import else "generated"
        if not name.lower().endswith(".map"):
            name += ".map"
        return os.path.join(folder, name)

    def _on_save(self):
        if not self._map_str:
            self._log("Nothing to save — generate or import first.", "warn")
            return
        self._do_save(manual=True)

    def _do_save(self, manual=False):
        path = self._current_out_path()
        try:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._map_str)
            self._last_map_path = path
            self._log(f"{'Saved' if manual else 'Auto-saved'}: {path}", "info")
        except Exception as e:
            self._log(f"Save error: {e}", "error")

    def _on_open_folder(self):
        folder = self._edit_out_folder.text().strip() or os.getcwd()
        os.makedirs(folder, exist_ok=True)
        try:
            if os.name == 'nt':
                os.startfile(folder)
            else:
                subprocess.run(['xdg-open', folder])
        except Exception as ex:
            self._log(f"Cannot open folder: {ex}", "error")

    def _on_launch_game(self):
        exe  = self._edit_game_exe.text().strip()
        path = self._last_map_path or self._current_out_path()
        if not exe:
            self._log("Set the game executable path first.", "warn")
            return
        if not path or not os.path.isfile(path):
            self._log("Save a map first (or generate + auto-save).", "warn")
            return
        try:
            self._write_texture_mapping(exe, path)
            cmd = [exe, "--", f"--import={path}"]
            subprocess.Popen(cmd)
            self._log(f"Launched: {' '.join(cmd)}", "info")
        except Exception as ex:
            self._log(f"Launch failed: {ex}", "error")

    def _write_texture_mapping(self, exe_path: str, map_path: str):
        """Write <game_dir>/map_wip/<map_name>.json with the current texture
        index mapping, mirroring what turnt_texture_mapper.bat generates."""
        import json as _json
        game_dir = os.path.dirname(os.path.abspath(exe_path))
        map_name = os.path.splitext(os.path.basename(map_path))[0]
        wip_dir  = os.path.join(game_dir, "map_wip")
        os.makedirs(wip_dir, exist_ok=True)
        out_path = os.path.join(wip_dir, f"{map_name}.json")
        payload  = {"inverse_scale": 24, "textures": dict(ALL_TEXTURES)}
        with open(out_path, "w", encoding="utf-8") as f:
            _json.dump(payload, f, indent=2)
        self._log(f"Texture map → {out_path}", "info")

    # ── Browse helpers ────────────────────────────────────────────────────
    def _browse_out_folder(self):
        d = QFileDialog.getExistingDirectory(
            self, "Select output folder",
            self._edit_out_folder.text() or os.getcwd())
        if d:
            self._edit_out_folder.setText(d)

    def _browse_tex_folder(self):
        d = QFileDialog.getExistingDirectory(
            self, "Select texture folder", self._edit_tex_folder.text())
        if d:
            self._edit_tex_folder.setText(d)
            self._tex_paths.clear()
            self._tex_pixmaps.clear()
            self._status_bar.showMessage("Scanning texture folder…")
            threading.Thread(target=self._scan_tex_folder, args=(d,), daemon=True).start()

    def _scan_tex_folder(self, folder: str):
        found = {}
        for root_d, _, files in os.walk(folder):
            for fn in files:
                nm, ext = os.path.splitext(fn)
                if ext.lower() not in IMG_EXTS:
                    continue
                for tex in ALL_TEXTURES:
                    base = tex.split("/")[-1]
                    if nm.lower() == base.lower():
                        found[tex] = os.path.join(root_d, fn)
        self._tex_paths.update(found)
        self._ui(lambda n=len(found):
            self._status_bar.showMessage(f"Scan complete — {n} textures matched"))
        self._ui(self._refresh_thumbs)

    def _refresh_thumbs(self):
        if not PIL_OK:
            return
        # Reload thumbnails by re-populating the list
        self._tex_pixmaps.clear()
        self._populate_tex_list()

    def _browse_game_exe(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select game executable", self._edit_game_exe.text(),
            "Executable (*.exe *.sh *.app);;All files (*.*)")
        if path:
            self._edit_game_exe.setText(path)

    def _browse_rbe(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Diabotical map", self._edit_rbe_path.text(),
            "Diabotical Map (*.rbe);;All files (*.*)")
        if path:
            self._edit_rbe_path.setText(path)
            # Auto-fill map name from source filename (user can still change it)
            stem = os.path.splitext(os.path.basename(path))[0]
            self._edit_map_name_rbe.setText(stem)

    # ── Preview ───────────────────────────────────────────────────────────
    def _redraw(self):
        self._preview2d.load(
            self._rooms, self._bridges,
            is_rbe_import=self._is_rbe_import,
            use_physics=self._chk_physics.isChecked(),
            show_labels=self._chk_prev_labels.isChecked(),
            show_hmap=self._chk_prev_hmap.isChecked(),
        )

    def _2d_fit(self):
        self._preview2d.fit()

    def _on_view_tab_changed(self, index: int):
        if index == 1 and self._rooms:  # 3D tab
            self._viewer3d.load(
                self._rooms, self._bridges,
                show_labels=(self._chk_prev_labels.isChecked() and not self._is_rbe_import))

    # ── Theme ─────────────────────────────────────────────────────────────
    def _apply_theme(self, dark: bool):
        """Switch between dark and light themes at runtime."""
        self._dark_mode = dark
        T.clear()
        T.update(DARK_T if dark else LIGHT_T)
        QApplication.instance().setStyleSheet(build_qss(T))
        # Refresh QPainter-based widgets so they repaint with new palette
        if hasattr(self, '_preview2d'):
            self._preview2d.update()
        if hasattr(self, '_viewer3d'):
            self._viewer3d.update()

    # ── Thread-safe UI dispatch ───────────────────────────────────────────
    def _ui(self, fn):
        """Call fn() on the main thread, safe to invoke from any thread."""
        if threading.current_thread() is threading.main_thread():
            fn()
        else:
            self._dispatch_signal.emit(fn)

    # ── Log ───────────────────────────────────────────────────────────────
    def _log(self, msg: str, level: str = "plain"):
        color_map = {
            "info":  QColor(T["success"]),
            "warn":  QColor(T["warning"]),
            "error": QColor(T["accent"]),
            "plain": QColor(T["text_dim"]),
        }
        pfx = {"info": "[OK] ", "warn": "[!!] ", "error": "[ERR] "}.get(level, "")
        fmt = QTextCharFormat()
        fmt.setForeground(color_map.get(level, QColor(T["text_dim"])))

        def _append():
            cursor = self._logbox.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.insertText(pfx + msg + "\n", fmt)
            self._logbox.setTextCursor(cursor)
            self._logbox.ensureCursorVisible()
            self._status_bar.showMessage(msg)

        self._ui(_append)

    def _clear_log(self):
        self._logbox.clear()

    # ── UI helpers ────────────────────────────────────────────────────────
    def _toggle_physics(self):
        enabled = self._chk_physics.isChecked()
        for sb in self._phy_widgets:
            sb.setEnabled(enabled)

    def _toggle_autorand(self):
        is_auto = self._btn_auto.isChecked()
        self._btn_auto.setProperty("active", "true" if is_auto else "false")
        self._btn_auto.style().unpolish(self._btn_auto)
        self._btn_auto.style().polish(self._btn_auto)
        self._spin_seed.setReadOnly(is_auto)
        self._spin_seed.setButtonSymbols(
            QSpinBox.ButtonSymbols.NoButtons if is_auto
            else QSpinBox.ButtonSymbols.UpDownArrows)
        if is_auto:
            self._randomize_seed(silent=True)

    def _randomize_seed(self, silent: bool = False):
        if not self._btn_auto.isChecked():
            return
        s = random.randint(0, 9_999_999)
        self._spin_seed.setValue(s)
        if not silent:
            self._log(f"Seed → {s}", "info")

    # ── Auto-update ───────────────────────────────────────────────────────
    def _on_update_available(self, version: str, url: str):
        self._ui(lambda v=version, u=url: self._show_update_banner(v, u))

    def _show_update_banner(self, version: str, url: str):
        banner = QWidget()
        banner.setObjectName("updateBanner")
        banner.setFixedHeight(36)
        row = QHBoxLayout(banner)
        row.setContentsMargins(12, 4, 12, 4)
        lbl = QLabel(f"  Update v{version} available!")
        btn_update = QPushButton("Update now")
        btn_update.setObjectName("btnSmall")
        btn_update.clicked.connect(
            lambda: download_and_restart(url, version, self._status_bar.showMessage))
        btn_dismiss = QPushButton("✕")
        btn_dismiss.setObjectName("btnSmall")
        btn_dismiss.setFixedWidth(28)
        btn_dismiss.clicked.connect(banner.hide)
        row.addWidget(lbl)
        row.addStretch()
        row.addWidget(btn_update)
        row.addWidget(btn_dismiss)
        self._root_layout.insertWidget(1, banner)

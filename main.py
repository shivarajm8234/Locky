import sys
import os
import time
import psutil
import json
import subprocess
import socket
from typing import Optional
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QLineEdit, QFrame,
                             QGraphicsDropShadowEffect, QProgressBar)
from PyQt6.QtCore import Qt, QTimer, QPoint, QPropertyAnimation, QEasingCurve, QRect, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPixmap, QIcon, QPainter, QLinearGradient, QBrush, QPen, QCursor
from lock_logic import GnomeLock

# Add local libs to path
sys.path.append(os.path.join(os.getcwd(), "libs"))

_DIR = os.path.dirname(os.path.abspath(__file__))

# Prefer a file named spiderlogo.jpg; fall back to the full-length filename
for _candidate in ("spiderlogo.png",
                   "HD-wallpaper-spiderlogo-marvel-spiderman-spiderman-logo-superhero-thumbnail.jpg"):
    _p = os.path.join(_DIR, _candidate)
    if os.path.exists(_p):
        LOGO_PATH = _p
        break
else:
    LOGO_PATH = ""   # no image found; will use emoji fallback

# Idle alert: 5 minutes of no mouse/keyboard activity
IDLE_THRESHOLD_MS = 5 * 60 * 1000   # milliseconds

# Best available alarm sound
ALARM_SOUNDS = [
    "/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga",
    "/usr/share/sounds/gnome/default/alerts/drip.ogg",
]
ALARM_SOUND = next((s for s in ALARM_SOUNDS if os.path.exists(s)), None)


# ─────────────────────────────────────────────────────────────────────────────
# Idle Alert Dialog
# ─────────────────────────────────────────────────────────────────────────────
class IdleAlertDialog(QWidget):
    """Fullscreen-topmost alert that loops an alarm sound until OK is clicked."""

    dismissed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)  # type: ignore[call-arg]
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.X11BypassWindowManagerHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(380, 260)

        self._sound_proc = None
        self._sound_timer = QTimer(self)
        self._sound_timer.timeout.connect(self._play_sound)
        self._build_ui()

        # Center on screen
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            screen.center().x() - self.width() // 2,
            screen.center().y() - self.height() // 2
        )

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        card = QFrame()
        card.setObjectName("alertCard")
        card.setStyleSheet("""
            #alertCard {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                                stop:0 #1a0000, stop:1 #0d0d0d);
                border-radius: 28px;
                border: 2px solid #E62429;
            }
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(40)
        shadow.setColor(QColor(230, 36, 41, 200))
        shadow.setOffset(0, 0)
        card.setGraphicsEffect(shadow)

        lay = QVBoxLayout(card)
        lay.setContentsMargins(36, 30, 36, 30)
        lay.setSpacing(14)

        # Icon row
        icon_lbl = QLabel("⚠️")
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet("font-size: 46px;")
        lay.addWidget(icon_lbl)

        # Title
        title = QLabel("IDLE DETECTED")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            "color: #E62429; font-size: 20px; font-weight: bold; letter-spacing: 4px;"
        )
        lay.addWidget(title)

        # Subtitle
        sub = QLabel("No activity for 5 minutes.\nAre you still working?")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet("color: rgba(255,255,255,0.65); font-size: 13px; line-height: 1.5;")
        sub.setWordWrap(True)
        lay.addWidget(sub)

        lay.addSpacing(6)

        # OK button
        ok_btn = QPushButton("YES, I'M HERE  ✓")
        ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ok_btn.setStyleSheet("""
            QPushButton {
                background-color: #E62429;
                color: white;
                border-radius: 18px;
                padding: 14px 24px;
                font-weight: 800;
                font-size: 14px;
                letter-spacing: 1px;
            }
            QPushButton:hover { background-color: #ff3c41; }
        """)
        ok_btn.clicked.connect(self._on_ok)
        lay.addWidget(ok_btn)

        root.addWidget(card)

    def start_alarm(self):
        """Begin playing the alarm sound in a loop."""
        self._play_sound()
        self._sound_timer.start(4000)   # replay every 4 s

    def _play_sound(self):
        """Fire-and-forget subprocess for the alarm."""
        if ALARM_SOUND:
            try:
                subprocess.Popen(
                    ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", ALARM_SOUND],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
            except Exception:
                pass
        else:
            # Fallback: terminal bell sequence
            try:
                subprocess.Popen(["bash", "-c", "echo -n '\a'"])
            except Exception:
                pass

    def _stop_sound(self):
        self._sound_timer.stop()
        # Kill any lingering ffplay processes
        try:
            subprocess.run(["pkill", "-f", "ffplay.*alarm"], capture_output=True)
        except Exception:
            pass

    def _on_ok(self):
        self._stop_sound()
        self.hide()
        self.dismissed.emit()

    def closeEvent(self, event):
        self._stop_sound()
        event.accept()


# ─────────────────────────────────────────────────────────────────────────────
# Floating desktop icon (replaces system tray — never in taskbar)
# ─────────────────────────────────────────────────────────────────────────────
class FloatingIcon(QWidget):
    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)  # type: ignore[call-arg]
        # Flags that keep it off the taskbar: Tool + X11Bypass + StaysOnTop
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.X11BypassWindowManagerHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(70, 70)

        self._drag_pos = None
        self._time_str = ""
        self._active = False

        # Build label layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._label = QLabel(self)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._label)

        self._load_logo()

        # Position bottom-right corner by default
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.right() - 85, screen.bottom() - 85)

    def _load_logo(self):
        size = 64
        base = QPixmap(size, size)
        base.fill(Qt.GlobalColor.transparent)
        painter = QPainter(base)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Circle background
        painter.setBrush(QBrush(QColor("#111111")))
        painter.setPen(QPen(QColor("#E62429"), 3))
        painter.drawEllipse(2, 2, size - 4, size - 4)
        # Spider logo image
        if os.path.exists(LOGO_PATH):
            logo = QPixmap(LOGO_PATH).scaled(
                45, 45,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            painter.drawPixmap((size - logo.width()) // 2,
                               (size - logo.height()) // 2,
                               logo)
        else:
            font = QFont("monospace", 30)
            painter.setFont(font)
            painter.setPen(QPen(QColor("#E62429")))
            painter.drawText(base.rect(), Qt.AlignmentFlag.AlignCenter, "🕷")
        painter.end()
        self._base_pixmap = base
        self._render()

    def _render(self):
        """Compose base logo + optional time overlay."""
        size = 64
        px = self._base_pixmap.copy()
        if self._active and self._time_str:
            painter = QPainter(px)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            # Semi-transparent badge at bottom
            painter.setBrush(QBrush(QColor(0, 0, 0, 180)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(4, size - 26, size - 8, 22, 8, 8)
            # Timer text
            font = QFont("monospace", 10, QFont.Weight.Bold)
            painter.setFont(font)
            painter.setPen(QPen(QColor("#E62429")))
            painter.drawText(4, size - 22, size - 8, 20,
                             Qt.AlignmentFlag.AlignCenter, self._time_str)
            painter.end()
        self._label.setPixmap(px)

    def update_time(self, time_str, active=True):
        self._time_str = time_str
        self._active = active
        self._render()

    # ── Drag support ──────────────────────────────────────────────
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.globalPosition().toPoint()
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if hasattr(self, "_drag_start_pos"):
                # If we moved less than 10 pixels, consider it a click
                dist = (event.globalPosition().toPoint() - self._drag_start_pos).manhattanLength()
                if dist < 10:
                    self.clicked.emit()
            self._drag_pos = None
            event.accept()

    def enterEvent(self, event):
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def leaveEvent(self, event):
        self.unsetCursor()


# ─────────────────────────────────────────────────────────────────────────────
# Main Locky widget
# ─────────────────────────────────────────────────────────────────────────────
class LockyWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.gnome_lock = GnomeLock()
        self.locked = False
        self.time_left = 0
        self.total_time = 0
        self.distraction_count = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_timer)

        self.whitelist = ['code', 'firefox', 'chrome', 'evince', 'vlc', 'Locky', 'python3', 'bash']

        # Create sub-widgets eagerly (hidden); avoids Optional/NoneType issues
        self._float_icon = FloatingIcon()
        self._float_icon.clicked.connect(self._restore_from_icon)

        self._idle_alert = IdleAlertDialog()
        self._idle_alert.dismissed.connect(self._on_idle_dismissed)

        self._idle_alert_shown = False
        self.study_elapsed = 0

        # Idle poll: every 30 s, only active during a session
        self._idle_poll = QTimer()
        self._idle_poll.timeout.connect(self._check_idle)

        self.init_ui()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.old_pos = None


    # ── Idle detection ────────────────────────────────────────────
    def _start_idle_watch(self):
        self._idle_alert_shown = False
        self._idle_poll.start(30_000)   # check every 30 s

    def _stop_idle_watch(self):
        self._idle_poll.stop()
        if self._idle_alert is not None:
            self._idle_alert._stop_sound()
            self._idle_alert.hide()
        self._idle_alert_shown = False

    def _get_idle_ms(self):
        """Return system idle time in ms via GNOME IdleMonitor (no extra deps)."""
        try:
            result = subprocess.run(
                ["gdbus", "call", "-e",
                 "-d", "org.gnome.Mutter.IdleMonitor",
                 "-o", "/org/gnome/Mutter/IdleMonitor/Core",
                 "-m", "org.gnome.Mutter.IdleMonitor.GetIdletime"],
                capture_output=True, text=True, timeout=3
            )
            # output looks like: (uint64 12345,)
            raw = result.stdout.strip().strip("()").replace("uint64 ", "").rstrip(",")
            return int(raw)
        except Exception:
            return 0

    def _check_idle(self):
        if not self.locked:
            return
        idle_ms = self._get_idle_ms()
        if idle_ms >= IDLE_THRESHOLD_MS and not self._idle_alert_shown:
            self._idle_alert_shown = True
            self._show_idle_alert()
        elif idle_ms < IDLE_THRESHOLD_MS and self._idle_alert_shown:
            # User became active — dismiss automatically too
            if self._idle_alert is not None and self._idle_alert.isVisible():
                self._idle_alert._on_ok()

    def _show_idle_alert(self):
        if self._idle_alert is None:
            self._idle_alert = IdleAlertDialog()
            self._idle_alert.dismissed.connect(self._on_idle_dismissed)
        self._idle_alert.show()
        self._idle_alert.raise_()
        self._idle_alert.activateWindow()
        self._idle_alert.start_alarm()

    def _on_idle_dismissed(self):
        self._idle_alert_shown = False


    def init_ui(self):
        self.setFixedSize(320, 520)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(15, 15, 15, 15)

        self.container = QFrame()
        self.container.setObjectName("container")
        self.update_style(False)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(25)
        shadow.setColor(QColor(230, 36, 41, 150))
        shadow.setOffset(0, 8)
        self.container.setGraphicsEffect(shadow)

        self.layout = QVBoxLayout(self.container)
        self.layout.setContentsMargins(20, 15, 20, 20)

        # ── Top bar: close/minimize button ────────────────────────
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)
        top_bar.addStretch()

        self.close_btn = QPushButton("×")
        self.close_btn.setFixedSize(28, 28)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setToolTip("Minimize to desktop icon")
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255,255,255,0.08);
                color: rgba(255,255,255,0.55);
                border: none;
                border-radius: 14px;
                font-size: 18px;
                font-weight: bold;
                padding-bottom: 2px;
            }
            QPushButton:hover {
                background-color: #E62429;
                color: white;
            }
        """)
        self.close_btn.clicked.connect(self._minimize_to_icon)
        top_bar.addWidget(self.close_btn)
        self.layout.addLayout(top_bar)

        # ── Logo ──────────────────────────────────────────────────
        self.logo_container = QLabel()
        self.logo_container.setFixedSize(90, 90)
        self.logo_container.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if os.path.exists(LOGO_PATH):
            pixmap = QPixmap(LOGO_PATH).scaled(
                80, 80,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.logo_container.setPixmap(pixmap)
        else:
            self.logo_container.setText("🕷")
            self.logo_container.setStyleSheet("color: #E62429; font-size: 70px;")
        self.layout.addWidget(self.logo_container, alignment=Qt.AlignmentFlag.AlignCenter)

        # Status Label
        self.title_label = QLabel("SYSTEM IDLE")
        self.title_label.setStyleSheet("color: rgba(255, 255, 255, 0.4); font-size: 11px; font-weight: bold; letter-spacing: 3px;")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.title_label)

        # Timer Display
        self.timer_label = QLabel("00:00")
        self.timer_label.setStyleSheet("color: #E62429; font-size: 58px; font-weight: 300; font-family: 'monospace';")
        self.timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.timer_label)

        # "Studying for" elapsed clock
        self.study_clock_label = QLabel("📚 STUDYING FOR  00:00:00")
        self.study_clock_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.study_clock_label.setStyleSheet("""
            color: rgba(255,255,255,0.75);
            font-size: 11px;
            font-weight: bold;
            letter-spacing: 1px;
            background: rgba(230,36,41,0.12);
            border-radius: 10px;
            padding: 5px 10px;
        """)
        self.study_clock_label.hide()
        self.layout.addWidget(self.study_clock_label)

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: rgba(255, 255, 255, 0.05);
                border-radius: 2px;
                border: none;
            }
            QProgressBar::chunk {
                background-color: #E62429;
                border-radius: 2px;
            }
        """)
        self.layout.addWidget(self.progress_bar)

        self.layout.addSpacing(15)

        # Task Input
        self.task_input = QLineEdit()
        self.task_input.setPlaceholderText("MISSION OBJECTIVE...")
        self.task_input.setStyleSheet("""
            QLineEdit {
                background-color: rgba(255, 255, 255, 0.07);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 12px;
                color: white;
                padding: 14px;
                font-size: 13px;
            }
            QLineEdit:focus { border: 1px solid #E62429; }
        """)
        self.layout.addWidget(self.task_input)

        # Allowed URLs (hidden by default)
        self.allowed_urls_input = QLineEdit()
        self.allowed_urls_input.setPlaceholderText("ALLOWED URLs (comma separated)")
        self.allowed_urls_input.setStyleSheet(self.task_input.styleSheet())
        self.allowed_urls_input.hide()
        self.layout.addWidget(self.allowed_urls_input)

        self.task_input.textChanged.connect(self.check_browser_mode)

        # Duration
        self.duration_input = QLineEdit()
        self.duration_input.setPlaceholderText("TIME (MINUTES)")
        self.duration_input.setStyleSheet(self.task_input.styleSheet())
        self.layout.addWidget(self.duration_input)

        # Distraction Counter
        self.distraction_label = QLabel("")
        self.distraction_label.setStyleSheet("color: #ffcc00; font-size: 10px; font-weight: bold;")
        self.distraction_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.distraction_label)

        self.layout.addStretch()

        # Action Button
        self.action_btn = QPushButton("INITIATE PROTOCOL")
        self.action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.action_btn.setStyleSheet("""
            QPushButton {
                background-color: #E62429;
                color: white;
                border-radius: 20px;
                padding: 18px;
                font-weight: 1000;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #ff3c41; }
        """)
        self.action_btn.clicked.connect(self.toggle_lock)
        self.layout.addWidget(self.action_btn)

        self.main_layout.addWidget(self.container)

    def check_browser_mode(self, text):
        t = text.lower()
        if 'browser' in t or 'chrome' in t or 'firefox' in t or 'brave' in t:
            self.allowed_urls_input.show()
        else:
            self.allowed_urls_input.hide()

    def update_style(self, locked):
        border_color = "#E62429"
        self.container.setStyleSheet(f"""
            #container {{
                background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1,
                    stop:0 #0f0f0f, stop:1 #050505);
                border-radius: 35px;
                border: 2px solid {border_color};
            }}
        """)

    # ── Drag ──────────────────────────────────────────────────────
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if hasattr(self, '_drag_offset') and self._drag_offset is not None:
            if event.buttons() & Qt.MouseButton.LeftButton:
                self.move(event.globalPosition().toPoint() - self._drag_offset)
                event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_offset = None
        event.accept()

    # ── Floating icon ─────────────────────────────────────────────
    def _minimize_to_icon(self):
        """Hide main window, show floating desktop icon."""
        if self._float_icon is None:
            self._float_icon = FloatingIcon()
            self._float_icon.clicked.connect(self._restore_from_icon)
        if self.locked:
            mins, secs = divmod(self.time_left, 60)
            self._float_icon.update_time(f"{mins:02}:{secs:02}", active=True)
        else:
            self._float_icon.update_time("", active=False)
        self._float_icon.show()
        self.hide()

    def _restore_from_icon(self):
        """Hide the floating icon, restore main window."""
        if self._float_icon is not None:
            self._float_icon.hide()
        self.show()
        self.raise_()
        self.activateWindow()

    def _update_float_icon(self):
        """Sync floating icon timer display (called every second when active)."""
        if self._float_icon is not None and self._float_icon.isVisible():
            mins, secs = divmod(self.time_left, 60)
            self._float_icon.update_time(f"{mins:02}:{secs:02}", active=True)

    # ── Lock logic ────────────────────────────────────────────────
    def toggle_lock(self):
        if not self.locked:
            try:
                mins = int(self.duration_input.text()) if self.duration_input.text() else 25
                self.total_time = mins * 60
                self.time_left = self.total_time
                self.start_lock()
            except ValueError:
                self.duration_input.setText("ERROR: INT ONLY")
        else:
            self.stop_lock()

    def start_lock(self):
        self.locked = True
        self.distraction_count = 0
        self.gnome_lock.lock()
        self.update_style(True)
        self.title_label.setText("SESSION ACTIVE")
        self.title_label.setStyleSheet("color: #E62429; font-size: 11px; font-weight: bold; letter-spacing: 3px;")
        self.action_btn.setText("TERMINATE PROTOCOL")
        self.action_btn.setStyleSheet(self.action_btn.styleSheet().replace("#E62429", "#222"))
        self.task_input.setReadOnly(True)
        self.duration_input.setReadOnly(True)
        self.allowed_urls_input.setReadOnly(True)
        self.timer.start(1000)
        self.distraction_label.setText("DISTRACTIONS: 0")

        urls_text = self.allowed_urls_input.text().strip()
        if self.allowed_urls_input.isVisible() and urls_text:
            self.configure_browser(urls_text)

        self.focus_timer = QTimer()
        self.focus_timer.timeout.connect(self.check_violations)
        self.focus_timer.start(2000)

        # Reset & show the study elapsed clock
        self.study_elapsed = 0
        self.study_clock_label.setText("📚 STUDYING FOR  00:00:00")
        self.study_clock_label.show()

        # Start idle inactivity watch
        self._start_idle_watch()

        # Minimize to floating icon automatically
        self._minimize_to_icon()


    def configure_browser(self, urls_text):
        ext_dir = os.path.expanduser("~/Desktop/Locky/ext")
        os.makedirs(ext_dir, exist_ok=True)

        allowed_list = [u.strip() for u in urls_text.split(",") if u.strip()]

        manifest = {
            "manifest_version": 3,
            "name": "Locky Focus",
            "version": "1.0",
            "permissions": ["tabs", "webNavigation"],
            "host_permissions": ["<all_urls>"],
            "background": {"service_worker": "bg.js"}
        }

        with open(os.path.join(ext_dir, "manifest.json"), "w") as f:
            json.dump(manifest, f)

        bg_js = f"""
        const allowedUrls = {json.dumps(allowed_list)};
        chrome.webNavigation.onBeforeNavigate.addListener((details) => {{
            if (details.frameId === 0) {{
                const isAllowed = allowedUrls.some(u => details.url.includes(u));
                if (!isAllowed && !details.url.startsWith("chrome://")) {{
                    chrome.tabs.update(details.tabId, {{url: "data:text/html,<h1>Locky: URL Blocked</h1>"}});
                }}
            }}
        }});
        chrome.tabs.onActivated.addListener((activeInfo) => {{
            chrome.tabs.query({{currentWindow: true}}, function(tabs) {{
                if(tabs.length > 1) {{
                    for(let t of tabs) {{
                        if(t.id !== activeInfo.tabId) chrome.tabs.remove(t.id);
                    }}
                }}
            }});
        }});
        """
        with open(os.path.join(ext_dir, "bg.js"), "w") as f:
            f.write(bg_js)

        try:
            import subprocess
            for browser_cmd in ["google-chrome", "brave-browser", "chromium"]:
                if os.system(f"which {browser_cmd} > /dev/null") == 0:
                    subprocess.Popen([browser_cmd, f"--load-extension={ext_dir}"])
                    break
        except Exception as e:
            print("Failed to launch browser:", e)

    def stop_lock(self):
        self.locked = False
        self.gnome_lock.unlock()
        self.update_style(False)
        self.title_label.setText("SESSION COMPLETE")
        self.action_btn.setText("INITIATE PROTOCOL")
        self.action_btn.setStyleSheet(self.action_btn.styleSheet().replace("#222", "#E62429"))
        self.task_input.setReadOnly(False)
        self.duration_input.setReadOnly(False)
        self.allowed_urls_input.setReadOnly(False)
        self.allowed_urls_input.clear()
        self.allowed_urls_input.hide()
        self.timer.stop()
        if hasattr(self, 'focus_timer'):
            self.focus_timer.stop()
        self.log_session()
        # Hide study elapsed clock
        self.study_clock_label.hide()
        self.study_elapsed = 0
        # Stop idle watch and dismiss any alert
        self._stop_idle_watch()
        # Hide floating icon and restore window
        if self._float_icon is not None:
            self._float_icon.hide()
        self.show()
        self.raise_()
        self.activateWindow()


    def check_violations(self):
        if not self.locked:
            return
        forbidden_found = False
        for proc in psutil.process_iter(['name']):
            if proc.info['name'] in ['discord', 'steam', 'spotify', 'telegram', 'slack']:
                forbidden_found = True
                try:
                    proc.terminate()
                    self.distraction_count += 1
                except:
                    pass
        if forbidden_found:
            self.distraction_label.setText(f"DISTRACTIONS: {self.distraction_count}")
            self.trigger_warning("DISTRACTION TERMINATED")
            QApplication.beep()

    def trigger_warning(self, message):
        self.title_label.setText(message)
        original_rect = self.geometry()
        self.shake_anim = QPropertyAnimation(self, b"geometry")
        self.shake_anim.setDuration(400)
        self.shake_anim.setStartValue(original_rect)
        for i in range(1, 10):
            offset = 10 if i % 2 == 0 else -10
            self.shake_anim.setKeyValueAt(i / 10, QRect(
                original_rect.x() + offset, original_rect.y(),
                original_rect.width(), original_rect.height()
            ))
        self.shake_anim.setEndValue(original_rect)
        self.shake_anim.start()
        QTimer.singleShot(2000, lambda: self.title_label.setText("SESSION ACTIVE"))

    def update_timer(self):
        if self.time_left > 0:
            self.time_left -= 1
            self.study_elapsed += 1
            mins, secs = divmod(self.time_left, 60)
            self.timer_label.setText(f"{mins:02}:{secs:02}")
            # Elapsed clock  HH:MM:SS
            h, rem = divmod(self.study_elapsed, 3600)
            m, s = divmod(rem, 60)
            self.study_clock_label.setText(f"📚 STUDYING FOR  {h:02}:{m:02}:{s:02}")
            progress = int(((self.total_time - self.time_left) / self.total_time) * 100)
            self.progress_bar.setValue(progress)
            self._update_float_icon()
        else:
            self.stop_lock()

    def log_session(self):
        h, rem = divmod(self.study_elapsed, 3600)
        m, s = divmod(rem, 60)
        log_data = {
            "timestamp": time.ctime(),
            "task": self.task_input.text(),
            "duration_set_min": self.total_time // 60,
            "studied_for": f"{h:02}:{m:02}:{s:02}",
            "distractions": self.distraction_count
        }
        with open("distractions.log", "a") as f:
            f.write(json.dumps(log_data) + "\n")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape and not self.locked:
            self.close()

    def closeEvent(self, event):
        if self.locked:
            self.stop_lock()
        else:
            self.gnome_lock.unlock()
        if self._float_icon is not None:
            self._float_icon.close()
        event.accept()


if __name__ == "__main__":
    # Use Wayland if available, otherwise fall back to X11 (xcb)
    if not os.environ.get("WAYLAND_DISPLAY") and not os.environ.get("QT_QPA_PLATFORM"):
        os.environ["QT_QPA_PLATFORM"] = "xcb"
    elif not os.environ.get("QT_QPA_PLATFORM"):
        os.environ["QT_QPA_PLATFORM"] = "wayland"

    # Single instance check
    try:
        # Use an abstract socket to prevent multiple instances
        lock_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        # The leading prefix \0 makes it an abstract socket (Linux only)
        lock_socket.bind('\0locky_focus_widget_lock')
    except socket.error:
        print("Locky is already running. Exiting.")
        sys.exit(0)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)   # keep alive when main window hides

    # Set spider logo as the app icon everywhere
    if LOGO_PATH and os.path.exists(LOGO_PATH):
        app_icon = QIcon(LOGO_PATH)
        app.setWindowIcon(app_icon)

    window = LockyWidget()

    if LOGO_PATH and os.path.exists(LOGO_PATH):
        window.setWindowIcon(QIcon(LOGO_PATH))

    window.show()
    sys.exit(app.exec())

import sys
import os
import time
import psutil
import json
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QPushButton, QLineEdit, QFrame, QGraphicsDropShadowEffect, QProgressBar)
from PyQt6.QtCore import Qt, QTimer, QPoint, QPropertyAnimation, QEasingCurve, QRect, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPixmap, QIcon, QPainter, QLinearGradient
from lock_logic import GnomeLock

# Add local libs to path
sys.path.append(os.path.join(os.getcwd(), "libs"))

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
        
        self.init_ui()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.old_pos = None

    def init_ui(self):
        self.setFixedSize(320, 520)
        
        self.main_layout = QVBoxLayout()
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
        self.layout.setContentsMargins(20, 20, 20, 20)
        
        # Logo with circular background
        self.logo_container = QLabel()
        self.logo_container.setFixedSize(110, 110)
        self.logo_container.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_path = "/home/satoru/Desktop/Locky/HD-wallpaper-spiderlogo-marvel-spiderman-spiderman-logo-superhero-thumbnail.jpg"
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path).scaled(100, 100, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
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
        
        # Allowed URLs (Hidden by default)
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
        
        # Distraction Counter (Hidden until session starts)
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
        self.setLayout(self.main_layout)
        
    def check_browser_mode(self, text):
        t = text.lower()
        if 'browser' in t or 'chrome' in t or 'firefox' in t or 'brave' in t:
            self.allowed_urls_input.show()
        else:
            self.allowed_urls_input.hide()

    def update_style(self, locked):
        border_color = "#E62429" if not locked else "#E62429"
        glow_color = "rgba(230, 36, 41, 150)" if not locked else "rgba(255, 0, 0, 200)"
        self.container.setStyleSheet(f"""
            #container {{
                background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, 
                    stop:0 #0f0f0f, stop:1 #050505);
                border-radius: 35px;
                border: 2px solid {border_color};
            }}
        """)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.old_pos is not None:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.old_pos = None

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
        
        # Configure browser if needed
        urls_text = self.allowed_urls_input.text().strip()
        if self.allowed_urls_input.isVisible() and urls_text:
            self.configure_browser(urls_text)
        
        # Focus Enforcement Timer
        self.focus_timer = QTimer()
        self.focus_timer.timeout.connect(self.check_violations)
        self.focus_timer.start(2000)

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
            "background": {
                "service_worker": "bg.js"
            }
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
        
        // Prevent tab shifting by enforcing only one active allowed tab or closing others
        chrome.tabs.onActivated.addListener((activeInfo) => {{
            chrome.tabs.query({{currentWindow: true}}, function(tabs) {{
                if(tabs.length > 1) {{
                    for(let t of tabs) {{
                        if(t.id !== activeInfo.tabId) {{
                            chrome.tabs.remove(t.id);
                        }}
                    }}
                }}
            }});
        }});
        """
        with open(os.path.join(ext_dir, "bg.js"), "w") as f:
            f.write(bg_js)
            
        # Try to launch chrome with this extension
        try:
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
        self.focus_timer.stop()
        self.log_session()

    def check_violations(self):
        if not self.locked: return
        
        forbidden_found = False
        for proc in psutil.process_iter(['name']):
            if proc.info['name'] in ['discord', 'steam', 'spotify', 'telegram', 'slack']:
                forbidden_found = True
                try: 
                    proc.terminate()
                    self.distraction_count += 1
                except: pass
        
        if forbidden_found:
            self.distraction_label.setText(f"DISTRACTIONS: {self.distraction_count}")
            self.trigger_warning("DISTRACTION TERMINATED")
            QApplication.beep()

    def trigger_warning(self, message):
        self.title_label.setText(message)
        # Shake animation
        original_rect = self.geometry()
        self.shake_anim = QPropertyAnimation(self, b"geometry")
        self.shake_anim.setDuration(400)
        self.shake_anim.setStartValue(original_rect)
        for i in range(1, 10):
            offset = 10 if i % 2 == 0 else -10
            self.shake_anim.setKeyValueAt(i/10, QRect(original_rect.x()+offset, original_rect.y(), original_rect.width(), original_rect.height()))
        self.shake_anim.setEndValue(original_rect)
        self.shake_anim.start()
        QTimer.singleShot(2000, lambda: self.title_label.setText("SESSION ACTIVE"))

    def update_timer(self):
        if self.time_left > 0:
            self.time_left -= 1
            mins, secs = divmod(self.time_left, 60)
            self.timer_label.setText(f"{mins:02}:{secs:02}")
            # Update progress
            progress = int(((self.total_time - self.time_left) / self.total_time) * 100)
            self.progress_bar.setValue(progress)
        else:
            self.stop_lock()

    def log_session(self):
        log_data = {
            "timestamp": time.ctime(),
            "task": self.task_input.text(),
            "duration": self.total_time // 60,
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
        event.accept()

if __name__ == "__main__":
    os.environ["QT_QPA_PLATFORM"] = "wayland"
    app = QApplication(sys.argv)
    window = LockyWidget()
    window.show()
    sys.exit(app.exec())

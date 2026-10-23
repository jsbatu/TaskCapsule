import sys
import random
import ctypes
from ctypes import wintypes
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QApplication
from PyQt6.QtCore import Qt, QPropertyAnimation, QRect, QEasingCurve, QTimer, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QPixmap, QImage, QPainterPath

# Win32 API Definitions for absolute topmost and taskbar ownership
user32 = ctypes.windll.user32
user32.SetWindowPos.argtypes = [
    wintypes.HWND, wintypes.HWND,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    ctypes.c_uint
]
user32.SetWindowPos.restype = wintypes.BOOL

user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.HWND]
user32.SetWindowLongPtrW.restype = wintypes.HWND

HWND_TOPMOST = wintypes.HWND(-1)
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
GWLP_HWNDPARENT = -8

def to_turkish_upper(text: str) -> str:
    """Converts a string to full uppercase, handling Turkish specific characters accurately."""
    if not text:
        return ""
    return text.replace('i', 'İ').replace('ı', 'I').upper()

class SpectrumWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(16, 16)
        self.is_playing = False
        self.timer = QTimer(self)
        self.timer.setInterval(120)
        self.timer.timeout.connect(self.update)
        self.heights = [3, 7, 3]

    def set_playing(self, playing):
        self.is_playing = playing
        if playing:
            self.timer.start()
        else:
            self.timer.stop()
            self.heights = [3, 3, 3]
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(255, 255, 255, 220)))
        
        for i in range(3):
            if self.is_playing:
                h = random.randint(3, 13)
            else:
                h = 3
            x = i * 5
            y = 16 - h
            painter.drawRoundedRect(x, y, 3, h, 1.5, 1.5)

class DynamicIsland(QWidget):
    space_pressed = pyqtSignal()

    def __init__(self):
        super().__init__()
        # Use Tool window flag to prevent taskbar auto-hide/send-to-back behaviors
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Dimensions
        self.collapsed_width = 240
        self.collapsed_height = 36
        self.expanded_width = 340
        self.expanded_height = 110
        
        # Calculate permanent position anchored inside the Windows Taskbar
        screen = QApplication.primaryScreen()
        full_geom = screen.geometry()
        avail_geom = screen.availableGeometry()
        
        taskbar_h = full_geom.height() - avail_geom.height()
        if taskbar_h <= 0:
            taskbar_h = 48
            
        taskbar_top = avail_geom.height() if avail_geom.height() < full_geom.height() else (full_geom.height() - taskbar_h)
        vertical_margin = max(2, (taskbar_h - self.collapsed_height) // 2)
        
        # Locked coordinates: bottom edge is base_y, left edge is base_x
        self.base_x = 12
        self.base_y = taskbar_top + self.collapsed_height + vertical_margin
        
        self.setGeometry(self.base_x, self.base_y - self.collapsed_height, self.collapsed_width, self.collapsed_height)
        
        self.is_expanded = False
        self.bg_color = QColor(15, 15, 15, 225)
        self.lyrics_data = []
        self.current_title = ""
        self.current_artist = ""
        self.current_curr_time = 0.0
        self.current_total_time = 0.0
        
        # Lead-in offset in seconds (negative delay: show lyrics ~2 seconds in advance)
        self.lyrics_offset = 2.0
        
        self.init_ui()
        
        # Auto-collapse timer (5 seconds of inactivity)
        self.auto_collapse_timer = QTimer(self)
        self.auto_collapse_timer.setSingleShot(True)
        self.auto_collapse_timer.setInterval(5000)
        self.auto_collapse_timer.timeout.connect(self.collapse)
        
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        
        # Continuous Win32 topmost enforcement
        self.topmost_timer = QTimer(self)
        self.topmost_timer.setInterval(150)
        self.topmost_timer.timeout.connect(self.enforce_topmost)
        self.topmost_timer.start()

    def showEvent(self, event):
        super().showEvent(event)
        self._bind_to_taskbar()
        self.enforce_topmost()

    def _bind_to_taskbar(self):
        try:
            tray_hwnd = user32.FindWindowW("Shell_TrayWnd", None)
            if tray_hwnd:
                user32.SetWindowLongPtrW(int(self.winId()), GWLP_HWNDPARENT, tray_hwnd)
        except Exception:
            pass

    def enforce_topmost(self):
        try:
            hwnd = int(self.winId())
            user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
        except Exception:
            pass

    def init_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 4, 10, 4)
        
        # --- COLLAPSED VIEW ---
        self.collapsed_widget = QWidget()
        self.collapsed_layout = QHBoxLayout(self.collapsed_widget)
        self.collapsed_layout.setContentsMargins(0, 0, 0, 0)
        self.collapsed_layout.setSpacing(8)
        
        self.mini_art = QLabel()
        self.mini_art.setFixedSize(24, 24)
        self.mini_art.setPixmap(self.create_placeholder_disc(24))
        self.collapsed_layout.addWidget(self.mini_art)
        
        self.mini_title = QLabel("No Media")
        self.mini_title.setStyleSheet("color: white; font-weight: 600; font-family: 'Segoe UI Variable Display', 'Segoe UI'; font-size: 12px;")
        self.mini_title.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self.collapsed_layout.addWidget(self.mini_title, 1)
        
        self.spectrum = SpectrumWidget()
        self.collapsed_layout.addWidget(self.spectrum)
        
        self.main_layout.addWidget(self.collapsed_widget)
        
        # --- EXPANDED VIEW ---
        self.expanded_widget = QWidget()
        self.expanded_layout = QHBoxLayout(self.expanded_widget)
        self.expanded_layout.setContentsMargins(4, 4, 4, 4)
        self.expanded_layout.setSpacing(12)
        
        self.art_label = QLabel()
        self.art_label.setFixedSize(72, 72)
        self.art_label.setStyleSheet("border-radius: 10px;")
        self.art_label.setScaledContents(True)
        self.art_label.setPixmap(self.create_placeholder_disc(72))
        self.expanded_layout.addWidget(self.art_label)
        
        self.details_layout = QVBoxLayout()
        self.details_layout.setSpacing(2)
        self.details_layout.setContentsMargins(0, 2, 0, 2)
        
        self.title_label = QLabel("NO MEDIA PLAYING")
        self.title_label.setStyleSheet("color: white; font-weight: bold; font-family: 'Segoe UI Variable Display', 'Segoe UI'; font-size: 14px;")
        
        self.artist_label = QLabel("Waiting for Spotify...")
        self.artist_label.setStyleSheet("color: #999999; font-family: 'Segoe UI Variable Display', 'Segoe UI'; font-size: 12px;")
        
        self.details_layout.addWidget(self.title_label)
        self.details_layout.addWidget(self.artist_label)
        self.details_layout.addStretch()
        
        self.progress_layout = QHBoxLayout()
        self.progress_layout.setSpacing(6)
        
        self.curr_time = QLabel("0:00")
        self.curr_time.setStyleSheet("color: #777777; font-size: 11px; font-family: 'Segoe UI';")
        
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 4px;
                background: #333333;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: white;
                width: 10px;
                margin: -3px 0;
                border-radius: 5px;
            }
            QSlider::sub-page:horizontal {
                background: white;
                border-radius: 2px;
            }
        """)
        self.slider.setEnabled(False)
        
        self.total_time = QLabel("0:00")
        self.total_time.setStyleSheet("color: #777777; font-size: 11px; font-family: 'Segoe UI';")
        
        self.progress_layout.addWidget(self.curr_time)
        self.progress_layout.addWidget(self.slider)
        self.progress_layout.addWidget(self.total_time)
        
        self.details_layout.addLayout(self.progress_layout)
        self.expanded_layout.addLayout(self.details_layout)
        
        self.expanded_widget.setVisible(False)
        self.main_layout.addWidget(self.expanded_widget)

    def create_placeholder_disc(self, size):
        img = QImage(size, size, QImage.Format.Format_ARGB32)
        img.fill(Qt.GlobalColor.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(255, 255, 255, 30), 1))
        p.setBrush(QBrush(QColor(35, 35, 35)))
        p.drawEllipse(1, 1, size - 2, size - 2)
        # Inner hole
        p.setBrush(QBrush(QColor(15, 15, 15)))
        p.drawEllipse(int(size * 0.35), int(size * 0.35), int(size * 0.3), int(size * 0.3))
        p.end()
        return QPixmap.fromImage(img)

    def get_circular_pixmap(self, img_data, size=24):
        img = QImage()
        img.loadFromData(img_data)
        if img.isNull():
            return self.create_placeholder_disc(size)
        
        img = img.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
        out_img = QImage(size, size, QImage.Format.Format_ARGB32)
        out_img.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(out_img)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addEllipse(0, 0, size, size)
        painter.setClipPath(path)
        painter.drawImage(0, 0, img)
        painter.end()
        
        return QPixmap.fromImage(out_img)

    def format_time(self, seconds):
        if seconds < 0: seconds = 0
        m = int(seconds // 60)
        s = int(seconds % 60)
        return f"{m}:{s:02d}"

    def update_lyrics(self, lyrics_list):
        self.lyrics_data = lyrics_list
        self._refresh_collapsed_text()

    def update_position(self, curr, total):
        self.current_curr_time = curr
        self.current_total_time = total
        
        self.curr_time.setText(self.format_time(curr))
        self.total_time.setText(self.format_time(total))
        if total > 0:
            self.slider.setValue(int((curr / total) * 100))
            
        if not self.is_expanded:
            self._refresh_collapsed_text()

    def _refresh_collapsed_text(self):
        if not self.current_title:
            self.mini_title.setText("NO MEDIA")
            return
            
        display_text = self.current_title
        curr = self.current_curr_time
        total = self.current_total_time
        
        # Apply negative delay (lead-in) so lyrics show ~2s in advance
        effective_curr = curr + self.lyrics_offset
        
        # If synchronized lyrics exist, find the matching line
        if self.lyrics_data:
            for i in range(len(self.lyrics_data)):
                lyric_time = self.lyrics_data[i]['time']
                next_time = self.lyrics_data[i+1]['time'] if i+1 < len(self.lyrics_data) else (total if total > 0 else lyric_time + 10)
                
                if lyric_time <= effective_curr < next_time:
                    display_text = self.lyrics_data[i]['text']
                    break
        
        if len(display_text) > 30:
            display_text = display_text[:27] + "..."
        self.mini_title.setText(display_text)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(self.bg_color))
        # Subtle glass border
        painter.setPen(QPen(QColor(255, 255, 255, 28), 1))
        rect = self.rect().adjusted(1, 1, -1, -1)
        radius = 16 if self.is_expanded else min(rect.width(), rect.height()) / 2
        painter.drawRoundedRect(rect, radius, radius)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if not self.is_expanded:
                self.expand()
            else:
                self.collapse()
            self.enforce_topmost()

    def enterEvent(self, event):
        # Pause auto-collapse countdown while user is hovering over expanded island
        if self.is_expanded:
            self.auto_collapse_timer.stop()
        super().enterEvent(event)

    def leaveEvent(self, event):
        # Resume 5-second auto-collapse countdown when cursor leaves
        if self.is_expanded:
            self.auto_collapse_timer.start(5000)
        super().leaveEvent(event)

    def keyPressEvent(self, event):
        if self.is_expanded and event.key() == Qt.Key.Key_Space:
            self.space_pressed.emit()
            self.auto_collapse_timer.start(5000)
        else:
            super().keyPressEvent(event)

    def expand(self):
        if self.is_expanded:
            return
        self.is_expanded = True
        self.collapsed_widget.setVisible(False)
        self.expanded_widget.setVisible(True)
        self.animate_geometry(self.expanded_width, self.expanded_height)
        self.auto_collapse_timer.start(5000)
        self.setFocus()

    def collapse(self):
        if not self.is_expanded:
            return
        self.is_expanded = False
        self.auto_collapse_timer.stop()
        self.collapsed_widget.setVisible(True)
        self.expanded_widget.setVisible(False)
        self.animate_geometry(self.collapsed_width, self.collapsed_height)
        self.clearFocus()
        self._refresh_collapsed_text()

    def animate_geometry(self, target_w, target_h):
        if hasattr(self, 'anim') and self.anim.state() == QPropertyAnimation.State.Running:
            self.anim.stop()
            
        self.anim = QPropertyAnimation(self, b"geometry")
        self.anim.setDuration(350)
        self.anim.setStartValue(self.geometry())
        target_y = self.base_y - target_h
        self.anim.setEndValue(QRect(self.base_x, target_y, target_w, target_h))
        self.anim.setEasingCurve(QEasingCurve.Type.OutBack)
        self.anim.start()

    def update_media(self, data):
        title = data.get("title", "")
        artist = data.get("artist", "")
        img_data = data.get("thumbnail", b"")
        playing = data.get("playing", False)
        
        # Auto-hide when Spotify / Media is closed or inactive
        if not title:
            self.current_title = ""
            self.current_artist = ""
            if self.isVisible():
                self.hide()
            return
            
        # Auto-show when Spotify / Media starts
        if not self.isVisible():
            self.show()
            self.enforce_topmost()
            
        self.current_title = title
        self.current_artist = artist
        self.spectrum.set_playing(playing)
        
        self.title_label.setText(title if len(title) <= 24 else title[:21] + "...")
        self.artist_label.setText(artist if artist else "Unknown Artist")
            
        if img_data:
            img = QImage()
            img.loadFromData(img_data)
            if not img.isNull():
                self.art_label.setPixmap(QPixmap.fromImage(img))
                self.mini_art.setPixmap(self.get_circular_pixmap(img_data, 24))
            else:
                self.art_label.setPixmap(self.create_placeholder_disc(72))
                self.mini_art.setPixmap(self.create_placeholder_disc(24))
        else:
            self.art_label.setPixmap(self.create_placeholder_disc(72))
            self.mini_art.setPixmap(self.create_placeholder_disc(24))
            
        self._refresh_collapsed_text()

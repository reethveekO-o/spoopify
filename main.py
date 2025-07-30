import sys
import requests
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from PyQt5.QtWidgets import QApplication, QLabel, QWidget, QVBoxLayout, QPushButton, QHBoxLayout, QFrame
from PyQt5.QtGui import QPixmap, QRegion, QPainterPath, QIcon, QPainter
from PyQt5.QtCore import Qt, QTimer, QRectF, QSize
import traceback
import webbrowser
from PyQt5.QtWidgets import QGraphicsDropShadowEffect
from PyQt5.QtCore import QPropertyAnimation, QEasingCurve, QEvent
import ctypes
from PyQt5.QtGui import QMovie
import sys
import os
from PyQt5.QtWidgets import QSpacerItem, QSizePolicy
import psutil
from PyQt5.QtCore import QTimer, QTime
from PyQt5.QtGui import QFontDatabase
from PyQt5.QtWidgets import QColorDialog
from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPainter, QColor, QFont
from PyQt5.QtCore import Qt
import json
from PyQt5.QtGui import QColor

def _hex(qc: QColor) -> str:
    return "#{:02x}{:02x}{:02x}".format(qc.red(), qc.green(), qc.blue())

def derive_palette(base_hex: str) -> dict:
    """Builds colors derived from the base color."""
    base = QColor(base_hex)
    # Lighter/darker factors: 100 = same, 115 = +15%, 130 = +30%, etc.
    hover = base.lighter(115)   # 15% lighter for hover
    pressed = base.darker(130)  # 30% darker for pressed
    border = base.darker(140)   # border a bit darker
    # Pick text color based on luminance for contrast
    luma = 0.2126*base.redF() + 0.7152*base.greenF() + 0.0722*base.blueF()
    text = QColor(0, 0, 0) if luma > 0.6 else QColor(255, 255, 255)

    return {
        "base": _hex(base),
        "hover": _hex(hover),
        "pressed": _hex(pressed),
        "border": _hex(border),
        "text": _hex(text),
    }


def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

SETTINGS_FILE = resource_path("assets/spotify_widget_settings.json")

from dotenv import load_dotenv
load_dotenv()

CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SPOTIPY_REDIRECT_URI")

SCOPE = 'user-read-currently-playing user-read-playback-state user-modify-playback-state'

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=CLIENT_ID, client_secret=CLIENT_SECRET, redirect_uri=REDIRECT_URI, scope=SCOPE))

class BatteryIndicator(QWidget):
    def __init__ (self, parent=None):
        super().__init__(parent)
        self.percentage = 100
        self.setFixedSize(30, 14)  # Smaller size
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background: transparent;")

    def set_percentage(self, percent):
        self.percentage = max(0, min(100, percent))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        frame_color = QColor("#000000")  # outer frame
        fill_color = QColor("#000000")   # inner fill

        # Outer frame (no fill)
        painter.setPen(frame_color)
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(0, 0, 24, 12, 3, 3)

        # Battery terminal
        painter.setBrush(frame_color)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(24, 4, 4, 4, 1, 1)

        # Fill bar with gap
        gap = 2  # space between outer frame and inner fill
        max_fill_width = 24 - (2 * gap) - 2  # reduce width to respect padding
        fill_width = int(max_fill_width * (self.percentage / 100))

        if fill_width > 0:
            painter.setBrush(fill_color)
            painter.drawRoundedRect(gap + 1, gap + 1, fill_width, 12 - 2 * gap - 1, 2, 2)

class DesktopSpotifyWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.resize(250, 420)

        # Default color
        bg_color = "#3266a8"

        # Try loading saved color
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r") as f:
                    settings = json.load(f)
                    if "bg_color" in settings:
                        bg_color = settings["bg_color"]
            except:
                pass

        # Apply loaded/default color
        self.setStyleSheet(f"background-color: {bg_color}; border-radius: 15px;")

# --- replace your top bar block in _init_ with this ---

                # Top bar (single row, fixed height)
        # --- TOP BAR (pixel-perfect vertical centering) ---

        def vcenter_box(w: QWidget, h: int = 24) -> QWidget:
            box = QWidget()
            v = QVBoxLayout(box)
            v.setContentsMargins(0, 0, 0, 0)
            v.setSpacing(0)
            v.addStretch()
            v.addWidget(w, 0, Qt.AlignCenter)
            v.addStretch()
            box.setFixedHeight(h)
            return box

        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(8, 4, 8, 0)
        top_bar.setSpacing(6)

        # ⏰ Time
        self.time_label = QLabel()
        self.time_label.setStyleSheet("""
            QLabel {
                color: black;
                font-family: 'Press Start 2P', 'Helvetica Neue', sans-serif;
                font-size: 13px;
                font-weight: 500;
                padding: 0px; margin: 0px;
            }
        """)
        self.time_label.setFixedHeight(18)  # keep text box shorter than the row
        # After creating self.time_label:
        self.time_label.setContentsMargins(0, 1, 0, 0)  # push text down by 1px

        self.update_time()
        timer = QTimer(self); timer.timeout.connect(self.update_time); timer.start(30000)

        # Battery
        self.battery_indicator = BatteryIndicator()
        self.update_battery_level()

        # Settings
        self.settings_button = QPushButton()
        self.settings_button.setIcon(QIcon(resource_path("assets/settings.png")))
        self.settings_button.setIconSize(QSize(30, 30))   # keep visual size small
        self.settings_button.setFixedSize(22, 22)
        self.settings_button.setStyleSheet("""
            QPushButton { background-color: transparent; border: none; padding: 0px; }
            QPushButton:hover { background-color: #ffffff; border-radius: 11px; }
        """)
        self.settings_button.clicked.connect(self.open_settings_dialog)

        # Quit
        # Quit (store as member so apply_theme can restyle it)
        self.quit_button = QPushButton("×")
        self.quit_button.setFixedSize(22, 22)
        self.quit_button.clicked.connect(self.close)


        # Assemble (wrap everything so they share the same vertical center)
        top_bar.addWidget(vcenter_box(self.time_label), 0)
        top_bar.addStretch(1)
        top_bar.addWidget(vcenter_box(self.settings_button), 0)
        top_bar.addWidget(vcenter_box(self.battery_indicator), 0)
        top_bar.addWidget(vcenter_box(self.quit_button), 0)

        top_bar_container = QWidget()
        top_bar_container.setLayout(top_bar)
        top_bar_container.setFixedHeight(28)
   # keeps all icons perfectly aligned

# --- replace your layout margins + first addWidget lines with this ---

        layout = QVBoxLayout()
        layout.setContentsMargins(10, 6, 10, 10)    # smaller top margin to move content up
        layout.setSpacing(6)                        # reduce vertical gaps between sections

        layout.addWidget(top_bar_container)         # add the top bar

        self.album_art = QLabel()
        self.album_art.setFixedSize(200, 200)
        self.album_art.setAlignment(Qt.AlignCenter)
        self.album_art.setStyleSheet("""
            QLabel {
                border: 4px solid #b5b5b5;
                background-color: #000000;
                border-radius: 8px;                    
            }
        """)

        self.loading_movie = QMovie(resource_path("assets/loading.gif"))
        self.loading_movie.setScaledSize(QSize(200, 200))
        self.loading_movie.frameChanged.connect(self.update_loading_frame)
        self.loading_movie.start()

        self.track_label_title = QLabel("")
        self.track_label_title.setAlignment(Qt.AlignCenter)
        self.track_label_title.setStyleSheet("color: black; font-size: 16px;")

        self.track_label_artist = QLabel("")
        self.track_label_artist.setAlignment(Qt.AlignCenter)
        self.track_label_artist.setStyleSheet("color: #1f1f1f; font-size: 14px; padding-left: 6px; padding-right: 6px;")
        self.fade_enabled = True
        # Curved rectangle container for control buttons
        control_frame = QFrame()
        control_frame.setStyleSheet("background-color: #b5b5b5; border-radius: 30px;")
        control_frame.setFixedSize(190, 60)

        control_layout = QHBoxLayout(control_frame)
        control_layout.setContentsMargins(15, 10, 15, 10)
        control_layout.setSpacing(20)

        self.prev_button = QPushButton()
        self.play_pause_button = QPushButton()
        self.next_button = QPushButton()
        self.transport_buttons = [self.prev_button, self.play_pause_button, self.next_button]

        self.prev_icon = QIcon(resource_path("assets/prev.png"))
        self.play_icon = QIcon(resource_path("assets/play.png"))
        self.pause_icon = QIcon(resource_path("assets/pause.png"))
        self.next_icon = QIcon(resource_path("assets/next.png"))

        for btn in [self.prev_button, self.play_pause_button, self.next_button]:
            btn.setFixedSize(40, 40)
            btn.setStyleSheet("""
                QPushButton { background-color: transparent; border: none; }
                QPushButton:hover { background-color: #ffffff; border-radius: 22px; }
                QPushButton:pressed { background-color: #505050; border-radius: 22px; }
            """)
            btn.setIconSize(QSize(30, 30))
            btn.setCursor(Qt.PointingHandCursor)

        self.prev_button.setIcon(self.prev_icon)
        self.play_pause_button.setIcon(self.play_icon)
        self.next_button.setIcon(self.next_icon)

        self.prev_button.clicked.connect(self.prev_track)
        self.play_pause_button.clicked.connect(self.toggle_play_pause)
        self.next_button.clicked.connect(self.next_track)

        control_layout.addWidget(self.prev_button)
        control_layout.addWidget(self.play_pause_button)
        control_layout.addWidget(self.next_button)

        album_layout = QHBoxLayout()
        album_layout.addStretch()
        album_layout.addWidget(self.album_art)
        album_layout.addStretch()
        layout.addLayout(album_layout)
        layout.addSpacing(7)
        layout.addWidget(self.track_label_title)
        layout.addSpacing(2)
        layout.addWidget(self.track_label_artist)
        layout.addSpacing(5)
        layout.addWidget(control_frame, alignment=Qt.AlignCenter)

        self.setLayout(layout)

        # Marquee state variables
        self.full_text_title = ""
        self.full_text_artist = ""
        self.scroll_index_title = 0
        self.scroll_index_artist = 0

        # Timers
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_track)
        self.timer.start(5000)

        self.scroll_timer = QTimer()
        self.scroll_timer.timeout.connect(self.scroll_texts)
        self.scroll_timer.start(200)
        self.battery_timer = QTimer()
        self.battery_timer.timeout.connect(self.update_battery_level)
        self.battery_timer.start(60000)  # update every 60 seconds

        self.apply_rounded_corners(15)
        self.apply_theme(bg_color)
        self.show()
        
        # Fade on idle setup
        self.idle_timer = QTimer()
        self.idle_timer.timeout.connect(self.fade_out)
        self.idle_timer.start(5000)

    def fade_out(self):
        if self.fade_enabled: 
            self.animate_opacity(self.windowOpacity(), 0.01, duration=1000)

    def animate_opacity(self, start, end, duration=500):
        self.animation = QPropertyAnimation(self, b"windowOpacity")
        self.animation.setDuration(duration)
        self.animation.setStartValue(start)
        self.animation.setEndValue(end)
        self.animation.setEasingCurve(QEasingCurve.InOutQuad)
        self.animation.start()
    def update_time(self):
        current_time = QTime.currentTime().toString("hh:mm")
        self.time_label.setText(current_time)

    def apply_theme(self, base_hex: str):
        p = derive_palette(base_hex)

        # Window background
        self.setStyleSheet(f"background-color: {p['base']}; border-radius: 15px;")

        # Top-bar buttons
        # Make quit a member so we can restyle it after creation (see section 3)
        if hasattr(self, "settings_button"):
            self.settings_button.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent; border: none; padding: 0px; color: {p['text']};
                }}
                QPushButton:hover {{
                    background-color: {p['hover']}; border-radius: 11px;
                }}
                QPushButton:pressed {{
                    background-color: {p['pressed']};
                }}
            """)

        if hasattr(self, "quit_button"):
            self.quit_button.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent; color: {p['text']}; font-size: 16px; border: none; padding: 0px;
                }}
                QPushButton:hover {{
                    background-color: {p['hover']}; border-radius: 11px; color: {p['text']};
                }}
                QPushButton:pressed {{
                    background-color: {p['pressed']}; color: {p['text']};
                }}
            """)

        # Transport controls
        for btn in getattr(self, "transport_buttons", []):
            btn.setStyleSheet(f"""
                QPushButton {{ background-color: transparent; border: none; color: {p['text']}; }}
                QPushButton:hover {{ background-color: {p['hover']}; border-radius: 22px; }}
                QPushButton:pressed {{ background-color: {p['pressed']}; border-radius: 22px; }}
            """)

        # Album art frame (optional: border color derived from base)
        if hasattr(self, "album_art"):
            self.album_art.setStyleSheet(f"""
                QLabel {{
                    border: 4px solid {p['border']};
                    background-color: #000000;
                    border-radius: 8px;
                }}
            """)

        # Track labels
        if hasattr(self, "track_label_title"):
            self.track_label_title.setStyleSheet(f"color: {p['text']}; font-size: 16px;")
        if hasattr(self, "track_label_artist"):
            # Slightly dimmer text for artist line
            self.track_label_artist.setStyleSheet(f"color: {p['text']}; font-size: 14px; padding-left: 6px; padding-right: 6px;")

    def update_loading_frame(self):
        current_frame = self.loading_movie.currentPixmap()
        size = current_frame.size()
        rounded_bg = QPixmap(size)
        rounded_bg.fill(Qt.transparent)

        painter = QPainter(rounded_bg)
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, size.width(), size.height()), 15, 15)
        painter.setClipPath(path)
        painter.fillPath(path, Qt.white)
        painter.drawPixmap(0, 0, current_frame)
        painter.end()

        self.album_art.setPixmap(rounded_bg)

    def enterEvent(self, event):
        self.animate_opacity(self.windowOpacity(), 1.0)
        self.idle_timer.start(10000)
        event.accept()

    def open_settings_dialog(self):
        color_dialog = QColorDialog(self)
        color_dialog.setWindowTitle("Choose Background Color")
        
        font = QFont("Press Start 2P", 8)
        color_dialog.setFont(font)

        # Explicit stylesheet for QColorDialog only
        color_dialog.setStyleSheet("""
            QWidget {
                background-color: white;
                color: black;
                font-family: 'Press Start 2P';
                font-size: 8px;
            }
            QPushButton {
                background-color: #ddd;
                border: 1px solid #999;
            }
        """)

        if color_dialog.exec_() == QColorDialog.Accepted:
            selected_color = color_dialog.selectedColor()
            if selected_color.isValid():
                self.apply_custom_color(selected_color.name())


    def apply_custom_color(self, hex_color):
        # Apply derived theme everywhere (base/hover/pressed/text/border)
        self.apply_theme(hex_color)
        # Persist
        with open(SETTINGS_FILE, "w") as f:
            json.dump({"bg_color": hex_color}, f)

    def leaveEvent(self, event):
        self.idle_timer.start(10000)
        event.accept()

    def apply_rounded_corners(self, radius):
        path = QPainterPath()
        rect = QRectF(0, 0, self.width(), self.height())
        path.addRoundedRect(rect, radius, radius)
        region = QRegion(path.toFillPolygon().toPolygon())
        self.setMask(region)

    def resizeEvent(self, event):
        self.apply_rounded_corners(15)
        super().resizeEvent(event)

    def scroll_texts(self):
        try:
            if self.full_text_title and len(self.full_text_title.strip()) > 10:
                display_title = (
                    self.full_text_title[self.scroll_index_title:] +
                    self.full_text_title[:self.scroll_index_title]
                )
                self.track_label_title.setText(display_title[:10])
                self.scroll_index_title = (self.scroll_index_title + 1) % len(self.full_text_title)
            else:
                self.track_label_title.setText(self.full_text_title.strip())
                self.track_label_title.setAlignment(Qt.AlignCenter)

            if self.full_text_artist and len(self.full_text_artist.strip()) > 10:
                display_artist = (
                    self.full_text_artist[self.scroll_index_artist:] +
                    self.full_text_artist[:self.scroll_index_artist]
                )
                self.track_label_artist.setText(display_artist[:10])
                self.scroll_index_artist = (self.scroll_index_artist + 1) % len(self.full_text_artist)
            else:
                self.track_label_artist.setText(self.full_text_artist.strip())
                self.track_label_artist.setAlignment(Qt.AlignCenter)
        except Exception as e:
            print(f"[ERROR] Scroll text failed: {e}")

    def update_track(self):
        try:
            current = sp.current_playback()
            if current and current['item']:
                track = current['item']['name'] + "     "
                artist = current['item']['artists'][0]['name'] + "     "
                img_url = current['item']['album']['images'][0]['url']

                self.full_text_title = track
                self.full_text_artist = artist
                self.scroll_index_title = 0
                self.scroll_index_artist = 0

                img_data = requests.get(img_url).content
                image = QPixmap()
                image.loadFromData(img_data)
                image = image.scaled(200, 200, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)

                rounded = QPixmap(image.size())
                rounded.fill(Qt.transparent)
                painter = QPainter(rounded)
                painter.setRenderHint(QPainter.Antialiasing)
                path = QPainterPath()
                path.addRoundedRect(QRectF(0, 0, image.width(), image.height()), 15, 15)
                painter.setClipPath(path)
                painter.drawPixmap(0, 0, image)
                painter.end()
                self.loading_movie.stop()
                try:
                    self.loading_movie.frameChanged.disconnect(self.update_loading_frame)
                except TypeError as e:
                    if "not connected" not in str(e):
                        raise
                self.album_art.setPixmap(rounded)

                if current['is_playing']:
                    self.play_pause_button.setIcon(self.pause_icon)
                else:
                    self.play_pause_button.setIcon(self.play_icon)
            else:
                self.track_label_title.setText("No song playing")
                self.track_label_artist.setText("")
                self.loading_movie.start()
        except Exception as e:
            print(f"Error updating track: {e}")
            traceback.print_exc()
    def update_battery_level(self):
        battery = psutil.sensors_battery()
        if battery:
            self.battery_indicator.set_percentage(battery.percent)

    def toggle_play_pause(self):
        try:
            current = sp.current_playback()
            if current and current['is_playing']:
                sp.pause_playback()
            else:
                sp.start_playback()
            self.update_track()
        except Exception as e:
            print(f"Error toggling play/pause: {e}")

    def next_track(self):
        try:
            sp.next_track()
            self.update_track()
        except Exception as e:
            print(f"Error skipping to next track: {e}")

    def prev_track(self):
        try:
            sp.previous_track()
            self.update_track()
        except Exception as e:
            print(f"Error going to previous track: {e}")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
        elif event.button() == Qt.RightButton and (event.modifiers() & Qt.ControlModifier):
            # Toggle fade behavior
            self.fade_enabled = not self.fade_enabled
            if self.fade_enabled:
                self.setWindowOpacity(1.0)
                self.idle_timer.start(5000)
            else:
                self.idle_timer.stop()
                self.setWindowOpacity(1.0)
            event.accept()

    def mouseReleaseEvent(self, event):
        self.drag_position = None
        event.accept()
             
    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and getattr(self, 'drag_position', None) is not None:
            self.move(event.globalPos() - self.drag_position)
            event.accept()


'''if _name_ == "_main_":
    app = QApplication(sys.argv)
    w = DesktopSpotifyWidget()
    app.setWindowIcon(QIcon("logo.png"))
    sys.exit(app.exec_())'''

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Load custom font inside main
    font_id = QFontDatabase.addApplicationFont(resource_path("assets/PressStart2P.ttf"))
    if font_id != -1:
        custom_font_family = QFontDatabase.applicationFontFamilies(font_id)[0]
        app.setFont(QFont(custom_font_family, 8))  # Set global font

    w = DesktopSpotifyWidget()
    app.setWindowIcon(QIcon("logo.png"))
    sys.exit(app.exec_())
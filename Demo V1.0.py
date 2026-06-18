import sys
import time
from PySide6.QtCore import QTimer, Qt, QSettings
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
    QMainWindow,
    QMessageBox,
)
from pynput import keyboard

FLASH_CD = 300
FLASH_CD_CI = 254

LANES = [
    "TOP",
    "JG",
    "MID",
    "ADC",
    "SUP",
]

COLOR_READY = "#1f6f3d"
COLOR_RED = "#7a1f1f"
COLOR_YELLOW = "#8a6a00"
COLOR_CI = "#4FC3F7"
COLOR_DISABLED = "#404040"

class OverlayWindow(QWidget):
    def __init__(self, tracker):
        super().__init__()

        self.tracker = tracker

        self.setWindowTitle("Overlay")
        self.setFixedSize(240, 180)

        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.WindowTransparentForInput  # Allow mouse clicks to pass through
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background: transparent;")

        container = QWidget(self)
        container.setObjectName("overlayContainer")
        container.setStyleSheet(
            "#overlayContainer {"
            " background-color: rgba(43, 43, 43, 220);"
            " border-radius: 12px;"
            "}"
        )
        container.setGeometry(0, 0, 240, 180)

        screen = QApplication.primaryScreen()
        if screen:
            available = screen.availableGeometry()
            self.move(
                available.x() + available.width() - self.width() - 10,
                available.y() + 10,
            )

        # 增加不透明度以提升字体可见度
        self.setWindowOpacity(0.55)

        layout = QVBoxLayout(container)
        layout.setSpacing(1)
        layout.setContentsMargins(4, 4, 4, 4)

        self.game_label = QLabel("GAME 00:00")
        self.game_label.setAlignment(Qt.AlignCenter)
        self.game_label.setStyleSheet(
            "font-size:14px;font-weight:bold;color:#ffffff;"
        )
        layout.addWidget(self.game_label)

        self.row_labels = {}

        for lane in LANES:
            row = QLabel()
            row.setMinimumHeight(22)
            # 使用纯白色以提高亮度
            row.setStyleSheet(
                "font-size:12px;font-weight:bold;color:#ffffff;"
            )
            layout.addWidget(row)
            self.row_labels[lane] = row

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_overlay)
        self.timer.start(1000)

    def update_overlay(self):
        if self.tracker.game_start is None:
            self.game_label.setText("GAME 00:00")

            for lane in LANES:
                self.row_labels[lane].setText(
                    f"{lane:<4}  READY"
                )
                # 使用更亮的绿色提示 READY
                self.row_labels[lane].setStyleSheet(
                    "font-size:12px;font-weight:bold;color:#e6ffe6;"
                )
            return

        elapsed = int(time.time() - self.tracker.game_start)

        game_min = elapsed // 60
        game_sec = elapsed % 60

        self.game_label.setText(
            f"GAME {game_min:02d}:{game_sec:02d}"
        )

        for lane in LANES:

            ready_at = self.tracker.flash_ready_at.get(lane)

            if ready_at is None:
                self.row_labels[lane].setText(
                    f"{lane:<4}  READY"
                )
                self.row_labels[lane].setStyleSheet(
                    "font-size:12px;font-weight:bold;color:#e6ffe6;"
                )
                continue

            remain = ready_at - elapsed

            if remain <= 0:
                self.row_labels[lane].setText(
                    f"{lane:<4}  READY"
                )
                self.row_labels[lane].setStyleSheet(
                    "font-size:12px;font-weight:bold;color:#9ec69e;"
                )
                continue

            ready_min = ready_at // 60
            ready_sec = ready_at % 60

            remain_min = remain // 60
            remain_sec = remain % 60

            # 更亮的警示色
            if remain <= 30:
                color = "#ffea6a"  # brighter yellow
            else:
                color = "#ff7b7b"  # brighter red

            self.row_labels[lane].setText(
                f"{lane:<4}  @{ready_min:02d}:{ready_sec:02d}   {remain_min:02d}:{remain_sec:02d}"
            )

            self.row_labels[lane].setStyleSheet(
                f"font-size:12px;font-weight:bold;color:{color};"
            )


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.settings = QSettings("lol_flash_tracker", "main")

        self.setWindowTitle(
            "LOL Flash Tracker | Ctrl+1 TOP Ctrl+2 JG Ctrl+3 MID Ctrl+4 ADC Ctrl+5 SUP"
        )
        
        # Set window size
        self.setFixedSize(500, 500)

        self.game_start = None
        self.flash_ready_at = {}
        self.flash_buttons = {}
        self.cosmic_checkboxes = {}
        self.ctrl_pressed = False
        self.cmd_pressed = False

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(2, 2, 2, 2)

        # GAME 00:00 label
        self.game_time_label = QLabel("GAME 00:00")
        self.game_time_label.setAlignment(Qt.AlignCenter)
        self.game_time_label.setMinimumHeight(22)
        self.game_time_label.setStyleSheet(
            "font-weight: bold; padding: 1px;"
        )
        main_layout.addWidget(self.game_time_label)

        # START GAME and RESET GAME buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(1)
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        self.start_game_button = QPushButton("START GAME")
        self.start_game_button.setMinimumHeight(18)
        self.start_game_button.setStyleSheet("font-weight: bold;")
        self.start_game_button.clicked.connect(self.start_game)
        buttons_layout.addWidget(self.start_game_button)

        self.reset_game_button = QPushButton("RESET GAME")
        self.reset_game_button.setMinimumHeight(18)
        self.reset_game_button.setStyleSheet("font-weight: bold;")
        self.reset_game_button.clicked.connect(self.reset_game)
        buttons_layout.addWidget(self.reset_game_button)

        main_layout.addLayout(buttons_layout)

        # Lanes
        for lane in LANES:
            row_layout = QHBoxLayout()

            flash_btn = QPushButton()
            flash_btn.setMinimumHeight(34)
            flash_btn.setMinimumWidth(100)
            flash_btn.clicked.connect(lambda checked, l=lane: self.flash_used(l))
            self.flash_buttons[lane] = flash_btn

            ci_btn = QPushButton("NO CI")
            ci_btn.setCheckable(True)
            ci_btn.setMinimumHeight(34)
            ci_btn.setMinimumWidth(100)
            ci_btn.clicked.connect(lambda checked, l=lane: self.update_flash_buttons())
            self.cosmic_checkboxes[lane] = ci_btn

            row_layout.addWidget(flash_btn)
            row_layout.addWidget(ci_btn)
            row_layout.setSpacing(1)
            row_layout.setContentsMargins(0, 0, 0, 0)

            main_layout.addLayout(row_layout)

        self.update_flash_buttons()
        self.update_ui_scaling()

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_clock)
        self.timer.start(1000)

        # Restore geometry
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        self.setFixedSize(500, 500)

        # Restore always on top
        always_on_top = self.settings.value("always_on_top", False, type=bool)
        if always_on_top:
            self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
            self.show()

        # Initialize global hotkeys
        self._init_hotkeys()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_ui_scaling()

    def update_ui_scaling(self):
        height = self.height()
        title_size = max(12, int(height * 0.025))
        button_size = max(9, int(height * 0.018))
        lane_size = max(9, int(height * 0.018))
        ci_size = max(8, int(height * 0.017))

        title_font = QFont(self.game_time_label.font())
        title_font.setPointSize(title_size)
        title_font.setBold(True)
        self.game_time_label.setFont(title_font)

        button_font = QFont(self.start_game_button.font())
        button_font.setPointSize(button_size)
        button_font.setBold(True)
        self.start_game_button.setFont(button_font)
        self.reset_game_button.setFont(button_font)

        lane_font = QFont(self.game_time_label.font())
        lane_font.setPointSize(lane_size)
        lane_font.setBold(True)
        for lane, btn in self.flash_buttons.items():
            btn.setFont(lane_font)

        ci_font = QFont(self.game_time_label.font())
        ci_font.setPointSize(ci_size)
        ci_font.setBold(True)
        for ci_btn in self.cosmic_checkboxes.values():
            ci_btn.setFont(ci_font)

    def toggle_always_on_top(self):
        current_flag = self.windowFlags() & Qt.WindowStaysOnTopHint
        self.setWindowFlag(Qt.WindowStaysOnTopHint, not bool(current_flag))
        self.show()
        self.settings.setValue("always_on_top", not bool(current_flag))

    def _init_hotkeys(self):
        """Initialize global hotkeys for flash tracking"""
        # Use pynput Listener for global hotkey monitoring
        self.ctrl_pressed = False
        self.cmd_pressed = False
        self.hotkey_enabled = False
        
        def on_press(key):
            try:
                # Check for Ctrl or Cmd key press
                if key == keyboard.Key.ctrl:
                    self.ctrl_pressed = True
                elif key == keyboard.Key.cmd:
                    self.cmd_pressed = True
                
                # Check for number keys 1-5 when Ctrl/Cmd is pressed
                if (self.ctrl_pressed or self.cmd_pressed) and hasattr(key, 'char') and key.char:
                    key_map = {
                        '1': 'TOP',
                        '2': 'JG',
                        '3': 'MID',
                        '4': 'ADC',
                        '5': 'SUP',
                    }
                    if key.char in key_map:
                        self.flash_used(key_map[key.char])
            except (AttributeError, TypeError):
                pass
        
        def on_release(key):
            try:
                if key == keyboard.Key.ctrl:
                    self.ctrl_pressed = False
                elif key == keyboard.Key.cmd:
                    self.cmd_pressed = False
            except (AttributeError, TypeError):
                pass
        
        try:
            self.hotkey_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
            self.hotkey_listener.start()
            self.hotkey_enabled = True
            print("✓ Global hotkeys initialized successfully")
        except Exception as e:
            print(f"✗ Could not initialize global hotkeys: {e}")
            self.hotkey_enabled = False
            # Schedule a dialog to show after the window is shown
            QTimer.singleShot(500, self._show_hotkey_permission_dialog)

    def keyPressEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            key_lane_map = {
                Qt.Key_1: "TOP",
                Qt.Key_2: "JG",
                Qt.Key_3: "MID",
                Qt.Key_4: "ADC",
                Qt.Key_5: "SUP",
            }
            lane = key_lane_map.get(event.key())
            if lane:
                self.flash_used(lane)

    def flash_used(self, lane):
        if self.game_start is None:
            return

        if lane in self.flash_ready_at:
            self.flash_ready_at.pop(lane, None)
            self.update_flash_buttons()
            return

        cooldown = (
            FLASH_CD_CI
            if self.cosmic_checkboxes[lane].isChecked()
            else FLASH_CD
        )
        current_game_time = int(time.time() - self.game_start)
        self.flash_ready_at[lane] = current_game_time + cooldown
        self.update_flash_buttons()

    def start_game(self):
        if self.game_start is not None:
            return
        self.game_start = time.time()
        self.flash_ready_at.clear()
        for ci_btn in self.cosmic_checkboxes.values():
            ci_btn.setChecked(False)
            ci_btn.setText("NO CI")
            ci_btn.setStyleSheet(
                f"background-color:{COLOR_DISABLED}; color:white;"
            )
        self.update_flash_buttons()
        self.update_clock()
        self.start_game_button.setEnabled(False)

    def reset_game(self):
        self.game_start = None
        self.flash_ready_at.clear()
        for ci_btn in self.cosmic_checkboxes.values():
            ci_btn.setChecked(False)
            ci_btn.setText("NO CI")
            ci_btn.setStyleSheet(
                f"background-color:{COLOR_DISABLED}; color:white;"
            )
        self.game_time_label.setText("GAME 00:00")
        self.update_flash_buttons()
        self.start_game_button.setEnabled(True)

    def _show_hotkey_permission_dialog(self):
        """Show a dialog informing the user about accessibility permissions"""
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Global Hotkeys Not Working")
        dialog.setText(
            "⚠️ Global hotkeys (Ctrl+1~5) are not working.\n\n"
            "This is because Python needs Accessibility permissions on macOS.\n\n"
            "To fix this:\n"
            "1. Go to System Settings > Privacy & Security > Accessibility\n"
            "2. Click the + button\n"
            "3. Find and add this Python application\n"
            "4. Restart the application\n\n"
            "You can still use the GUI buttons to track Flash cooldowns."
        )
        dialog.setIcon(QMessageBox.Warning)
        dialog.setStandardButtons(QMessageBox.Ok)
        dialog.exec()

    def closeEvent(self, event):
        self.settings.setValue("geometry", self.saveGeometry())
        try:
            if hasattr(self, 'hotkey_listener'):
                self.hotkey_listener.stop()
        except Exception:
            pass
        super().closeEvent(event)

    def update_clock(self):
        if self.game_start is None:
            self.game_time_label.setText("GAME 00:00")
            self.update_flash_buttons()
            return

        elapsed = int(time.time() - self.game_start)
        minutes = elapsed // 60
        seconds = elapsed % 60
        self.game_time_label.setText(f"GAME {minutes:02d}:{seconds:02d}")

        self.update_flash_buttons()

    def update_flash_buttons(self):
        if self.game_start is None:
            for lane, btn in self.flash_buttons.items():
                btn.setStyleSheet(
                    f"background-color: {COLOR_READY}; color: white;"
                )
                btn.setText(f"{lane}\nREADY")
            for lane, ci_btn in self.cosmic_checkboxes.items():
                if ci_btn.isChecked():
                    ci_btn.setText("CI")
                    ci_btn.setStyleSheet(
                        f"background-color: {COLOR_CI}; color: black;"
                    )
                else:
                    ci_btn.setText("NO CI")
                    ci_btn.setStyleSheet(
                        f"background-color:{COLOR_DISABLED}; color:white;"
                    )
            return

        current_game_time = int(time.time() - self.game_start)

        for lane, btn in self.flash_buttons.items():
            ready_at = self.flash_ready_at.get(lane)

            if ready_at is None:
                btn.setStyleSheet(
                    f"background-color: {COLOR_READY}; color: white;"
                )
                btn.setText(f"{lane}\nREADY")
            else:
                remain = ready_at - current_game_time
                if remain <= 0:
                    btn.setStyleSheet(
                        f"background-color: {COLOR_READY}; color: white;"
                    )
                    btn.setText(f"{lane}\nREADY")
                    self.flash_ready_at.pop(lane, None)
                else:
                    if remain <= 30:
                        bg_color = COLOR_YELLOW  # yellow
                    else:
                        bg_color = COLOR_RED  # red

                    btn.setStyleSheet(
                        f"background-color: {bg_color}; color: white;"
                    )

                    ready_min = ready_at // 60
                    ready_sec = ready_at % 60
                    if ready_min > 99:
                        ready_min = 99
                    remain_min = remain // 60
                    remain_sec = remain % 60

                    ci_text = " CI" if self.cosmic_checkboxes[lane].isChecked() else ""
                    btn.setText(
                        f"{lane}{ci_text}\nREADY @ {ready_min:02d}:{ready_sec:02d}\n{remain_min:02d}:{remain_sec:02d}"
                    )

            ci_btn = self.cosmic_checkboxes[lane]
            if ci_btn.isChecked():
                ci_btn.setText("CI")
                ci_btn.setStyleSheet(
                    f"background-color: {COLOR_CI}; color: black;"
                )
            else:
                ci_btn.setText("NO CI")
                ci_btn.setStyleSheet(
                    f"background-color:{COLOR_DISABLED}; color:white;"
                )


app = QApplication(sys.argv)

window = MainWindow()

overlay = OverlayWindow(window)

window.show()
overlay.show()
overlay.raise_()
overlay.activateWindow()
app.exec()
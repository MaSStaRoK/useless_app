"""Electrician puzzle worker and always-on-top controller window."""

from __future__ import annotations

import threading
import time

import cv2
import mss
import numpy as np
import pyautogui

from PyQt6.QtCore import QPoint, QSettings, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QCloseEvent, QMouseEvent, QShowEvent
from PyQt6.QtWidgets import QDialog, QLabel, QVBoxLayout


REFERENCE_WIDTH = 2048
REFERENCE_HEIGHT = 1151
LEFT_X = 640
RIGHT_X = 1375
TOP_Y = 115
BOTTOM_Y = 950
DETECTION_SETTLE_SECONDS = 0.5
DRAG_DURATION = 0.05
CONNECT_DELAY = 0.03
SEARCH_TIMEOUT_SECONDS = 5
SEARCH_INTERVAL_SECONDS = 0.4
MIN_WIRE_HEIGHT = 8
MIN_SATURATION = 85
MIN_BRIGHTNESS = 140

COLOR_NAMES = {
    "red": "Красный",
    "orange": "Оранжевый",
    "yellow": "Жёлтый",
    "green": "Зелёный",
    "cyan": "Голубой",
    "blue": "Синий",
    "purple": "Фиолетовый",
}


def classify_color(hue: int) -> str | None:
    if hue < 6 or hue >= 175:
        return "red"
    if hue < 16:
        return "orange"
    if hue < 36:
        return "yellow"
    if hue < 86:
        return "green"
    if hue < 96:
        return "cyan"
    if hue < 125:
        return "blue"
    if hue < 165:
        return "purple"
    return None


def find_wires(image, x: int, top: int, bottom: int, cv2, np) -> list[dict[str, int | str]]:
    height, width = image.shape[:2]
    x = max(5, min(x, width - 6))
    top = max(0, top)
    bottom = min(bottom, height)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    strip = hsv[top:bottom, x - 4:x + 5]
    saturation = strip[:, :, 1]
    brightness = strip[:, :, 2]
    colored = (saturation >= MIN_SATURATION) & (brightness >= MIN_BRIGHTNESS)
    valid_rows = np.count_nonzero(colored, axis=1) >= 4

    segments: list[tuple[int, int]] = []
    start = None
    for index, active in enumerate(valid_rows):
        if active and start is None:
            start = index
        elif not active and start is not None:
            if index - start >= MIN_WIRE_HEIGHT:
                segments.append((start, index))
            start = None
    if start is not None and len(valid_rows) - start >= MIN_WIRE_HEIGHT:
        segments.append((start, len(valid_rows)))

    results: list[dict[str, int | str]] = []
    for segment_start, segment_end in segments:
        region = strip[segment_start:segment_end]
        region_mask = colored[segment_start:segment_end]
        hues = region[:, :, 0][region_mask]
        names = [name for hue in hues if (name := classify_color(int(hue)))]
        if names:
            color = max(set(names), key=names.count)
            results.append({"color": color, "x": x, "y": top + (segment_start + segment_end) // 2})
    return results


def match_wires(left_wires: list[dict], right_wires: list[dict]) -> list[tuple[dict, dict]]:
    matches = []
    used: set[int] = set()
    for left in left_wires:
        for index, right in enumerate(right_wires):
            if index not in used and left["color"] == right["color"]:
                matches.append((left, right))
                used.add(index)
                break
    return matches


class ElectricianWorker(QThread):
    """Run one detection-and-solve cycle outside the Qt UI thread."""

    status_changed = pyqtSignal(str)
    solved = pyqtSignal()

    def __init__(self, stop_event: threading.Event) -> None:
        super().__init__()
        self.stop_event = stop_event

    def _checkpoint(self) -> bool:
        return not self.stop_event.is_set()

    def _drag_wire(self, pyautogui, start_x: int, start_y: int, end_x: int, end_y: int) -> bool:
        mouse_held = False
        try:
            pyautogui.moveTo(start_x, start_y, duration=0.03)
            if not self._checkpoint():
                return False
            pyautogui.mouseDown(button="left")
            mouse_held = True
            steps = max(6, int(DRAG_DURATION / 0.01))
            step_delay = DRAG_DURATION / steps
            for step in range(1, steps + 1):
                if not self._checkpoint():
                    return False
                progress = step / steps
                x = start_x + (end_x - start_x) * progress
                y = start_y + (end_y - start_y) * progress
                pyautogui.moveTo(x, y, duration=0)
                if self.stop_event.wait(step_delay):
                    return False
            pyautogui.mouseUp(button="left")
            mouse_held = False
            return True
        finally:
            if mouse_held:
                pyautogui.mouseUp(button="left")

    def run(self) -> None:
        try:
            pyautogui.FAILSAFE = True
            pyautogui.PAUSE = 0.001
            self.status_changed.emit("Ищем мини-игру «Электрик»…")
            deadline = time.monotonic() + SEARCH_TIMEOUT_SECONDS
            last_countdown = -1
            with mss.MSS() as screen_capture:
                monitor = screen_capture.monitors[1]
                while not self.stop_event.is_set():
                    remaining = max(0, int(deadline - time.monotonic()))
                    if remaining != last_countdown:
                        last_countdown = remaining
                        self.status_changed.emit(f"Ищем мини-игру… осталось 00:{remaining:02d}.")
                    if remaining <= 0:
                        self.status_changed.emit(
                            "За 5 секунд мини-игра не найдена. Нажмите E, чтобы попробовать снова."
                        )
                        return

                    screenshot = np.array(screen_capture.grab(monitor))
                    image = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2BGR)
                    height, width = image.shape[:2]
                    left_x = round(LEFT_X * width / REFERENCE_WIDTH)
                    right_x = round(RIGHT_X * width / REFERENCE_WIDTH)
                    top_y = round(TOP_Y * height / REFERENCE_HEIGHT)
                    bottom_y = round(BOTTOM_Y * height / REFERENCE_HEIGHT)
                    left_wires = find_wires(image, left_x, top_y, bottom_y, cv2, np)
                    right_wires = find_wires(image, right_x, top_y, bottom_y, cv2, np)
                    matches = match_wires(left_wires, right_wires)

                    # The game board has several colored terminals at both scan lines.
                    # This is more robust than matching a tiny texture crop that varies by resolution.
                    if len(left_wires) >= 3 and len(right_wires) >= 3 and len(matches) >= 3:
                        break
                    self.stop_event.wait(SEARCH_INTERVAL_SECONDS)

            if not self._checkpoint():
                self.status_changed.emit("Поиск остановлен: окно «Электрик» закрыто.")
                return
            if not (len(left_wires) >= 3 and len(right_wires) >= 3 and len(matches) >= 3):
                return

            self.status_changed.emit("Распознали мини-игру. Соединяем провода…")
            if self.stop_event.wait(DETECTION_SETTLE_SECONDS) or not self._checkpoint():
                self.status_changed.emit("Остановлено.")
                return

            if not matches:
                self.status_changed.emit("Не удалось найти совпадающие провода.")
                return
            if len(matches) != len(left_wires):
                self.status_changed.emit("Найдены провода без пары. Соединение отменено.")
                return

            offset_x = monitor["left"]
            offset_y = monitor["top"]
            for number, (left, right) in enumerate(matches, start=1):
                if not self._checkpoint():
                    self.status_changed.emit("Остановлено.")
                    return
                self.status_changed.emit(
                    f"Соединяем провод {number}/{len(matches)}: {COLOR_NAMES[str(left['color'])]}"
                )
                connected = self._drag_wire(
                    pyautogui,
                    int(left["x"]) + offset_x,
                    int(left["y"]) + offset_y,
                    int(right["x"]) + offset_x,
                    int(right["y"]) + offset_y,
                )
                if not connected:
                    self.status_changed.emit("Остановлено.")
                    return
                if self.stop_event.wait(CONNECT_DELAY) or not self._checkpoint():
                    self.status_changed.emit("Остановлено.")
                    return

            self.solved.emit()
            self.status_changed.emit("Все провода соединены.")
        except pyautogui.FailSafeException as error:
            self.status_changed.emit("Аварийная остановка: курсор перемещён в угол экрана.")
            return
        except pyautogui.PyAutoGUIException as error:
            self.status_changed.emit(
                f"Не удалось захватить экран для распознавания: {error}. "
                "Проверьте установку Pillow и pyscreeze."
            )
        except Exception as error:
            self.status_changed.emit(f"Ошибка «Электрика»: {error}")


class ElectricianOverlay(QDialog):
    """Always-on-top status window listening for the global E key."""

    closed = pyqtSignal()
    hotkey_pressed = pyqtSignal()

    def __init__(self, parent=None) -> None:
        flags = (
            Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint
        )
        super().__init__(parent, flags)
        self.stop_event = threading.Event()
        self.worker: ElectricianWorker | None = None
        self.keyboard_module = None
        self.hotkey_hook = None
        self.last_hotkey_time = 0.0
        self.solved_count = 0
        self._drag_offset: QPoint | None = None
        self._settings = QSettings("GTA5RP Helper", "GTA5RP Helper")
        self.setFixedWidth(320)

        self.counter_label = QLabel("Решено: 0")
        self.counter_label.setStyleSheet("font-size: 19px; font-weight: 700;")
        self.status_label = QLabel("Окно активно. Нажмите E, чтобы начать поиск.")
        self.status_label.setWordWrap(True)

        layout = QVBoxLayout()
        layout.addWidget(self.counter_label)
        layout.addWidget(self.status_label)
        self.setLayout(layout)
        self.setStyleSheet(
            "QDialog { background: #171a21; } QWidget { color: #edf0f7; font-size: 13px; }"
        )
        self.move(
            self._settings.value("electrician/window_x", 0, type=int),
            self._settings.value("electrician/window_y", 0, type=int),
        )

        self.hotkey_pressed.connect(self._on_hotkey_pressed)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if (
            event.button() == Qt.MouseButton.LeftButton
            and event.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if (
            self._drag_offset is not None
            and event.buttons() & Qt.MouseButton.LeftButton
            and event.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._drag_offset is not None:
            self._drag_offset = None
            self._save_position()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _save_position(self) -> None:
        position = self.pos()
        self._settings.setValue("electrician/window_x", position.x())
        self._settings.setValue("electrician/window_y", position.y())

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        if self.hotkey_hook is not None:
            return
        try:
            import keyboard

            self.keyboard_module = keyboard
            self.hotkey_hook = keyboard.on_press_key("e", self._emit_hotkey_pressed, suppress=False)
            self.status_label.setText("Окно активно. Нажмите E, чтобы начать поиск (до 5 секунд).")
        except Exception as error:
            self.status_label.setText(f"Не удалось включить прослушивание клавиши E: {error}")

    def _emit_hotkey_pressed(self, _event) -> None:
        self.hotkey_pressed.emit()

    def _on_hotkey_pressed(self) -> None:
        if not self.isVisible():
            return
        now = time.monotonic()
        if now - self.last_hotkey_time < 0.35:
            return
        self.last_hotkey_time = now
        if self.worker is not None and self.worker.isRunning():
            return
        self.start_solver()

    def start_solver(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            return
        self.stop_event.clear()
        worker = ElectricianWorker(self.stop_event)
        self.worker = worker
        worker.status_changed.connect(self.status_label.setText)
        worker.solved.connect(self._on_solved)
        worker.finished.connect(lambda worker=worker: self._on_finished(worker))
        self.status_label.setText("Запускаем поиск…")
        worker.start()

    def _on_solved(self) -> None:
        self.solved_count += 1
        self.counter_label.setText(f"Решено: {self.solved_count}")

    def _on_finished(self, worker: ElectricianWorker) -> None:
        if self.worker is worker:
            self.worker = None

    def _stop_and_unhook(self) -> None:
        self.stop_event.set()
        if self.keyboard_module is not None and self.hotkey_hook is not None:
            try:
                self.keyboard_module.unhook(self.hotkey_hook)
            except Exception:
                pass
        self.hotkey_hook = None
        self.keyboard_module = None
        if self.worker is not None and self.worker.isRunning():
            self.worker.wait()
        self.worker = None

    def closeEvent(self, event: QCloseEvent) -> None:
        self._save_position()
        self._stop_and_unhook()
        super().closeEvent(event)
        QTimer.singleShot(0, self.closed.emit)


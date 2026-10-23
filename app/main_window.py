"""Main application window with the available helper programs."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QCloseEvent, QPainter
from PyQt6.QtWidgets import QCheckBox, QGroupBox, QHBoxLayout, QLabel, QMainWindow, QVBoxLayout, QWidget

from app.electrician import ElectricianOverlay


class ToggleSwitch(QCheckBox):
    """Compact slider-style checkbox for enabling a tool overlay."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setText("")
        self.setFixedSize(48, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def hitButton(self, position) -> bool:
        """Make the full painted switch track clickable, not just Qt's tiny checkbox icon."""
        return self.rect().contains(position)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        track_color = QColor("#5865f2" if self.isChecked() else "#444b58")
        if not self.isEnabled():
            track_color.setAlpha(110)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track_color)
        painter.drawRoundedRect(1, 3, self.width() - 2, self.height() - 6, 11, 11)
        knob_size = self.height() - 12
        knob_x = self.width() - knob_size - 6 if self.isChecked() else 6
        painter.setBrush(QColor("#ffffff"))
        painter.drawEllipse(knob_x, 6, knob_size, knob_size)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("GTA5RP Helper")
        self.resize(760, 500)

        self.electrician_overlay = ElectricianOverlay(self)

        welcome = QLabel("Вспомогательные программы")
        welcome.setStyleSheet("font-size: 23px; font-weight: 700;")

        electrician_title = QLabel("Электрик")
        electrician_title.setStyleSheet("font-size: 17px; font-weight: 600;")
        electrician_description = QLabel(
            "Распознаёт цветные провода и помогает соединить их в мини-игре. "
            "Окно управления останется поверх остальных окон."
        )
        electrician_description.setWordWrap(True)
        self.electrician_toggle = ToggleSwitch()
        self.electrician_toggle.setAccessibleName("Показывать окно управления Электрик")
        self.electrician_toggle.stateChanged.connect(self._toggle_electrician)
        self.electrician_overlay.closed.connect(self._on_electrician_closed)

        toggle_row = QHBoxLayout()
        toggle_row.addWidget(QLabel("Показывать окно управления"))
        toggle_row.addStretch()
        toggle_row.addWidget(self.electrician_toggle)

        card_layout = QVBoxLayout()
        card_layout.addWidget(electrician_title)
        card_layout.addWidget(electrician_description)
        card_layout.addLayout(toggle_row)
        electrician_card = QGroupBox()
        electrician_card.setLayout(card_layout)

        layout = QVBoxLayout()
        layout.setContentsMargins(32, 28, 32, 28)
        layout.addWidget(welcome)
        layout.addSpacing(18)
        layout.addWidget(electrician_card)
        layout.addStretch()
        root = QWidget()
        root.setLayout(layout)
        self.setCentralWidget(root)
        self.setStyleSheet(
            "QMainWindow { background: #171a21; } QWidget { color: #edf0f7; font-size: 15px; }"
            "QGroupBox { background: #20242d; border: 1px solid #343a46; border-radius: 8px; margin-top: 0; }"
        )

    def _toggle_electrician(self, state: int) -> None:
        if state == Qt.CheckState.Checked.value:
            self.electrician_overlay.show()
            self.electrician_overlay.raise_()
            self.electrician_overlay.activateWindow()
        else:
            if self.electrician_overlay.isVisible():
                self.electrician_overlay.close()

    def _on_electrician_closed(self) -> None:
        if self.electrician_toggle.isChecked():
            self.electrician_toggle.setChecked(False)

    def closeEvent(self, event: QCloseEvent) -> None:
        self.electrician_overlay.close()
        super().closeEvent(event)

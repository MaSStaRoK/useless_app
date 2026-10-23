"""Launcher window that downloads the latest App release and starts it."""

from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from launcher.app_manager import AppManager


class AppUpdateWorker(QThread):
    succeeded = pyqtSignal(object, str)
    failed = pyqtSignal(str)
    progress = pyqtSignal(int, int)

    def __init__(self, manager: AppManager) -> None:
        super().__init__()
        self.manager = manager

    def run(self) -> None:
        try:
            executable, message = self.manager.ensure_latest(
                lambda downloaded, total: self.progress.emit(downloaded, total)
            )
            self.succeeded.emit(executable, message)
        except Exception as error:
            self.failed.emit(str(error))


class UpdateWindow(QMainWindow):
    def __init__(self, manager: AppManager) -> None:
        super().__init__()
        self.manager = manager
        self.worker: AppUpdateWorker | None = None
        self.setWindowTitle("GTA5RP Helper Launcher")
        self.setFixedWidth(460)

        heading = QLabel("GTA5RP Helper")
        heading.setObjectName("heading")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status = QLabel("Launcher проверит App и при необходимости скачает обновление.")
        self.status.setWordWrap(True)
        self.status.setObjectName("status")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.hide()

        self.update_button = QPushButton("Проверить и запустить App")
        self.update_button.setDefault(True)
        self.update_button.clicked.connect(self._check_and_launch)
        self.offline_button = QPushButton("Запустить установленную версию")
        self.offline_button.clicked.connect(self._launch_installed)
        self.offline_button.setEnabled(manager.installed_executable() is not None)

        layout = QVBoxLayout()
        layout.addWidget(heading)
        layout.addSpacing(12)
        layout.addWidget(self.status)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.update_button)
        layout.addWidget(self.offline_button)
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)
        self.setStyleSheet(
            "QMainWindow { background: #171a21; } QWidget { color: #edf0f7; font-size: 14px; }"
            "QPushButton { background: #5865f2; border: 0; padding: 11px; border-radius: 5px; font-weight: 600; }"
            "QPushButton:hover { background: #6975ff; } QLabel#heading { font-size: 24px; font-weight: 700; }"
            "QLabel#status { color: #aab4c5; }"
        )

    def _check_and_launch(self) -> None:
        self.update_button.setEnabled(False)
        self.offline_button.setEnabled(False)
        self.status.setText("Проверяем релиз App на GitHub…")
        self.progress_bar.setValue(0)
        self.progress_bar.show()
        self.worker = AppUpdateWorker(self.manager)
        self.worker.succeeded.connect(self._on_update_succeeded)
        self.worker.failed.connect(self._on_update_failed)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.start()

    def _on_progress(self, downloaded: int, total: int) -> None:
        if total > 0:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(min(100, round(downloaded * 100 / total)))
            self.status.setText(f"Скачиваем App: {downloaded // (1024 * 1024)} МБ")
        else:
            self.progress_bar.setRange(0, 0)
            self.status.setText("Скачиваем App с GitHub…")

    def _on_update_succeeded(self, executable: Path, message: str) -> None:
        try:
            self.manager.launch(executable)
        except OSError as error:
            QMessageBox.critical(self, "Не удалось запустить App", str(error))
            self.status.setText(message)
            return
        QApplication.quit()

    def _on_update_failed(self, message: str) -> None:
        self.status.setText(f"Не удалось обновить App: {message}")
        installed = self.manager.installed_executable()
        self.offline_button.setEnabled(installed is not None)
        QMessageBox.warning(self, "Обновление App", message)

    def _launch_installed(self) -> None:
        executable = self.manager.installed_executable()
        if executable is None:
            self.offline_button.setEnabled(False)
            return
        try:
            self.manager.launch(executable)
        except OSError as error:
            QMessageBox.critical(self, "Не удалось запустить App", str(error))
            return
        QApplication.quit()

    def _on_worker_finished(self) -> None:
        self.progress_bar.hide()
        self.update_button.setEnabled(True)
        self.offline_button.setEnabled(self.manager.installed_executable() is not None)
        self.worker = None

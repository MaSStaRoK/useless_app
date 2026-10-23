"""Standalone entry point for the frequently updated App."""

import sys

from PyQt6.QtWidgets import QApplication

from app.main_window import MainWindow


def run() -> int:
    application = QApplication(sys.argv)
    application.setApplicationName("GTA5RP Helper")
    application.setOrganizationName("GTA5RP Helper")
    window = MainWindow()
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(run())

"""Launcher entry point."""

import sys

from PyQt6.QtWidgets import QApplication

from launcher.app_manager import AppManager
from launcher.update_window import UpdateWindow
from shared.config import load_config


def run() -> int:
    application = QApplication(sys.argv)
    application.setApplicationName("GTA5RP Helper Launcher")
    application.setOrganizationName("GTA5RP Helper")

    manager = AppManager(load_config())
    launcher = UpdateWindow(manager)
    launcher.show()
    return application.exec()

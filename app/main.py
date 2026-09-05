import sys
import os
import ctypes
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from app.ui.main_window import MainWindow
from app.core.logger import setup_logger

logger = setup_logger("app.main")

APP_ID = "JuguruJinganiya.MT5StrategyConsole.1.0"


def _set_taskbar_icon():
    """Force Windows to show the correct icon in the taskbar (not the Python icon)."""
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except Exception:
        pass  # Non-Windows or old Windows — silently skip


def _find_icon() -> str:
    """Find icon.ico relative to the script or PyInstaller bundle."""
    # PyInstaller bundles files to sys._MEIPASS
    if hasattr(sys, "_MEIPASS"):
        ico = os.path.join(sys._MEIPASS, "app", "icon.ico")
        if os.path.exists(ico):
            return ico

    # Dev mode: relative to this file
    here = os.path.dirname(os.path.abspath(__file__))
    ico = os.path.join(here, "icon.ico")
    if os.path.exists(ico):
        return ico

    return ""


def main():
    logger.info("Starting MT5 Strategy Console…")

    # Must be called BEFORE QApplication on Windows
    _set_taskbar_icon()

    app = QApplication(sys.argv)
    app.setApplicationName("MT5 Strategy Console")
    app.setOrganizationName("JuguruJinganiya")
    app.setApplicationVersion("1.0")

    # App-wide icon (taskbar + title bar)
    icon_path = _find_icon()
    if icon_path:
        icon = QIcon(icon_path)
        app.setWindowIcon(icon)
        logger.info(f"Icon loaded: {icon_path}")
    else:
        logger.warning("icon.ico not found — using default icon.")

    window = MainWindow()

    # Set the window icon explicitly too (belt-and-suspenders for Windows taskbar)
    if icon_path:
        window.setWindowIcon(QIcon(icon_path))

    window.show()
    logger.info("Application window shown.")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

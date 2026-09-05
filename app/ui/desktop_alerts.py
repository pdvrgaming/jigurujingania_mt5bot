from PySide6.QtWidgets import QSystemTrayIcon
from PySide6.QtGui import QIcon
from app.core.logger import setup_logger

logger = setup_logger("app.ui.desktop_alerts")

class DesktopAlerter:
    def __init__(self, parent_widget=None):
        self.tray = QSystemTrayIcon(parent_widget)
        # We need an icon for the tray to show notifications
        # Since we might not have one, we'll create a dummy one or use default
        self.tray.setIcon(QIcon.fromTheme("dialog-information"))
        self.tray.show()

    def show_alert(self, title: str, message: str):
        logger.info(f"ALERT: {title} - {message}")
        if self.tray.isSystemTrayAvailable():
            self.tray.showMessage(title, message, QSystemTrayIcon.Information, 10000)

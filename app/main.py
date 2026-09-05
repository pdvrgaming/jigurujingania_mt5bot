import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from app.ui.main_window import MainWindow
from app.core.logger import setup_logger

logger = setup_logger("app.main")

def main():
    logger.info("Starting MT5 Strategy Console...")
    app = QApplication(sys.argv)
    
    # Setup App Icon (works in PyInstaller too since we bundle it)
    icon_path = os.path.join(os.path.dirname(__file__), 'icon.ico')
    app.setWindowIcon(QIcon(icon_path))
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QMessageBox)
from app.core.config import config

class SettingsUI(QWidget):
    def __init__(self):
        super().__init__()
        
        layout = QVBoxLayout()
        
        self.settings = [
            ("MT5 Default Symbol", "mt5_default_symbol"),
            ("MT5 Default Timeframe", "mt5_default_timeframe"),
            ("Polling Interval (ms)", "polling_interval_ms"),
            ("Data Directory", "data_directory"),
            ("Log Directory", "log_directory")
        ]
        
        self.inputs = {}
        
        for label_text, key in self.settings:
            h = QHBoxLayout()
            h.addWidget(QLabel(label_text))
            inp = QLineEdit(str(config.get(key, "")))
            self.inputs[key] = inp
            h.addWidget(inp)
            layout.addLayout(h)
            
        self.btn_save = QPushButton("Save Settings")
        self.btn_save.clicked.connect(self.save)
        layout.addWidget(self.btn_save)
        
        layout.addStretch()
        self.setLayout(layout)
        
    def save(self):
        try:
            for _, key in self.settings:
                val = self.inputs[key].text()
                if key == "polling_interval_ms":
                    val = int(val)
                config.set(key, val)
            QMessageBox.information(self, "Saved", "Settings saved successfully. Some changes require a restart.")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save settings: {e}")

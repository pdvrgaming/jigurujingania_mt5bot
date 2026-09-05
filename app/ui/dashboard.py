from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import QTimer

class Dashboard(QWidget):
    def __init__(self, provider, observer):
        super().__init__()
        self.provider = provider
        self.observer = observer
        
        layout = QVBoxLayout()
        self.status_label = QLabel("MT5: DISCONNECTED")
        self.status_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(self.status_label)
        
        self.obs_status = QLabel("Bot Observer: STOPPED")
        layout.addWidget(self.obs_status)
        
        self.setLayout(layout)
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_status)
        self.timer.start(1000)
        self.update_status()
        
    def update_status(self):
        if self.provider.is_connected():
            self.status_label.setText("MT5: CONNECTED")
            self.status_label.setStyleSheet("font-size: 18px; font-weight: bold; color: green;")
        else:
            self.status_label.setText("MT5: DISCONNECTED")
            self.status_label.setStyleSheet("font-size: 18px; font-weight: bold; color: red;")
            
        if self.observer.running:
            self.obs_status.setText("Bot Observer: RUNNING")
            self.obs_status.setStyleSheet("color: green;")
        else:
            self.obs_status.setText("Bot Observer: STOPPED")
            self.obs_status.setStyleSheet("color: black;")

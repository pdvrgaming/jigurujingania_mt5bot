from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QLineEdit
from PySide6.QtCore import QTimer
import os

class BotObserverUI(QWidget):
    def __init__(self, observer):
        super().__init__()
        self.observer = observer
        
        layout = QVBoxLayout()
        
        self.title = QLabel("BOT OBSERVER (XAUUSD Trial)")
        self.title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(self.title)
        
        self.status = QLabel("Status: STOPPED")
        layout.addWidget(self.status)
        
        self.events_label = QLabel("Events captured: 0")
        layout.addWidget(self.events_label)
        
        magic_layout = QHBoxLayout()
        magic_layout.addWidget(QLabel("Target Magic Number (Optional):"))
        self.target_magic_input = QLineEdit()
        self.target_magic_input.setPlaceholderText("Leave blank to observe all")
        magic_layout.addWidget(self.target_magic_input)
        layout.addLayout(magic_layout)
        
        btn_layout = QHBoxLayout()
        self.btn_start = QPushButton("START OBSERVER")
        self.btn_start.clicked.connect(self.start_observer)
        self.btn_stop = QPushButton("STOP OBSERVER")
        self.btn_stop.clicked.connect(self.stop_observer)
        self.btn_stop.setEnabled(False)
        self.btn_open_csv = QPushButton("OPEN CSV")
        self.btn_open_csv.clicked.connect(self.open_csv)
        
        btn_layout.addWidget(self.btn_start)
        btn_layout.addWidget(self.btn_stop)
        btn_layout.addWidget(self.btn_open_csv)
        
        layout.addLayout(btn_layout)
        layout.addStretch()
        self.setLayout(layout)
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.poll_observer)
        
    def start_observer(self):
        magic_val = self.target_magic_input.text().strip()
        self.observer.target_magic = int(magic_val) if magic_val.isdigit() else None
        
        self.observer.establish_baseline()
        self.observer.running = True
        self.status.setText("Status: RUNNING")
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.timer.start(int(self.observer.interval * 1000))
        
    def stop_observer(self):
        self.observer.running = False
        self.status.setText("Status: STOPPED")
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.timer.stop()
        
    def poll_observer(self):
        if self.observer.running:
            self.observer.poll()
            # Count lines in CSV for events captured
            try:
                with open(self.observer.csv_path, 'r') as f:
                    count = sum(1 for _ in f) - 1 # exclude header
                self.events_label.setText(f"Events captured: {max(0, count)}")
            except Exception:
                pass
                
    def open_csv(self):
        os.startfile(str(self.observer.csv_path)) if os.name == 'nt' else None

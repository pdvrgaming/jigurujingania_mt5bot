import json
from pathlib import Path
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QFileDialog, QMessageBox, QTextEdit)
from app.core.config import config

class LiveMonitorUI(QWidget):
    def __init__(self, monitor, alerter):
        super().__init__()
        self.monitor = monitor
        self.alerter = alerter
        self.active_strategy = None
        
        layout = QVBoxLayout()
        
        self.status = QLabel("Live Monitor: STOPPED")
        self.status.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(self.status)
        
        self.strat_label = QLabel("Strategy: None")
        layout.addWidget(self.strat_label)
        
        ctrl = QHBoxLayout()
        self.btn_load = QPushButton("Load Strategy")
        self.btn_load.clicked.connect(self.load_strategy)
        
        self.btn_start = QPushButton("START MONITORING")
        self.btn_start.clicked.connect(self.start_monitoring)
        
        self.btn_stop = QPushButton("STOP MONITORING")
        self.btn_stop.clicked.connect(self.stop_monitoring)
        self.btn_stop.setEnabled(False)
        
        ctrl.addWidget(self.btn_load)
        ctrl.addWidget(self.btn_start)
        ctrl.addWidget(self.btn_stop)
        layout.addLayout(ctrl)
        
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log)
        
        self.setLayout(layout)
        
        self.monitor.signal_generated.connect(self.on_signal)
        
    def load_strategy(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Open Strategy", "", "JSON Files (*.json)")
        if filepath:
            try:
                with open(filepath, "r") as f:
                    self.active_strategy = json.load(f)
                self.strat_label.setText(f"Strategy: {self.active_strategy.get('name', 'Unknown')}")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not load strategy: {e}")

    def start_monitoring(self):
        if not self.active_strategy:
            QMessageBox.warning(self, "Error", "Load a strategy first.")
            return
        self.monitor.start(self.active_strategy)
        self.status.setText("Live Monitor: RUNNING")
        self.status.setStyleSheet("color: green; font-size: 18px; font-weight: bold;")
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.log.append("Started monitoring...")
        
    def stop_monitoring(self):
        self.monitor.stop()
        self.status.setText("Live Monitor: STOPPED")
        self.status.setStyleSheet("color: black; font-size: 18px; font-weight: bold;")
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.log.append("Stopped monitoring.")
        
    def on_signal(self, data):
        sig = data["signal"]
        sym = data["strategy"]["symbol"]
        tf = data["strategy"]["timeframe"]
        
        title = f"{sig['direction']} CONDITIONS MET"
        msg = f"{sym} {tf}\nPrice: {sig['price']}\nTime: {sig['timestamp']}\n"
        for d in sig['debug']:
            msg += f"- {d}\n"
            
        self.log.append(f"SIGNAL: {title}")
        self.log.append(msg)
        
        # Desktop Alert
        self.alerter.show_alert(title, msg)

import json
import pandas as pd
from pathlib import Path
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QComboBox, QFileDialog, QTextEdit,
                             QMessageBox)
from app.core.strategy_engine import StrategyEngine

class BacktestUI(QWidget):
    def __init__(self):
        super().__init__()
        
        self.engine = StrategyEngine()
        
        layout = QVBoxLayout()
        
        # Controls
        ctrl_layout = QHBoxLayout()
        self.btn_load_strat = QPushButton("Load Strategy JSON")
        self.btn_load_strat.clicked.connect(self.load_strategy)
        
        self.btn_load_data = QPushButton("Load CSV Data")
        self.btn_load_data.clicked.connect(self.load_data)
        
        self.btn_run = QPushButton("RUN BACKTEST")
        self.btn_run.clicked.connect(self.run_backtest)
        
        ctrl_layout.addWidget(self.btn_load_strat)
        ctrl_layout.addWidget(self.btn_load_data)
        ctrl_layout.addWidget(self.btn_run)
        layout.addLayout(ctrl_layout)
        
        self.strat_label = QLabel("Strategy: None")
        self.data_label = QLabel("Data: None")
        layout.addWidget(self.strat_label)
        layout.addWidget(self.data_label)
        
        # Results
        self.results_out = QTextEdit()
        self.results_out.setReadOnly(True)
        layout.addWidget(self.results_out)
        
        self.setLayout(layout)
        
        self.strategy = None
        self.data_df = None
        
    def load_strategy(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Open Strategy", "", "JSON Files (*.json)")
        if filepath:
            try:
                with open(filepath, "r") as f:
                    self.strategy = json.load(f)
                self.strat_label.setText(f"Strategy: {self.strategy.get('name', 'Unknown')} v{self.strategy.get('version', 1)}")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not load strategy: {e}")
                
    def load_data(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Open Data CSV", "", "CSV Files (*.csv)")
        if filepath:
            try:
                self.data_df = pd.read_csv(filepath)
                # Ensure correct columns exist
                if 'timestamp' in self.data_df.columns:
                    self.data_df['time'] = pd.to_datetime(self.data_df['timestamp'])
                self.data_label.setText(f"Data: {filepath} ({len(self.data_df)} rows)")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not load data: {e}")
                
    def run_backtest(self):
        if not self.strategy or self.data_df is None or self.data_df.empty:
            QMessageBox.warning(self, "Error", "Please load both Strategy and Data CSV.")
            return
            
        self.results_out.clear()
        self.results_out.append(f"Running backtest for: {self.strategy.get('name')} v{self.strategy.get('version')}")
        self.results_out.append(f"Total candles: {len(self.data_df)}")
        
        try:
            signals = self.engine.evaluate(self.strategy, self.data_df)
            
            self.results_out.append(f"Total Signals Generated: {len(signals)}\n")
            
            for s in signals:
                time_str = str(s['timestamp'])
                price_str = str(s['price'])
                dir_str = s['direction']
                
                self.results_out.append(f"SIGNAL {dir_str} @ {time_str} | Price: {price_str}")
                for d in s['debug']:
                    self.results_out.append(f"  - {d}")
                self.results_out.append("")
                
        except Exception as e:
            self.results_out.append(f"\nERROR running backtest: {e}")

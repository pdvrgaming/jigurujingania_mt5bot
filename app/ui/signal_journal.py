import pandas as pd
from pathlib import Path
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QTableWidget, 
                             QTableWidgetItem, QPushButton, QHBoxLayout, QLabel)
from app.core.config import config

class SignalJournalUI(QWidget):
    def __init__(self):
        super().__init__()
        self.journal_path = Path(config.get("data_directory", "data")) / "journal" / "signals.csv"
        
        layout = QVBoxLayout()
        
        # Stats
        self.stats_label = QLabel("Stats: ...")
        layout.addWidget(self.stats_label)
        
        # Table
        self.table = QTableWidget()
        layout.addWidget(self.table)
        
        # Controls
        ctrl = QHBoxLayout()
        self.btn_refresh = QPushButton("Refresh Journal")
        self.btn_refresh.clicked.connect(self.load_journal)
        ctrl.addWidget(self.btn_refresh)
        ctrl.addStretch()
        layout.addLayout(ctrl)
        
        self.setLayout(layout)
        self.load_journal()
        
    def load_journal(self):
        if not self.journal_path.exists():
            self.stats_label.setText("No journal found.")
            return
            
        try:
            df = pd.read_csv(self.journal_path)
            
            # Update stats
            total_signals = len(df)
            buy_signals = len(df[df['direction'] == 'BUY']) if 'direction' in df.columns else 0
            sell_signals = len(df[df['direction'] == 'SELL']) if 'direction' in df.columns else 0
            
            self.stats_label.setText(f"Total Signals: {total_signals} | BUY: {buy_signals} | SELL: {sell_signals}")
            
            # Update table
            self.table.clear()
            self.table.setColumnCount(len(df.columns))
            self.table.setHorizontalHeaderLabels(df.columns)
            self.table.setRowCount(len(df))
            
            for i, row in df.iterrows():
                for j, col in enumerate(df.columns):
                    self.table.setItem(i, j, QTableWidgetItem(str(row[col])))
                    
        except Exception as e:
            self.stats_label.setText(f"Error loading journal: {e}")

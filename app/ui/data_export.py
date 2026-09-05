import pandas as pd
from pathlib import Path
import shutil
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QMessageBox, QFileDialog
from app.core.config import config
from app.core.historical_data import HistoricalDataManager

class DataExportUI(QWidget):
    def __init__(self, provider):
        super().__init__()
        self.provider = provider
        self.hist_manager = HistoricalDataManager(provider)
        
        layout = QVBoxLayout()
        
        self.btn_candles = QPushButton("Export Candles (XAUUSD M15)")
        self.btn_candles.clicked.connect(self.export_candles)
        
        self.btn_journal = QPushButton("Export Signal Journal")
        self.btn_journal.clicked.connect(self.export_journal)
        
        self.btn_obs = QPushButton("Export Bot Observations")
        self.btn_obs.clicked.connect(self.export_obs)
        
        layout.addWidget(self.btn_candles)
        layout.addWidget(self.btn_journal)
        layout.addWidget(self.btn_obs)
        layout.addStretch()
        
        self.setLayout(layout)
        
    def export_candles(self):
        filepath = self.hist_manager.export_candles("XAUUSD", "M15", 1000)
        if filepath:
            QMessageBox.information(self, "Exported", f"Candles exported to:\n{filepath}")
        else:
            QMessageBox.warning(self, "Error", "Failed to export candles.")
            
    def _copy_file(self, src_relative, name):
        src = Path(config.get("data_directory", "data")) / src_relative
        if not src.exists():
            QMessageBox.warning(self, "Error", f"File does not exist: {src}")
            return
            
        dst, _ = QFileDialog.getSaveFileName(self, "Save CSV", name, "CSV Files (*.csv)")
        if dst:
            shutil.copy(src, dst)
            QMessageBox.information(self, "Exported", f"Saved to {dst}")
            
    def export_journal(self):
        self._copy_file("journal/signals.csv", "signals_export.csv")
        
    def export_obs(self):
        self._copy_file("observations/xauusd_trial_activity.csv", "observations_export.csv")

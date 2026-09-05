"""
Signal Journal — records system signals and lets the user log what they
actually did with each one (Took Trade / Ignored) plus outcome notes.

Clearly separates SYSTEM SIGNAL from USER RECORDED TRADE.
"""
import csv
import uuid
from pathlib import Path
from datetime import datetime

import pytz
import pandas as pd

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
    QLineEdit, QTextEdit, QGroupBox, QSplitter, QMessageBox,
    QFrame, QDoubleSpinBox, QFileDialog, QTabWidget
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont

from app.core.config import config
from app.core.logger import setup_logger

logger = setup_logger("app.ui.signal_journal")

IST = pytz.timezone("Asia/Kolkata")

# ── CSV schema ──────────────────────────────────────────────────────────────
COLUMNS = [
    "signal_id", "strategy_name", "symbol", "timeframe",
    "timestamp_ist", "direction", "price",
    "conditions",           # pipe-separated condition strings
    "user_action",          # Took Trade | Ignored | Watching | —
    "manual_entry_price",
    "manual_exit_price",
    "manual_result",        # Win | Loss | Break Even | —
    "notes",
    "recorded_at_ist"
]

ACTION_COLORS = {
    "Took Trade": "#00d26a",
    "Ignored": "#888888",
    "Watching": "#f5a623",
    "—": "#555555",
}
RESULT_COLORS = {
    "Win": "#00d26a",
    "Loss": "#ff4757",
    "Break Even": "#f5a623",
    "—": "#555555",
}


class SignalJournalUI(QWidget):
    def __init__(self):
        super().__init__()
        self.journal_path = (
            Path(config.get("data_directory", "data")) / "journal" / "signals.csv"
        )
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_csv()
        self._records: list[dict] = []

        self._build_ui()
        self.load_journal()

    # ── Public API (called by LiveMonitorUI) ─────────────────────────────────

    def add_signal(self, strategy_name: str, symbol: str, timeframe: str,
                   direction: str, price: float, timestamp_ist: str,
                   conditions: list[str]):
        """
        Automatically add a system-generated signal to the journal.
        Called from the Live Monitor when a signal fires.
        """
        row = {
            "signal_id": str(uuid.uuid4())[:8],
            "strategy_name": strategy_name,
            "symbol": symbol,
            "timeframe": timeframe,
            "timestamp_ist": timestamp_ist,
            "direction": direction,
            "price": f"{price:,.5f}",
            "conditions": " | ".join(conditions[:5]),
            "user_action": "—",
            "manual_entry_price": "",
            "manual_exit_price": "",
            "manual_result": "—",
            "notes": "",
            "recorded_at_ist": datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S"),
        }
        self._append_csv(row)
        self._records.insert(0, row)
        self._refresh_table()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(6)

        # ── Header stats ──────────────────────────────────────────────────
        stats_frame = QFrame()
        stats_frame.setStyleSheet("background:#1a1a2e; border-radius:6px; padding:6px;")
        stats_lay = QHBoxLayout(stats_frame)

        self.lbl_total   = self._stat_card("Total Signals", "0")
        self.lbl_buy     = self._stat_card("BUY", "0", "#00d26a")
        self.lbl_sell    = self._stat_card("SELL", "0", "#ff4757")
        self.lbl_took    = self._stat_card("Trades Taken", "0", "#00d26a")
        self.lbl_ignored = self._stat_card("Ignored", "0", "#888")
        self.lbl_wins    = self._stat_card("Wins", "0", "#00d26a")
        self.lbl_losses  = self._stat_card("Losses", "0", "#ff4757")

        for w in [self.lbl_total, self.lbl_buy, self.lbl_sell,
                  self.lbl_took, self.lbl_ignored, self.lbl_wins, self.lbl_losses]:
            stats_lay.addWidget(w)
        stats_lay.addStretch()
        root.addWidget(stats_frame)

        # ── Controls ──────────────────────────────────────────────────────
        ctrl = QHBoxLayout()
        self.btn_refresh = QPushButton("🔄 Refresh")
        self.btn_refresh.clicked.connect(self.load_journal)
        ctrl.addWidget(self.btn_refresh)

        self.btn_export = QPushButton("💾 Export CSV")
        self.btn_export.clicked.connect(self._export)
        ctrl.addWidget(self.btn_export)

        ctrl.addStretch()

        ctrl.addWidget(QLabel("Filter:"))
        self.cb_filter = QComboBox()
        self.cb_filter.addItems(["All", "BUY", "SELL", "Took Trade", "Ignored", "Win", "Loss"])
        self.cb_filter.currentIndexChanged.connect(self._refresh_table)
        ctrl.addWidget(self.cb_filter)

        root.addLayout(ctrl)

        # ── Splitter: table + edit panel ─────────────────────────────────
        splitter = QSplitter(Qt.Vertical)

        # Signal table
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "ID", "Time (IST)", "Strategy", "Symbol/TF",
            "Dir", "Price", "Action", "Result", "Notes"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.cellClicked.connect(self._on_row_clicked)
        splitter.addWidget(self.table)

        # Edit panel
        edit_group = QGroupBox("RECORD YOUR TRADE OUTCOME  — select a row then fill in below")
        edit_lay = QHBoxLayout(edit_group)

        # Action
        a_col = QVBoxLayout()
        a_col.addWidget(QLabel("Your Action:"))
        self.cb_action = QComboBox()
        self.cb_action.addItems(["—", "Took Trade", "Ignored", "Watching"])
        a_col.addWidget(self.cb_action)
        edit_lay.addLayout(a_col)

        # Entry / Exit prices
        p_col = QVBoxLayout()
        p_col.addWidget(QLabel("Entry Price:"))
        self.spin_entry = QDoubleSpinBox()
        self.spin_entry.setRange(0, 1_000_000)
        self.spin_entry.setDecimals(5)
        self.spin_entry.setSingleStep(0.1)
        p_col.addWidget(self.spin_entry)
        edit_lay.addLayout(p_col)

        p2_col = QVBoxLayout()
        p2_col.addWidget(QLabel("Exit Price:"))
        self.spin_exit = QDoubleSpinBox()
        self.spin_exit.setRange(0, 1_000_000)
        self.spin_exit.setDecimals(5)
        self.spin_exit.setSingleStep(0.1)
        p2_col.addWidget(self.spin_exit)
        edit_lay.addLayout(p2_col)

        # Result
        r_col = QVBoxLayout()
        r_col.addWidget(QLabel("Result:"))
        self.cb_result = QComboBox()
        self.cb_result.addItems(["—", "Win", "Loss", "Break Even"])
        r_col.addWidget(self.cb_result)
        edit_lay.addLayout(r_col)

        # Notes
        n_col = QVBoxLayout()
        n_col.addWidget(QLabel("Notes:"))
        self.txt_notes = QLineEdit()
        self.txt_notes.setPlaceholderText("Why did you take / ignore this?")
        n_col.addWidget(self.txt_notes)
        edit_lay.addLayout(n_col)

        # Save button
        self.btn_save = QPushButton("💾\nSave")
        self.btn_save.setMinimumWidth(60)
        self.btn_save.setMinimumHeight(50)
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self._save_edit)
        edit_lay.addWidget(self.btn_save)

        edit_group.setMaximumHeight(130)
        splitter.addWidget(edit_group)

        # Condition detail
        detail_group = QGroupBox("SIGNAL CONDITIONS  — what made this signal fire")
        detail_lay = QVBoxLayout(detail_group)
        self.lbl_conditions = QLabel("Select a signal row to see its conditions.")
        self.lbl_conditions.setWordWrap(True)
        self.lbl_conditions.setStyleSheet("font-family:monospace; color:#aaa; font-size:11px;")
        detail_lay.addWidget(self.lbl_conditions)
        detail_group.setMaximumHeight(100)
        splitter.addWidget(detail_group)

        splitter.setSizes([350, 120, 90])
        root.addWidget(splitter)

        self._selected_idx: int = -1

    # ── Stat card helper ──────────────────────────────────────────────────────

    def _stat_card(self, title: str, value: str, color: str = "#e0e0e0") -> QLabel:
        lbl = QLabel(f"<span style='color:#666;font-size:10px;'>{title}</span><br>"
                     f"<span style='color:{color};font-size:16px;font-weight:bold;'>{value}</span>")
        lbl.setTextFormat(Qt.RichText)
        lbl.setMinimumWidth(80)
        return lbl

    def _update_stat(self, widget: QLabel, title: str, value, color: str = "#e0e0e0"):
        widget.setText(
            f"<span style='color:#666;font-size:10px;'>{title}</span><br>"
            f"<span style='color:{color};font-size:16px;font-weight:bold;'>{value}</span>"
        )

    # ── Data loading ──────────────────────────────────────────────────────────

    def _ensure_csv(self):
        if not self.journal_path.exists():
            with open(self.journal_path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=COLUMNS)
                writer.writeheader()

    def load_journal(self):
        try:
            if not self.journal_path.exists() or self.journal_path.stat().st_size < 10:
                self._records = []
            else:
                df = pd.read_csv(self.journal_path, dtype=str).fillna("—")
                self._records = df.to_dict("records")
                self._records.reverse()  # newest first
        except Exception as e:
            logger.error(f"Journal load error: {e}")
            self._records = []
        self._refresh_table()

    def _refresh_table(self):
        flt = self.cb_filter.currentText() if hasattr(self, "cb_filter") else "All"
        rows = self._records

        if flt == "BUY":
            rows = [r for r in rows if r.get("direction") == "BUY"]
        elif flt == "SELL":
            rows = [r for r in rows if r.get("direction") == "SELL"]
        elif flt == "Took Trade":
            rows = [r for r in rows if r.get("user_action") == "Took Trade"]
        elif flt == "Ignored":
            rows = [r for r in rows if r.get("user_action") == "Ignored"]
        elif flt == "Win":
            rows = [r for r in rows if r.get("manual_result") == "Win"]
        elif flt == "Loss":
            rows = [r for r in rows if r.get("manual_result") == "Loss"]

        self.table.setRowCount(len(rows))
        for i, rec in enumerate(rows):
            d = rec.get("direction", "—")
            action = rec.get("user_action", "—")
            result = rec.get("manual_result", "—")
            cells = [
                rec.get("signal_id", ""),
                rec.get("timestamp_ist", ""),
                rec.get("strategy_name", ""),
                f"{rec.get('symbol','')} {rec.get('timeframe','')}",
                d,
                rec.get("price", ""),
                action,
                result,
                rec.get("notes", ""),
            ]
            for col, val in enumerate(cells):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignCenter)
                if col == 4:  # direction
                    item.setForeground(QColor("#00d26a" if d == "BUY" else "#ff4757"))
                    item.setFont(QFont("Segoe UI", 9, QFont.Bold))
                if col == 6:  # action
                    item.setForeground(QColor(ACTION_COLORS.get(action, "#555")))
                if col == 7:  # result
                    item.setForeground(QColor(RESULT_COLORS.get(result, "#555")))
                self.table.setItem(i, col, item)

        # Update stats
        all_r = self._records
        buys    = sum(1 for r in all_r if r.get("direction") == "BUY")
        sells   = sum(1 for r in all_r if r.get("direction") == "SELL")
        took    = sum(1 for r in all_r if r.get("user_action") == "Took Trade")
        ignored = sum(1 for r in all_r if r.get("user_action") == "Ignored")
        wins    = sum(1 for r in all_r if r.get("manual_result") == "Win")
        losses  = sum(1 for r in all_r if r.get("manual_result") == "Loss")

        self._update_stat(self.lbl_total,   "Total Signals", len(all_r))
        self._update_stat(self.lbl_buy,     "BUY",           buys,    "#00d26a")
        self._update_stat(self.lbl_sell,    "SELL",          sells,   "#ff4757")
        self._update_stat(self.lbl_took,    "Trades Taken",  took,    "#00d26a")
        self._update_stat(self.lbl_ignored, "Ignored",       ignored, "#888")
        self._update_stat(self.lbl_wins,    "Wins",          wins,    "#00d26a")
        self._update_stat(self.lbl_losses,  "Losses",        losses,  "#ff4757")

        # Store filtered rows for click lookup
        self._filtered_rows = rows

    def _on_row_clicked(self, row: int, _col: int):
        if not hasattr(self, "_filtered_rows") or row >= len(self._filtered_rows):
            return
        rec = self._filtered_rows[row]
        self._selected_idx = row

        # Populate edit panel
        self.cb_action.setCurrentText(rec.get("user_action", "—"))
        try:
            self.spin_entry.setValue(float(str(rec.get("manual_entry_price", "0") or "0").replace(",", "")))
        except Exception:
            self.spin_entry.setValue(0)
        try:
            self.spin_exit.setValue(float(str(rec.get("manual_exit_price", "0") or "0").replace(",", "")))
        except Exception:
            self.spin_exit.setValue(0)
        self.cb_result.setCurrentText(rec.get("manual_result", "—"))
        self.txt_notes.setText(rec.get("notes", ""))
        self.btn_save.setEnabled(True)

        # Show conditions
        conds = rec.get("conditions", "")
        if conds and conds != "—":
            lines = [f"  ✓ {c}" for c in conds.split(" | ")]
            self.lbl_conditions.setText(
                f"Signal #{rec.get('signal_id','')} — {rec.get('strategy_name','')}  "
                f"@ {rec.get('price','')}  {rec.get('timestamp_ist','')}\n" +
                "\n".join(lines)
            )
        else:
            self.lbl_conditions.setText("No condition detail recorded for this signal.")

    def _save_edit(self):
        if self._selected_idx < 0 or not hasattr(self, "_filtered_rows"):
            return
        rec = self._filtered_rows[self._selected_idx]
        signal_id = rec.get("signal_id", "")

        # Update the record in memory
        for r in self._records:
            if r.get("signal_id") == signal_id:
                r["user_action"]          = self.cb_action.currentText()
                r["manual_entry_price"]   = f"{self.spin_entry.value():,.5f}" if self.spin_entry.value() > 0 else ""
                r["manual_exit_price"]    = f"{self.spin_exit.value():,.5f}" if self.spin_exit.value() > 0 else ""
                r["manual_result"]        = self.cb_result.currentText()
                r["notes"]                = self.txt_notes.text()
                r["recorded_at_ist"]      = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
                break

        # Rewrite CSV
        self._rewrite_csv()
        self._refresh_table()
        self.btn_save.setEnabled(False)

    def _rewrite_csv(self):
        try:
            rows_to_write = list(reversed(self._records))  # chronological order
            with open(self.journal_path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(rows_to_write)
        except Exception as e:
            logger.error(f"Journal rewrite error: {e}")

    def _append_csv(self, row: dict):
        try:
            with open(self.journal_path, "a", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
                writer.writerow(row)
        except Exception as e:
            logger.error(f"Journal append error: {e}")

    def _export(self):
        fp, _ = QFileDialog.getSaveFileName(
            self, "Export Journal", "signal_journal.csv", "CSV Files (*.csv)")
        if not fp:
            return
        try:
            import shutil
            shutil.copy(self.journal_path, fp)
            QMessageBox.information(self, "Exported", f"Journal saved to:\n{fp}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

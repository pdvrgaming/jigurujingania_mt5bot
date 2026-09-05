"""
Bot Observer UI — rich event viewer with full CSV table, statistics,
market-status awareness, and multi-bot magic number filtering.
"""
import os
import csv
from pathlib import Path
from datetime import datetime

import pandas as pd
import pytz

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QGroupBox, QFrame, QComboBox, QSplitter, QSpinBox,
    QMessageBox
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont

from app.core.config import config
from app.core.logger import setup_logger

logger = setup_logger("app.ui.bot_observer_ui")

IST = pytz.timezone("Asia/Kolkata")

EVENT_COLORS = {
    "POSITION_OPENED":  "#00d26a",
    "POSITION_UPDATED": "#f5a623",
    "POSITION_CLOSED":  "#ff4757",
    "DEAL_EXECUTED":    "#00bfff",
    "ORDER_CREATED":    "#b39ddb",
    "ORDER_UPDATED":    "#ce93d8",
    "PRICE_SNAPSHOT":   "#444455",
    "MT5_DISCONNECTED": "#ff6b35",
    "MT5_RECONNECTED":  "#00d26a",
}

DISPLAY_COLS = [
    ("timestamp_ist", "Time (IST)", 140),
    ("event_type",    "Event",       140),
    ("direction",     "Dir",          50),
    ("symbol",        "Symbol",       70),
    ("volume",        "Lot",          55),
    ("price",         "Price",        90),
    ("sl",            "SL",           80),
    ("tp",            "TP",           80),
    ("profit",        "Profit",       80),
    ("magic",         "Magic",        65),
    ("comment",       "Comment",     120),
    ("current_price", "Cur.Price",    90),
    ("ticket",        "Ticket",       80),
]


class BotObserverUI(QWidget):
    def __init__(self, observer):
        super().__init__()
        self.observer = observer
        self._all_records: list[dict] = []
        self._poll_timer = QTimer()
        self._poll_timer.timeout.connect(self._do_poll)

        self._build_ui()
        self._load_existing_csv()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(8)
        root.setContentsMargins(10, 10, 10, 10)

        # ── Header ─────────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        title = QLabel("🤖  BOT OBSERVER")
        title.setFont(QFont("Segoe UI", 15, QFont.Bold))
        title.setStyleSheet("color:#e0e0e0;")
        hdr.addWidget(title)
        hdr.addStretch()

        self.lbl_status = QLabel("⏹  STOPPED")
        self.lbl_status.setStyleSheet(
            "color:#888; font-size:13px; font-weight:bold; "
            "background:#1a1a2e; border:1px solid #2a2a4a; "
            "border-radius:6px; padding:4px 12px;"
        )
        hdr.addWidget(self.lbl_status)
        root.addLayout(hdr)

        # ── Purpose notice ──────────────────────────────────────────────────
        notice = QLabel(
            "📡  READ-ONLY observer. Records every observable MT5 account event (positions, deals, price) "
            "to a CSV. Does NOT interfere with any running Expert Advisor."
        )
        notice.setWordWrap(True)
        notice.setStyleSheet(
            "color:#888; font-size:10px; background:#111122; "
            "border:1px solid #222244; border-radius:4px; padding:6px;"
        )
        root.addWidget(notice)

        # ── Stats row ───────────────────────────────────────────────────────
        stats_frame = QFrame()
        stats_frame.setStyleSheet(
            "QFrame{background:#1a1a2e; border-radius:8px; border:1px solid #2a2a4a;}"
        )
        stats_lay = QHBoxLayout(stats_frame)
        stats_lay.setContentsMargins(12, 8, 12, 8)

        self._stat_opens   = self._make_stat("Positions Opened", "0", "#00d26a")
        self._stat_closes  = self._make_stat("Positions Closed", "0", "#ff4757")
        self._stat_deals   = self._make_stat("Deals Executed",   "0", "#00bfff")
        self._stat_updates = self._make_stat("Updates",          "0", "#f5a623")
        self._stat_total   = self._make_stat("Total Events",     "0")
        self._stat_last    = self._make_stat("Last Update",      "—")

        for w in [self._stat_opens, self._stat_closes, self._stat_deals,
                  self._stat_updates, self._stat_total, self._stat_last]:
            stats_lay.addWidget(w)
        stats_lay.addStretch()
        root.addWidget(stats_frame)

        # ── Configuration ───────────────────────────────────────────────────
        cfg_group = QGroupBox("CONFIGURATION")
        cfg_group.setStyleSheet(
            "QGroupBox{color:#666;font-size:10px;font-weight:bold;"
            "border:1px solid #2a2a4a;border-radius:6px;margin-top:6px;padding:8px;}"
        )
        cfg_lay = QHBoxLayout(cfg_group)

        cfg_lay.addWidget(QLabel("Symbol:"))
        self.sym_input = QLineEdit("XAUUSD")
        self.sym_input.setFixedWidth(80)
        cfg_lay.addWidget(self.sym_input)

        cfg_lay.addWidget(QLabel("Magic # filter:"))
        self.magic_input = QLineEdit()
        self.magic_input.setPlaceholderText("blank = all bots")
        self.magic_input.setFixedWidth(100)
        cfg_lay.addWidget(self.magic_input)

        cfg_lay.addWidget(QLabel("Poll (sec):"))
        self.spin_poll = QSpinBox()
        self.spin_poll.setRange(3, 60)
        self.spin_poll.setValue(5)
        self.spin_poll.setFixedWidth(60)
        cfg_lay.addWidget(self.spin_poll)

        cfg_lay.addStretch()

        # Buttons
        self.btn_start = QPushButton("▶  START OBSERVER")
        self.btn_start.setMinimumHeight(34)
        self.btn_start.setStyleSheet(
            "QPushButton{background:#1a6b3a;color:white;font-weight:bold;"
            "border:none;border-radius:5px;}"
            "QPushButton:hover{background:#228b4e;}"
        )
        self.btn_start.clicked.connect(self._start)
        cfg_lay.addWidget(self.btn_start)

        self.btn_stop = QPushButton("⏹  STOP")
        self.btn_stop.setMinimumHeight(34)
        self.btn_stop.setEnabled(False)
        self.btn_stop.setStyleSheet(
            "QPushButton{background:#6b1a1a;color:white;font-weight:bold;"
            "border:none;border-radius:5px;}"
            "QPushButton:hover{background:#8b2222;}"
            "QPushButton:disabled{background:#333;color:#666;}"
        )
        self.btn_stop.clicked.connect(self._stop)
        cfg_lay.addWidget(self.btn_stop)

        self.btn_open_csv = QPushButton("📄 Open CSV")
        self.btn_open_csv.setMinimumHeight(34)
        self.btn_open_csv.clicked.connect(self._open_csv)
        cfg_lay.addWidget(self.btn_open_csv)

        self.btn_refresh = QPushButton("🔄 Refresh")
        self.btn_refresh.setMinimumHeight(34)
        self.btn_refresh.clicked.connect(self._load_existing_csv)
        cfg_lay.addWidget(self.btn_refresh)

        root.addWidget(cfg_group)

        # ── Filter bar ──────────────────────────────────────────────────────
        filter_lay = QHBoxLayout()
        filter_lay.addWidget(QLabel("Show events:"))
        self.cb_event_filter = QComboBox()
        self.cb_event_filter.addItems([
            "All", "POSITION_OPENED", "POSITION_CLOSED", "POSITION_UPDATED",
            "DEAL_EXECUTED", "PRICE_SNAPSHOT", "MT5_DISCONNECTED"
        ])
        self.cb_event_filter.setFixedWidth(160)
        self.cb_event_filter.currentIndexChanged.connect(self._refresh_table)
        filter_lay.addWidget(self.cb_event_filter)

        filter_lay.addWidget(QLabel("Hide price snapshots:"))
        self.cb_hide_snap = QComboBox()
        self.cb_hide_snap.addItems(["Yes", "No"])
        self.cb_hide_snap.setFixedWidth(60)
        self.cb_hide_snap.currentIndexChanged.connect(self._refresh_table)
        filter_lay.addWidget(self.cb_hide_snap)

        filter_lay.addStretch()

        self.lbl_row_count = QLabel("0 events")
        self.lbl_row_count.setStyleSheet("color:#666; font-size:11px;")
        filter_lay.addWidget(self.lbl_row_count)
        root.addLayout(filter_lay)

        # ── Events table ────────────────────────────────────────────────────
        self.table = QTableWidget()
        self.table.setColumnCount(len(DISPLAY_COLS))
        self.table.setHorizontalHeaderLabels([c[1] for c in DISPLAY_COLS])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        for i, (_, _, w) in enumerate(DISPLAY_COLS):
            self.table.setColumnWidth(i, w)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.verticalHeader().setDefaultSectionSize(22)
        self.table.setStyleSheet(
            "QTableWidget{gridline-color:#1a1a2e;}"
            "QHeaderView::section{background:#1a1a2e;color:#aaa;font-size:10px;"
            "font-weight:bold;border:1px solid #2a2a4a;}"
        )
        self.table.cellClicked.connect(self._on_row_click)
        root.addWidget(self.table)

        # ── Detail panel ────────────────────────────────────────────────────
        detail_group = QGroupBox("EVENT DETAIL")
        detail_group.setStyleSheet(
            "QGroupBox{color:#555;font-size:10px;font-weight:bold;"
            "border:1px solid #1a1a2e;border-radius:4px;margin-top:4px;"
            "max-height:100px;}"
        )
        detail_lay = QHBoxLayout(detail_group)
        self.lbl_detail = QLabel("Click any event row to see full details.")
        self.lbl_detail.setWordWrap(True)
        self.lbl_detail.setStyleSheet(
            "color:#aaa; font-family:monospace; font-size:11px;")
        detail_lay.addWidget(self.lbl_detail)
        detail_group.setMaximumHeight(90)
        root.addWidget(detail_group)

    # ── Stat card helper ──────────────────────────────────────────────────────

    def _make_stat(self, title: str, value: str,
                   color: str = "#e0e0e0") -> QLabel:
        lbl = QLabel(
            f"<span style='color:#555;font-size:9px;'>{title}</span><br>"
            f"<span style='color:{color};font-size:15px;font-weight:bold;'>{value}</span>"
        )
        lbl.setTextFormat(Qt.RichText)
        lbl.setMinimumWidth(90)
        return lbl

    def _update_stat(self, widget: QLabel, title: str, value,
                     color: str = "#e0e0e0"):
        widget.setText(
            f"<span style='color:#555;font-size:9px;'>{title}</span><br>"
            f"<span style='color:{color};font-size:15px;font-weight:bold;'>{value}</span>"
        )

    # ── Observer control ──────────────────────────────────────────────────────

    def _start(self):
        magic_text = self.magic_input.text().strip()
        self.observer.target_magic = (
            int(magic_text) if magic_text.isdigit() else None)
        self.observer.symbol = self.sym_input.text().strip() or "XAUUSD"
        self.observer.establish_baseline()
        self.observer.running = True

        self.lbl_status.setText("▶  RUNNING")
        self.lbl_status.setStyleSheet(
            "color:#00d26a; font-size:13px; font-weight:bold; "
            "background:#0a2a1a; border:1px solid #1a4a2a; "
            "border-radius:6px; padding:4px 12px;"
        )
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self._poll_timer.start(self.spin_poll.value() * 1000)
        logger.info(f"Bot Observer started — symbol={self.observer.symbol} "
                    f"magic={self.observer.target_magic}")

    def _stop(self):
        self.observer.running = False
        self._poll_timer.stop()

        self.lbl_status.setText("⏹  STOPPED")
        self.lbl_status.setStyleSheet(
            "color:#888; font-size:13px; font-weight:bold; "
            "background:#1a1a2e; border:1px solid #2a2a4a; "
            "border-radius:6px; padding:4px 12px;"
        )
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)

    def _do_poll(self):
        if self.observer.running:
            self.observer.poll()
            self._load_existing_csv()

    # ── Data loading ──────────────────────────────────────────────────────────

    def _load_existing_csv(self):
        """Load all records from the CSV file and refresh the table."""
        csv_path = self.observer.csv_path
        if not csv_path.exists():
            return
        try:
            df = pd.read_csv(csv_path, dtype=str).fillna("")
            self._all_records = df.to_dict("records")
            self._refresh_table()
            self._update_stats()
        except Exception as e:
            logger.error(f"Bot Observer CSV load error: {e}")

    def _update_stats(self):
        records = self._all_records
        opens   = sum(1 for r in records if r.get("event_type") == "POSITION_OPENED")
        closes  = sum(1 for r in records if r.get("event_type") == "POSITION_CLOSED")
        deals   = sum(1 for r in records if r.get("event_type") == "DEAL_EXECUTED")
        updates = sum(1 for r in records if r.get("event_type") == "POSITION_UPDATED")
        total   = len(records)

        self._update_stat(self._stat_opens,   "Positions Opened", opens,  "#00d26a")
        self._update_stat(self._stat_closes,  "Positions Closed", closes, "#ff4757")
        self._update_stat(self._stat_deals,   "Deals Executed",   deals,  "#00bfff")
        self._update_stat(self._stat_updates, "Updates",          updates,"#f5a623")
        self._update_stat(self._stat_total,   "Total Events",     total)

        # Last update time
        if self._all_records:
            last = self._all_records[-1].get("timestamp_ist", "?")
            self._update_stat(self._stat_last, "Last Update", last[:16], "#aaa")

    def _refresh_table(self):
        flt = self.cb_event_filter.currentText()
        hide_snap = self.cb_hide_snap.currentText() == "Yes"

        records = self._all_records

        if flt != "All":
            records = [r for r in records if r.get("event_type") == flt]
        if hide_snap:
            records = [r for r in records
                       if r.get("event_type") != "PRICE_SNAPSHOT"]

        # Show newest first
        records = list(reversed(records))

        self.table.setRowCount(len(records))
        self.lbl_row_count.setText(f"{len(records):,} events")

        for row_i, rec in enumerate(records):
            et = rec.get("event_type", "")
            color = QColor(EVENT_COLORS.get(et, "#aaa"))
            direction = rec.get("direction", "")

            for col_i, (key, _, _) in enumerate(DISPLAY_COLS):
                val = str(rec.get(key, ""))
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignCenter)

                # Colour event_type column
                if col_i == 1:
                    item.setForeground(color)
                    item.setFont(QFont("Segoe UI", 8, QFont.Bold))

                # Colour direction column
                if col_i == 2:
                    if direction == "BUY":
                        item.setForeground(QColor("#00d26a"))
                    elif direction == "SELL":
                        item.setForeground(QColor("#ff4757"))

                # Colour profit column
                if col_i == 8 and val:
                    try:
                        pnl = float(val)
                        item.setForeground(
                            QColor("#00d26a") if pnl >= 0 else QColor("#ff4757"))
                    except ValueError:
                        pass

                # Grey out price snapshots
                if et == "PRICE_SNAPSHOT":
                    item.setForeground(QColor("#444455"))

                self.table.setItem(row_i, col_i, item)

        # Store for click lookup
        self._displayed_records = records

    def _on_row_click(self, row: int, _col: int):
        if not hasattr(self, "_displayed_records"):
            return
        if row >= len(self._displayed_records):
            return
        rec = self._displayed_records[row]
        et = rec.get("event_type", "?")
        parts = [
            f"Event:    {et}",
            f"Time IST: {rec.get('timestamp_ist', '?')}",
            f"Time UTC: {rec.get('timestamp_utc', '?')}",
            f"Symbol:   {rec.get('symbol', '?')}",
        ]
        if et in ("POSITION_OPENED", "POSITION_UPDATED", "POSITION_CLOSED"):
            parts += [
                f"Direction:{rec.get('direction','?')}  Volume:{rec.get('volume','?')}",
                f"Price:    {rec.get('price','?')}  SL:{rec.get('sl','?')}  TP:{rec.get('tp','?')}",
                f"Profit:   {rec.get('profit','?')}  Magic:{rec.get('magic','?')}",
                f"Comment:  {rec.get('comment','?')}  Ticket:{rec.get('ticket','?')}",
            ]
        elif et == "DEAL_EXECUTED":
            parts += [
                f"Volume:{rec.get('volume','?')}  Price:{rec.get('price','?')}",
                f"Commission:{rec.get('commission','?')}  Swap:{rec.get('swap','?')}",
                f"Profit:{rec.get('profit','?')}  Magic:{rec.get('magic','?')}",
            ]
        elif et == "PRICE_SNAPSHOT":
            parts.append(f"Cur.Price: {rec.get('current_price','?')}")

        self.lbl_detail.setText("  |  ".join(parts[:3]) + "\n" +
                                 "  |  ".join(parts[3:]))

    def _open_csv(self):
        path = self.observer.csv_path
        if path.exists():
            os.startfile(str(path))
        else:
            QMessageBox.information(
                self, "No CSV",
                f"CSV not found yet.\nStart the observer first to create it.\n\n"
                f"Expected: {path}")

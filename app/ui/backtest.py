"""
Backtest UI — run strategy against historical data with full P&L reporting,
signal debug inspection, and chart-data export.
"""
import json
import csv
from pathlib import Path
from datetime import datetime, timezone, timedelta

import pytz
import pandas as pd

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QFileDialog, QTextEdit, QMessageBox, QRadioButton,
    QGroupBox, QStackedWidget, QGridLayout, QCheckBox, QSplitter,
    QTableWidget, QTableWidgetItem, QHeaderView, QDoubleSpinBox, QSpinBox,
    QFrame, QTabWidget, QApplication
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont

from app.core.strategy_engine import StrategyEngine
from app.core.mt5_provider import provider as mt5_provider
from app.core.logger import setup_logger

logger = setup_logger("app.ui.backtest")

IST = pytz.timezone("Asia/Kolkata")


def _ist(ts) -> str:
    try:
        if hasattr(ts, "tz_convert"):
            return ts.tz_convert(IST).strftime("%Y-%m-%d %H:%M")
        return str(ts)
    except Exception:
        return str(ts)


# ── Metric card widget ─────────────────────────────────────────────────────

def _card(title: str, value: str, positive=None) -> QFrame:
    frame = QFrame()
    frame.setFrameShape(QFrame.StyledPanel)
    frame.setStyleSheet("""
        QFrame {
            background: #1a1a2e;
            border: 1px solid #2a2a4a;
            border-radius: 8px;
        }
    """)
    lay = QVBoxLayout(frame)
    lay.setSpacing(2)
    lay.setContentsMargins(10, 8, 10, 8)

    t = QLabel(title)
    t.setStyleSheet("color: #666; font-size: 10px; font-weight: bold; text-transform: uppercase;")
    lay.addWidget(t)

    v = QLabel(value)
    color = "#e0e0e0"
    if positive is True:
        color = "#00d26a"
    elif positive is False:
        color = "#ff4757"
    v.setStyleSheet(f"color: {color}; font-size: 15px; font-weight: bold;")
    lay.addWidget(v)
    return frame


# ── Main backtest widget ───────────────────────────────────────────────────

class BacktestUI(QWidget):
    # Emit signals + df so the Chart tab can overlay markers
    backtest_done = Signal(object, object)   # (signals_list, dataframe)

    def __init__(self):
        super().__init__()
        self.engine = StrategyEngine()
        self.strategy = None
        self.data_df = None
        self.data_cache = {}
        self._last_result = None
        self._last_signals = []

        self._build_ui()

    # ── UI construction ────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(6)

        # ── Strategy row ─────────────────────────────────────────────────
        strat_row = QHBoxLayout()
        self.btn_load_strat = QPushButton("📂  Load Strategy JSON")
        self.btn_load_strat.setFixedHeight(32)
        self.btn_load_strat.clicked.connect(self.load_strategy)
        self.strat_label = QLabel("Strategy: None")
        self.strat_label.setStyleSheet("color: #aaa; font-style: italic;")
        strat_row.addWidget(self.btn_load_strat)
        strat_row.addWidget(self.strat_label)
        strat_row.addStretch()
        root.addLayout(strat_row)

        # ── Data Source ───────────────────────────────────────────────────
        source_group = QGroupBox("DATA SOURCE")
        source_row = QHBoxLayout(source_group)
        self.radio_csv = QRadioButton("CSV File")
        self.radio_mt5 = QRadioButton("MT5 Terminal (Live Historical)")
        self.radio_mt5.setChecked(True)
        source_row.addWidget(self.radio_csv)
        source_row.addWidget(self.radio_mt5)
        source_row.addStretch()
        root.addWidget(source_group)

        # ── Stacked: CSV vs MT5 ───────────────────────────────────────────
        self.stacked = QStackedWidget()

        # CSV page
        csv_page = QWidget()
        csv_layout = QHBoxLayout(csv_page)
        self.btn_load_csv = QPushButton("📂  Load CSV Data")
        self.btn_load_csv.clicked.connect(self.load_csv)
        self.csv_label = QLabel("No file loaded")
        self.csv_label.setStyleSheet("color: #aaa; font-style: italic;")
        csv_layout.addWidget(self.btn_load_csv)
        csv_layout.addWidget(self.csv_label)
        csv_layout.addStretch()

        # MT5 page
        mt5_page = QWidget()
        mt5_grid = QGridLayout(mt5_page)
        mt5_grid.setSpacing(6)

        self.conn_label = QLabel("○  Not Connected")
        self.conn_label.setStyleSheet("color: #ff4757; font-weight: bold;")
        self.btn_connect = QPushButton("Connect MT5")
        self.btn_connect.setFixedWidth(120)
        self.btn_connect.clicked.connect(self.connect_mt5)

        mt5_grid.addWidget(self.conn_label, 0, 0)
        mt5_grid.addWidget(self.btn_connect, 0, 1)

        mt5_grid.addWidget(QLabel("Symbol:"), 1, 0)
        self.cb_symbol = QComboBox()
        self.cb_symbol.setEditable(True)
        self.cb_symbol.addItems(["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "BTCUSD", "US30", "NAS100"])
        mt5_grid.addWidget(self.cb_symbol, 1, 1)

        mt5_grid.addWidget(QLabel("Timeframe:"), 2, 0)
        self.cb_tf = QComboBox()
        self.cb_tf.addItems(["M1", "M5", "M15", "M30", "H1", "H4", "D1"])
        mt5_grid.addWidget(self.cb_tf, 2, 1)

        mt5_grid.addWidget(QLabel("Period:"), 3, 0)
        self.cb_period = QComboBox()
        self.cb_period.addItems([
            "Last 1 Day", "Last 3 Days", "Last 5 Days", "Last 7 Days",
            "Last 14 Days", "Last 30 Days"
        ])
        self.cb_period.setCurrentText("Last 5 Days")
        mt5_grid.addWidget(self.cb_period, 3, 1)

        self.btn_fetch = QPushButton("⬇  FETCH MT5 DATA")
        self.btn_fetch.setFixedHeight(30)
        self.btn_fetch.clicked.connect(self.fetch_mt5_data)
        self.fetch_label = QLabel("No data fetched")
        self.fetch_label.setStyleSheet("color: #aaa; font-style: italic;")
        mt5_grid.addWidget(self.btn_fetch, 4, 0)
        mt5_grid.addWidget(self.fetch_label, 4, 1)
        mt5_grid.setColumnStretch(2, 1)

        self.stacked.addWidget(csv_page)
        self.stacked.addWidget(mt5_page)
        self.stacked.setCurrentIndex(1)
        root.addWidget(self.stacked)

        self.radio_csv.toggled.connect(self._toggle_source)

        # ── Simulation params ─────────────────────────────────────────────
        risk_group = QGroupBox("SIMULATION PARAMETERS")
        risk_row = QHBoxLayout(risk_group)

        risk_row.addWidget(QLabel("Initial Balance ($):"))
        self.spin_balance = QDoubleSpinBox()
        self.spin_balance.setRange(100, 10_000_000)
        self.spin_balance.setValue(10000)
        self.spin_balance.setSingleStep(1000)
        risk_row.addWidget(self.spin_balance)

        risk_row.addWidget(QLabel("Lot Size:"))
        self.spin_lot = QDoubleSpinBox()
        self.spin_lot.setRange(0.01, 100)
        self.spin_lot.setValue(0.01)
        self.spin_lot.setSingleStep(0.01)
        self.spin_lot.setDecimals(2)
        risk_row.addWidget(self.spin_lot)

        risk_row.addWidget(QLabel("SL (pips, 0=off):"))
        self.spin_sl = QSpinBox()
        self.spin_sl.setRange(0, 5000)
        self.spin_sl.setValue(50)
        risk_row.addWidget(self.spin_sl)

        risk_row.addWidget(QLabel("TP (pips, 0=off):"))
        self.spin_tp = QSpinBox()
        self.spin_tp.setRange(0, 5000)
        self.spin_tp.setValue(100)
        risk_row.addWidget(self.spin_tp)

        self.chk_incomplete = QCheckBox("Include current incomplete candle")
        risk_row.addWidget(self.chk_incomplete)
        risk_row.addStretch()
        root.addWidget(risk_group)

        # ── Run + Export ──────────────────────────────────────────────────
        run_row = QHBoxLayout()
        run_row.addStretch()

        self.btn_export_results = QPushButton("💾  Export Results CSV")
        self.btn_export_results.setEnabled(False)
        self.btn_export_results.clicked.connect(self._export_results)
        run_row.addWidget(self.btn_export_results)

        self.btn_view_chart = QPushButton("📊  View on Chart")
        self.btn_view_chart.setEnabled(False)
        self.btn_view_chart.clicked.connect(self._send_to_chart)
        run_row.addWidget(self.btn_view_chart)

        self.btn_run = QPushButton("▶  RUN BACKTEST")
        self.btn_run.setMinimumHeight(38)
        self.btn_run.setMinimumWidth(160)
        self.btn_run.setStyleSheet("""
            QPushButton {
                background: #0f3460; color: white;
                font-weight: bold; font-size: 14px;
                border-radius: 6px; border: 1px solid #1a4a8a;
            }
            QPushButton:hover { background: #1a4a8a; }
        """)
        self.btn_run.clicked.connect(self.run_backtest)
        run_row.addWidget(self.btn_run)
        root.addLayout(run_row)

        # ── Results tabs ──────────────────────────────────────────────────
        results_tabs = QTabWidget()

        # Tab 1: Metrics
        metrics_tab = QWidget()
        self.metrics_layout = QGridLayout(metrics_tab)
        self.metrics_layout.setSpacing(8)
        results_tabs.addTab(metrics_tab, "📈 Metrics")

        # Tab 2: Trade Log
        trades_tab = QWidget()
        trades_lay = QVBoxLayout(trades_tab)
        self.trade_table = QTableWidget()
        self.trade_table.setColumnCount(9)
        self.trade_table.setHorizontalHeaderLabels([
            "Entry Time (IST)", "Exit Time (IST)", "Dir",
            "Entry Price", "Exit Price", "Lots",
            "Profit", "Balance", "Reason"
        ])
        self.trade_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.trade_table.setAlternatingRowColors(True)
        self.trade_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.trade_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.trade_table.cellClicked.connect(self._on_trade_clicked)
        trades_lay.addWidget(self.trade_table)
        results_tabs.addTab(trades_tab, "📋 Trade Log")

        # Tab 3: Signal Inspector
        signal_tab = QWidget()
        signal_lay = QVBoxLayout(signal_tab)
        signal_lay.addWidget(QLabel("All signals generated (including those without a trade exit):"))
        self.signal_table = QTableWidget()
        self.signal_table.setColumnCount(5)
        self.signal_table.setHorizontalHeaderLabels([
            "Index", "Time (IST)", "Price", "Direction", "Conditions Met"
        ])
        self.signal_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.signal_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.signal_table.setAlternatingRowColors(True)
        self.signal_table.setEditTriggers(QTableWidget.NoEditTriggers)
        signal_lay.addWidget(self.signal_table)
        results_tabs.addTab(signal_tab, "🔍 All Signals")

        # Tab 4: Debug log
        log_tab = QWidget()
        log_lay = QVBoxLayout(log_tab)
        self.log_out = QTextEdit()
        self.log_out.setReadOnly(True)
        self.log_out.setStyleSheet("font-family: monospace; font-size: 11px; color: #aaa;")
        log_lay.addWidget(self.log_out)
        results_tabs.addTab(log_tab, "🖥 Log")

        root.addWidget(results_tabs, 1)

        # ── Trade detail panel ────────────────────────────────────────────
        self.detail_group = QGroupBox("TRADE / SIGNAL DETAIL  — click any row")
        detail_lay = QVBoxLayout(self.detail_group)
        self.lbl_detail = QLabel("Select a row above to inspect the exact conditions that generated it.")
        self.lbl_detail.setWordWrap(True)
        self.lbl_detail.setStyleSheet("color:#aaa; font-family:monospace; font-size:11px;")
        detail_lay.addWidget(self.lbl_detail)
        self.detail_group.setMaximumHeight(140)
        root.addWidget(self.detail_group)

        self._update_mt5_status()

    # ── Helpers ────────────────────────────────────────────────────────────

    def _toggle_source(self):
        self.stacked.setCurrentIndex(0 if self.radio_csv.isChecked() else 1)
        if not self.radio_csv.isChecked():
            self._update_mt5_status()

    def _update_mt5_status(self):
        if mt5_provider.is_connected():
            self.conn_label.setText("●  Connected")
            self.conn_label.setStyleSheet("color: #00d26a; font-weight: bold;")
            self.btn_connect.setEnabled(False)
        else:
            self.conn_label.setText("○  Not Connected")
            self.conn_label.setStyleSheet("color: #ff4757; font-weight: bold;")
            self.btn_connect.setEnabled(True)

    def _clear_metrics(self):
        while self.metrics_layout.count():
            item = self.metrics_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _show_metrics(self, summary: dict):
        self._clear_metrics()
        pf = summary['profit_factor']
        pf_ok = (pf != "∞" and float(str(pf)) >= 1) if pf != "∞" else True
        items = [
            ("Net Profit",       f"${summary['net_profit']:,.2f}",       summary['net_profit'] >= 0),
            ("Final Balance",    f"${summary['final_balance']:,.2f}",     summary['final_balance'] >= summary['initial_balance']),
            ("Total Trades",     str(summary['total_trades']),             None),
            ("Win Rate",         f"{summary['win_rate_pct']}%",           summary['win_rate_pct'] >= 50),
            ("Profit Factor",    str(pf),                                  pf_ok),
            ("Max Drawdown",     f"{summary['max_drawdown_pct']}%",       summary['max_drawdown_pct'] < 20),
            ("Gross Profit",     f"${summary['gross_profit']:,.2f}",      True),
            ("Gross Loss",       f"${summary['gross_loss']:,.2f}",        False),
            ("Avg Win",          f"${summary['avg_profit']:,.2f}",        True),
            ("Avg Loss",         f"${summary['avg_loss']:,.2f}",          False),
            ("Largest Win",      f"${summary['largest_win']:,.2f}",       True),
            ("Largest Loss",     f"${summary['largest_loss']:,.2f}",      False),
        ]
        for i, (title, val, pos) in enumerate(items):
            card = _card(title, val, pos)
            self.metrics_layout.addWidget(card, i // 4, i % 4)

    def _show_trades(self, trades: list, direction: str):
        self.trade_table.setRowCount(len(trades))
        for row, t in enumerate(trades):
            profit = t["profit"]
            row_color = QColor("#0d2b1a") if profit > 0 else QColor("#2b0d0d")
            cells = [
                _ist(t["entry_time"]),
                _ist(t["exit_time"]),
                t["direction"],
                f"{t['entry_price']:,.5f}",
                f"{t['exit_price']:,.5f}",
                str(t["lots"]),
                f"{'+' if profit >= 0 else ''}{profit:.2f}",
                f"{t['balance']:,.2f}",
                t["reason"]
            ]
            for col, val in enumerate(cells):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignCenter)
                item.setBackground(row_color)
                if col == 6:
                    item.setForeground(QColor("#00d26a") if profit > 0 else QColor("#ff4757"))
                    item.setFont(QFont("Segoe UI", 9, QFont.Bold))
                if col == 2:
                    item.setForeground(QColor("#00d26a") if t["direction"] == "BUY" else QColor("#ff4757"))
                self.trade_table.setItem(row, col, item)

    def _show_signals(self, signals: list, direction: str):
        self.signal_table.setRowCount(len(signals))
        for row, sig in enumerate(signals):
            cells = [
                str(sig["index"]),
                _ist(sig.get("timestamp", "")),
                f"{sig['price']:,.5f}",
                direction,
                " | ".join(sig.get("debug", [])[:3])
            ]
            color = QColor("#00d26a") if direction == "BUY" else QColor("#ff4757")
            for col, val in enumerate(cells):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignCenter)
                if col == 3:
                    item.setForeground(color)
                self.signal_table.setItem(row, col, item)

    def _on_trade_clicked(self, row: int, _col: int):
        if self._last_result:
            trades = self._last_result["trades"]
            if row < len(trades):
                t = trades[row]
                # Find matching signal for debug info
                sig_idx = t.get("signal_index")
                debug_lines = []
                for sig in self._last_signals:
                    if sig["index"] == sig_idx:
                        debug_lines = sig.get("debug", [])
                        break
                profit = t["profit"]
                lines = [
                    f"  Entry: {_ist(t['entry_time'])}  @  {t['entry_price']:,.5f}",
                    f"  Exit:  {_ist(t['exit_time'])}  @  {t['exit_price']:,.5f}  ({t['reason']})",
                    f"  P&L:   {'+'if profit>=0 else ''}{profit:.2f}  |  Balance after: {t['balance']:,.2f}",
                ]
                if debug_lines:
                    lines += ["", "  Signal conditions:"] + [f"    ✓ {d}" for d in debug_lines]
                self.lbl_detail.setText("\n".join(lines))

    # ── Actions ────────────────────────────────────────────────────────────

    def connect_mt5(self):
        if mt5_provider.connect():
            self._update_mt5_status()
            symbols = mt5_provider.get_symbols()
            if symbols:
                current = self.cb_symbol.currentText()
                existing = [self.cb_symbol.itemText(i) for i in range(self.cb_symbol.count())]
                all_syms = sorted(set(existing + symbols))
                self.cb_symbol.clear()
                self.cb_symbol.addItems(all_syms)
                self.cb_symbol.setCurrentText(current)
            self.log_out.append("✅ MT5 connected successfully.")
        else:
            QMessageBox.critical(self, "MT5 Error",
                "Could not connect to MetaTrader 5.\nMake sure the terminal is running.")

    def load_strategy(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Open Strategy JSON", "", "JSON Files (*.json)")
        if not filepath:
            return
        try:
            with open(filepath, encoding='utf-8-sig') as f:
                self.strategy = json.load(f)
            name = self.strategy.get("name", "Unknown")
            ver  = self.strategy.get("version", 1)
            sym  = self.strategy.get("symbol", "XAUUSD")
            tf   = self.strategy.get("timeframe", "M1")
            self.strat_label.setText(f"Strategy: {name} v{ver}  |  {sym} {tf}")
            self.strat_label.setStyleSheet("color: #00d26a; font-weight: bold;")
            if sym:
                self.cb_symbol.setCurrentText(sym)
            if tf in ["M1", "M5", "M15", "M30", "H1", "H4", "D1"]:
                self.cb_tf.setCurrentText(tf)
            self.log_out.append(f"✅ Loaded strategy: {name} v{ver}")
        except Exception as e:
            QMessageBox.warning(self, "Load Error", f"Could not load strategy:\n{e}")

    def load_csv(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Open CSV Data", "", "CSV Files (*.csv)")
        if not filepath:
            return
        try:
            df = pd.read_csv(filepath)
            if "timestamp" in df.columns:
                df["time"] = pd.to_datetime(df["timestamp"])
            elif "time" in df.columns:
                df["time"] = pd.to_datetime(df["time"])
            # Normalise column names to lowercase
            df.columns = [c.lower() for c in df.columns]
            self.data_df = df
            self.csv_label.setText(f"{Path(filepath).name}  ({len(df):,} bars)")
            self.csv_label.setStyleSheet("color: #00d26a;")
            self.log_out.append(f"✅ Loaded CSV: {Path(filepath).name} ({len(df):,} rows)")
        except Exception as e:
            QMessageBox.warning(self, "Load Error", f"Could not load CSV:\n{e}")

    def fetch_mt5_data(self):
        if not mt5_provider.is_connected():
            if not mt5_provider.connect():
                QMessageBox.warning(self, "MT5 Error", "MT5 Terminal is not connected.")
                return
            self._update_mt5_status()

        symbol     = self.cb_symbol.currentText().strip()
        timeframe  = self.cb_tf.currentText()
        period_txt = self.cb_period.currentText()
        days_map   = {
            "Last 1 Day": 1, "Last 3 Days": 3, "Last 5 Days": 5,
            "Last 7 Days": 7, "Last 14 Days": 14, "Last 30 Days": 30
        }
        days      = days_map.get(period_txt, 5)
        cache_key = f"{symbol}_{timeframe}_{days}"

        if cache_key in self.data_cache:
            self.data_df = self.data_cache[cache_key]
            self.fetch_label.setText(
                f"{symbol} {timeframe}  |  {len(self.data_df):,} bars (cached)")
            self.log_out.append(f"📦 Using cached data: {cache_key}")
            return

        self.btn_fetch.setText("⬇  Fetching…")
        self.btn_fetch.setEnabled(False)
        QApplication.processEvents()

        try:
            df = mt5_provider.get_recent_rates(symbol, timeframe, days)
            if df is None or df.empty:
                QMessageBox.warning(self, "No Data",
                    f"MT5 returned 0 bars for {symbol} {timeframe}.\n\n"
                    "Possible causes:\n"
                    "  • Market is closed / holiday\n"
                    "  • Symbol name differs at your broker\n"
                    "  • Not enough history in MT5 terminal")
            else:
                if not self.chk_incomplete.isChecked():
                    df = df.iloc[:-1].copy()
                self.data_df = df
                self.data_cache[cache_key] = df
                start = _ist(df.iloc[0]["time"])
                end   = _ist(df.iloc[-1]["time"])
                self.fetch_label.setText(
                    f"{symbol} {timeframe}  |  {len(df):,} bars  |  {start} → {end}")
                self.fetch_label.setStyleSheet("color: #00d26a;")
                self.log_out.append(
                    f"✅ Fetched {len(df):,} bars of {symbol} {timeframe} ({days}d)\n"
                    f"   Range: {start} → {end}")
        except Exception as e:
            QMessageBox.critical(self, "Fetch Error", str(e))
        finally:
            self.btn_fetch.setText("⬇  FETCH MT5 DATA")
            self.btn_fetch.setEnabled(True)

    def run_backtest(self):
        if not self.strategy:
            QMessageBox.warning(self, "Missing Strategy", "Load a Strategy JSON first.")
            return
        if self.data_df is None or self.data_df.empty:
            QMessageBox.warning(self, "Missing Data",
                "Load CSV data or fetch MT5 data first.")
            return

        source = "MT5" if self.radio_mt5.isChecked() else "CSV"
        df = self.data_df.copy()

        self.log_out.clear()
        self.log_out.append(
            f"▶ Running: {self.strategy.get('name')} | {source} | {len(df):,} candles")

        try:
            result = self.engine.run_backtest(
                self.strategy, df,
                initial_balance=self.spin_balance.value(),
                lot_size=self.spin_lot.value(),
                sl_pips=self.spin_sl.value(),
                tp_pips=self.spin_tp.value()
            )
            self._last_result  = result
            self._last_signals = result.get("signals", [])
            summary = result["summary"]
            trades  = result["trades"]
            direction = self.strategy.get("direction", "BUY")

            self._show_metrics(summary)
            self._show_trades(trades, direction)
            self._show_signals(self._last_signals, direction)

            self.log_out.append(
                f"✅ Done.\n"
                f"   Candles: {len(df):,}  |  Signals: {summary['signals_total']}\n"
                f"   Trades:  {summary['total_trades']}  |  Win Rate: {summary['win_rate_pct']}%\n"
                f"   Net P&L: ${summary['net_profit']:,.2f}  |  "
                f"Max DD: {summary['max_drawdown_pct']}%"
            )

            if summary["signals_total"] == 0:
                self.log_out.append(
                    "\n⚠ 0 signals generated.\n"
                    "Tips:\n"
                    "  1. Make sure the strategy 'field' matches a column in your data\n"
                    "  2. Try a larger date range (more bars = more signals)\n"
                    "  3. Check that your strategy conditions are not too strict"
                )

            self.btn_export_results.setEnabled(True)
            self.btn_view_chart.setEnabled(len(self._last_signals) > 0)

            # Notify chart tab
            self.backtest_done.emit(self._last_signals, df)

        except Exception as e:
            self.log_out.append(f"❌ Backtest error: {e}")
            QMessageBox.critical(self, "Backtest Error", str(e))
            logger.exception("Backtest error")

    def _export_results(self):
        if not self._last_result:
            return
        fp, _ = QFileDialog.getSaveFileName(
            self, "Export Results", "backtest_results.csv", "CSV Files (*.csv)")
        if not fp:
            return
        try:
            trades = self._last_result["trades"]
            with open(fp, "w", newline="") as f:
                if trades:
                    writer = csv.DictWriter(f, fieldnames=trades[0].keys())
                    writer.writeheader()
                    writer.writerows(trades)
                else:
                    f.write("No trades\n")
            QMessageBox.information(self, "Exported", f"Trade log saved to:\n{fp}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    def _send_to_chart(self):
        if self._last_signals and self.data_df is not None:
            self.backtest_done.emit(self._last_signals, self.data_df)
            QMessageBox.information(self, "Chart Updated",
                "Signal markers sent to Chart tab.\nSwitch to the Chart tab to view.")

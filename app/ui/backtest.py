import json
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone, timedelta

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QFileDialog, QTextEdit, QMessageBox, QRadioButton,
    QGroupBox, QStackedWidget, QGridLayout, QCheckBox, QSplitter,
    QTableWidget, QTableWidgetItem, QHeaderView, QDoubleSpinBox, QSpinBox,
    QFrame, QScrollArea
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor

from app.core.strategy_engine import StrategyEngine
from app.core.mt5_provider import provider as mt5_provider


def _card(title: str, value: str, positive: bool = None) -> QFrame:
    """Create a metric card widget."""
    frame = QFrame()
    frame.setFrameShape(QFrame.StyledPanel)
    frame.setStyleSheet("""
        QFrame { 
            background: #1a1a2e; 
            border: 1px solid #333; 
            border-radius: 6px; 
            padding: 4px;
        }
    """)
    layout = QVBoxLayout(frame)
    layout.setSpacing(2)
    layout.setContentsMargins(8, 6, 8, 6)

    title_lbl = QLabel(title)
    title_lbl.setStyleSheet("color: #888; font-size: 10px; font-weight: bold;")
    layout.addWidget(title_lbl)

    val_lbl = QLabel(value)
    color = "#ffffff"
    if positive is True:
        color = "#00d26a"
    elif positive is False:
        color = "#ff4757"
    val_lbl.setStyleSheet(f"color: {color}; font-size: 14px; font-weight: bold;")
    layout.addWidget(val_lbl)
    return frame


class BacktestUI(QWidget):
    def __init__(self):
        super().__init__()

        self.engine = StrategyEngine()
        self.strategy = None
        self.data_df = None
        self.data_cache = {}
        self._last_result = None

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(6)

        # ── Strategy row ────────────────────────────────────────────────
        strat_row = QHBoxLayout()
        self.btn_load_strat = QPushButton("📂  Load Strategy JSON")
        self.btn_load_strat.setFixedHeight(32)
        self.btn_load_strat.clicked.connect(self.load_strategy)
        self.strat_label = QLabel("Strategy: None")
        self.strat_label.setStyleSheet("color: #aaa; font-style: italic;")
        strat_row.addWidget(self.btn_load_strat)
        strat_row.addWidget(self.strat_label)
        strat_row.addStretch()
        main_layout.addLayout(strat_row)

        # ── Data Source ──────────────────────────────────────────────────
        source_group = QGroupBox("DATA SOURCE")
        source_row = QHBoxLayout(source_group)
        self.radio_csv = QRadioButton("CSV File")
        self.radio_mt5 = QRadioButton("MT5 Terminal (Live Historical)")
        self.radio_csv.setChecked(True)
        source_row.addWidget(self.radio_csv)
        source_row.addWidget(self.radio_mt5)
        source_row.addStretch()
        main_layout.addWidget(source_group)

        # ── Stacked: CSV vs MT5 ─────────────────────────────────────────
        self.stacked = QStackedWidget()

        # -- CSV page --
        csv_page = QWidget()
        csv_layout = QHBoxLayout(csv_page)
        self.btn_load_csv = QPushButton("📂  Load CSV Data")
        self.btn_load_csv.clicked.connect(self.load_csv)
        self.csv_label = QLabel("No file loaded")
        self.csv_label.setStyleSheet("color: #aaa; font-style: italic;")
        csv_layout.addWidget(self.btn_load_csv)
        csv_layout.addWidget(self.csv_label)
        csv_layout.addStretch()

        # -- MT5 page --
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
        main_layout.addWidget(self.stacked)

        self.radio_csv.toggled.connect(self._toggle_source)
        self.radio_mt5.toggled.connect(self._toggle_source)

        # ── Risk / Simulation params ─────────────────────────────────────
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
        self.spin_sl.setValue(0)
        risk_row.addWidget(self.spin_sl)

        risk_row.addWidget(QLabel("TP (pips, 0=off):"))
        self.spin_tp = QSpinBox()
        self.spin_tp.setRange(0, 5000)
        self.spin_tp.setValue(0)
        risk_row.addWidget(self.spin_tp)

        self.chk_incomplete = QCheckBox("Include current incomplete candle")
        risk_row.addWidget(self.chk_incomplete)
        risk_row.addStretch()
        main_layout.addWidget(risk_group)

        # ── Run Button ───────────────────────────────────────────────────
        run_row = QHBoxLayout()
        self.btn_run = QPushButton("▶  RUN BACKTEST")
        self.btn_run.setMinimumHeight(38)
        self.btn_run.setStyleSheet("""
            QPushButton {
                background: #0f3460;
                color: white;
                font-weight: bold;
                font-size: 14px;
                border-radius: 6px;
                border: 1px solid #16213e;
            }
            QPushButton:hover { background: #16213e; }
        """)
        self.btn_run.clicked.connect(self.run_backtest)
        run_row.addStretch()
        run_row.addWidget(self.btn_run)
        main_layout.addLayout(run_row)

        # ── Results area ─────────────────────────────────────────────────
        splitter = QSplitter(Qt.Vertical)

        # Metrics cards
        self.metrics_widget = QWidget()
        self.metrics_layout = QGridLayout(self.metrics_widget)
        self.metrics_layout.setSpacing(6)
        splitter.addWidget(self.metrics_widget)

        # Trade log table
        self.trade_table = QTableWidget()
        self.trade_table.setColumnCount(9)
        self.trade_table.setHorizontalHeaderLabels([
            "Entry Time", "Exit Time", "Dir", "Entry Price", "Exit Price",
            "Lots", "Profit", "Balance", "Reason"
        ])
        self.trade_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.trade_table.setAlternatingRowColors(True)
        self.trade_table.setEditTriggers(QTableWidget.NoEditTriggers)
        splitter.addWidget(self.trade_table)

        # Log / debug output
        self.log_out = QTextEdit()
        self.log_out.setReadOnly(True)
        self.log_out.setMaximumHeight(120)
        self.log_out.setStyleSheet("font-family: monospace; font-size: 11px; color: #aaa;")
        splitter.addWidget(self.log_out)

        splitter.setSizes([180, 300, 100])
        main_layout.addWidget(splitter)

        self._update_mt5_status()

    # ── Helpers ──────────────────────────────────────────────────────────

    def _toggle_source(self):
        if self.radio_csv.isChecked():
            self.stacked.setCurrentIndex(0)
        else:
            self.stacked.setCurrentIndex(1)
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
        items = [
            ("Net Profit",    f"${summary['net_profit']:,.2f}",    summary['net_profit'] >= 0),
            ("Final Balance", f"${summary['final_balance']:,.2f}", summary['final_balance'] >= summary['initial_balance']),
            ("Total Trades",  str(summary['total_trades']),         None),
            ("Win Rate",      f"{summary['win_rate_pct']}%",        summary['win_rate_pct'] >= 50),
            ("Profit Factor", str(summary['profit_factor']),        summary['profit_factor'] != "∞" and float(str(summary['profit_factor'])) >= 1 if summary['profit_factor'] != "∞" else True),
            ("Max Drawdown",  f"{summary['max_drawdown_pct']}%",    summary['max_drawdown_pct'] < 20),
            ("Gross Profit",  f"${summary['gross_profit']:,.2f}",   True),
            ("Gross Loss",    f"${summary['gross_loss']:,.2f}",     False),
            ("Avg Win",       f"${summary['avg_profit']:,.2f}",     True),
            ("Avg Loss",      f"${summary['avg_loss']:,.2f}",       False),
            ("Largest Win",   f"${summary['largest_win']:,.2f}",    True),
            ("Largest Loss",  f"${summary['largest_loss']:,.2f}",   False),
        ]
        for i, (title, val, pos) in enumerate(items):
            card = _card(title, val, pos)
            self.metrics_layout.addWidget(card, i // 4, i % 4)

    def _show_trades(self, trades: list):
        self.trade_table.setRowCount(len(trades))
        for row, t in enumerate(trades):
            profit = t["profit"]
            color = QColor("#00d26a") if profit > 0 else QColor("#ff4757")
            cells = [
                t["entry_time"], t["exit_time"], t["direction"],
                f"{t['entry_price']:.5f}", f"{t['exit_price']:.5f}",
                str(t["lots"]),
                f"{'+' if profit >= 0 else ''}{profit:.2f}",
                f"{t['balance']:.2f}",
                t["reason"]
            ]
            for col, val in enumerate(cells):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignCenter)
                if col == 6:  # profit column
                    item.setForeground(color)
                self.trade_table.setItem(row, col, item)

    # ── Actions ──────────────────────────────────────────────────────────

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
            QMessageBox.critical(self, "MT5 Error", "Could not connect to MetaTrader 5.\nMake sure the terminal is running.")

    def load_strategy(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Open Strategy JSON", "", "JSON Files (*.json)")
        if not filepath:
            return
        try:
            with open(filepath, "r") as f:
                self.strategy = json.load(f)
            name = self.strategy.get("name", "Unknown")
            ver = self.strategy.get("version", 1)
            sym = self.strategy.get("symbol", "XAUUSD")
            tf = self.strategy.get("timeframe", "M1")
            self.strat_label.setText(f"Strategy: {name} v{ver}  |  {sym} {tf}")
            self.strat_label.setStyleSheet("color: #00d26a; font-weight: bold;")
            self.cb_symbol.setCurrentText(sym)
            if tf in ["M1", "M5", "M15", "M30", "H1", "H4", "D1"]:
                self.cb_tf.setCurrentText(tf)
            self.log_out.append(f"✅ Loaded strategy: {name} v{ver}")
        except Exception as e:
            QMessageBox.warning(self, "Load Error", f"Could not load strategy:\n{e}")

    def load_csv(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Open CSV Data", "", "CSV Files (*.csv)")
        if not filepath:
            return
        try:
            df = pd.read_csv(filepath)
            if "timestamp" in df.columns:
                df["time"] = pd.to_datetime(df["timestamp"])
            elif "time" in df.columns:
                df["time"] = pd.to_datetime(df["time"])
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

        symbol = self.cb_symbol.currentText().strip()
        timeframe = self.cb_tf.currentText()
        period_text = self.cb_period.currentText()

        days_map = {
            "Last 1 Day": 1, "Last 3 Days": 3, "Last 5 Days": 5,
            "Last 7 Days": 7, "Last 14 Days": 14, "Last 30 Days": 30
        }
        days = days_map.get(period_text, 5)
        cache_key = f"{symbol}_{timeframe}_{days}"

        if cache_key in self.data_cache:
            self.data_df = self.data_cache[cache_key]
            self.fetch_label.setText(f"{symbol} {timeframe}  |  {len(self.data_df):,} bars (cached)")
            self.log_out.append(f"📦 Using cached data: {cache_key}")
            return

        self.btn_fetch.setText("⬇  Fetching…")
        self.btn_fetch.setEnabled(False)

        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()

        try:
            df = mt5_provider.get_recent_rates(symbol, timeframe, days)
            if df is None or df.empty:
                QMessageBox.warning(self, "No Data",
                    f"MT5 returned 0 bars for {symbol} {timeframe}.\n"
                    "Possible causes:\n"
                    "• Market is closed / holiday\n"
                    "• Symbol name differs at your broker\n"
                    "• Not enough history loaded in MT5 terminal")
            else:
                if not self.chk_incomplete.isChecked():
                    df = df.iloc[:-1].copy()  # Drop last possibly incomplete bar
                self.data_df = df
                self.data_cache[cache_key] = df
                start = df.iloc[0]["time"].strftime("%Y-%m-%d %H:%M")
                end = df.iloc[-1]["time"].strftime("%Y-%m-%d %H:%M")
                self.fetch_label.setText(f"{symbol} {timeframe}  |  {len(df):,} bars  |  {start} → {end}")
                self.fetch_label.setStyleSheet("color: #00d26a;")
                self.log_out.append(f"✅ Fetched {len(df):,} bars of {symbol} {timeframe} ({days}d)")
        except Exception as e:
            QMessageBox.critical(self, "Fetch Error", str(e))
            self.log_out.append(f"❌ Fetch error: {e}")
        finally:
            self.btn_fetch.setText("⬇  FETCH MT5 DATA")
            self.btn_fetch.setEnabled(True)

    def run_backtest(self):
        if not self.strategy:
            QMessageBox.warning(self, "Missing Strategy", "Please load a Strategy JSON first.")
            return
        if self.data_df is None or self.data_df.empty:
            QMessageBox.warning(self, "Missing Data", "Please load CSV or fetch MT5 data first.")
            return

        source = "MT5 Terminal" if self.radio_mt5.isChecked() else "CSV"
        df = self.data_df.copy()

        self.log_out.clear()
        self.log_out.append(f"▶ Running backtest: {self.strategy.get('name')} | {source} | {len(df):,} candles")

        try:
            result = self.engine.run_backtest(
                self.strategy, df,
                initial_balance=self.spin_balance.value(),
                lot_size=self.spin_lot.value(),
                sl_pips=self.spin_sl.value(),
                tp_pips=self.spin_tp.value()
            )
            self._last_result = result
            summary = result["summary"]
            trades = result["trades"]

            self._show_metrics(summary)
            self._show_trades(trades)

            # Log summary
            self.log_out.append(
                f"✅ Done. Signals: {summary['signals_total']}  |  "
                f"Trades: {summary['total_trades']}  |  "
                f"Net P&L: ${summary['net_profit']:,.2f}  |  "
                f"Win Rate: {summary['win_rate_pct']}%"
            )

            if summary["total_trades"] == 0 and summary["signals_total"] > 0:
                self.log_out.append(
                    "⚠ Signals generated but no trades simulated "
                    "(likely due to signals on the last bar with no exit candle)."
                )
            elif summary["signals_total"] == 0:
                self.log_out.append(
                    "⚠ 0 signals generated. Check your strategy conditions against the loaded data."
                )

        except Exception as e:
            self.log_out.append(f"❌ Backtest error: {e}")
            QMessageBox.critical(self, "Backtest Error", str(e))

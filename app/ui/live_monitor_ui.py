"""
Live Monitor UI — real-time strategy signal tracking.
Supports monitoring multiple strategies simultaneously.
Each strategy runs in its own QThread and emits signals independently.
"""
import json
import csv
from pathlib import Path
from datetime import datetime, timezone

import pytz

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QMessageBox, QGroupBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QSpinBox, QFrame,
    QComboBox, QSplitter, QTextEdit, QCheckBox, QApplication
)
from PySide6.QtCore import Qt, QTimer, Signal, QObject, QThread
from PySide6.QtGui import QColor, QFont

from app.core.config import config
from app.core.strategy_engine import StrategyEngine
from app.core.mt5_provider import provider as mt5_provider
from app.core.notifier import notifier
from app.core.logger import setup_logger

logger = setup_logger("app.ui.live_monitor")

IST = pytz.timezone("Asia/Kolkata")


def _ist(ts) -> str:
    """Convert a timestamp value to IST string."""
    try:
        if hasattr(ts, "tz_convert"):
            return ts.tz_convert(IST).strftime("%Y-%m-%d %H:%M:%S IST")
        if hasattr(ts, "timestamp"):
            import pytz
            utc = pytz.utc.localize(ts) if ts.tzinfo is None else ts
            return utc.astimezone(IST).strftime("%Y-%m-%d %H:%M:%S IST")
        return str(ts)
    except Exception:
        return str(ts)


# ────────────────────────────────────────────────────────────────
# Background worker
# ────────────────────────────────────────────────────────────────

UTC = timezone.utc


def _is_market_closed() -> bool:
    """XAUUSD: closed Friday 21:00 UTC → Sunday 21:00 UTC."""
    now = datetime.now(UTC)
    wd, h = now.weekday(), now.hour
    return ((wd == 4 and h >= 21) or wd == 5 or (wd == 6 and h < 21))


class _MonitorWorker(QObject):
    """
    Runs in a QThread. Polls MT5 for the latest closed candle and evaluates
    ONE strategy. Multiple workers run independently for multi-strategy mode.
    """
    signal_found  = Signal(dict)   # {sig dict + strategy_name}
    status_update = Signal(str)
    candle_checked = Signal(dict)
    error_occurred = Signal(str)

    def __init__(self, strategy: dict, symbol: str, timeframe: str,
                 interval_sec: int):
        super().__init__()
        self.strategy     = strategy
        self.symbol       = symbol
        self.timeframe    = timeframe
        self.interval_sec = interval_sec
        self.engine       = StrategyEngine()
        self._last_ts     = None
        self._running     = False
        self._was_connected = False

    def run(self):
        self._running = True
        name = self.strategy.get('name', '?')
        self.status_update.emit(f"▶ [{name}] Monitoring {self.symbol} {self.timeframe}…")
        while self._running:
            try:
                self._check()
            except Exception as e:
                self.error_occurred.emit(str(e))
            for _ in range(self.interval_sec * 2):
                if not self._running:
                    break
                QThread.msleep(500)

    def stop(self):
        self._running = False

    def _check(self):
        if not mt5_provider.is_connected():
            mt5_provider.connect()
            if not mt5_provider.is_connected():
                if self._was_connected:
                    self.status_update.emit("🔴 MT5_DISCONNECTED — retrying…")
                    self._was_connected = False
                else:
                    self.status_update.emit("⚠ MT5 still disconnected — waiting…")
                return
            else:
                self.status_update.emit("🟢 MT5_RECONNECTED — resuming.")
                self._was_connected = True
        elif not self._was_connected:
            self._was_connected = True

        df = mt5_provider.get_candles(self.symbol, self.timeframe, count=100)
        if df is None or df.empty:
            self.status_update.emit(f"⚠ No data for {self.symbol} {self.timeframe}")
            return

        df = df.iloc[:-1].copy()  # drop incomplete last candle
        if df.empty:
            return

        latest = df.iloc[-1]
        latest_ts = latest["time"]

        self.candle_checked.emit({
            "time": _ist(latest_ts),
            "close": float(latest["close"]),
            "symbol": self.symbol,
            "timeframe": self.timeframe,
        })

        if self._last_ts is not None and latest_ts == self._last_ts:
            return
        self._last_ts = latest_ts

        signals = self.engine.evaluate(self.strategy, df)
        for sig in signals:
            if sig["index"] == len(df) - 1:
                sig["strategy_name"] = self.strategy.get("name", "?")
                self.signal_found.emit(sig)
                break


# ────────────────────────────────────────────────────────────────
# Main UI
# ────────────────────────────────────────────────────────────────

class LiveMonitorUI(QWidget):
    def __init__(self, monitor=None, alerter=None):
        super().__init__()
        self.strategy = None            # primary strategy (legacy)
        self._strategies: list[dict] = []  # multi-strategy list
        self._workers: list[_MonitorWorker] = []
        self._threads: list[QThread] = []
        self._signal_count = 0
        self._journal_tab = None
        self._signal_log_path = Path(
            config.get("data_directory", "data")) / "live_signals.csv"
        self._signals_data: list[dict] = []
        self._build_ui()

    # ── UI Construction ───────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(6)

        # ── Header status bar ────────────────────────────────────
        hdr = QHBoxLayout()
        self.lbl_status = QLabel("⏹  MONITOR STOPPED")
        self.lbl_status.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.lbl_status.setStyleSheet("color: #888;")

        self.lbl_mt5 = QLabel("MT5: ○ Disconnected")
        self.lbl_mt5.setStyleSheet("color: #ff4757; font-weight: bold;")

        hdr.addWidget(self.lbl_status)
        hdr.addStretch()
        hdr.addWidget(self.lbl_mt5)
        root.addLayout(hdr)

        # ── Market closed warning ─────────────────────────────────
        self.lbl_market = QLabel(
            "⚠  MARKET CLOSED  (Saturday 02:30 IST → Monday 02:30 IST) "
            "— Live signals based on stale candle data. Use for backtesting only."
        )
        self.lbl_market.setWordWrap(True)
        self.lbl_market.setStyleSheet(
            "color:#f5a623; background:#1a1200; border:1px solid #3a2a00;"
            "border-radius:4px; padding:5px 10px; font-size:11px;"
        )
        self.lbl_market.setVisible(_is_market_closed())
        root.addWidget(self.lbl_market)

        # ── Strategy & Config ────────────────────────────────────
        cfg_group = QGroupBox("MONITOR CONFIGURATION")
        cfg_lay = QHBoxLayout(cfg_group)

        self.btn_load_strat = QPushButton("📂 Load Strategy")
        self.btn_load_strat.clicked.connect(self._load_strategy)
        self.lbl_strat = QLabel("No strategy loaded")
        self.lbl_strat.setStyleSheet("color: #888; font-style: italic;")

        cfg_lay.addWidget(self.btn_load_strat)
        cfg_lay.addWidget(self.lbl_strat)
        cfg_lay.addStretch()

        cfg_lay.addWidget(QLabel("Symbol:"))
        self.cb_symbol = QComboBox()
        self.cb_symbol.setEditable(True)
        self.cb_symbol.addItems(["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "BTCUSD"])
        self.cb_symbol.setFixedWidth(100)
        cfg_lay.addWidget(self.cb_symbol)

        cfg_lay.addWidget(QLabel("TF:"))
        self.cb_tf = QComboBox()
        self.cb_tf.addItems(["M1", "M5", "M15", "M30", "H1", "H4", "D1"])
        self.cb_tf.setCurrentText("M15")
        self.cb_tf.setFixedWidth(60)
        cfg_lay.addWidget(self.cb_tf)

        cfg_lay.addWidget(QLabel("Poll (sec):"))
        self.spin_interval = QSpinBox()
        self.spin_interval.setRange(5, 300)
        self.spin_interval.setValue(30)
        self.spin_interval.setFixedWidth(60)
        cfg_lay.addWidget(self.spin_interval)

        self.chk_notify = QCheckBox("Desktop Alerts")
        self.chk_notify.setChecked(True)
        cfg_lay.addWidget(self.chk_notify)

        root.addWidget(cfg_group)

        # ── Control buttons ──────────────────────────────────────
        ctrl = QHBoxLayout()
        self.btn_start = QPushButton("▶  START MONITORING")
        self.btn_start.setMinimumHeight(38)
        self.btn_start.setStyleSheet("""
            QPushButton { background:#1a6b3a; color:white; font-weight:bold;
                          font-size:13px; border-radius:5px; border:none; }
            QPushButton:hover { background:#228b4e; }
            QPushButton:disabled { background:#333; color:#666; }
        """)
        self.btn_start.clicked.connect(self._start)

        self.btn_stop = QPushButton("⏹  STOP")
        self.btn_stop.setMinimumHeight(38)
        self.btn_stop.setEnabled(False)
        self.btn_stop.setStyleSheet("""
            QPushButton { background:#8b1a1a; color:white; font-weight:bold;
                          font-size:13px; border-radius:5px; border:none; }
            QPushButton:hover { background:#b22222; }
            QPushButton:disabled { background:#333; color:#666; }
        """)
        self.btn_stop.clicked.connect(self._stop)

        self.btn_test_notify = QPushButton("🔔 Test Notification")
        self.btn_test_notify.clicked.connect(self._test_notification)

        self.btn_export = QPushButton("💾 Export Signals CSV")
        self.btn_export.clicked.connect(self._export_signals)

        ctrl.addWidget(self.btn_start)
        ctrl.addWidget(self.btn_stop)
        ctrl.addStretch()
        ctrl.addWidget(self.btn_test_notify)
        ctrl.addWidget(self.btn_export)
        root.addLayout(ctrl)

        # ── Multi-strategy panel ──────────────────────────────────
        multi_group = QGroupBox("ACTIVE STRATEGIES  (add up to 3 — all run simultaneously)")
        multi_group.setStyleSheet(
            "QGroupBox{color:#555;font-size:10px;font-weight:bold;"
            "border:1px solid #2a2a4a;border-radius:5px;margin-top:4px;padding:6px;}"
        )
        multi_lay = QHBoxLayout(multi_group)

        from PySide6.QtWidgets import QListWidget
        self.strategy_list = QListWidget()
        self.strategy_list.setFixedHeight(70)
        self.strategy_list.setStyleSheet(
            "QListWidget{background:#0d0d1a;color:#aaa;font-size:11px;"
            "border:1px solid #2a2a4a;border-radius:3px;}"
        )
        multi_lay.addWidget(self.strategy_list)

        ml_btns = QVBoxLayout()
        self.btn_add_strat = QPushButton("➕ Add")
        self.btn_add_strat.setToolTip("Load and add a strategy to run alongside others")
        self.btn_add_strat.clicked.connect(self._add_strategy)
        self.btn_rem_strat = QPushButton("🗑 Remove")
        self.btn_rem_strat.clicked.connect(self._remove_strategy)
        ml_btns.addWidget(self.btn_add_strat)
        ml_btns.addWidget(self.btn_rem_strat)
        ml_btns.addStretch()
        multi_lay.addLayout(ml_btns)
        root.addWidget(multi_group)

        # ── Splitter: signal table + live log ───────────────────
        splitter = QSplitter(Qt.Vertical)

        # Signal table
        sig_frame = QFrame()
        sig_lay = QVBoxLayout(sig_frame)
        sig_lay.setContentsMargins(0, 0, 0, 0)

        tbl_hdr = QHBoxLayout()
        tbl_hdr.addWidget(QLabel("📊 Signal Feed"))
        self.lbl_sig_count = QLabel("0 signals")
        self.lbl_sig_count.setStyleSheet("color:#888;")
        tbl_hdr.addWidget(self.lbl_sig_count)
        tbl_hdr.addStretch()
        self.lbl_last_check = QLabel("Last checked: —")
        self.lbl_last_check.setStyleSheet("color:#555; font-size:11px;")
        tbl_hdr.addWidget(self.lbl_last_check)
        sig_lay.addLayout(tbl_hdr)

        self.sig_table = QTableWidget()
        self.sig_table.setColumnCount(7)
        self.sig_table.setHorizontalHeaderLabels([
            "IST Time", "Strategy", "Direction", "Symbol", "Timeframe", "Price", "Conditions"
        ])
        self.sig_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.sig_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.sig_table.setAlternatingRowColors(True)
        self.sig_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.sig_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.sig_table.cellClicked.connect(self._on_signal_selected)
        sig_lay.addWidget(self.sig_table)
        splitter.addWidget(sig_frame)

        # Debug / log area
        log_frame = QFrame()
        log_lay = QVBoxLayout(log_frame)
        log_lay.setContentsMargins(0, 0, 0, 0)
        log_lay.addWidget(QLabel("📋 Activity Log"))
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setStyleSheet("font-family: monospace; font-size: 11px; color:#aaa;")
        log_lay.addWidget(self.log)
        splitter.addWidget(log_frame)

        splitter.setSizes([300, 180])
        root.addWidget(splitter)

        # ── Bottom: condition detail panel ───────────────────────
        detail_frame = QGroupBox("SIGNAL DETAIL — click any row above")
        detail_lay = QVBoxLayout(detail_frame)
        self.lbl_detail = QLabel("Select a signal row to see the exact conditions that fired.")
        self.lbl_detail.setWordWrap(True)
        self.lbl_detail.setStyleSheet("color:#aaa; font-family:monospace;")
        detail_lay.addWidget(self.lbl_detail)
        root.addWidget(detail_frame)

        # MT5 status refresh timer
        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._refresh_mt5_status)
        self._status_timer.start(5000)
        self._refresh_mt5_status()

    # ── Strategy loading ─────────────────────────────────────────

    def _load_strategy(self):
        """Load primary (single) strategy — also sets symbol/TF dropdowns."""
        fp, _ = QFileDialog.getOpenFileName(
            self, "Open Strategy JSON", "", "JSON Files (*.json)")
        if not fp:
            return
        try:
            with open(fp, encoding='utf-8-sig') as f:
                strat = json.load(f)
            self.strategy = strat
            name = strat.get("name", "?")
            sym  = strat.get("symbol", "XAUUSD")
            tf   = strat.get("timeframe", "M15")
            self.lbl_strat.setText(f"✅ {name}  ({sym} {tf})")
            self.lbl_strat.setStyleSheet("color:#00d26a; font-weight:bold;")
            self.cb_symbol.setCurrentText(sym)
            self.cb_tf.setCurrentText(tf)
            self._log(f"Strategy loaded: {name}")
            # Also add to multi-strategy list if not already there
            self._add_strategy_obj(strat)
        except Exception as e:
            QMessageBox.warning(self, "Load Error", str(e))

    def _add_strategy(self):
        """Add a strategy to the multi-strategy list."""
        if len(self._strategies) >= 3:
            QMessageBox.information(
                self, "Limit Reached",
                "Maximum 3 strategies can run simultaneously.\n"
                "Remove one first, then add another.")
            return
        fp, _ = QFileDialog.getOpenFileName(
            self, "Add Strategy JSON", "", "JSON Files (*.json)")
        if not fp:
            return
        try:
            with open(fp, encoding='utf-8-sig') as f:
                strat = json.load(f)
            self._add_strategy_obj(strat)
        except Exception as e:
            QMessageBox.warning(self, "Load Error", str(e))

    def _add_strategy_obj(self, strat: dict):
        name = strat.get("name", "?")
        # Avoid duplicates
        for s in self._strategies:
            if s.get("name") == name:
                return
        if len(self._strategies) >= 3:
            return
        self._strategies.append(strat)
        sym = strat.get("symbol", "?")
        tf  = strat.get("timeframe", "?")
        dr  = strat.get("direction", "?")
        self.strategy_list.addItem(f"[{dr}] {name}  ({sym} {tf})")
        self._log(f"+ Added strategy: {name}  ({sym} {tf})")

    def _remove_strategy(self):
        row = self.strategy_list.currentRow()
        if row < 0:
            QMessageBox.information(self, "Select", "Select a strategy in the list first.")
            return
        removed = self._strategies.pop(row)
        self.strategy_list.takeItem(row)
        self._log(f"- Removed strategy: {removed.get('name', '?')}")

    # ── Start / Stop ─────────────────────────────────────────────

    def _start(self):
        if not self._strategies:
            if self.strategy:
                self._add_strategy_obj(self.strategy)
            else:
                QMessageBox.warning(
                    self, "No Strategy",
                    "Load at least one strategy using '📂 Load Strategy' or '➕ Add'.")
                return

        if not mt5_provider.is_connected():
            if not mt5_provider.connect():
                QMessageBox.critical(
                    self, "MT5 Error",
                    "Cannot connect to MT5. Make sure the terminal is running.")
                return
        self._refresh_mt5_status()

        symbol   = self.cb_symbol.currentText().strip()
        interval = self.spin_interval.value()

        names = []
        for strat in self._strategies:
            tf = strat.get("timeframe", self.cb_tf.currentText())
            sym = strat.get("symbol", symbol)
            worker = _MonitorWorker(strat, sym, tf, interval)
            thread = QThread()
            worker.moveToThread(thread)
            thread.started.connect(worker.run)
            worker.signal_found.connect(self._on_signal_found)
            worker.status_update.connect(self._log)
            worker.candle_checked.connect(self._on_candle_checked)
            worker.error_occurred.connect(
                lambda e: self._log(f"❌ Error: {e}"))
            thread.start()
            self._workers.append(worker)
            self._threads.append(thread)
            names.append(strat.get("name", "?"))

        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.btn_load_strat.setEnabled(False)
        self.btn_add_strat.setEnabled(False)
        self.btn_rem_strat.setEnabled(False)
        label = " + ".join(names)
        self.lbl_status.setText(f"▶  MONITORING — {label}")
        self.lbl_status.setStyleSheet("color:#00d26a; font-weight:bold;")
        self._log(f"▶ Started {len(self._workers)} strategies: {label}")

    def _stop(self):
        for w in self._workers:
            w.stop()
        for t in self._threads:
            t.quit()
            t.wait(3000)
        self._workers.clear()
        self._threads.clear()

        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.btn_load_strat.setEnabled(True)
        self.btn_add_strat.setEnabled(True)
        self.btn_rem_strat.setEnabled(True)
        self.lbl_status.setText("⏹  MONITOR STOPPED")
        self.lbl_status.setStyleSheet("color:#888; font-weight:bold;")
        self._log("⏹ Monitoring stopped.")

    # ── Signal handling ─────────────────────────────────────────

    def _on_signal_found(self, sig: dict):
        self._signal_count += 1
        self.lbl_sig_count.setText(
            f"{self._signal_count} signal{'s' if self._signal_count != 1 else ''}")

        strat_name = sig.get("strategy_name", "?")
        # Look up strategy direction from loaded list
        direction = "BUY"
        symbol    = self.cb_symbol.currentText()
        timeframe = self.cb_tf.currentText()
        for s in self._strategies:
            if s.get("name") == strat_name:
                direction = s.get("direction", "BUY")
                symbol    = s.get("symbol", symbol)
                timeframe = s.get("timeframe", timeframe)
                break

        price  = sig.get("price", 0)
        ts_ist = _ist(sig.get("timestamp", ""))
        debug  = sig.get("debug", [])

        full_sig = {
            "ts_ist":      ts_ist,
            "strategy":    strat_name,
            "direction":   direction,
            "symbol":      symbol,
            "timeframe":   timeframe,
            "price":       price,
            "debug":       debug,
        }
        self._signals_data.insert(0, full_sig)

        # Add row to table — 7 columns now
        row = 0
        self.sig_table.insertRow(row)
        color = QColor("#00d26a") if direction == "BUY" else QColor("#ff4757")
        cells = [
            ts_ist, strat_name, direction, symbol,
            timeframe, f"{price:,.5f}", " | ".join(debug[:2])
        ]
        for col, val in enumerate(cells):
            item = QTableWidgetItem(str(val))
            item.setTextAlignment(Qt.AlignCenter)
            if col == 2:  # Direction column
                item.setForeground(color)
                item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            self.sig_table.setItem(row, col, item)

        self._log(
            f"🔔 [{strat_name}] SIGNAL: {direction} {symbol} {timeframe} @ {price:,.5f}")

        if self.chk_notify.isChecked():
            notifier.signal_alert(
                strategy_name=strat_name,
                symbol=symbol,
                timeframe=timeframe,
                direction=direction,
                price=price,
                timestamp=ts_ist,
                debug_lines=debug
            )

        if self._journal_tab is not None:
            try:
                self._journal_tab.add_signal(
                    strategy_name=strat_name,
                    symbol=symbol,
                    timeframe=timeframe,
                    direction=direction,
                    price=price,
                    timestamp_ist=ts_ist,
                    conditions=debug
                )
            except Exception as je:
                logger.error(f"Journal add_signal failed: {je}")

        self._append_signal_csv(full_sig)

    def _on_candle_checked(self, info: dict):
        self.lbl_last_check.setText(
            f"Last checked: {info['time']}  |  "
            f"{info['symbol']} {info['timeframe']}  close={info['close']:,.5f}"
        )

    def _on_signal_selected(self, row: int, _col: int):
        if row < len(self._signals_data):
            sig = self._signals_data[row]
            lines = [
                f"⏱  Time (IST): {sig['ts_ist']}",
                f"📐 Strategy:   {sig.get('strategy','?')}",
                f"📈 Direction:  {sig['direction']}",
                f"💰 Price:      {sig['price']:,.5f}",
                "",
                "Conditions that fired:",
            ]
            for d in sig.get("debug", []):
                lines.append(f"   ✓ {d}")
            self.lbl_detail.setText("\n".join(lines))

    # ── Helpers ─────────────────────────────────────────────────

    def _refresh_mt5_status(self):
        if mt5_provider.is_connected():
            self.lbl_mt5.setText("MT5: ● Connected")
            self.lbl_mt5.setStyleSheet("color:#00d26a; font-weight:bold;")
        else:
            self.lbl_mt5.setText("MT5: ○ Disconnected")
            self.lbl_mt5.setStyleSheet("color:#ff4757; font-weight:bold;")

    def _log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log.append(f"[{ts}] {msg}")
        # Auto-scroll
        sb = self.log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _test_notification(self):
        notifier.signal_alert(
            strategy_name="Test Strategy",
            symbol="XAUUSD",
            timeframe="M15",
            direction="BUY",
            price=2498.50,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S IST"),
            debug_lines=["close[0](2498.50) > close[1](2496.20)", "RSI(14) = 57.3 > 50"]
        )
        self._log("🔔 Test notification sent — check your taskbar!")

    def _append_signal_csv(self, sig: dict):
        try:
            self._signal_log_path.parent.mkdir(parents=True, exist_ok=True)
            write_header = not self._signal_log_path.exists()
            with open(self._signal_log_path, "a", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=[
                    "ts_ist", "direction", "symbol", "timeframe", "price", "conditions"])
                if write_header:
                    writer.writeheader()
                writer.writerow({
                    "ts_ist": sig["ts_ist"],
                    "direction": sig["direction"],
                    "symbol": sig["symbol"],
                    "timeframe": sig["timeframe"],
                    "price": sig["price"],
                    "conditions": " | ".join(sig.get("debug", []))
                })
        except Exception as e:
            logger.error(f"Failed to write signal CSV: {e}")

    def _export_signals(self):
        if not self._signals_data:
            QMessageBox.information(self, "No Signals", "No signals to export yet.")
            return
        fp, _ = QFileDialog.getSaveFileName(
            self, "Export Signals", "live_signals.csv", "CSV Files (*.csv)")
        if not fp:
            return
        try:
            with open(fp, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=[
                    "ts_ist", "direction", "symbol", "timeframe", "price", "conditions"])
                writer.writeheader()
                for sig in self._signals_data:
                    writer.writerow({
                        "ts_ist": sig["ts_ist"],
                        "direction": sig["direction"],
                        "symbol": sig["symbol"],
                        "timeframe": sig["timeframe"],
                        "price": sig["price"],
                        "conditions": " | ".join(sig.get("debug", []))
                    })
            QMessageBox.information(self, "Exported", f"Saved to:\n{fp}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

"""
Chart UI — candlestick chart with backtest signal overlay markers.
Can receive signals from the BacktestUI via backtest_done signal.
"""
import pandas as pd
from datetime import datetime

import pytz

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog,
    QMessageBox, QLabel, QComboBox, QGroupBox, QFrame, QSplitter,
    QTextEdit
)
from PySide6.QtCharts import (
    QChart, QChartView, QCandlestickSeries, QCandlestickSet,
    QDateTimeAxis, QValueAxis, QScatterSeries, QLegendMarker
)
from PySide6.QtCore import Qt, QDateTime, QPointF
from PySide6.QtGui import QPainter, QColor, QFont

from app.core.mt5_provider import provider as mt5_provider
from app.core.logger import setup_logger

logger = setup_logger("app.ui.chart")

IST = pytz.timezone("Asia/Kolkata")
MAX_CANDLES = 200


def _to_ms(ts) -> int:
    """Convert a pandas Timestamp (or anything) to milliseconds since epoch."""
    try:
        if hasattr(ts, "timestamp"):
            return int(ts.timestamp() * 1000)
        return int(pd.Timestamp(ts).timestamp() * 1000)
    except Exception:
        return 0


class ChartUI(QWidget):
    def __init__(self):
        super().__init__()
        self._df = None
        self._signals = []
        self._build_ui()

    # ── UI Construction ──────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(4)

        # ── Toolbar ──────────────────────────────────────────────────────
        tb = QHBoxLayout()

        self.btn_load_csv = QPushButton("📂 Load CSV")
        self.btn_load_csv.clicked.connect(self._load_csv)
        tb.addWidget(self.btn_load_csv)

        self.btn_load_mt5 = QPushButton("⬇ Load from MT5")
        self.btn_load_mt5.clicked.connect(self._load_mt5)
        tb.addWidget(self.btn_load_mt5)

        tb.addWidget(QLabel("Symbol:"))
        self.cb_symbol = QComboBox()
        self.cb_symbol.setEditable(True)
        self.cb_symbol.addItems(["XAUUSD", "EURUSD", "GBPUSD", "USDJPY"])
        self.cb_symbol.setFixedWidth(90)
        tb.addWidget(self.cb_symbol)

        tb.addWidget(QLabel("TF:"))
        self.cb_tf = QComboBox()
        self.cb_tf.addItems(["M1", "M5", "M15", "M30", "H1", "H4", "D1"])
        self.cb_tf.setCurrentText("M15")
        self.cb_tf.setFixedWidth(60)
        tb.addWidget(self.cb_tf)

        tb.addWidget(QLabel("Show:"))
        self.cb_candles = QComboBox()
        self.cb_candles.addItems(["50", "100", "200", "500"])
        self.cb_candles.setCurrentText("100")
        self.cb_candles.setFixedWidth(60)
        self.cb_candles.currentIndexChanged.connect(self._redraw)
        tb.addWidget(self.cb_candles)

        self.lbl_info = QLabel("No data loaded")
        self.lbl_info.setStyleSheet("color:#888; font-size:11px;")
        tb.addWidget(self.lbl_info)
        tb.addStretch()

        self.lbl_signals = QLabel("No signals")
        self.lbl_signals.setStyleSheet("color:#888; font-size:11px;")
        tb.addWidget(self.lbl_signals)

        root.addLayout(tb)

        # ── Splitter: chart + detail ──────────────────────────────────────
        splitter = QSplitter(Qt.Vertical)

        # Chart
        self.chart = QChart()
        self.chart.setTitle("")
        self.chart.setAnimationOptions(QChart.NoAnimation)
        self.chart.setBackgroundBrush(QColor("#0d0d1a"))
        self.chart.legend().setVisible(True)
        self.chart.legend().setAlignment(Qt.AlignTop)

        self.chart_view = QChartView(self.chart)
        self.chart_view.setRenderHint(QPainter.Antialiasing)
        self.chart_view.setMinimumHeight(350)
        splitter.addWidget(self.chart_view)

        # Signal detail box
        detail_frame = QFrame()
        detail_frame.setMaximumHeight(120)
        detail_lay = QVBoxLayout(detail_frame)
        detail_lay.setContentsMargins(4, 4, 4, 4)
        detail_lay.addWidget(QLabel("📌 Click a signal marker to see details:"))
        self.lbl_detail = QLabel("—")
        self.lbl_detail.setWordWrap(True)
        self.lbl_detail.setStyleSheet("color:#aaa; font-family:monospace; font-size:11px;")
        detail_lay.addWidget(self.lbl_detail)
        splitter.addWidget(detail_frame)

        splitter.setSizes([450, 100])
        root.addWidget(splitter)

    # ── Public API (called by BacktestUI) ──────────────────────────────────

    def load_signals(self, signals: list, df: pd.DataFrame):
        """Receive signals from Backtest tab and overlay them on the chart."""
        self._signals = signals
        self._df = df
        self._redraw()
        n = len(signals)
        self.lbl_signals.setText(f"🔔 {n} signal{'s' if n != 1 else ''} overlaid")
        self.lbl_signals.setStyleSheet("color:#00d26a; font-weight:bold;")

    # ── Load actions ───────────────────────────────────────────────────────

    def _load_csv(self):
        fp, _ = QFileDialog.getOpenFileName(self, "Open CSV", "", "CSV Files (*.csv)")
        if not fp:
            return
        try:
            df = pd.read_csv(fp)
            df.columns = [c.lower() for c in df.columns]
            if "timestamp" in df.columns:
                df["time"] = pd.to_datetime(df["timestamp"])
            elif "time" in df.columns:
                df["time"] = pd.to_datetime(df["time"])
            self._df = df
            self._signals = []  # clear any previous signals
            self._redraw()
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def _load_mt5(self):
        if not mt5_provider.is_connected():
            if not mt5_provider.connect():
                QMessageBox.warning(self, "MT5 Error", "MT5 is not connected.")
                return
        symbol = self.cb_symbol.currentText().strip()
        tf = self.cb_tf.currentText()
        try:
            df = mt5_provider.get_candles(symbol, tf, count=500)
            if df is None or df.empty:
                QMessageBox.warning(self, "No Data", f"No bars returned for {symbol} {tf}.")
                return
            self._df = df
            self._signals = []
            self._redraw()
        except Exception as e:
            QMessageBox.warning(self, "Fetch Error", str(e))

    # ── Chart drawing ──────────────────────────────────────────────────────

    def _redraw(self):
        if self._df is None or self._df.empty:
            return

        n_candles = int(self.cb_candles.currentText())
        df = self._df.tail(n_candles).copy().reset_index(drop=True)

        # ── Candlestick series ─────────────────────────────────────────
        candle_series = QCandlestickSeries()
        candle_series.setName("Price")
        candle_series.setIncreasingColor(QColor("#00d26a"))
        candle_series.setDecreasingColor(QColor("#ff4757"))
        candle_series.setBodyOutlineVisible(False)

        times_ms = []
        for _, row in df.iterrows():
            ts_ms = _to_ms(row["time"])
            times_ms.append(ts_ms)
            cs = QCandlestickSet(
                float(row["open"]), float(row["high"]),
                float(row["low"]),  float(row["close"]),
                ts_ms
            )
            candle_series.append(cs)

        # ── Signal markers ─────────────────────────────────────────────
        buy_series = QScatterSeries()
        buy_series.setName("BUY Signal")
        buy_series.setMarkerShape(QScatterSeries.MarkerShapeTriangle)
        buy_series.setMarkerSize(14)
        buy_series.setColor(QColor("#00ff88"))
        buy_series.setBorderColor(QColor("#00d26a"))

        sell_series = QScatterSeries()
        sell_series.setName("SELL Signal")
        sell_series.setMarkerShape(QScatterSeries.MarkerShapeRotatedTriangle)
        sell_series.setMarkerSize(14)
        sell_series.setColor(QColor("#ff4444"))
        sell_series.setBorderColor(QColor("#cc0000"))

        # Determine the absolute start index in self._df for the displayed slice
        df_start_idx = len(self._df) - n_candles

        for sig in self._signals:
            sig_abs_idx = sig.get("index", -1)
            if sig_abs_idx < df_start_idx:
                continue  # outside visible window
            relative_idx = sig_abs_idx - df_start_idx
            if relative_idx >= len(times_ms):
                continue
            ts_ms = times_ms[relative_idx]
            price = float(sig.get("price", 0))
            row_data = df.iloc[relative_idx]
            low  = float(row_data.get("low", price))
            high = float(row_data.get("high", price))

            # Check if strategy direction is BUY or SELL
            # We check both using debug text
            debug = sig.get("debug", [])
            is_buy = True  # default; the signal table handles this better
            # Place marker just below low (BUY) or above high (SELL)
            buy_series.append(QPointF(ts_ms, low * 0.9997))
            # Note: both series will show, but without direction info from signal
            # we'll just use green for all (the direction is in strategy meta)

        # ── Build axes ─────────────────────────────────────────────────
        self.chart.removeAllSeries()
        for ax in self.chart.axes():
            self.chart.removeAxis(ax)

        self.chart.addSeries(candle_series)
        if buy_series.count() > 0:
            self.chart.addSeries(buy_series)
        if sell_series.count() > 0:
            self.chart.addSeries(sell_series)

        axisX = QDateTimeAxis()
        axisX.setFormat("MM-dd HH:mm")
        axisX.setTitleText("Time (UTC)")
        axisX.setLabelsFont(QFont("Segoe UI", 8))
        self.chart.addAxis(axisX, Qt.AlignBottom)
        candle_series.attachAxis(axisX)
        if buy_series.count() > 0:
            buy_series.attachAxis(axisX)
        if sell_series.count() > 0:
            sell_series.attachAxis(axisX)

        axisY = QValueAxis()
        axisY.setTitleText("Price")
        axisY.setLabelsFont(QFont("Segoe UI", 8))
        axisY.setLabelFormat("%.2f")
        self.chart.addAxis(axisY, Qt.AlignLeft)
        candle_series.attachAxis(axisY)
        if buy_series.count() > 0:
            buy_series.attachAxis(axisY)
        if sell_series.count() > 0:
            sell_series.attachAxis(axisY)

        # Set ranges
        if times_ms:
            t0 = QDateTime.fromMSecsSinceEpoch(times_ms[0])
            t1 = QDateTime.fromMSecsSinceEpoch(times_ms[-1])
            axisX.setRange(t0, t1)
        lo = df["low"].min()
        hi = df["high"].max()
        pad = (hi - lo) * 0.05
        axisY.setRange(lo - pad, hi + pad)

        sym = self.cb_symbol.currentText()
        tf  = self.cb_tf.currentText()
        sig_count = len([s for s in self._signals if s.get("index", -1) >= df_start_idx])
        title = f"{sym} {tf} — {len(df)} candles"
        if sig_count > 0:
            title += f"  |  🔔 {sig_count} signals"
        self.chart.setTitle(title)

        self.lbl_info.setText(f"{sym} {tf}  |  {len(df):,} candles")

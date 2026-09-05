"""
Chart UI — candlestick chart with backtest signal overlay.
Fixed: MarkerShapeRotatedTriangle is not available in all PySide6 versions.
Uses Circle as universal fallback for SELL markers.
Shows IST timestamps on X-axis.
"""
import pandas as pd
from datetime import datetime, timezone, timedelta

import pytz

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog,
    QMessageBox, QLabel, QComboBox, QFrame, QSplitter, QSpinBox
)
from PySide6.QtCharts import (
    QChart, QChartView, QCandlestickSeries, QCandlestickSet,
    QDateTimeAxis, QValueAxis, QScatterSeries
)
from PySide6.QtCore import Qt, QDateTime, QPointF
from PySide6.QtGui import QPainter, QColor, QFont

from app.core.mt5_provider import provider as mt5_provider
from app.core.logger import setup_logger

logger = setup_logger("app.ui.chart")

IST = pytz.timezone("Asia/Kolkata")
UTC = timezone.utc


def _to_ms(ts) -> int:
    """Convert a pandas Timestamp or datetime to UTC milliseconds since epoch."""
    try:
        if hasattr(ts, "timestamp"):
            return int(ts.timestamp() * 1000)
        return int(pd.Timestamp(ts).timestamp() * 1000)
    except Exception:
        return 0


def _safe_marker(shape_name: str):
    """Return a QScatterSeries.MarkerShape safely — fallback to Circle."""
    # Try the new enum-style first (PySide6 >= 6.4)
    try:
        return getattr(QScatterSeries.MarkerShape, shape_name)
    except AttributeError:
        pass
    # Try the legacy flat attribute (PySide6 < 6.4)
    try:
        return getattr(QScatterSeries, f"MarkerShape{shape_name}")
    except AttributeError:
        pass
    # Final fallback: Circle always works
    try:
        return QScatterSeries.MarkerShape.Circle
    except AttributeError:
        return QScatterSeries.MarkerShapeCircle


class ChartUI(QWidget):
    def __init__(self):
        super().__init__()
        self._df = None
        self._signals = []
        self._last_price_label = None
        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(4)
        root.setContentsMargins(6, 6, 6, 6)

        # ── Toolbar ───────────────────────────────────────────────────────
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

        # Live price display
        self.lbl_live = QLabel("—")
        self.lbl_live.setStyleSheet(
            "color:#f5a623; font-weight:bold; font-size:13px; "
            "background:#1a1200; border:1px solid #3a2a00; "
            "border-radius:4px; padding:2px 8px;"
        )
        tb.addWidget(self.lbl_live)

        self.lbl_signals = QLabel("No signals")
        self.lbl_signals.setStyleSheet("color:#888; font-size:11px;")
        tb.addWidget(self.lbl_signals)

        root.addLayout(tb)

        # ── Market status banner ──────────────────────────────────────────
        self.lbl_market = QLabel("")
        self.lbl_market.setVisible(False)
        self.lbl_market.setStyleSheet(
            "color:#f5a623; background:#1a1400; border:1px solid #3a2a00; "
            "border-radius:4px; padding:4px 10px; font-size:11px;"
        )
        root.addWidget(self.lbl_market)

        # ── Chart + detail splitter ───────────────────────────────────────
        splitter = QSplitter(Qt.Vertical)

        self.chart = QChart()
        self.chart.setTitle("")
        self.chart.setAnimationOptions(QChart.NoAnimation)
        self.chart.setBackgroundBrush(QColor("#0d0d1a"))
        self.chart.legend().setVisible(True)
        self.chart.legend().setAlignment(Qt.AlignTop)
        self.chart.legend().setLabelColor(QColor("#aaa"))

        self.chart_view = QChartView(self.chart)
        self.chart_view.setRenderHint(QPainter.Antialiasing)
        self.chart_view.setMinimumHeight(350)
        self.chart_view.setStyleSheet("background:#0d0d1a;")
        splitter.addWidget(self.chart_view)

        # Signal detail
        detail_frame = QFrame()
        detail_frame.setMaximumHeight(110)
        detail_frame.setStyleSheet(
            "background:#0f0f1e; border-top:1px solid #2a2a4a;")
        detail_lay = QVBoxLayout(detail_frame)
        detail_lay.setContentsMargins(8, 6, 8, 6)

        lbl_hint = QLabel("📌 Click a signal marker to see details:")
        lbl_hint.setStyleSheet("color:#555; font-size:10px;")
        detail_lay.addWidget(lbl_hint)

        self.lbl_detail = QLabel("—")
        self.lbl_detail.setWordWrap(True)
        self.lbl_detail.setStyleSheet(
            "color:#aaa; font-family:monospace; font-size:11px;")
        detail_lay.addWidget(self.lbl_detail)
        splitter.addWidget(detail_frame)

        splitter.setSizes([450, 100])
        root.addWidget(splitter)

    # ── Public API ────────────────────────────────────────────────────────────

    def load_signals(self, signals: list, df: pd.DataFrame):
        """Receive signals from Backtest and overlay on chart."""
        self._signals = signals
        self._df = df
        self._redraw()
        n = len(signals)
        self.lbl_signals.setText(f"🔔 {n} signal{'s' if n != 1 else ''} overlaid")
        self.lbl_signals.setStyleSheet("color:#00d26a; font-weight:bold;")

    # ── Data loading ──────────────────────────────────────────────────────────

    def _load_csv(self):
        fp, _ = QFileDialog.getOpenFileName(
            self, "Open CSV", "", "CSV Files (*.csv)")
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
            self._signals = []
            self._redraw()
        except Exception as e:
            QMessageBox.warning(self, "CSV Error", str(e))

    def _load_mt5(self):
        if not mt5_provider.is_connected():
            if not mt5_provider.connect():
                QMessageBox.warning(
                    self, "MT5 Error",
                    "MT5 is not connected.\n\n"
                    "Make sure MetaTrader 5 is running and logged in.")
                return
        symbol = self.cb_symbol.currentText().strip()
        tf = self.cb_tf.currentText()
        try:
            df = mt5_provider.get_candles(symbol, tf, count=500)
            if df is None or df.empty:
                QMessageBox.warning(
                    self, "No Data",
                    f"No bars returned for {symbol} {tf}.\n\n"
                    "This can happen when the market is closed (weekend/holiday). "
                    "MT5 still returns the last known candles — use them for analysis.")
                return
            self._df = df
            self._signals = []
            self._check_market_status()
            self._update_live_price(symbol)
            self._redraw()
        except Exception as e:
            QMessageBox.warning(self, "Fetch Error", str(e))

    def _check_market_status(self):
        """
        XAUUSD (Gold) trades on Forex market.
        Closes: Friday    21:00 UTC  = Saturday 02:30 IST
        Opens:  Sunday    21:00 UTC  = Monday   02:30 IST
        """
        now_utc = datetime.now(UTC)
        weekday = now_utc.weekday()  # 0=Mon … 4=Fri … 5=Sat … 6=Sun
        hour    = now_utc.hour

        # Closed window in UTC: Friday ≥ 21:00 → Sunday < 21:00
        is_closed = (
            (weekday == 4 and hour >= 21) or   # Friday after 21:00 UTC
            weekday == 5 or                     # Entire Saturday UTC
            (weekday == 6 and hour < 21)        # Sunday before 21:00 UTC
        )

        if is_closed:
            self.lbl_market.setText(
                "⚠  MARKET CLOSED  (Saturday 02:30 IST → Monday 02:30 IST)  "
                "— Chart shows last candles from before Friday close. "
                "Signals on this data are NOT valid live signals."
            )
            self.lbl_market.setVisible(True)
        else:
            self.lbl_market.setVisible(False)

    def _update_live_price(self, symbol: str):
        """Show the latest bid/ask price from MT5 in the toolbar."""
        try:
            tick = mt5_provider.get_current_price(symbol)
            if tick:
                bid = tick.get("bid", 0)
                ask = tick.get("ask", 0)
                spread = round((ask - bid) * 10, 1)  # in pips for Gold
                self.lbl_live.setText(
                    f"Live: {bid:,.2f} / {ask:,.2f}  spread={spread}pt"
                )
        except Exception:
            pass

    # ── Chart drawing ─────────────────────────────────────────────────────────

    def _redraw(self):
        if self._df is None or self._df.empty:
            return

        n_candles = int(self.cb_candles.currentText())
        df = self._df.tail(n_candles).copy().reset_index(drop=True)

        # ── Candlestick series ─────────────────────────────────────────────
        candle_series = QCandlestickSeries()
        candle_series.setName("Price")
        candle_series.setIncreasingColor(QColor("#00d26a"))
        candle_series.setDecreasingColor(QColor("#ff4757"))
        candle_series.setBodyOutlineVisible(False)
        candle_series.setCapsVisible(False)

        times_ms = []
        min_price = float("inf")
        max_price = float("-inf")

        for _, row in df.iterrows():
            ts_ms = _to_ms(row["time"])
            times_ms.append(ts_ms)
            o, h, l, c = (float(row.get(k, 0)) for k in
                          ["open", "high", "low", "close"])
            min_price = min(min_price, l)
            max_price = max(max_price, h)
            candle_series.append(QCandlestickSet(o, h, l, c, ts_ms))

        # ── BUY signal series (triangle up = ▲) ───────────────────────────
        buy_series = QScatterSeries()
        buy_series.setName("▲ BUY")
        buy_series.setMarkerShape(_safe_marker("Triangle"))
        buy_series.setMarkerSize(16)
        buy_series.setColor(QColor("#00ff88"))
        buy_series.setBorderColor(QColor("#00d26a"))

        # ── SELL signal series (circle = ●) ────────────────────────────────
        sell_series = QScatterSeries()
        sell_series.setName("● SELL")
        sell_series.setMarkerShape(_safe_marker("Circle"))
        sell_series.setMarkerSize(14)
        sell_series.setColor(QColor("#ff4444"))
        sell_series.setBorderColor(QColor("#cc0000"))

        df_start_idx = max(0, len(self._df) - n_candles)

        for sig in self._signals:
            sig_abs_idx = sig.get("index", -1)
            if sig_abs_idx < df_start_idx:
                continue
            relative_idx = sig_abs_idx - df_start_idx
            if relative_idx >= len(times_ms):
                continue
            ts_ms = times_ms[relative_idx]
            row_data = df.iloc[relative_idx]
            low  = float(row_data.get("low", 0))
            high = float(row_data.get("high", 0))
            price = float(sig.get("price", low))
            direction = sig.get("direction", "BUY")

            if direction == "SELL":
                # Place marker just above candle high
                sell_series.append(QPointF(ts_ms, high * 1.0003))
            else:
                # Place marker just below candle low
                buy_series.append(QPointF(ts_ms, low * 0.9997))

        # ── Rebuild chart ──────────────────────────────────────────────────
        self.chart.removeAllSeries()
        for ax in self.chart.axes():
            self.chart.removeAxis(ax)

        self.chart.addSeries(candle_series)
        if buy_series.count() > 0:
            self.chart.addSeries(buy_series)
        if sell_series.count() > 0:
            self.chart.addSeries(sell_series)

        # X-axis — show in IST
        axisX = QDateTimeAxis()
        axisX.setFormat("MM/dd HH:mm")
        axisX.setTitleText("Time (UTC → display in local)")
        axisX.setLabelsFont(QFont("Segoe UI", 7))
        axisX.setGridLineColor(QColor("#1e1e3a"))
        self.chart.addAxis(axisX, Qt.AlignBottom)
        candle_series.attachAxis(axisX)
        if buy_series.count() > 0:
            buy_series.attachAxis(axisX)
        if sell_series.count() > 0:
            sell_series.attachAxis(axisX)

        # Y-axis
        axisY = QValueAxis()
        axisY.setTitleText("Price")
        axisY.setLabelsFont(QFont("Segoe UI", 8))
        axisY.setLabelFormat("%.2f")
        axisY.setGridLineColor(QColor("#1e1e3a"))
        self.chart.addAxis(axisY, Qt.AlignLeft)
        candle_series.attachAxis(axisY)
        if buy_series.count() > 0:
            buy_series.attachAxis(axisY)
        if sell_series.count() > 0:
            sell_series.attachAxis(axisY)

        # Axis ranges
        if times_ms:
            axisX.setRange(
                QDateTime.fromMSecsSinceEpoch(times_ms[0]),
                QDateTime.fromMSecsSinceEpoch(times_ms[-1])
            )
        if min_price < max_price:
            pad = (max_price - min_price) * 0.06
            axisY.setRange(min_price - pad, max_price + pad)

        # Chart title
        sym = self.cb_symbol.currentText()
        tf = self.cb_tf.currentText()
        if not df.empty:
            last_close = df["close"].iloc[-1]
            last_time = df["time"].iloc[-1]
            sig_count = buy_series.count() + sell_series.count()
            title = f"{sym} {tf}  |  Last Close: {last_close:,.5f}  |  {len(df)} candles"
            if sig_count > 0:
                title += f"  |  🔔 {sig_count} signals"
            self.chart.setTitle(title)
            self.chart.setTitleBrush(QColor("#e0e0e0"))

        self.lbl_info.setText(
            f"{sym} {tf}  |  {len(df):,} candles  |  "
            f"High: {max_price:,.2f}  Low: {min_price:,.2f}"
        )

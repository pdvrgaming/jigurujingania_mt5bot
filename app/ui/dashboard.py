"""
Dashboard — shows real-time app status at a glance.
MT5 status, active strategy, monitoring state, last signal, observer status.
"""
from datetime import datetime
from pathlib import Path

import pytz

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QFrame, QGroupBox
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QColor

from app.core.config import config
from app.core.logger import setup_logger

logger = setup_logger("app.ui.dashboard")

IST = pytz.timezone("Asia/Kolkata")


def _now_ist() -> str:
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST")


def _card(label: str, value: str = "—",
          val_color: str = "#e0e0e0",
          label_color: str = "#666") -> tuple[QFrame, QLabel]:
    """Returns (frame, value_label) so caller can update value_label later."""
    frame = QFrame()
    frame.setFrameShape(QFrame.StyledPanel)
    frame.setStyleSheet("""
        QFrame {
            background: #1a1a2e;
            border: 1px solid #2a2a4a;
            border-radius: 10px;
        }
    """)
    lay = QVBoxLayout(frame)
    lay.setSpacing(4)
    lay.setContentsMargins(14, 10, 14, 10)

    lbl = QLabel(label)
    lbl.setStyleSheet(
        f"color: {label_color}; font-size: 10px; font-weight: bold; "
        "text-transform: uppercase; background: transparent; border: none;")
    lay.addWidget(lbl)

    val = QLabel(value)
    val.setStyleSheet(
        f"color: {val_color}; font-size: 14px; font-weight: bold; "
        "background: transparent; border: none;")
    val.setWordWrap(True)
    lay.addWidget(val)

    return frame, val


class Dashboard(QWidget):
    def __init__(self, provider, observer):
        super().__init__()
        self.provider = provider
        self.observer = observer

        # State refs injected by MainWindow after all tabs are created
        self._monitor_tab = None
        self._backtest_tab = None
        self._journal_tab = None

        self._build_ui()

        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh)
        self._refresh_timer.start(2000)
        self._refresh()

    def set_tabs(self, monitor_tab, backtest_tab, journal_tab):
        """Inject tab references so Dashboard can read their live state."""
        self._monitor_tab = monitor_tab
        self._backtest_tab = backtest_tab
        self._journal_tab = journal_tab

    # ── UI Construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(16, 16, 16, 16)

        # ── App header ────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        title = QLabel("MT5 Strategy Console")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet("color: #e0e0e0;")
        hdr.addWidget(title)
        hdr.addStretch()

        self.lbl_clock = QLabel(_now_ist())
        self.lbl_clock.setStyleSheet("color: #555; font-size: 12px;")
        hdr.addWidget(self.lbl_clock)
        root.addLayout(hdr)

        # ── Row 1: Connection + Monitor + Observer ─────────────────────────
        row1 = QHBoxLayout()
        row1.setSpacing(12)

        # MT5 Connection
        f, self.val_mt5 = _card("MT5 Connection", "○  Disconnected", "#ff4757")
        self.frm_mt5 = f
        row1.addWidget(f)

        # Live Monitor
        f2, self.val_monitor = _card("Live Monitor", "⏹  Stopped", "#888")
        row1.addWidget(f2)

        # Bot Observer
        f3, self.val_observer = _card("Bot Observer", "⏹  Stopped", "#888")
        row1.addWidget(f3)

        root.addLayout(row1)

        # ── Row 2: Active strategy + Last signal ───────────────────────────
        row2 = QHBoxLayout()
        row2.setSpacing(12)

        f4, self.val_strategy = _card("Active Strategy", "None loaded", "#888")
        row2.addWidget(f4, 2)

        f5, self.val_last_sig = _card("Last Signal", "No signals yet", "#888")
        row2.addWidget(f5, 2)

        root.addLayout(row2)

        # ── Row 3: Stats ───────────────────────────────────────────────────
        row3 = QHBoxLayout()
        row3.setSpacing(12)

        f6,  self.val_signals_today = _card("Signals Today",   "0")
        f7,  self.val_took           = _card("Trades Taken",    "0", "#00d26a")
        f8,  self.val_wins           = _card("Wins",            "0", "#00d26a")
        f9,  self.val_losses         = _card("Losses",          "0", "#ff4757")
        f10, self.val_obs_events     = _card("Bot Events Today", "0")

        for f in [f6, f7, f8, f9, f10]:
            row3.addWidget(f)
        root.addLayout(row3)

        # ── Strategies on disk ────────────────────────────────────────────
        strat_group = QGroupBox("AVAILABLE STRATEGIES")
        strat_group.setStyleSheet("QGroupBox { color:#666; font-size:10px; "
                                  "font-weight:bold; border:1px solid #2a2a4a; "
                                  "border-radius:8px; margin-top:8px; padding:8px; }")
        strat_lay = QHBoxLayout(strat_group)
        self.lbl_strategies = QLabel("Scanning…")
        self.lbl_strategies.setWordWrap(True)
        self.lbl_strategies.setStyleSheet("color:#aaa; font-size:11px;")
        strat_lay.addWidget(self.lbl_strategies)
        root.addWidget(strat_group)

        # ── Important notice ──────────────────────────────────────────────
        notice = QLabel(
            "⚠  This application is READ-ONLY. It does NOT place, modify, or close trades. "
            "All signals are advisory only — YOU make the final decision."
        )
        notice.setWordWrap(True)
        notice.setStyleSheet(
            "color: #f5a623; font-size: 11px; "
            "background: #1a1400; border: 1px solid #3a2a00; "
            "border-radius: 6px; padding: 8px;"
        )
        root.addWidget(notice)

        root.addStretch()

    # ── Live refresh ─────────────────────────────────────────────────────────

    def _refresh(self):
        self.lbl_clock.setText(_now_ist())

        # MT5
        if self.provider.is_connected():
            self.val_mt5.setText("●  Connected")
            self.val_mt5.setStyleSheet(
                "color:#00d26a; font-size:14px; font-weight:bold; "
                "background:transparent; border:none;")
        else:
            self.val_mt5.setText("○  Disconnected")
            self.val_mt5.setStyleSheet(
                "color:#ff4757; font-size:14px; font-weight:bold; "
                "background:transparent; border:none;")

        # Bot Observer
        if self.observer.running:
            self.val_observer.setText("▶  Running")
            self.val_observer.setStyleSheet(
                "color:#00d26a; font-size:14px; font-weight:bold; "
                "background:transparent; border:none;")
        else:
            self.val_observer.setText("⏹  Stopped")
            self.val_observer.setStyleSheet(
                "color:#888; font-size:14px; font-weight:bold; "
                "background:transparent; border:none;")

        # Live Monitor (via injected ref)
        if self._monitor_tab:
            is_running = (
                self._monitor_tab._thread is not None
                and self._monitor_tab._thread.isRunning()
            )
            strat = self._monitor_tab.strategy
            strat_name = strat.get("name", "?") if strat else None

            if is_running and strat_name:
                sym = strat.get("symbol", "")
                tf = strat.get("timeframe", "")
                self.val_monitor.setText(f"▶  {strat_name}\n{sym} {tf}")
                self.val_monitor.setStyleSheet(
                    "color:#00d26a; font-size:13px; font-weight:bold; "
                    "background:transparent; border:none;")
                # Active strategy card
                self.val_strategy.setText(f"{strat_name}\n{sym} {tf}")
                self.val_strategy.setStyleSheet(
                    "color:#00d26a; font-size:13px; font-weight:bold; "
                    "background:transparent; border:none;")
            elif strat_name:
                self.val_monitor.setText("⏹  Stopped")
                self.val_monitor.setStyleSheet(
                    "color:#888; font-size:14px; font-weight:bold; "
                    "background:transparent; border:none;")
                self.val_strategy.setText(f"{strat_name} (not monitoring)")
                self.val_strategy.setStyleSheet(
                    "color:#aaa; font-size:13px; font-weight:bold; "
                    "background:transparent; border:none;")
            else:
                self.val_monitor.setText("⏹  Stopped")
                self.val_monitor.setStyleSheet(
                    "color:#888; font-size:14px; font-weight:bold; "
                    "background:transparent; border:none;")

            # Last signal
            if self._monitor_tab._signals_data:
                sig = self._monitor_tab._signals_data[0]
                d = sig.get("direction", "?")
                col = "#00d26a" if d == "BUY" else "#ff4757"
                self.val_last_sig.setText(
                    f"{d}  {sig.get('symbol','')} {sig.get('timeframe','')}\n"
                    f"Price: {sig.get('price', 0):,.5f}\n"
                    f"{sig.get('ts_ist','')}"
                )
                self.val_last_sig.setStyleSheet(
                    f"color:{col}; font-size:12px; font-weight:bold; "
                    "background:transparent; border:none;")

            # Signals today count
            today_str = datetime.now(IST).strftime("%Y-%m-%d")
            today_sigs = sum(
                1 for s in self._monitor_tab._signals_data
                if s.get("ts_ist", "").startswith(today_str)
            )
            self.val_signals_today.setText(str(today_sigs))

        # Journal stats (via injected ref)
        if self._journal_tab and self._journal_tab._records:
            records = self._journal_tab._records
            took   = sum(1 for r in records if r.get("user_action") == "Took Trade")
            wins   = sum(1 for r in records if r.get("manual_result") == "Win")
            losses = sum(1 for r in records if r.get("manual_result") == "Loss")
            self.val_took.setText(str(took))
            self.val_wins.setText(str(wins))
            self.val_losses.setText(str(losses))

        # Bot observer event count today
        self._refresh_obs_count()

        # Strategies on disk
        self._refresh_strategies()

    def _refresh_obs_count(self):
        try:
            obs_path = Path(config.get("data_directory", "data")) / "observations" / "xauusd_trial_activity.csv"
            if obs_path.exists():
                today = datetime.now(IST).strftime("%Y-%m-%d")
                count = 0
                with open(obs_path) as f:
                    for line in f:
                        if today in line:
                            count += 1
                self.val_obs_events.setText(str(max(0, count - 1)))  # minus header match
        except Exception:
            pass

    def _refresh_strategies(self):
        try:
            strat_dir = Path(config.get("data_directory", "data")) / "strategies"
            if strat_dir.exists():
                files = sorted(strat_dir.glob("*.json"))
                if files:
                    names = [f.stem for f in files[-12:]]  # last 12
                    self.lbl_strategies.setText("  |  ".join(names))
                else:
                    self.lbl_strategies.setText("No strategies found. Create one in the Strategies tab.")
            else:
                self.lbl_strategies.setText("Strategies folder not found.")
        except Exception:
            pass

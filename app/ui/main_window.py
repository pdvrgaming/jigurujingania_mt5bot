from PySide6.QtWidgets import QMainWindow, QTabWidget, QVBoxLayout, QWidget
from app.core.logger import setup_logger
from app.core.mt5_provider import provider
from app.core.bot_observer import BotObserver
from app.core.live_monitor import LiveMonitor
from app.ui.desktop_alerts import DesktopAlerter

from app.ui.dashboard import Dashboard
from app.ui.bot_observer_ui import BotObserverUI
from app.ui.strategy_builder import StrategyBuilder
from app.ui.backtest import BacktestUI
from app.ui.live_monitor_ui import LiveMonitorUI
from app.ui.signal_journal import SignalJournalUI
from app.ui.data_export import DataExportUI
from app.ui.chart import ChartUI
from app.ui.settings import SettingsUI
from app.ui.help_tab import HelpTab

logger = setup_logger("app.ui.main_window")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MT5 Strategy Console")
        self.resize(1024, 768)
        
        # Core components
        provider.connect()
        self.bot_observer = BotObserver(provider)
        self.live_monitor = LiveMonitor(provider)
        self.alerter = DesktopAlerter(self)
        
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.setCentralWidget(self.tabs)
        
        # Tabs
        self.dashboard_tab = Dashboard(provider, self.bot_observer)
        self.builder_tab = StrategyBuilder()
        self.monitor_tab = LiveMonitorUI()
        self.backtest_tab = BacktestUI()
        self.chart_tab = ChartUI()
        self.journal_tab = SignalJournalUI()
        self.observer_tab = BotObserverUI(self.bot_observer)
        self.data_tab = DataExportUI(provider)
        self.settings_tab = SettingsUI()
        self.help_tab = HelpTab()
        
        # Wire backtest results → chart overlay
        self.backtest_tab.backtest_done.connect(self._on_backtest_done)

        self.tabs.addTab(self.dashboard_tab, "Dashboard")
        self.tabs.addTab(self.builder_tab, "Strategies")
        self.tabs.addTab(self.monitor_tab, "Monitor")
        self.tabs.addTab(self.backtest_tab, "Backtest")
        self.tabs.addTab(self.chart_tab, "Chart")
        self.tabs.addTab(self.journal_tab, "Journal")
        self.tabs.addTab(self.observer_tab, "Bot Observer")
        self.tabs.addTab(self.data_tab, "Data Export")
        self.tabs.addTab(self.settings_tab, "Settings")
        self.tabs.addTab(self.help_tab, "Help & Docs")
        
        logger.debug("MainWindow initialized.")

    def _on_backtest_done(self, signals, df):
        """Forward backtest results to the chart tab for signal overlay."""
        self.chart_tab.load_signals(signals, df)
        # Optionally switch to chart tab
        # self.tabs.setCurrentWidget(self.chart_tab)

    def closeEvent(self, event):
        # Gracefully stop the live monitor thread
        if hasattr(self.monitor_tab, '_stop'):
            try:
                self.monitor_tab._stop()
            except Exception:
                pass
        provider.disconnect()
        super().closeEvent(event)

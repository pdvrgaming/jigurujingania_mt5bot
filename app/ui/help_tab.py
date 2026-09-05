from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextBrowser

class HelpTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        
        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(True)
        
        html_content = """
        <style>
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #E0E0E0; background: #1E1E1E; padding: 20px; }
            h2 { color: #58A6FF; border-bottom: 1px solid #30363D; padding-bottom: 5px; }
            h3 { color: #79C0FF; margin-top: 20px; }
            p { margin-bottom: 15px; }
            ul { margin-bottom: 20px; }
            li { margin-bottom: 5px; }
            b { color: #FFFFFF; }
            i { color: #8B949E; }
            .highlight { background-color: #21262D; padding: 2px 5px; border-radius: 3px; font-family: monospace; }
            .warning { color: #FFA657; font-weight: bold; }
        </style>

        <h2>MT5 Strategy Console (v1) - Help & Documentation</h2>
        
        <h3>Philosophy</h3>
        <p>This application is designed as a strict <span class="highlight">Read-Only</span> analysis tool. It will <b class="warning">never</b> execute, modify, or close trades automatically. The core philosophy is:<br>
        <i>MARKET DATA &rarr; USER DEFINED RULES &rarr; DETERMINISTIC EVALUATION &rarr; OBSERVABLE SIGNAL &rarr; HUMAN DECISION</i></p>

        <h3>1. Dashboard</h3>
        <ul>
            <li><b>Status:</b> Verifies your connection to the local MT5 terminal. If it says disconnected, ensure MT5 is open.</li>
            <li><b>Live Feed:</b> A real-time log of signals generated across all your active strategies.</li>
        </ul>

        <h3>2. Strategy Builder (Full Control)</h3>
        <p>The Builder allows you to construct logic without constraints. It uses a Split-View design:</p>
        <ul>
            <li><b>Visual Editor (Left):</b> Construct Smart Money Concepts (SMC) rules using dropdowns (e.g., Close Crosses Above Constant, SMA Crosses EMA).</li>
            <li><b>JSON Editor (Right):</b> For advanced users, edit your strategy directly. The JSON format is transparent, and changes sync instantly to the visual editor.</li>
        </ul>

        <h3>3. Live Monitor (Multi-Strategy)</h3>
        <p>Once your strategy is built, go to the Monitor tab.</p>
        <ul>
            <li><b>Multi-Threading:</b> You can load up to 3 different strategies at once. Each runs in its own background thread.</li>
            <li><b>Market Awareness:</b> The monitor automatically pauses checking rules during weekend hours (Sat 02:30 IST to Mon 02:30 IST) to prevent false signals.</li>
        </ul>

        <h3>4. Backtester</h3>
        <p>Don't run a strategy blindly. Load it in the Backtester, fetch historical candles (M1, M15, H1, etc.), and simulate it to see Win Rate, Max Drawdown, and Total PnL.</p>

        <h3>5. Bot Observer</h3>
        <p>A specialized tracking tool designed to audit existing automated Expert Advisors (EAs) running on your MT5 terminal.</p>
        <ul>
            <li><b>Target Magic Number:</b> EAs attach a 'Magic Number' to their trades. Enter multiple Magic Numbers separated by commas (e.g., <span class="highlight">1001, 1002</span>) to track up to 5 bots.</li>
            <li><b>CSV Output:</b> Trades are categorized by Magic Number into separate CSV files in the <span class="highlight">data/observations/</span> folder.</li>
        </ul>
        """
        self.browser.setHtml(html_content)
        
        layout.addWidget(self.browser)
        self.setLayout(layout)

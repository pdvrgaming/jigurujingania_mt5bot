# MT5 Strategy Console (v1)

A professional desktop application designed for **Read-Only** MT5 market data analysis, SMC (Smart Money Concept) strategy validation, and live alerting. 

Built with PyQt/PySide6, this application connects directly to your local MetaTrader 5 terminal without ever placing a trade. It empowers you to build, backtest, and monitor complex trading logic deterministically.

## 🚀 Features

- **Read-Only Philosophy**: The app **will never** execute, modify, or close trades automatically. It strictly observes the market and generates signals for you to act upon.
- **SMC Strategy Builder**: Construct rules based on Price Action, Indicators (SMA, EMA, RSI, ATR), and Order Blocks using a visual UI or raw JSON.
- **Multi-Strategy Monitor**: Monitor up to 3 strategies simultaneously in real-time, in the background. Get audible or visual alerts when your setups form.
- **Bot Observer**: Audit external Expert Advisors (EAs). Track bot performance (by Magic Number) and export detailed trade histories to separate CSV tabs.
- **Historical Backtesting**: Load months of historical MT5 data (M1, M15, H1, etc.) and validate your strategy's win rate, max drawdown, and PnL before testing it live.
- **Market Hours Awareness**: Automatically detects weekend and holiday market closures to prevent false signals.

## 📦 Installation (Pre-built)

If you don't want to deal with Python, just download the pre-compiled executable from the **Releases** tab on GitHub:
1. Download `MT5_Strategy_Console.exe`.
2. Ensure MetaTrader 5 is open and logged into your broker.
3. Run the executable.

## 🛠 Run from Source (For Developers)

### Requirements
- Windows 10/11
- MetaTrader 5 Terminal installed and running
- Python 3.10+

### Setup
```bash
# Clone the repository
git clone https://github.com/pdvrgaming/jigurujingania_mt5bot.git
cd jigurujingania_mt5bot

# Create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the app
python -m app.main
```

## 🏗 Building the Executable
If you modify the source and want to build your own `.exe`, run:
```bash
python -m PyInstaller -y MT5_Strategy_Console.spec
```
The compiled output will be available in the `dist/` and `release/` folders.

## 📚 Documentation
Check out the **Help & Docs** tab inside the application for a full walkthrough of how to use the Dashboard, Builder, Monitor, and Bot Observer.

## ⚠️ Disclaimer
This tool is provided for educational and analytical purposes only. Trading financial markets carries a high level of risk. The authors are not responsible for any financial losses incurred while using this software.

# Building EXE

To build the executable for Windows:

```powershell
uv run pyinstaller --noconfirm --onedir --windowed --name "MT5_Strategy_Console"  app/main.py
```

Then copy the EXE to `release/MT5_Strategy_Console.exe`.

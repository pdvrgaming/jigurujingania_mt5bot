"""
Desktop alert system for MT5 Strategy Console.
Uses Windows toast notifications (winotify) with plyer as fallback.
"""
import threading
from app.core.logger import setup_logger

logger = setup_logger("app.core.notifier")


def _try_winotify(title: str, message: str, icon_path: str = "") -> bool:
    """Try Windows 10/11 toast via winotify package."""
    try:
        from winotify import Notification, audio
        toast = Notification(
            app_id="MT5 Strategy Console",
            title=title,
            msg=message,
            duration="short",
            icon=icon_path if icon_path else ""
        )
        toast.set_audio(audio.Default, loop=False)
        toast.show()
        return True
    except Exception:
        return False


def _try_plyer(title: str, message: str) -> bool:
    """Fallback: plyer cross-platform notifications."""
    try:
        from plyer import notification
        notification.notify(
            title=title,
            message=message[:250],  # plyer limit
            app_name="MT5 Strategy Console",
            timeout=8,
        )
        return True
    except Exception:
        return False


def _try_win32(title: str, message: str) -> bool:
    """Last resort: win10toast."""
    try:
        from win10toast import ToastNotifier
        toaster = ToastNotifier()
        toaster.show_toast(title, message[:200], duration=6, threaded=True)
        return True
    except Exception:
        return False


class Notifier:
    """
    Send desktop toast notifications for trading signals.
    Tries multiple backends in order, falls back gracefully.
    """

    def __init__(self, icon_path: str = ""):
        self.icon_path = icon_path
        self._enabled = True

    def enable(self, enabled: bool):
        self._enabled = enabled

    def notify(self, title: str, message: str):
        """Send notification asynchronously so it never blocks the UI."""
        if not self._enabled:
            return
        t = threading.Thread(
            target=self._send,
            args=(title, message),
            daemon=True
        )
        t.start()

    def _send(self, title: str, message: str):
        try:
            if _try_winotify(title, message, self.icon_path):
                logger.debug(f"Notification sent via winotify: {title}")
                return
            if _try_plyer(title, message):
                logger.debug(f"Notification sent via plyer: {title}")
                return
            if _try_win32(title, message):
                logger.debug(f"Notification sent via win10toast: {title}")
                return
            logger.warning(f"All notification backends failed for: {title}")
        except Exception as e:
            logger.error(f"Notification error: {e}")

    def signal_alert(self, strategy_name: str, symbol: str, timeframe: str,
                     direction: str, price: float, timestamp: str,
                     debug_lines: list[str]):
        """Format and send a trading signal notification."""
        emoji = "🔼" if direction == "BUY" else "🔽"
        title = f"{emoji} {direction} SIGNAL — {symbol} {timeframe}"
        conditions = "\n".join(f"  ✓ {d}" for d in debug_lines[:4])
        msg = (
            f"Strategy: {strategy_name}\n"
            f"Price: {price:,.5f}\n"
            f"Time: {timestamp}\n"
            f"Conditions:\n{conditions}"
        )
        self.notify(title, msg)


# Singleton
notifier = Notifier()

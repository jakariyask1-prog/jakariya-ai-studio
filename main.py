import os
import sys
import logging
import faulthandler
from pathlib import Path

# When running as a windowed application on Windows (PyInstaller console=False / pythonw),
# sys.stdout and sys.stderr are None. Provide safe fallbacks to prevent
# RuntimeError: sys.stderr is None and AttributeError on print / logging calls.
class _NullWriter:
    def write(self, text) -> int:
        return len(text) if text else 0

    def flush(self) -> None:
        pass

    def isatty(self) -> bool:
        return False


_has_real_stderr = sys.stderr is not None
if sys.stdout is None:
    sys.stdout = _NullWriter()
if sys.stderr is None:
    sys.stderr = _NullWriter()

# Enable automatic tracebacks on segmentation faults only if a real stderr exists
if _has_real_stderr:
    try:
        faulthandler.enable(file=sys.stderr)
    except Exception:
        pass

# Ensure UTF-8 output encoding for Windows consoles and logs
def _safe_reconfigure_utf8(stream) -> None:
    """Reconfigure a stream to UTF-8 when the runtime exposes a reconfigure API."""
    if stream is None or isinstance(stream, _NullWriter):
        return
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


_safe_reconfigure_utf8(sys.stdout)
_safe_reconfigure_utf8(sys.stderr)

# Configure file and console logging
try:
    log_dir = Path(sys.executable).resolve().parent / "logs" if getattr(sys, "frozen", False) else Path(__file__).resolve().parent / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "app.log"
    handlers = [logging.FileHandler(str(log_file), mode="a", encoding="utf-8")]
    if _has_real_stderr and not isinstance(sys.stdout, _NullWriter):
        handlers.append(logging.StreamHandler(sys.stdout))
except Exception:
    handlers = [logging.StreamHandler(sys.stdout)] if _has_real_stderr else []

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    handlers=handlers,
)

# Intercept uncaught Python exceptions and log them
def handle_uncaught_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logging.critical("Uncaught Exception: %s", exc_value, exc_info=(exc_type, exc_value, exc_traceback))

sys.excepthook = handle_uncaught_exception

# Suppress verbose third-party library DEBUG logs in terminal
for _logger in ("urllib3", "httpcore", "httpx", "asyncio", "speech_recognition", "PySide6", "openai"):
    logging.getLogger(_logger).setLevel(logging.WARNING)

# Suppress Qt Multimedia and Font Database warnings in terminal
os.environ["QT_LOGGING_RULES"] = "qt.multimedia*=false;qt.text.font.db=false"

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon, QFontDatabase
from PySide6.QtCore import qInstallMessageHandler, QtMsgType


def qt_message_handler(mode, context, message):
    msg_str = str(message)
    if any(k in msg_str for k in ("qt.multimedia", "qt.text.font.db", "DirectWrite:", "DWrite")):
        return
    levels = {
        QtMsgType.QtDebugMsg: logging.DEBUG,
        QtMsgType.QtInfoMsg: logging.INFO,
        QtMsgType.QtWarningMsg: logging.WARNING,
        QtMsgType.QtCriticalMsg: logging.ERROR,
        QtMsgType.QtFatalMsg: logging.CRITICAL,
    }
    level = levels.get(mode, logging.INFO)
    ctx_info = f" ({context.file}:{context.line})" if context and context.file else ""
    logging.getLogger("Qt").log(level, "%s%s", msg_str, ctx_info)


qInstallMessageHandler(qt_message_handler)

from app.database import DatabaseService
from app.ui.main_window import MainWindow
from app.utils.paths import get_resource_path, load_environment


def load_application_fonts() -> None:
    """Load custom application fonts from assets/fonts/."""
    fonts_dir = get_resource_path("assets", "fonts")
    if fonts_dir.exists() and fonts_dir.is_dir():
        for font_file in fonts_dir.glob("*.ttf"):
            font_id = QFontDatabase.addApplicationFont(str(font_file))
            if font_id == -1:
                logging.getLogger(__name__).warning("Failed to load font: %s", font_file.name)



def _check_api_key(app: QApplication) -> bool:
    """Check API keys and ensure environment settings are loaded.

    Allow the application to launch regardless of initial key state so the user
    can easily set their API keys directly inside the application Settings UI.
    """
    load_environment()
    try:
        from app.settings.configuration_service import ConfigurationService
        config_service = ConfigurationService()
        has_key = config_service.get_next_available_provider("supports_chat") is not None
        if has_key:
            logging.info("API key detected in configuration/environment.")
        else:
            logging.info("No API key set yet. User can configure API key in Settings UI.")
    except Exception as exc:
        logging.warning("API key resolution check failed: %s", exc)
    return True


from app.voice.utils.patch_speech import patch_speech_recognition


def main():
    # Load environment variables and SSL certificates early
    load_environment()

    # Apply speech_recognition patch before voice subsystem is initialized
    patch_speech_recognition()

    # Configure PySide6 plugin search paths BEFORE QApplication is created
    if getattr(sys, "frozen", False):
        meipass = Path(getattr(sys, "_MEIPASS", sys.executable)).resolve()
        exe_dir = Path(sys.executable).resolve().parent
        plugin_dirs = [
            meipass / "PySide6" / "plugins",
            meipass / "PySide6" / "Qt" / "plugins",
            meipass / "plugins",
            meipass,
            exe_dir / "PySide6" / "plugins",
            exe_dir / "plugins",
        ]
        from PySide6.QtCore import QCoreApplication
        valid_paths = []
        for p in plugin_dirs:
            if p.exists():
                valid_paths.append(str(p))
                QCoreApplication.addLibraryPath(str(p))
        if valid_paths:
            os.environ["QT_PLUGIN_PATH"] = os.pathsep.join(valid_paths)

    app = QApplication(sys.argv)

    # Load custom application fonts
    load_application_fonts()
    from PySide6.QtGui import QFont
    app_font = QFont("Segoe UI Variable", 10)
    app_font.setStyleHint(QFont.StyleHint.SansSerif)
    app.setFont(app_font)

    # Fail fast if the API key is missing — show a clear dialog before
    # the main window opens instead of crashing on the first message send.
    # _check_api_key always returns True by design — the app always opens so the
    # user can configure API keys via the in-app Settings UI without needing to
    # edit a .env file first.  The 'return 1' branch below is kept for future
    # use (e.g., a hard-fail mode toggle) but is currently unreachable.
    if not _check_api_key(app):
        return 1

    # Initialize persistent storage and apply any pending schema changes
    # before the UI can access conversations or messages.
    database_service = DatabaseService()

    try:
        database_service.initialize()

        icon_path = get_resource_path("assets", "icons", "logo.ico")
        if not icon_path.exists():
            icon_path = get_resource_path("assets", "icons", "logo.png")

        app.setWindowIcon(QIcon(str(icon_path)))

        window = MainWindow()
        window.show()

        # Prevent GC of main window while event loop is active
        setattr(app, "_main_window", window)

        return app.exec()
    finally:
        database_service.close()


if __name__ == "__main__":
    # Required for child-process based tool execution in a PyInstaller build.
    import multiprocessing
    multiprocessing.freeze_support()
    sys.exit(main())

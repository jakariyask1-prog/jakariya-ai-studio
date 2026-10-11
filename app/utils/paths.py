import os
import sys
from pathlib import Path


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        if hasattr(sys, "_MEIPASS") and sys._MEIPASS:
            return Path(sys._MEIPASS).resolve()
        return Path(sys.executable).resolve().parent

    return Path(__file__).resolve().parents[2]


def get_resource_path(*parts: str) -> Path:
    base_dir = get_base_dir()
    return base_dir.joinpath(*parts)


def get_env_path() -> Path:
    # In a PyInstaller build, prefer a user-managed .env beside the .exe.
    # This lets API keys be updated without rebuilding the application.
    if is_frozen():
        external_env = Path(sys.executable).resolve().parent / ".env"
        if external_env.exists():
            return external_env
    return get_resource_path(".env")


def load_environment() -> None:
    from dotenv import load_dotenv

    # Ensure certifi CA bundle is set for PyInstaller frozen executable
    try:
        import certifi
        ca_path = certifi.where()
        if ca_path and os.path.exists(ca_path):
            os.environ["SSL_CERT_FILE"] = ca_path
            os.environ["REQUESTS_CA_BUNDLE"] = ca_path
    except Exception as exc:
        import logging
        logging.getLogger(__name__).debug("Certifi CA bundle resolution skipped: %s", exc)

    env_path = get_env_path()
    if env_path.exists():
        load_dotenv(env_path, override=True)
    else:
        load_dotenv(override=True)


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def get_generated_images_dir() -> Path:
    """Return persistent, writable storage for generated images.

    A packaged application may be installed in a read-only location, so it
    must not write generated files beside the executable.  During local
    development we keep the files in the project's exports folder instead.
    """
    if is_frozen():
        local_app_data = os.getenv("LOCALAPPDATA")
        base = Path(local_app_data) if local_app_data else Path.home() / ".jakariya_ai_studio"
        return base / "Jakariya AI Studio" / "generated_images"
    return get_base_dir() / "exports" / "generated_images"


def get_uploaded_files_dir() -> Path:
    """Return persistent, writable storage for uploaded source files."""
    if is_frozen():
        local_app_data = os.getenv("LOCALAPPDATA")
        base = Path(local_app_data) if local_app_data else Path.home() / ".jakariya_ai_studio"
        return base / "Jakariya AI Studio" / "uploads"
    return get_base_dir() / "uploads"

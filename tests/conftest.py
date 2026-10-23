"""conftest.py — project-wide pytest configuration and shared fixtures.

Redirects Python's tempfile module to a dedicated sub-folder inside the
existing system TEMP directory. This avoids the Windows PermissionError
(WinError 5) that occurs when pytest-qt tries to create directories inside
a previously-locked 'pytest-of-<user>' folder in the system temp.
"""

import os
import tempfile
from pathlib import Path


# ---------------------------------------------------------------------------
# Redirect Python's tempfile to a fresh sub-folder we own inside system TEMP
# ---------------------------------------------------------------------------

def _setup_temp_dir() -> None:
    """Create and register a fresh temp dir we have full control over."""
    base_temp = Path(os.environ.get("TEMP", tempfile.gettempdir()))
    our_temp = base_temp / "pytest-jakariya-ai-studio"
    try:
        our_temp.mkdir(parents=True, exist_ok=True)
        tempfile.tempdir = str(our_temp)
        os.environ["TEMP"] = str(our_temp)
        os.environ["TMP"] = str(our_temp)
    except PermissionError:
        # If even that fails, fall back silently — tests will use system default
        pass


_setup_temp_dir()

try:
    import keyring
    import keyring.backend

    class InMemoryKeyring(keyring.backend.KeyringBackend):
        priority = 10

        def __init__(self):
            self.passwords = {}

        def get_password(self, service, username):
            return self.passwords.get((service, username))

        def set_password(self, service, username, password):
            self.passwords[(service, username)] = password

        def delete_password(self, service, username):
            self.passwords.pop((service, username), None)

    _in_memory_keyring = InMemoryKeyring()
    keyring.set_keyring(_in_memory_keyring)
except Exception:
    _in_memory_keyring = None

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(autouse=True)
def clean_keyring_fixture():
    """Ensure in-memory keyring is clean for each test."""
    if _in_memory_keyring is not None:
        _in_memory_keyring.passwords.clear()
    yield
    if _in_memory_keyring is not None:
        _in_memory_keyring.passwords.clear()


@pytest.fixture(autouse=True)
def reset_provider_manager_fixture():
    """Ensure singleton ProviderManager is clean after each test."""
    yield
    try:
        from app.providers.manager.provider_manager import ProviderManager
        ProviderManager.reset_instance()
    except Exception:
        pass


@pytest.fixture(scope="session")
def qapp():
    """Ensure a singleton QApplication exists across test execution."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class _QtBotHelper:
    """Lightweight test helper simulating qtbot for widget registration & events."""

    def __init__(self, app: QApplication):
        self._app = app
        self._widgets = []

    def addWidget(self, widget, *, before_close_func=None):
        self._widgets.append(widget)

    def wait(self, ms: int):
        self._app.processEvents()

    def waitExposed(self, widget, timeout=1000):
        self._app.processEvents()


@pytest.fixture
def qtbot(qapp):
    """Provide a reliable qtbot fixture for UI tests."""
    return _QtBotHelper(qapp)

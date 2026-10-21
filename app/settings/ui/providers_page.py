"""AI Providers settings page widget with API key inputs, base URLs, live connection testing,
priority ordering, and URL validation. API keys are shown as masked but stored securely
in Windows Credential Manager (keyring) — not in plaintext JSON.
"""

from __future__ import annotations

import re
import threading
import urllib.request
import urllib.error
from PySide6.QtCore import Signal, QObject
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.settings.settings_schema import ProviderConfig


# ---------------------------------------------------------------------------
# Background connection test worker (daemon thread based - crash safe)
# ---------------------------------------------------------------------------

class _TestBridge(QObject):
    finished_signal = Signal(bool, str)  # is_success, message


class ConnectionTestWorker:
    """Background thread worker to test provider API key connections without freezing UI.

    Uses a standard Python daemon thread and QObject signal bridge instead of QThread.
    This guarantees that window closing or object destruction can NEVER trigger
    fatal QThread destruction crashes (__fastfail / 0xc0000409).
    """

    def __init__(self, provider_id: str, api_key: str, base_url: str, parent: QObject | None = None) -> None:
        self.bridge = _TestBridge(parent)
        self.provider_id = provider_id
        self.api_key = api_key.strip()
        self.base_url = base_url.strip()
        self._is_cancelled = False
        self._thread: threading.Thread | None = None

    @property
    def finished_signal(self):
        return self.bridge.finished_signal

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def cancel(self) -> None:
        self._is_cancelled = True

    def isRunning(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _emit(self, success: bool, msg: str) -> None:
        if not self._is_cancelled:
            try:
                self.bridge.finished_signal.emit(success, msg)
            except RuntimeError:
                pass

    def _run(self) -> None:
        if not self.api_key:
            self._emit(False, "API Key is empty")
            return

        try:
            # Custom lightweight endpoint check per provider
            if self.provider_id == "google_ai_studio":
                url = f"https://generativelanguage.googleapis.com/v1beta/models?key={self.api_key}"
                req = urllib.request.Request(url, headers={"User-Agent": "JakariyaAIStudio/2.0"})
            elif self.provider_id == "openrouter":
                url = "https://openrouter.ai/api/v1/auth/key"
                req = urllib.request.Request(url, headers={"Authorization": f"Bearer {self.api_key}", "User-Agent": "JakariyaAIStudio/2.0"})
            elif self.provider_id == "anthropic":
                url = "https://api.anthropic.com/v1/messages"
                import json
                payload = json.dumps({"messages": [{"role": "user", "content": "ping"}], "model": "claude-3-haiku-20240307", "max_tokens": 1}).encode("utf-8")
                req = urllib.request.Request(url, data=payload, headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
            elif self.provider_id == "stability_ai":
                url = "https://api.stability.ai/v1/user/account"
                req = urllib.request.Request(url, headers={"Authorization": f"Bearer {self.api_key}", "User-Agent": "JakariyaAIStudio/2.0"})
            elif self.provider_id == "cartesia":
                url = "https://api.cartesia.ai/voices"
                req = urllib.request.Request(url, headers={"X-API-Key": self.api_key, "Cartesia-Version": "2024-06-10", "User-Agent": "JakariyaAIStudio/2.0"})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    if resp.status not in (200, 201):
                        self._emit(False, f"HTTP Error {resp.status}")
                        return
                # Verify active synthesis credits to avoid silent fallback confusion
                try:
                    import json
                    test_payload = json.dumps({
                        "model_id": "sonic-latest",
                        "transcript": "ping",
                        "voice": {"mode": "id", "id": "2c8d7dfb-ca84-4888-9600-8d8c54022dba"},
                        "output_format": {"container": "raw", "encoding": "pcm_s16le", "sample_rate": 16000}
                    }).encode("utf-8")
                    test_req = urllib.request.Request(
                        "https://api.cartesia.ai/tts/bytes",
                        data=test_payload,
                        headers={"X-API-Key": self.api_key, "Cartesia-Version": "2026-08-14", "Content-Type": "application/json", "User-Agent": "JakariyaAIStudio/2.0"}
                    )
                    with urllib.request.urlopen(test_req, timeout=6) as tts_resp:
                        if tts_resp.status in (200, 201):
                            self._emit(True, "Connection Successful (200 OK & Credits Active)")
                            return
                except urllib.error.HTTPError as tts_err:
                    if tts_err.code == 402:
                        self._emit(False, "Key OK, but Credits Limit Reached (402 Quota Exceeded). Recharge at play.cartesia.ai")
                        return
                    # Other errors fall through to outer HTTPError handler
                    raise
            elif self.provider_id == "fish_audio":
                url = "https://api.fish.audio/v1/model"
                req = urllib.request.Request(url, headers={"Authorization": f"Bearer {self.api_key}", "User-Agent": "JakariyaAIStudio/2.0"})
            elif self.provider_id == "brave_search":
                url = "https://api.search.brave.com/res/v1/web/search?q=Jakariya+AI+Studio"
                req = urllib.request.Request(
                    url,
                    headers={"X-Subscription-Token": self.api_key, "Accept": "application/json", "User-Agent": "JakariyaAIStudio/2.0"},
                )
            elif self.provider_id == "tavily":
                import json
                url = "https://api.tavily.com/search"
                payload = json.dumps({"api_key": self.api_key, "query": "Jakariya AI Studio", "max_results": 1}).encode("utf-8")
                req = urllib.request.Request(
                    url,
                    data=payload,
                    headers={"Content-Type": "application/json", "User-Agent": "JakariyaAIStudio/2.0"},
                )
            elif self.provider_id == "mistral":
                url = "https://api.mistral.ai/v1/models"
                req = urllib.request.Request(url, headers={"Authorization": f"Bearer {self.api_key}", "User-Agent": "JakariyaAIStudio/2.0"})
            elif self.provider_id == "elevenlabs":
                url = "https://api.elevenlabs.io/v1/user"
                req = urllib.request.Request(url, headers={"xi-api-key": self.api_key, "User-Agent": "JakariyaAIStudio/2.0"})
            elif self.provider_id == "huggingface":
                url = "https://huggingface.co/api/whoami-v2"
                req = urllib.request.Request(url, headers={"Authorization": f"Bearer {self.api_key}", "User-Agent": "JakariyaAIStudio/2.0"})
            elif self.provider_id == "llamaparse":
                if self.api_key.startswith("llx-") and len(self.api_key) > 20:
                    self._emit(True, "Key Validated (LlamaParse Format OK)")
                    return
                else:
                    self._emit(False, "Invalid Key (must start with 'llx-')")
                    return
            else:
                # Standard OpenAI-compatible models endpoint ping
                url = f"{self.base_url.rstrip('/')}/models" if self.base_url else "https://api.openai.com/v1/models"
                req = urllib.request.Request(url, headers={"Authorization": f"Bearer {self.api_key}", "User-Agent": "JakariyaAIStudio/2.0"})

            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status in (200, 201):
                    self._emit(True, "Connection Successful (200 OK)")
                else:
                    self._emit(False, f"HTTP Error {resp.status}")

        except urllib.error.HTTPError as err:
            err_msg = ""
            try:
                raw_body = err.read().decode("utf-8", errors="ignore")
                import json
                parsed = json.loads(raw_body)
                if isinstance(parsed, dict):
                    detail = parsed.get("detail") or parsed.get("error")
                    if isinstance(detail, dict):
                        err_msg = detail.get("message") or detail.get("code") or ""
                    elif isinstance(detail, str):
                        err_msg = detail
            except Exception:
                pass

            if err.code == 401:
                self._emit(False, f"Invalid API Key (401 Unauthorized){': ' + err_msg if err_msg else ''}")
            elif err_msg:
                self._emit(False, f"HTTP {err.code}: {err_msg}")
            else:
                self._emit(False, f"HTTP Error {err.code}")
        except urllib.error.URLError as err:
            self._emit(False, f"Network Error ({err.reason})")
        except Exception as exc:
            self._emit(False, f"Error: {str(exc)}")


# ---------------------------------------------------------------------------
# URL Validation helper
# ---------------------------------------------------------------------------

_URL_RE = re.compile(
    r"^https?://"                    # scheme
    r"(?:[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]+)"  # host + path
    r"$",
    re.IGNORECASE,
)


def _is_valid_url(url: str) -> bool:
    """Return True if url looks like a valid http/https URL."""
    return bool(_URL_RE.match(url.strip())) if url.strip() else True  # empty = OK (use default)


# ---------------------------------------------------------------------------
# Provider Card Widget
# ---------------------------------------------------------------------------

class ProviderCardWidget(QFrame):
    """Widget card representing a single AI Provider.

    API keys are displayed masked in the UI.  When keyring is available the
    key typed here is stored in Windows Credential Manager and never written
    to disk in plaintext; a sentinel '__keyring__' is written to JSON instead.
    When the card loads a saved '__keyring__' sentinel it shows a placeholder
    so the user knows a key is already stored without revealing it.
    """

    setting_changed = Signal()

    def __init__(self, provider_id: str, default_name: str, default_base_url: str,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.provider_id = provider_id
        self.default_name = default_name
        self.default_base_url = default_base_url
        self.priority = 1
        self._test_worker: ConnectionTestWorker | None = None
        self._key_in_vault = False   # True when saved key lives in keyring
        self._current_theme = "light"
        self._last_badge_text = "⚪ Not Configured"
        self._last_badge_style = "neutral"
        self._init_ui()

    def _init_ui(self) -> None:
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setObjectName("ProviderCard")
        self.setStyleSheet(
            "ProviderCardWidget#ProviderCard { border-radius: 12px; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(8)

        # --- Header Row: Provider Name + Enabled Checkbox + Status Badge ---
        header_layout = QHBoxLayout()

        self.name_label = QLabel(self.default_name)
        self.name_label.setStyleSheet("font-size: 14.5px; font-weight: 700;")
        header_layout.addWidget(self.name_label)

        header_layout.addStretch()

        self.status_badge = QLabel("⚪ Not Configured")
        self.status_badge.setObjectName("StatusBadge")
        self.status_badge.setStyleSheet(
            "color: #64748B; background-color: #F1F5F9; border: 1px solid #E2E8F0; "
            "font-size: 11px; font-weight: 600; padding: 3px 10px; border-radius: 6px;"
        )
        header_layout.addWidget(self.status_badge)

        self.enable_check = QCheckBox("Enable Provider")
        self.enable_check.toggled.connect(self._on_changed)
        header_layout.addWidget(self.enable_check)

        layout.addLayout(header_layout)

        # --- Form Layout: API Key, Base URL, Priority ---
        form_layout = QFormLayout()
        form_layout.setContentsMargins(0, 5, 0, 5)
        form_layout.setSpacing(8)

        # API Key Row with Show/Hide toggle
        key_layout = QHBoxLayout()
        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_edit.setPlaceholderText("Enter API Key...")
        self.key_edit.textChanged.connect(self._on_key_changed)
        key_layout.addWidget(self.key_edit)

        self.btn_toggle_eye = QPushButton("👁")
        self.btn_toggle_eye.setFixedWidth(36)
        self.btn_toggle_eye.setToolTip("Show / Hide API Key")
        self.btn_toggle_eye.clicked.connect(self._toggle_eye)
        key_layout.addWidget(self.btn_toggle_eye)

        form_layout.addRow("API Key:", key_layout)

        # Base URL (with inline validation feedback)
        url_layout = QHBoxLayout()
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText(self.default_base_url)
        self.url_edit.textChanged.connect(self._on_url_changed)
        url_layout.addWidget(self.url_edit)

        self.url_warn_label = QLabel("")
        self.url_warn_label.setStyleSheet("color: #F59E0B; font-size: 11px;")
        self.url_warn_label.hide()
        url_layout.addWidget(self.url_warn_label)

        form_layout.addRow("Base URL:", url_layout)

        # Priority spinbox
        priority_layout = QHBoxLayout()
        self.priority_spin = QSpinBox()
        self.priority_spin.setRange(1, 99)
        self.priority_spin.setValue(1)
        self.priority_spin.setToolTip(
            "Failover priority: lower number = higher priority (tried first)."
        )
        self.priority_spin.valueChanged.connect(self._on_changed)
        self.priority_spin.setFixedWidth(70)
        priority_layout.addWidget(self.priority_spin)
        priority_layout.addWidget(QLabel("(1 = highest priority)"))
        priority_layout.addStretch()
        form_layout.addRow("Failover Priority:", priority_layout)

        layout.addLayout(form_layout)

        # --- Action Row: Test Connection ---
        action_layout = QHBoxLayout()
        action_layout.addStretch()

        self.btn_test = QPushButton("🔌 Test Connection")
        self.btn_test.setStyleSheet(
            "background-color: #4F46E5; color: #FFFFFF; "
            "font-size: 12px; padding: 4px 12px; border-radius: 5px;"
        )
        self.btn_test.clicked.connect(self.test_connection)
        action_layout.addWidget(self.btn_test)

        layout.addLayout(action_layout)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _toggle_eye(self) -> None:
        if self.key_edit.echoMode() == QLineEdit.EchoMode.Password:
            if not self.key_edit.text().strip():
                saved_key = self._resolve_test_key()
                if saved_key:
                    self.key_edit.blockSignals(True)
                    self.key_edit.setText(saved_key)
                    self.key_edit.blockSignals(False)
            self.key_edit.setEchoMode(QLineEdit.EchoMode.Normal)
            self.btn_toggle_eye.setText("🔒")
        else:
            self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self.btn_toggle_eye.setText("👁")

    def _on_changed(self) -> None:
        if self.enable_check.isChecked():
            if self.key_edit.text().strip():
                self._set_badge("🟢 Active", "success")
            else:
                self._set_badge("⚠️ Enabled (Key Empty)", "warning")
        elif not self.key_edit.text().strip():
            self._set_badge("⚪ Not Configured", "neutral")
        else:
            self._set_badge("⚪ Disabled", "neutral")
        self.setting_changed.emit()

    def _on_key_changed(self) -> None:
        """When user types a new key, mark that vault sentinel is no longer valid."""
        self._key_in_vault = False
        self._on_changed()

    def _on_url_changed(self, text: str) -> None:
        if text and not _is_valid_url(text):
            self.url_warn_label.setText("⚠ Invalid URL")
            self.url_warn_label.show()
        else:
            self.url_warn_label.hide()
        self._on_changed()

    def url_is_valid(self) -> bool:
        """Return False if the current Base URL input fails validation."""
        url = self.url_edit.text().strip()
        return _is_valid_url(url)

    # ------------------------------------------------------------------
    # Connection test
    # ------------------------------------------------------------------

    def test_connection(self) -> None:
        """Run asynchronous connection test for provider."""
        if self._test_worker and self._test_worker.isRunning():
            self._test_worker.cancel()

        api_key = self._resolve_test_key()
        base_url = self.url_edit.text().strip() or self.default_base_url

        if not api_key:
            self._set_badge("⚠️ API Key Empty", "warning")
            return

        if not _is_valid_url(base_url):
            self._set_badge("⚠️ Invalid Base URL", "warning")
            return

        self.btn_test.setEnabled(False)
        self._set_badge("⏳ Testing...", "info")

        self._test_worker = ConnectionTestWorker(self.provider_id, api_key, base_url, self)
        self._test_worker.finished_signal.connect(self._on_test_finished)
        self._test_worker.start()

    def stop_test(self) -> None:
        """Cancel ongoing connection test safely."""
        if self._test_worker:
            self._test_worker.cancel()

    def _resolve_test_key(self) -> str:
        """Return the effective API key for a test (keyring, current field value, or .env)."""
        typed = self.key_edit.text().strip()
        if typed and typed != "__keyring__":
            return typed
        if self._key_in_vault:
            from app.settings.key_vault import retrieve_api_key
            vault_k = retrieve_api_key(self.provider_id)
            if vault_k:
                return vault_k
        from app.settings.settings_manager import SettingsManager
        return SettingsManager.instance().service.get_api_key(self.provider_id)

    def _on_test_finished(self, success: bool, message: str) -> None:
        try:
            self.btn_test.setEnabled(True)
            if success:
                self._set_badge("🟢 Connected", "success")
            else:
                self._set_badge(f"🔴 {message}", "error")
        except RuntimeError:
            pass  # Widget was already deleted when dialog closed

    def apply_theme(self, theme_name: str) -> None:
        """Apply active theme styles to provider card labels and buttons."""
        self._current_theme = theme_name
        from app.ui.styles import get_theme_palette
        p = get_theme_palette(theme_name)
        accent = p.get("accent", "#4F46E5")
        accent_hover = p.get("accent_hover", "#4338CA")

        self.name_label.setStyleSheet(f"font-size: 14.5px; font-weight: 700; color: {p['input_text']};")
        self.btn_test.setStyleSheet(
            f"QPushButton {{ background-color: {accent}; color: #FFFFFF; font-size: 12px; padding: 4px 12px; border-radius: 5px; border: none; }} "
            f"QPushButton:hover {{ background-color: {accent_hover}; }}"
        )
        self._set_badge(self._last_badge_text, self._last_badge_style)

    def _set_badge(self, text: str, style: str = "neutral") -> None:
        self._last_badge_text = text
        self._last_badge_style = style
        is_dark = str(getattr(self, "_current_theme", "light")).lower() in ("dark", "oled", "neon")
        if is_dark:
            STYLES = {
                "success": "color: #34D399; background-color: #064E3B; border: 1px solid #059669;",
                "error": "color: #F87171; background-color: #7F1D1D; border: 1px solid #DC2626;",
                "warning": "color: #FBBF24; background-color: #78350F; border: 1px solid #D97706;",
                "info": "color: #60A5FA; background-color: #1E3A8A; border: 1px solid #2563EB;",
                "neutral": "color: #94A3B8; background-color: #1E293B; border: 1px solid #334155;",
            }
        else:
            STYLES = {
                "success": "color: #059669; background-color: #D1FAE5; border: 1px solid #A7F3D0;",
                "error": "color: #DC2626; background-color: #FEE2E2; border: 1px solid #FECACA;",
                "warning": "color: #D97706; background-color: #FEF3C7; border: 1px solid #FDE68A;",
                "info": "color: #2563EB; background-color: #DBEAFE; border: 1px solid #BFDBFE;",
                "neutral": "color: #64748B; background-color: #F1F5F9; border: 1px solid #E2E8F0;",
            }
        base_qss = "font-size: 11px; font-weight: 600; padding: 3px 10px; border-radius: 6px;"
        self.status_badge.setText(text)
        self.status_badge.setStyleSheet(STYLES.get(style, STYLES["neutral"]) + base_qss)

    # ------------------------------------------------------------------
    # Load / Get config
    # ------------------------------------------------------------------

    def load_config(self, config: ProviderConfig) -> None:
        self.blockSignals(True)
        self.key_edit.blockSignals(True)
        self.enable_check.blockSignals(True)
        self.url_edit.blockSignals(True)
        self.priority_spin.blockSignals(True)

        self.enable_check.setChecked(config.enabled)
        self.url_edit.setText(config.base_url if config.base_url != self.default_base_url else "")
        self.priority_spin.setValue(config.priority if config.priority and config.priority > 0 else 1)
        self.priority = self.priority_spin.value()

        # Handle keyring sentinel
        if config.api_key == "__keyring__":
            from app.settings.key_vault import retrieve_api_key
            vault_k = retrieve_api_key(self.provider_id)
            if vault_k:
                self._key_in_vault = True
                self.key_edit.setText(vault_k)
                self.key_edit.setPlaceholderText("Enter API Key...")
                self._set_badge("🔑 Key in Vault", "info")
            else:
                self._key_in_vault = False
                from app.settings.settings_manager import SettingsManager
                env_key = SettingsManager.instance().service.get_api_key(self.provider_id)
                if env_key:
                    self.key_edit.setText(env_key)
                    self.key_edit.setPlaceholderText("Enter API Key...")
                    self._set_badge("🔑 Key in .env", "info")
                else:
                    self.key_edit.clear()
                    self.key_edit.setPlaceholderText("Enter API Key...")
                    self._set_badge("⚪ Not Configured", "neutral")
        elif config.api_key:
            self._key_in_vault = False
            self.key_edit.setText(config.api_key)
            self.key_edit.setPlaceholderText("Enter API Key...")
            self._set_badge("🔑 Key Present", "info")
        else:
            from app.settings.settings_manager import SettingsManager
            env_key = SettingsManager.instance().service.get_api_key(self.provider_id)
            if env_key:
                self._key_in_vault = False
                self.key_edit.setText(env_key)
                self.key_edit.setPlaceholderText("Enter API Key...")
                self._set_badge("🔑 Key in .env", "info")
            else:
                self._key_in_vault = False
                self.key_edit.clear()
                self.key_edit.setPlaceholderText("Enter API Key...")
                self._set_badge("⚪ Not Configured", "neutral")

        if config.enabled:
            effective_k = self.key_edit.text().strip()
            if effective_k:
                self._set_badge("🟢 Active", "success")
            else:
                self._set_badge("⚠️ Enabled (Key Empty)", "warning")
        elif not self.key_edit.text().strip():
            self._set_badge("⚪ Not Configured", "neutral")
        else:
            self._set_badge("⚪ Disabled", "neutral")

        self.priority_spin.blockSignals(False)
        self.url_edit.blockSignals(False)
        self.enable_check.blockSignals(False)
        self.key_edit.blockSignals(False)
        self.blockSignals(False)

    def get_config(self) -> ProviderConfig:
        typed_key = self.key_edit.text().strip()
        # Determine effective key value for storage
        if typed_key and typed_key != "__keyring__":
            key_val = typed_key          # New key typed by user
        elif self._key_in_vault:
            key_val = "__keyring__"      # Preserve vault reference
        else:
            key_val = ""                 # Empty

        raw_url = self.url_edit.text().strip()
        effective_url = raw_url if raw_url else self.default_base_url
        status_val = "active" if self.enable_check.isChecked() and (key_val or self._key_in_vault) else "not_configured"

        return ProviderConfig(
            name=self.default_name,
            enabled=self.enable_check.isChecked(),
            api_key=key_val,
            base_url=effective_url,
            status=status_val,
            priority=self.priority_spin.value(),
        )


# ---------------------------------------------------------------------------
# Providers Page
# ---------------------------------------------------------------------------

class ProvidersPage(QWidget):
    """AI Providers settings UI page (Google AI Studio, OpenRouter, Groq, Cerebras, Plugsky, etc.)."""

    setting_changed = Signal(str, object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._cards: dict[str, ProviderCardWidget] = {}
        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 12, 16, 8)
        main_layout.setSpacing(10)

        # Title & Subtitle Banner
        self.title_label = QLabel("🔌 AI Providers & API Credentials")
        self.title_label.setStyleSheet("font-size: 18px; font-weight: 700;")
        main_layout.addWidget(self.title_label)

        desc_label = QLabel(
            "API keys are stored securely in Windows Credential Manager — never written to disk in plaintext.\n"
            "Failover priority controls fallback order (lower number = attempted first)."
        )
        desc_label.setProperty("subtext", "true")
        desc_label.setWordWrap(True)
        main_layout.addWidget(desc_label)

        # Scroll Area for Provider Cards
        scroll = QScrollArea()
        scroll.setObjectName("providersScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea#providersScrollArea, QScrollArea#providersScrollArea > QWidget > QWidget { background: transparent; border: none; }")

        container = QWidget()
        container.setObjectName("providersContainer")
        container.setStyleSheet("QWidget#providersContainer { background: transparent; border: none; }")
        scroll_layout = QVBoxLayout(container)
        scroll_layout.setContentsMargins(0, 4, 10, 4)
        scroll_layout.setSpacing(10)

        # Provider Card Specs
        provider_specs = [
            ("google_ai_studio", "Google AI Studio (Gemini)", "https://generativelanguage.googleapis.com/v1beta/openai"),
            ("openrouter", "OpenRouter (Unified Multi-Model Gateway)", "https://openrouter.ai/api/v1"),
            ("groq", "Groq (Ultra High-Speed Llama & Mixtral)", "https://api.groq.com/openai/v1"),
            ("cerebras", "Cerebras (Wafer-Scale AI Engine)", "https://api.cerebras.ai/v1"),
            ("anthropic", "Anthropic (Claude)", "https://api.anthropic.com/v1"),
            ("ollama", "Ollama (Local Models)", "http://localhost:11434/v1"),
            ("plugsky", "Plugsky AI", "https://api.plugsky.com/v1"),
            ("tavily", "Tavily (Real-Time Web Search)", "https://api.tavily.com"),
            ("brave_search", "Brave Search API (Real-Time Web Search)", "https://api.search.brave.com/res/v1"),
            ("stability_ai", "Stability AI (Image Generation)", "https://api.stability.ai/v1"),
            ("cartesia", "Cartesia AI (Sonic Ultra-Fast Voice)", "https://api.cartesia.ai"),
            ("fish_audio", "Fish Audio (Expressive Neural Voice)", "https://api.fish.audio/v1"),
            ("mistral", "Mistral AI (Codestral & Mistral Large)", "https://api.mistral.ai/v1"),
            ("elevenlabs", "ElevenLabs (Voice Cloning & TTS)", "https://api.elevenlabs.io/v1"),
            ("llamaparse", "LlamaParse (Advanced PDF & Doc Parser)", "https://api.cloud.llamaindex.ai/api/v1"),
            ("huggingface", "Hugging Face (Inference & Hub Models)", "https://api-inference.huggingface.co"),
        ]

        for p_id, name, base_url in provider_specs:
            card = ProviderCardWidget(p_id, name, base_url, container)
            card.setting_changed.connect(self._on_card_changed)
            self._cards[p_id] = card
            scroll_layout.addWidget(card)

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

    def apply_theme(self, theme_name: str) -> None:
        """Propagate active theme to all provider cards and labels."""
        from app.ui.styles import get_theme_palette
        p = get_theme_palette(theme_name)
        if hasattr(self, "title_label"):
            self.title_label.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {p['input_text']};")
        for card in self._cards.values():
            if hasattr(card, "apply_theme") and callable(card.apply_theme):
                card.apply_theme(theme_name)

    def _on_card_changed(self) -> None:
        self.setting_changed.emit("providers", self.get_settings())

    def validate(self) -> list[str]:
        """Return a list of validation error messages, or empty list if all valid."""
        errors = []
        for p_id, card in self._cards.items():
            if not card.url_is_valid():
                errors.append(f"{card.default_name}: invalid Base URL.")
        return errors

    def load_settings(self, providers_dict: dict[str, ProviderConfig] | dict[str, dict]) -> None:
        """Populate provider cards from dict of ProviderConfig objects or dicts."""
        self.blockSignals(True)
        for p_id, card in self._cards.items():
            conf_data = providers_dict.get(p_id, {})
            if isinstance(conf_data, dict):
                conf_obj = ProviderConfig.from_dict(conf_data)
            elif isinstance(conf_data, ProviderConfig):
                conf_obj = conf_data
            else:
                conf_obj = ProviderConfig(name=card.default_name, base_url=card.default_base_url)
            card.load_config(conf_obj)
        self.blockSignals(False)

    def get_settings(self) -> dict[str, ProviderConfig]:
        """Return dictionary mapping provider_id to ProviderConfig objects."""
        return {p_id: card.get_config() for p_id, card in self._cards.items()}

    def stop_all_tests(self) -> None:
        """Cancel all running connection test workers across all cards."""
        for card in self._cards.values():
            card.stop_test()

import logging
import os
import sqlite3
import sys
from dataclasses import dataclass

from PySide6.QtCore import Slot, QPropertyAnimation, QEasingCurve
from PySide6.QtWidgets import (
    QMainWindow,
    QMessageBox,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QFileDialog,
    QGraphicsOpacityEffect,
)
from PySide6.QtGui import QDragEnterEvent, QDropEvent

from app.ui.sidebar import Sidebar
from app.ui.header import Header
from app.ui.chat_area import ChatArea
from app.ui.input_bar import InputBar
from app.ui.rename_chat_dialog import RenameChatDialog
from app.ui.status_bar import AppStatusBar

from app.chat.chat_controller import ChatController
from app.chat.chat_manager import ChatManager
from app.uploads import FileService, UploadedFile
from app.models.attachment import AttachmentInput
from app.export import ExportOptions
from app.export.business_logic import build_default_exporter_registry
from app.export.export_manager import ExportManager
from app.export.export_service import ExportService
from app.export.import_service import ImportService
from app.agent.agent_worker import AgentController

from app.voice import (
    VoiceController,
    VoiceManager,
    VoiceService,
    VoiceSettings,
    VoiceState,
)
from app.voice.business_logic.stt.google_stt import GoogleSTT
from app.voice.business_logic.stt.stt_registry import STTRegistry
from app.voice.business_logic.tts.edge_neural_tts import EdgeNeuralTTS
from app.voice.business_logic.tts.google_tts import GoogleTTS
from app.voice.business_logic.tts.tts_registry import TTSRegistry


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PendingMessage:
    """A user turn shown in the UI but saved only after a successful reply."""

    conversation_id: str
    content: str
    attachments: tuple[AttachmentInput, ...]


class MainWindow(QMainWindow):
    """
    Main application window.
    """

    def __init__(self):
        super().__init__()

        from PySide6.QtGui import QIcon
        from app.utils.paths import get_resource_path

        self.setWindowTitle("Jakariya AI Studio")
        self.resize(1400, 900)
        self.setMinimumSize(720, 480)
        self.setAcceptDrops(True)

        logo_path = get_resource_path("assets", "logo.ico")
        if not logo_path.exists():
            logo_path = get_resource_path("assets", "logo.png")
        if logo_path.exists():
            self.setWindowIcon(QIcon(str(logo_path)))

        # -----------------------------
        # Chat Controller & Voice Stack
        # -----------------------------
        self.controller = ChatController()

        self.stt_registry = STTRegistry()
        self.tts_registry = TTSRegistry()

        # Register ALL voice providers unconditionally at startup.
        # Availability (API key presence) is checked at runtime per-call,
        # not at registration time. This ensures providers added via Settings
        # UI after startup are always available in the registry.
        try:
            self.stt_registry.register(GoogleSTT())
        except Exception as exc:
            logger.debug("GoogleSTT registration skipped: %s", exc)

        try:
            from app.voice.business_logic.stt.groq_stt import GroqSTT
            self.stt_registry.register(GroqSTT())
        except Exception as exc:
            logger.debug("GroqSTT registration skipped: %s", exc)

        try:
            from app.voice.business_logic.stt.elevenlabs_stt import ElevenLabsSTT
            self.stt_registry.register(ElevenLabsSTT())
        except Exception as exc:
            logger.debug("ElevenLabsSTT registration skipped: %s", exc)

        try:
            self.tts_registry.register(EdgeNeuralTTS())
        except Exception as exc:
            logger.debug("EdgeNeuralTTS registration skipped: %s", exc)

        try:
            self.tts_registry.register(GoogleTTS())
        except Exception as exc:
            logger.debug("GoogleTTS registration skipped: %s", exc)

        try:
            from app.voice.business_logic.tts.cartesia_tts import CartesiaTTS
            self.tts_registry.register(CartesiaTTS())
        except Exception as exc:
            logger.debug("CartesiaTTS registration skipped: %s", exc)

        try:
            from app.voice.business_logic.tts.fish_audio_tts import FishAudioTTS
            self.tts_registry.register(FishAudioTTS())
        except Exception as exc:
            logger.debug("FishAudioTTS registration skipped: %s", exc)

        try:
            from app.voice.business_logic.tts.elevenlabs_tts import ElevenLabsTTS
            self.tts_registry.register(ElevenLabsTTS())
        except Exception as exc:
            logger.debug("ElevenLabsTTS registration skipped: %s", exc)

        # Load active voice providers from SettingsManager
        from app.settings.settings_manager import SettingsManager

        saved_voice = SettingsManager.instance().service.schema.voice
        available_stt = self.stt_registry.available_ids()
        available_tts = self.tts_registry.available_ids()

        stt_id = saved_voice.stt_provider_id if saved_voice.stt_provider_id in available_stt else "google_stt"
        tts_id = saved_voice.tts_provider_id if saved_voice.tts_provider_id in available_tts else "edge_neural_tts"

        initial_settings = VoiceSettings(
            stt_provider_id=stt_id,
            tts_provider_id=tts_id,
            voice_id=saved_voice.voice_id,
            custom_voices=list(getattr(saved_voice, "custom_voices", []) or []),
            auto_send=saved_voice.auto_send,
            voice_response=saved_voice.voice_response,
            silence_timeout_ms=saved_voice.silence_timeout_ms,
            vad_threshold=saved_voice.vad_threshold,
            language=saved_voice.language,
        )

        self.voice_service = VoiceService(
            self.stt_registry,
            self.tts_registry,
            settings=initial_settings,
        )
        self.voice_manager = VoiceManager(self.voice_service)
        self.voice_controller = VoiceController(self.voice_manager)

        # Chat Management
        # -----------------------------
        # The manager owns the active conversation state. Sidebar controls,
        # history rendering, and message persistence are connected in later
        # Phase 3 steps.
        self.chat_manager = ChatManager()
        self.chat_manager.initialize()
        self._pending_message: PendingMessage | None = None
        self._chat_search_query = ""
        self.file_service = FileService()
        self.pending_uploads: list[UploadedFile] = []

        # --- Startup orphan sweep ----------------------------------------
        # Remove any file in the uploads folder that the database no longer
        # references.  This catches files left behind by crashes, failed API
        # calls, or any previous incomplete cleanup path.
        _known_paths = self.chat_manager.get_all_stored_attachment_paths()
        _removed = self.file_service.sweep_orphans(_known_paths)
        if _removed:
            import logging
            logging.getLogger(__name__).info(
                "Startup orphan sweep removed %d unreferenced upload file(s).", _removed
            )
        # -----------------------------------------------------------------

        self.export_manager = ExportManager(
            ExportService(self.chat_manager, build_default_exporter_registry())
        )
        self.import_service = ImportService(self.chat_manager)
        self.agent_controller = AgentController()
        self._settings_dialog = None

        # -----------------------------
        # Central Widget
        # -----------------------------
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # -----------------------------
        # Main Layout
        # -----------------------------
        main_layout = QHBoxLayout(central_widget)

        # Left Sidebar
        self.sidebar = Sidebar()

        # Right Layout
        right_layout = QVBoxLayout()

        self.header = Header()
        self.chat_area = ChatArea()
        self.input_bar = InputBar()

        right_layout.addWidget(self.header, 0)
        right_layout.addWidget(self.chat_area, 1)
        right_layout.addWidget(self.input_bar, 0)

        main_layout.addWidget(self.sidebar, 1)
        main_layout.addLayout(right_layout, 4)

        from app.ui.styles import GLOBAL_APP_STYLE
        self.setStyleSheet(GLOBAL_APP_STYLE)

        # -----------------------------
        # Signal Connections
        # -----------------------------
        self.input_bar.send_requested.connect(
            self.send_message
        )
        self.chat_area.prompt_selected.connect(self.send_message)

        self.input_bar.attach_requested.connect(self.select_files)
        self.input_bar.folder_requested.connect(self.select_project_folder)
        self.input_bar.workspace_cleared.connect(self.clear_project_workspace)
        self.input_bar.attachment_remove_requested.connect(self.remove_pending_attachment)
        self.header.export_requested.connect(self.export_active_chat)
        self.header.settings_requested.connect(self.open_settings_window)
        self.header.upgrade_requested.connect(self.open_upgrade_window)
        self.header.auth_requested.connect(self.open_auth_window)
        self.chat_area.response_export_requested.connect(self.export_response)
        self.header.set_export_formats(self.export_manager.available_formats())

        # Voice UI Connections
        self.input_bar.voice_requested.connect(self.on_voice_button_clicked)
        self.input_bar.live_requested.connect(self.on_live_button_clicked)
        self.voice_controller.state_changed.connect(self.input_bar.set_voice_state)

        # Select initial voice language and connect update signal
        self.voice_controller.state_changed.connect(self.on_voice_state_changed)
        self.voice_controller.transcript_ready.connect(self.on_voice_transcript_ready)
        self.voice_controller.response_started.connect(self.chat_area.start_assistant_stream)
        self.voice_controller.partial_token.connect(self.chat_area.append_assistant_stream)
        self.voice_controller.response_ready.connect(self.on_voice_response_ready)
        self.voice_controller.audio_ready.connect(self.on_voice_audio_ready)
        self.voice_controller.error_occurred.connect(self.on_voice_error)
        
        # Voice UI Animations
        self.voice_controller.mic_manager.level_updated.connect(self.input_bar.update_mic_level)
        self.voice_controller.player.state_changed.connect(self.input_bar.set_playing_state)

        # Provide history and selected model to the controller
        self.voice_controller.set_history_provider(self._get_voice_history)
        self.voice_controller.set_model_provider(self.header.selected_model)
        self.voice_controller.set_provider_id_provider(self.header.selected_provider)

        self.sidebar.new_chat_requested.connect(
            self.create_new_chat
        )
        self.sidebar.import_requested.connect(
            self.import_chat
        )

        self.agent_controller.started.connect(self.chat_area.start_agent_bubble)
        self.agent_controller.progress.connect(
            lambda msg, tool_name, is_tool: self.chat_area.update_agent_progress(msg, tool_name, is_tool)
        )
        self.agent_controller.finished.connect(self.on_agent_finished)
        self.agent_controller.failed.connect(self.on_agent_failed)
        self.agent_controller.request_approval.connect(self.on_request_tool_approval)

        self.sidebar.conversation_selected.connect(
            self.switch_chat
        )

        self.sidebar.rename_requested.connect(
            self.rename_chat
        )

        self.sidebar.delete_requested.connect(
            self.delete_chat
        )

        self.sidebar.bulk_delete_requested.connect(
            self.delete_multiple_chats
        )

        self.sidebar.search_changed.connect(
            self.search_chats
        )

        self.controller.reply_ready.connect(
            self.on_reply
        )

        self.controller.error.connect(
            self.on_error
        )

        self.controller.thinking.connect(
            self.on_thinking
        )

        # Forward partial streaming updates to the chat area
        self.controller.partial.connect(
            self.on_partial
        )

        # When the worker starts, prepare the chat area for streaming
        self.controller.thinking.connect(
            self.chat_area.start_assistant_stream
        )

        # Restore the latest conversation when the application opens.
        self.load_active_chat()

        # ── Install custom status bar ────────────────────────────────────
        self._app_status_bar = AppStatusBar(self)
        self.setStatusBar(self._app_status_bar)

        # Keep model badge in sync with the model selector
        self.header.model_selector.currentIndexChanged.connect(self._sync_model_badge)
        self._sync_model_badge()

        # Apply initial saved theme
        self._sync_theme_from_config()
        self.update_status_bar("Ready")

        # Prompt for login or 3-day free trial on first launch if not logged in
        from PySide6.QtCore import QTimer
        QTimer.singleShot(700, self._check_first_launch_auth)

    def apply_theme(self, theme_name: str) -> None:
        """Propagate active theme changes to all central application widgets."""
        from app.ui.styles import get_global_app_style
        self.setStyleSheet(get_global_app_style(theme_name))
        self.sidebar.apply_theme(theme_name)
        self.header.apply_theme(theme_name)
        self.input_bar.apply_theme(theme_name)
        self.chat_area.set_theme(theme_name)
        self._app_status_bar.apply_theme(theme_name)

        # Apply Windows 11 native Mica / Acrylic backdrop and dark mode titlebar
        try:
            from app.ui.dwm_blur import apply_dwm_backdrop
            is_dark = str(theme_name).lower() in ("dark", "oled", "neon")
            apply_dwm_backdrop(int(self.winId()), is_dark=is_dark, backdrop_type="mica")
        except Exception as exc:
            logger.debug("[MainWindow] DWM backdrop application skipped: %s", exc)

        # Refresh active conversation rendering so existing bubbles adapt to new theme colors
        try:
            if hasattr(self, "chat_manager"):
                active_chat = self.chat_manager.get_active_chat()
                if active_chat:
                    msgs = self.chat_manager.get_messages(active_chat.id)
                    if msgs:
                        self.chat_area.load_messages(
                            msgs,
                            self.chat_manager.get_conversation_attachments(active_chat.id),
                        )
        except Exception as exc:
            logger.debug("[MainWindow] Chat refresh on theme change: %s", exc)

    def _sync_theme_from_config(self) -> None:
        """Read saved theme preference from SettingsManager and apply it."""
        try:
            from app.settings.settings_manager import SettingsManager
            active_theme = SettingsManager.instance().service.schema.appearance.theme
            self.apply_theme(active_theme)
        except Exception as exc:
            logger.debug("[MainWindow] Could not load saved theme: %s", exc)
            self.apply_theme("light")

    # ------------------------------------------------------------------
    # Status bar helpers
    # ------------------------------------------------------------------


    def _sync_model_badge(self) -> None:
        """Push current model name into the status bar badge pill."""
        model_text = str(self.header.model_selector.currentText() or "").strip()
        self._app_status_bar.set_model_badge(model_text)

    def update_status_bar(self, message: str = "Ready") -> None:
        """Show *message* on the status bar (INFO severity, transient)."""
        self._app_status_bar.show_info(message)
        self._app_status_bar.set_idle_message(message)



    # --------------------------------------------------

    def send_message(self, message: str):
        """Display a user turn and send it with only this chat's history."""
        conversation = self.chat_manager.get_active_chat()
        attachments = list(self.pending_uploads)
        history = self.chat_manager.get_api_messages(conversation.id)
        prompt_with_files = self.file_service.build_message_content(message, attachments)
        self._pending_message = PendingMessage(
            conversation_id=conversation.id,
            content=message,
            attachments=tuple(item.to_attachment_input() for item in attachments),
        )
        self.chat_area.append_user_message(message, attachments)

        self.input_bar.disable()

        if self.input_bar.is_agent_mode_active():
            from app.licensing.license_manager import LicenseManager
            if not LicenseManager.instance().is_feature_allowed("unlimited_agent"):
                self.input_bar.enable()
                self.open_upgrade_window("Autonomous ReAct Agent সুবিধাটি Pro এবং ৩ দিনের ফ্রি ট্রায়ালের অন্তর্ভুক্ত।")
                return

            from app.providers.models.chat_request import MessageContent
            history_msgs = [MessageContent(role=m["role"], content=m["content"]) for m in history]
            self.statusBar().showMessage("Autonomous ReAct Agent executing task...")
            self.agent_controller.run_agent_task(
                # FileService already includes the instruction text in its
                # multimodal payload. Passing it unchanged preserves image
                # blocks for vision-capable providers and avoids duplicating
                # the prompt for text-only attachments.
                task_description=prompt_with_files,
                model=self.header.selected_model(),
                provider_id=self.header.selected_provider(),
                history_msgs=history_msgs,
            )
            self.pending_uploads.clear()
            self.input_bar.clear_attachments()
            return

        self.controller.send_message(
            prompt_with_files,
            history,
            model=self.header.selected_model(),
            provider_id=self.header.selected_provider(),
        )
        self.pending_uploads.clear()
        self.input_bar.clear_attachments()

    def select_files(self):
        """Choose and validate files without putting parsing logic in the UI."""
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Attach files",
            "",
            "All Supported (*.pdf *.docx *.txt *.md *.csv *.json *.html *.xlsx *.png *.jpg *.jpeg *.webp *.gif);;"
            "Documents (*.pdf *.docx *.txt *.md *.csv *.json *.html *.xlsx);;"
            "Images (*.png *.jpg *.jpeg *.webp *.gif)",
        ) 
        if not paths:
            return

        self.add_selected_files(paths)

    def select_project_folder(self):
        """Open a directory picker for selecting a project workspace folder."""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Project Folder / Workspace (Antigravity Mode)",
            "",
            QFileDialog.Option.ShowDirsOnly,
        )
        if not folder:
            return
        self.set_project_workspace(folder)

    def set_project_workspace(self, folder_path: str):
        """Set active project workspace and configure agent file tool boundaries."""
        from pathlib import Path
        p = Path(folder_path).resolve()
        if not p.is_dir():
            self._app_status_bar.show_error(f"Not a valid directory: {folder_path}")
            return
        from app.agent.tools.file_tool import set_active_workspace
        set_active_workspace(str(p))
        self.input_bar.set_workspace_folder(str(p))
        self._app_status_bar.show_success(f"Active Workspace: {p.name}")

    def clear_project_workspace(self):
        """Clear active project workspace."""
        from app.agent.tools.file_tool import set_active_workspace
        set_active_workspace(None)
        self.input_bar.clear_workspace_folder()
        self._app_status_bar.show_info("Workspace disconnected")


    def add_selected_files(self, paths: list[str]):
        """Validate files selected by the picker or dropped into the window."""
        if not paths:
            return

        try:
            self.pending_uploads.extend(self.file_service.add_files(paths))
        except (OSError, ValueError) as error:
            self._app_status_bar.show_error(str(error))
            self.chat_area.append_error(str(error))
            return

        self.input_bar.set_attachments(self.pending_uploads)
        self._app_status_bar.show_success(f"Attached {len(paths)} file(s)")

    def remove_pending_attachment(self, index: int):
        """Remove a file from the outgoing message before it is sent."""
        if index < 0 or index >= len(self.pending_uploads):
            return
        removed = self.pending_uploads.pop(index)
        self.file_service.discard_files((removed,))
        self.input_bar.set_attachments(self.pending_uploads)
        self._app_status_bar.show_info(f"Removed attachment: {removed.original_name}")

    def clear_pending_attachments(self):
        self.file_service.discard_files(self.pending_uploads)
        self.pending_uploads.clear()
        self.input_bar.clear_attachments()

    def export_active_chat(self, format_id: str):
        """Prompt for a destination and export the active conversation."""
        from app.licensing.license_manager import LicenseManager
        pro_exports = {
            "pdf": "styled_pdf_export",
            "docx": "docx_export",
            "xlsx": "excel_export",
        }
        req_feature = pro_exports.get(format_id)
        if req_feature and not LicenseManager.instance().is_feature_allowed(req_feature):
            self.open_upgrade_window(f"{format_id.upper()} এক্সপোর্ট সুবিধাটি Pro এবং ৩ দিনের ফ্রি ট্রায়ালের অন্তর্ভুক্ত।")
            return

        try:
            export_format = next(
                item for item in self.export_manager.available_formats()
                if item.format_id == format_id
            )
        except StopIteration:
            self._app_status_bar.show_warning("That export format is unavailable.")
            return

        conversation = self.chat_manager.get_active_chat()
        safe_title = "".join(
            character if character not in '<>:"/\\|?*' else "_"
            for character in conversation.title
        ).strip() or "conversation"
        destination, _ = QFileDialog.getSaveFileName(
            self,
            "Export conversation",
            f"{safe_title}{export_format.file_extension}",
            export_format.file_filter,
        )
        if not destination:
            return

        try:
            result = self.export_manager.export_conversation(
                destination, ExportOptions(format_id), conversation.id
            )
        except (OSError, ValueError, RuntimeError) as error:
            self._app_status_bar.show_error(f"Could not export chat: {error}")
            return

        self._app_status_bar.show_success(
            f"Exported {result.message_count} messages to {result.destination.name}"
        )

    def export_response(self, format_id: str, content: str):
        from app.licensing.license_manager import LicenseManager
        pro_exports = {
            "pdf": "styled_pdf_export",
            "docx": "docx_export",
            "xlsx": "excel_export",
        }
        req_feature = pro_exports.get(format_id)
        if req_feature and not LicenseManager.instance().is_feature_allowed(req_feature):
            self.open_upgrade_window(f"{format_id.upper()} এক্সপোর্ট সুবিধাটি Pro এবং ৩ দিনের ফ্রি ট্রায়ালের অন্তর্ভুক্ত।")
            return

        export_format = next((item for item in self.export_manager.available_formats() if item.format_id == format_id), None)
        if export_format is None:
            return
        destination, _ = QFileDialog.getSaveFileName(self, "Download AI response", f"ai_response{export_format.file_extension}", export_format.file_filter)
        if not destination:
            return
        try:
            result = self.export_manager.export_response(destination, ExportOptions(format_id), "AI Response", content)
        except (OSError, ValueError, RuntimeError) as error:
            self._app_status_bar.show_error(f"Could not save response: {error}")
            return
        self._app_status_bar.show_success(f"Saved: {result.destination.name}")

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls() and any(url.isLocalFile() for url in event.mimeData().urls()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        if not paths:
            event.ignore()
            return
        import os
        dir_paths = [p for p in paths if os.path.isdir(p)]
        file_paths = [p for p in paths if not os.path.isdir(p)]
        if dir_paths:
            self.set_project_workspace(dir_paths[0])
        if file_paths:
            self.add_selected_files(file_paths)
        event.acceptProposedAction()

    # --------------------------------------------------

    def create_new_chat(self):
        """Create a fresh conversation and prepare the UI for its first message."""
        if not self.input_bar.send_button.isEnabled():
            self._app_status_bar.show_warning("Please wait for the current response.")
            return

        conversation = self.chat_manager.create_new_chat()
        self.sidebar.clear_search()
        self.chat_area.clear_chat()
        self.header.set_chat_title(conversation.title)
        self.input_bar.clear()
        self.clear_pending_attachments()
        self.input_bar.focus_input()
        self.refresh_sidebar()
        self._app_status_bar.show_success("New chat created")

    # --------------------------------------------------

    def switch_chat(self, conversation_id: str):
        """Select a chat and replace the displayed conversation history."""
        if not self.input_bar.send_button.isEnabled():
            self._app_status_bar.show_warning("Please wait for the current response.")
            return

        conversation = self.chat_manager.select_chat(conversation_id)
        self.load_active_chat()
        self.clear_pending_attachments()
        self.input_bar.focus_input()
        self._app_status_bar.show_info(f"Opened: {conversation.title}")

    def open_settings_window(self) -> None:
        """Open central Settings & Personalization Window (non-modal & minimizable)."""
        from app.settings.ui.settings_window import SettingsWindow

        # If window is already open or minimized, restore and focus it
        if getattr(self, "_settings_dialog", None) is not None and self._settings_dialog.isVisible():
            if self._settings_dialog.isMinimized():
                self._settings_dialog.showNormal()
            self._settings_dialog.raise_()
            self._settings_dialog.activateWindow()
            return

        dialog = SettingsWindow(self)
        self._settings_dialog = dialog
        dialog.theme_preview_requested.connect(self.apply_theme)
        # settings_applied fires on every Apply click — sync runtime immediately
        dialog.settings_applied.connect(self._sync_all_runtime_settings)

        def _on_finished(result: int) -> None:
            if result == SettingsWindow.DialogCode.Accepted:
                self._sync_all_runtime_settings()
            else:
                self._sync_theme_from_config()
            self._settings_dialog = None

        dialog.finished.connect(_on_finished)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _sync_all_runtime_settings(self) -> None:
        """Apply ALL saved settings at runtime — called after Apply or Save & Close."""
        from app.settings.settings_manager import SettingsManager
        schema = SettingsManager.instance().service.schema

        # 1. Theme
        self._sync_theme_from_config()

        # 2. Voice settings
        self._sync_voice_settings_from_config()

        # 3. Chat history limit — pass to controller
        try:
            self.controller.worker.max_history_turns = schema.chat.max_history_turns
        except Exception:
            pass

        # 4. Log level
        try:
            import logging as _log
            _log.getLogger().setLevel(getattr(_log, schema.advanced.log_level.upper(), _log.INFO))
        except Exception:
            pass

        # 5. Notifications enabled flag (store for later use in on_reply etc.)
        self._notifications_enabled = schema.general.notifications_enabled

        # 6. Refresh provider/model dropdowns in header
        try:
            self.header.refresh_providers_and_models()
        except Exception:
            pass

        logger.info(
            "[MainWindow] Runtime settings synced — theme=%s history=%d log=%s notif=%s",
            schema.appearance.theme,
            schema.chat.max_history_turns,
            schema.advanced.log_level,
            schema.general.notifications_enabled,
        )

    def _check_first_launch_auth(self) -> None:
        """Prompt user for login or 3-day free trial on startup if not already logged in."""
        if "pytest" in sys.modules or "unittest" in sys.modules or os.environ.get("PYTEST_CURRENT_TEST"):
            return
        try:
            from app.auth.auth_service import AuthService
            if not AuthService.instance().is_logged_in:
                self.open_auth_window()
        except Exception as exc:
            logger.debug("[MainWindow] First launch auth prompt skipped: %s", exc)

    def open_auth_window(self) -> None:
        """Open the Login and 3-Day Free Trial signup dialog."""
        from app.auth.ui.auth_dialog import AuthDialog
        theme = getattr(self, "_current_theme", "light")
        dialog = AuthDialog(self, theme=theme)
        dialog.authenticated.connect(lambda _: self.header.refresh_plan_badge())
        dialog.exec()
        self.header.refresh_plan_badge()

    def open_upgrade_window(self, reason: str = "") -> None:
        """Open the Pro upgrade dialog and license key activation."""
        if reason:
            self._app_status_bar.show_warning(reason)
        from app.licensing.ui.upgrade_dialog import UpgradeDialog
        theme = getattr(self, "_current_theme", "light")
        dialog = UpgradeDialog(self, theme=theme)
        dialog.license_activated.connect(self.header.refresh_plan_badge)
        dialog.exec()
        self.header.refresh_plan_badge()

    def _sync_voice_settings_from_config(self) -> None:
        """Sync active VoiceService and VoiceController settings from saved ConfigurationService schema."""
        from app.settings.settings_manager import SettingsManager
        saved_voice = SettingsManager.instance().service.schema.voice
        available_stt = self.stt_registry.available_ids()
        available_tts = self.tts_registry.available_ids()

        stt_id = saved_voice.stt_provider_id if saved_voice.stt_provider_id in available_stt else (
            "google_stt" if "google_stt" in available_stt else ""
        )
        tts_id = saved_voice.tts_provider_id if saved_voice.tts_provider_id in available_tts else (
            "edge_neural_tts" if "edge_neural_tts" in available_tts else ""
        )

        updated = VoiceSettings(
            stt_provider_id=stt_id,
            tts_provider_id=tts_id,
            voice_id=saved_voice.voice_id,
            custom_voices=list(getattr(saved_voice, "custom_voices", []) or []),
            auto_send=saved_voice.auto_send,
            voice_response=saved_voice.voice_response,
            silence_timeout_ms=saved_voice.silence_timeout_ms,
            vad_threshold=saved_voice.vad_threshold,
            language=saved_voice.language,
        )
        self.voice_service.update_settings(updated)
        self.voice_controller.update_settings(updated)

        logger.info(
            "[MainWindow] Voice settings synced — STT=%s TTS=%s VoiceID=%s",
            stt_id, tts_id, saved_voice.voice_id,
        )


    # --------------------------------------------------

    def rename_chat(self, conversation_id: str):
        """Prompt for and persist a new title for a sidebar conversation."""
        if not self.input_bar.send_button.isEnabled():
            self._app_status_bar.show_warning("Please wait for the current response.")
            return

        try:
            conversation = self.chat_manager.get_chat(conversation_id)
        except ValueError as error:
            self._app_status_bar.show_error(f"Could not open rename dialog: {error}")
            self.refresh_sidebar()
            return

        dialog = RenameChatDialog(conversation.title, self)
        if dialog.exec() != RenameChatDialog.DialogCode.Accepted:
            return

        try:
            renamed_chat = self.chat_manager.rename_chat(conversation_id, dialog.title)
        except ValueError as error:
            self._app_status_bar.show_error(f"Could not rename chat: {error}")
            return

        if renamed_chat.id == self.chat_manager.active_conversation_id:
            self.header.set_chat_title(renamed_chat.title)
        self.refresh_sidebar()
        self._app_status_bar.show_success("Chat renamed")

    # --------------------------------------------------

    def delete_chat(self, conversation_id: str):
        """Confirm and delete a conversation, then refresh the visible state."""
        if not self.input_bar.send_button.isEnabled():
            self._app_status_bar.show_warning("Please wait for the current response.")
            return

        try:
            conversation = self.chat_manager.get_chat(conversation_id)
        except ValueError as error:
            self._app_status_bar.show_error(f"Could not delete chat: {error}")
            self.refresh_sidebar()
            return

        choice = QMessageBox.question(
            self,
            "Delete Chat",
            f"Delete '{conversation.title}'? This cannot be undone.",
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Ok,
            QMessageBox.StandardButton.Cancel,
        )
        if choice != QMessageBox.StandardButton.Ok:
            return

        was_active = conversation_id == self.chat_manager.active_conversation_id
        try:
            attachments_by_message = self.chat_manager.get_conversation_attachments(
                conversation_id
            )
            self.chat_manager.delete_chat(conversation_id)
        except (ValueError, RuntimeError, sqlite3.Error) as error:
            self._app_status_bar.show_error(f"Could not delete chat: {error}")
            self.refresh_sidebar()
            return

        self.file_service.discard_files(
            attachment
            for attachments in attachments_by_message.values()
            for attachment in attachments
        )

        if was_active:
            self.load_active_chat()
        else:
            self.refresh_sidebar()
        self._app_status_bar.show_success("Chat deleted")

    def delete_multiple_chats(self, conversation_ids: list[str]):
        """Confirm and delete multiple selected conversations at once."""
        if not conversation_ids:
            return

        if not self.input_bar.send_button.isEnabled():
            self._app_status_bar.show_warning("Please wait for the current response.")
            return

        count = len(conversation_ids)
        choice = QMessageBox.question(
            self,
            "Delete Selected Chats",
            f"Delete {count} selected conversation{'s' if count > 1 else ''}? This cannot be undone.",
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Ok,
            QMessageBox.StandardButton.Cancel,
        )
        if choice != QMessageBox.StandardButton.Ok:
            return

        deleted_count = 0
        was_active_deleted = False

        for cid in conversation_ids:
            if cid == self.chat_manager.active_conversation_id:
                was_active_deleted = True
            try:
                attachments_by_message = self.chat_manager.get_conversation_attachments(cid)
                self.chat_manager.delete_chat(cid)
                self.file_service.discard_files(
                    attachment
                    for attachments in attachments_by_message.values()
                    for attachment in attachments
                )
                deleted_count += 1
            except Exception as error:
                logger.exception(f"[MainWindow] Error deleting conversation {cid}: {error}")

        if was_active_deleted:
            self.load_active_chat()
        else:
            self.refresh_sidebar()

        self._app_status_bar.show_success(f"Successfully deleted {deleted_count} conversation{'s' if deleted_count > 1 else ''}.")

    # --------------------------------------------------

    def on_reply(self, message: str, skip_render: bool = False):
        """Persist the completed AI reply in the conversation that requested it."""
        pending_message = self._pending_message
        if pending_message is None:
            self.chat_area.cancel_assistant_stream()
            self.chat_area.append_error("The response did not match an active request.")
            self.input_bar.enable()
            return

        saved_user_message_id: str | None = None
        try:
            saved_user_message_id = self.chat_manager.add_user_message(
                pending_message.content,
                pending_message.conversation_id,
                attachments=pending_message.attachments,
            ).id
            self.chat_manager.add_assistant_message(message, pending_message.conversation_id)
        except (ValueError, RuntimeError, sqlite3.Error) as error:
            if saved_user_message_id is not None:
                try:
                    self.chat_manager.delete_message(saved_user_message_id)
                except (RuntimeError, sqlite3.Error):
                    # Keep the original persistence error visible. A later
                    # database recovery can handle this exceptional case.
                    pass
            self.file_service.discard_files(pending_message.attachments)
            self.chat_area.cancel_assistant_stream()
            self.load_active_chat()
            self.chat_area.append_error(f"Could not save AI response: {error}")
            self.input_bar.enable()
            self.input_bar.focus_input()
            self._app_status_bar.show_error("Database error")
            self._pending_message = None
            return

        # Finalize streaming and render the final assistant message if active
        is_active = (pending_message.conversation_id == self.chat_manager.active_conversation_id)
        if is_active:
            if not skip_render:
                self.chat_area.end_assistant_stream(final_message=message)
            # When skip_render is True (e.g. from on_agent_finished), the chat area
            # has already been updated with rich agent cards, timeline, and diff reviews.
            # Do NOT reload from database as that wipes the live agent timeline!
        self.refresh_sidebar()

        self.input_bar.enable()

        self.input_bar.focus_input()

        self.update_status_bar("Ready")
        self._pending_message = None

    # --------------------------------------------------

    def on_error(self, message: str):
        self.chat_area.cancel_assistant_stream()
        if self._pending_message is not None:
            self.file_service.discard_files(self._pending_message.attachments)
        self.chat_area.append_error(message)

        self.input_bar.enable()

        self._app_status_bar.show_error("Error")
        self._pending_message = None

    def on_agent_finished(self, output: str):
        """Finalize agent execution and persist response."""
        self.chat_area.end_agent_bubble(final_message=output)

        clean_output = output
        if "Final Answer:" in clean_output:
            clean_output = clean_output.split("Final Answer:", 1)[1].strip()
        elif "Observation: Error" in clean_output or "Observation: Exception" in clean_output:
            for line in clean_output.split("\n"):
                s = line.strip()
                if s.startswith(("Observation: Error", "Observation: Exception")):
                    clean_output = f"❌ Execution Failed\nReason: {s.replace('Observation: Error -', '').replace('Observation: Exception running tool', '').strip()}"
                    break
        else:
            cleaned_lines = []
            for line in clean_output.split("\n"):
                s = line.strip()
                if s.startswith(("Thought:", "Action:", "Action Input:", "Observation:")):
                    continue
                cleaned_lines.append(line)
            clean_output = "\n".join(cleaned_lines).strip()

        if not clean_output:
            clean_output = output

        # Preserve Antigravity Diff & Changes summary in database record so it displays upon chat reload
        if "### 📝 Code Changes Summary" in output and "### 📝 Code Changes Summary" not in clean_output:
            summary_part = output.split("### 📝 Code Changes Summary", 1)[1]
            clean_output = f"{clean_output.rstrip()}\n\n### 📝 Code Changes Summary{summary_part}"

        self.on_reply(clean_output, skip_render=True)

    def on_agent_failed(self, error_msg: str):
        """Handle agent execution failure."""
        self.chat_area.cancel_assistant_stream()
        self.on_error(f"Agent Execution Error: {error_msg}")

    @Slot(str, str)
    def on_request_tool_approval(self, tool_name: str, approval_id: str):
        """Show approval dialog on main GUI thread and store result back via registry."""
        from PySide6.QtWidgets import QDialog
        from app.ui.approval_dialog import ToolApprovalDialog
        from app.agent.agent_worker import _approval_registry, _registry_lock

        with _registry_lock:
            entry = _approval_registry.get(approval_id)

        if entry is None:
            logger.warning("[MainWindow] Approval registry entry '%s' not found.", approval_id)
            return

        params = entry.get("params", {})
        theme = getattr(self, "_current_theme", "light")
        dialog = ToolApprovalDialog(
            tool_name=tool_name,
            tool_description=f"AI Agent is requesting permission to execute: {tool_name}",
            params=params,
            parent=self,
            theme=theme,
        )
        approved = (dialog.exec() == QDialog.DialogCode.Accepted)
        entry["result"][0] = approved
        entry["allow_all_for_task"] = approved and dialog.is_allow_all
        entry["remember_for_task"] = approved and dialog.remember_for_task.isChecked()
        entry["event"].set()  # Unblock the worker thread

    def prompt_tool_approval(self, tool_name: str, params: dict) -> bool:
        """Fallback direct approval (only safe to call from main thread)."""
        return self._show_approval_dialog(tool_name, params)

    def _show_approval_dialog(self, tool_name: str, params: dict) -> bool:
        from PySide6.QtWidgets import QDialog
        from app.ui.approval_dialog import ToolApprovalDialog

        dialog = ToolApprovalDialog(
            tool_name=tool_name,
            tool_description=f"AI Agent requested permission to execute tool '{tool_name}'",
            params=params,
            parent=self,
            theme=getattr(self, "_current_theme", "light"),
        )
        approved = (dialog.exec() == QDialog.DialogCode.Accepted)
        if approved and dialog.is_allow_all:
            if hasattr(self, "agent_controller") and hasattr(self.agent_controller, "worker"):
                self.agent_controller.worker.enable_auto_approval_for_task()
        return approved

    def import_chat(self):
        """Prompt for an exported conversation file and import it into ChatManager."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import conversation file",
            "",
            "Supported Files (*.json *.txt *.md);;JSON Files (*.json);;Text/Markdown (*.txt *.md);;All Files (*.*)",
        )
        if not file_path:
            return

        try:
            conversation = self.import_service.import_conversation_file(file_path)
            self.chat_manager.select_chat(conversation.id)
            self.load_active_chat()
            self._app_status_bar.show_success(f"Imported conversation '{conversation.title}'")
        except Exception as error:
            self._app_status_bar.show_error(f"Could not import chat: {error}")
            QMessageBox.warning(self, "Import Error", f"Failed to import conversation:\n{error}")

    # --------------------------------------------------

    def on_thinking(self):
        self._app_status_bar.show_info("Creating response...")

    def on_partial(self, chunk: str):

        # Append incremental chunk received from worker
        self.chat_area.append_assistant_stream(chunk)

    def refresh_sidebar(self):
        """Display conversations held by the chat management layer."""
        self.sidebar.set_conversations(
            self.chat_manager.search_chats(self._chat_search_query),
            self.chat_manager.active_conversation_id,
        )

    def search_chats(self, search_text: str):
        """Refresh the sidebar using its debounced chat-title search query."""
        self._chat_search_query = search_text
        self.refresh_sidebar()

    def load_active_chat(self):
        """Restore the selected conversation's persisted messages into the UI."""
        conversation = self.chat_manager.get_active_chat()
        self.chat_area.load_messages(
            self.chat_manager.get_messages(conversation.id),
            self.chat_manager.get_conversation_attachments(conversation.id),
        )
        self.header.set_chat_title(conversation.title)
        self.refresh_sidebar()

    # --------------------------------------------------
    # Voice Handlers
    # --------------------------------------------------

    def show_voice_settings_dialog(self) -> None:
        """Open the Voice Settings dialog and update settings if accepted."""
        from app.ui.voice_settings_dialog import VoiceSettingsDialog
        from app.settings.settings_manager import SettingsManager
        
        active_theme = SettingsManager.instance().service.schema.appearance.theme
        dialog = VoiceSettingsDialog(
            self.voice_controller.settings,
            self.voice_controller,
            self,
            theme=active_theme,
        )
        if dialog.exec() == VoiceSettingsDialog.DialogCode.Accepted:
            new_settings = dialog.get_settings()
            self.voice_controller.update_settings(new_settings)
            
            # Persist to SettingsManager so preferences are remembered
            try:
                mgr = SettingsManager.instance()
                mgr.service.schema.voice.stt_provider_id = new_settings.stt_provider_id
                mgr.service.schema.voice.tts_provider_id = new_settings.tts_provider_id
                mgr.service.schema.voice.voice_id = new_settings.voice_id
                mgr.service.schema.voice.custom_voices = list(getattr(new_settings, "custom_voices", []) or [])
                mgr.service.schema.voice.language = new_settings.language
                mgr.service.schema.voice.auto_send = new_settings.auto_send
                mgr.service.schema.voice.voice_response = new_settings.voice_response
                mgr.save_settings()
            except Exception as e:
                logger.warning("[MainWindow] Failed to persist voice settings: %s", e)

            self._app_status_bar.show_success("Voice settings updated successfully.")


    def _get_voice_history(self) -> list:
        """Return the current conversation history for the voice pipeline."""
        try:
            conversation = self.chat_manager.get_active_chat()
            return self.chat_manager.get_api_messages(conversation.id)
        except Exception:
            return []

    def on_voice_button_clicked(self):
        """Handle user click on the microphone button based on current VoiceState."""
        current_state = self.voice_controller.state
        if current_state in (VoiceState.READY, VoiceState.INTERRUPTED, VoiceState.ERROR):
            if current_state in (VoiceState.INTERRUPTED, VoiceState.ERROR):
                self.voice_controller.reset()
            self.voice_controller.start_listening()
        elif current_state == VoiceState.LISTENING:
            # Single STT Mode: stop recording without passing conversation history
            self.voice_controller.stop_listening(history=None)
        elif current_state in (VoiceState.SPEAKING, VoiceState.THINKING, VoiceState.TRANSCRIBING):
            self.voice_controller.interrupt()

    def on_live_button_clicked(self):
        """Toggle the continuous Live Conversation mode on or off."""
        if self.voice_controller.is_live_session_active():
            self.voice_controller.stop_live_session()
            self.input_bar.set_live_mode(False)
            self._app_status_bar.show_info("Live Conversation stopped")
        else:
            from app.licensing.license_manager import LicenseManager
            active_tts = getattr(self.voice_controller.settings, "tts_provider_id", "")
            clean_tts = active_tts.replace("_tts", "")
            if clean_tts in ("cartesia", "elevenlabs", "fish_audio"):
                from app.settings.settings_manager import SettingsManager
                has_own_key = bool(SettingsManager.instance().service.get_api_key(clean_tts))
                if not has_own_key and not LicenseManager.instance().is_feature_allowed("cartesia_voice"):
                    self.open_upgrade_window("Cartesia / ElevenLabs লাইভ ভয়েস সুবিধাটি Pro এবং ৩ দিনের ফ্রি ট্রায়ালের অন্তর্ভুক্ত।")
                    return

            conversation = self.chat_manager.get_active_chat()
            self._live_history_conversation_id = conversation.id
            if self.voice_controller.state in (VoiceState.ERROR, VoiceState.INTERRUPTED):
                self.voice_controller.reset()
            self.voice_controller.start_live_session()
            if self.voice_controller.is_live_session_active():
                self.input_bar.set_live_mode(True)
                self._app_status_bar.show_success("Live Conversation started — speak now!")
            else:
                self.input_bar.set_live_mode(False)
                self._app_status_bar.show_error("Could not start Live Conversation. Please check microphone.")

    def on_voice_state_changed(self, state: VoiceState):
        """Update window status bar text when VoiceState changes."""
        {VoiceState.READY, VoiceState.LISTENING, VoiceState.TRANSCRIBING, VoiceState.THINKING}
        _STATE_SUCCESS = {VoiceState.SPEAKING}
        _STATE_WARNING = {VoiceState.INTERRUPTED}
        _STATE_ERROR = {VoiceState.ERROR}

        state_messages = {
            VoiceState.READY:        "Ready",
            VoiceState.LISTENING:    "Voice: Listening...",
            VoiceState.TRANSCRIBING: "Voice: Transcribing...",
            VoiceState.THINKING:     "Voice: Thinking...",
            VoiceState.SPEAKING:     "Voice: Speaking...",
            VoiceState.INTERRUPTED:  "Voice: Interrupted",
            VoiceState.ERROR:        "Voice: Error occurred",
        }
        msg = state_messages.get(state, f"Voice: {state.name}")

        if state in _STATE_ERROR:
            self._app_status_bar.show_error(msg)
            if hasattr(self.chat_area, "_stream_block_start_position") and self.chat_area._stream_block_start_position is not None:
                self.chat_area.end_assistant_stream()
        elif state in _STATE_WARNING:
            self._app_status_bar.show_warning(msg)
            if state == VoiceState.INTERRUPTED and hasattr(self.chat_area, "_stream_block_start_position") and self.chat_area._stream_block_start_position is not None:
                self.chat_area.end_assistant_stream()
        elif state in _STATE_SUCCESS:
            self._app_status_bar.show_success(msg)
        else:
            self._app_status_bar.show_info(msg)

    def on_voice_transcript_ready(self, transcript: str):
        """Display voice transcript in input box for Speech-to-Text conversion."""
        if not transcript:
            return

        if self.voice_controller.is_live_session_active():
            self.input_bar.clear()
            conversation = self.chat_manager.get_active_chat()
            try:
                self.chat_manager.add_user_message(transcript, conversation.id)
                self.chat_area.append_user_message(transcript)
                self.refresh_sidebar()
            except Exception:
                logger.exception("Failed to add user message during voice transcript processing.")
        else:
            # Pure Speech-to-Text Mode: append transcribed text to input box without erasing existing content
            current_text = self.input_bar.message_input.text()
            if current_text.strip():
                new_text = f"{current_text.strip()} {transcript.strip()}"
            else:
                new_text = transcript.strip()
            self.input_bar.message_input.setText(new_text)
            self.input_bar.message_input.setFocus()

    def on_voice_response_ready(self, response_text: str):
        """Persist AI response when voice turn completes."""
        if not response_text:
            return
        conversation = self.chat_manager.get_active_chat()
        try:
            self.chat_manager.add_assistant_message(response_text, conversation.id)
        except Exception:
            logger.exception("Failed to add assistant message during voice response processing.")

        if self.voice_controller.is_live_session_active():
            self.chat_area.end_assistant_stream(response_text)
            self.refresh_sidebar()
        else:
            self.load_active_chat()
        self.input_bar.clear()

    def on_voice_audio_ready(self, audio_bytes: bytes):
        """Play TTS audio through speaker."""
        if audio_bytes:
            self.voice_controller.player.append_bytes(audio_bytes)

    def on_voice_error(self, error_msg: str):
        """Show voice error message on status bar."""
        self._app_status_bar.show_error(f"Voice Error: {error_msg}")
        if not self.voice_controller.is_live_session_active():
            self.input_bar.set_live_mode(False)

    # --------------------------------------------------

    def showEvent(self, event):
        super().showEvent(event)
        if not hasattr(self, "_faded_in"):
            self._faded_in = True
            self._opacity_effect = QGraphicsOpacityEffect(self)
            self.setGraphicsEffect(self._opacity_effect)
            self._fade_anim = QPropertyAnimation(self._opacity_effect, b"opacity")
            self._fade_anim.setDuration(800)
            self._fade_anim.setStartValue(0.0)
            self._fade_anim.setEndValue(1.0)
            self._fade_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
            self._fade_anim.finished.connect(self._clear_opacity_effect)
            self._fade_anim.start()

    def _clear_opacity_effect(self):
        self.setGraphicsEffect(None)

    def closeEvent(self, event):
        # Discard any files the user had staged but never sent, so they are
        # not left as orphans on disk after the application closes.
        self.clear_pending_attachments()

        if getattr(self, "_settings_dialog", None) is not None:
            try:
                self._settings_dialog.close()
            except Exception:
                pass

        self.controller.shutdown()
        self.agent_controller.shutdown()
        self.voice_controller.shutdown()

        super().closeEvent(event)

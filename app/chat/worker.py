from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from PySide6.QtCore import QObject, Signal, Slot

from app.api.ClaudeClient import ClaudeClient
from app.image_generation import (
    StabilityImageClient,
    ImageEnhancer,
    is_image_generation_request,
    is_image_enhancement_request,
    extract_image_payload,
)


@dataclass(frozen=True)
class ChatRequest:
    """One request plus the persisted history for its selected conversation."""

    message: str | list[dict[str, Any]]
    history: tuple[dict[str, Any], ...] = ()
    model: str | None = None
    provider_id: str | None = None


class ClaudeWorker(QObject):
    """
    Background worker that communicates with AI and image services.

    This object always runs inside a QThread.
    It never updates the GUI directly.
    """

    # Signals
    started = Signal()
    partial = Signal(str)
    finished = Signal(str)
    failed = Signal(str)

    def __init__(self):
        super().__init__()

        self.client = None
        self.image_client = None
        self.enhancer = None

        # Loaded from settings; trimmed before each LLM call so history limit is respected at runtime
        try:
            from app.settings.settings_manager import SettingsManager
            self.max_history_turns: int = SettingsManager.instance().service.schema.chat.max_history_turns
        except Exception:
            self.max_history_turns = 20

    def _get_client(self):
        if self.client is None:
            self.client = ClaudeClient()
        return self.client

    def _get_image_client(self):
        if self.image_client is None:
            self.image_client = StabilityImageClient()
        return self.image_client

    def _get_enhancer(self):
        if self.enhancer is None:
            self.enhancer = ImageEnhancer()
        return self.enhancer

    @Slot(object)
    def process(self, request: ChatRequest | str | list[dict[str, Any]]):
        """
        Process user message, supporting image enhancement, image generation,
        and streaming conversational LLM requests.
        """
        if isinstance(request, ChatRequest):
            message = request.message
            history = request.history
            model = request.model
            provider_id = request.provider_id
        else:
            message = request
            history = ()
            model = None
            provider_id = None

        self.started.emit()

        try:
            prompt_text, image_bytes_list = extract_image_payload(message)

            # -------------------------------------------------------------
            # Case 1: Image attached + enhancement/clarity request
            # -------------------------------------------------------------
            if image_bytes_list and is_image_enhancement_request(prompt_text):
                target_image = image_bytes_list[0]
                enhanced_path, meta = self._get_enhancer().enhance_clarity(target_image, upscale_factor=2.0)
                save_target = quote(str(enhanced_path.resolve()))

                orig_res = meta.get("orig_size", "Original")
                new_res = meta.get("new_size", "Enhanced")
                megapixels = meta.get("megapixels", "")
                mp_badge = f" • {megapixels} MP" if megapixels else ""

                card_html = (
                    '<div style="margin: 10px 0; padding: 14px; background: rgba(16, 185, 129, 0.08); '
                    'border-radius: 12px; border: 1px solid rgba(16, 185, 129, 0.25);">'
                    '<p style="margin: 0 0 8px 0; font-weight: bold; color: #059669; font-size: 14px;">'
                    '✨ Ultra-HD Portrait Clarity (ক্লিয়ার ও প্রফেশনাল শার্প করা ছবি):'
                    '</p>'
                    '<div style="margin: 0 0 10px 0; font-size: 12px; color: #047857;">'
                    f'<b>রেজোলিউশন আপস্কেল:</b> {orig_res} ➔ <b>{new_res}</b> (2X Ultra HD{mp_badge})'
                    '</div>'
                    '<div style="text-align:center; margin:8px 0;">'
                    f'<img src="{enhanced_path.as_uri()}" width="460" style="border-radius: 8px;">'
                    '<br><br>'
                    f'<a href="saveimage:{save_target}" style="background-color:#059669; color:#ffffff; padding:7px 16px; text-decoration:none; border-radius:6px; font-weight:bold; font-size:13px;">'
                    '💾 Save Ultra-HD Image'
                    '</a>'
                    '</div>'
                    '<p style="margin: 10px 0 0 0; font-size: 11.5px; color: #6b7280; text-align: center;">'
                    'Applied: Dual-Frequency Separation, Eye & Face Micro-Detailing, Dynamic Range Balancing & Lossless Chroma.'
                    '</p>'
                    '</div>'
                )
                self.finished.emit(card_html)
                return

            # -------------------------------------------------------------
            # Case 2: Plain text prompt asking to create/generate an image
            # -------------------------------------------------------------
            if isinstance(message, str) and is_image_generation_request(message):
                image_path = self._get_image_client().generate(message)
                save_target = quote(str(image_path.resolve()))
                self.finished.emit(
                    '<div style="text-align:center; margin:8px 0;">'
                    f'<img src="{image_path.as_uri()}" width="460">'
                    '<br><a href="saveimage:' + save_target + '">💾 Save image</a>'
                    '</div>'
                )
                return

            # -------------------------------------------------------------
            # Case 3: Conversational multimodal/text stream
            # -------------------------------------------------------------
            client = self._get_client()
            full_reply = []

            # Respect max_history_turns setting: keep only the most recent N turns
            trimmed_history = history[-self.max_history_turns:] if self.max_history_turns > 0 else history

            for chunk in client.ask_stream(message, model=model, history=trimmed_history, provider_id=provider_id):
                full_reply.append(chunk)
                self.partial.emit(chunk)

            self.finished.emit("".join(full_reply))

        except Exception as error:
            self.failed.emit(str(error))

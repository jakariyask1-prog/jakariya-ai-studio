"""Business logic for managing the application's conversations."""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from app.chat.chat_repository import ChatRepository
from app.models.attachment import Attachment, AttachmentInput
from app.models.conversation import Conversation
from app.models.message import Message, MessageRole


class ChatNotFoundError(ValueError):
    """Raised when an operation targets a conversation that does not exist."""


class ChatManager:
    """Coordinate chat state while keeping UI and database concerns separate."""

    DEFAULT_TITLE = "New Chat"
    MAX_TITLE_LENGTH = 60

    def __init__(self, repository: ChatRepository | None = None) -> None:
        self._repository = repository or ChatRepository()
        self._active_conversation_id: str | None = None

    @property
    def active_conversation_id(self) -> str | None:
        """Return the ID of the selected conversation, if any."""
        return self._active_conversation_id

    def initialize(self) -> Conversation:
        """Load the latest chat, or create the first chat for a new user."""
        conversations = self.list_conversations()
        if conversations:
            self._active_conversation_id = conversations[0].id
            return conversations[0]
        return self.create_new_chat()

    # Conversations -----------------------------------------------------

    def list_conversations(self) -> list[Conversation]:
        """Return the sidebar conversations in most-recent-first order."""
        return self._repository.list_conversations()

    def search_chats(self, search_text: str) -> list[Conversation]:
        """Return chats whose title matches a user-entered search query."""
        clean_query = search_text.strip()
        if not clean_query:
            return self.list_conversations()
        return self._repository.search_conversations(clean_query)

    def create_new_chat(self, title: str | None = None) -> Conversation:
        """Create a conversation and make it the active chat."""
        conversation = self._repository.create_conversation(
            self._normalise_title(title or self.DEFAULT_TITLE)
        )
        self._active_conversation_id = conversation.id
        return conversation

    def select_chat(self, conversation_id: str) -> Conversation:
        """Select an existing conversation and return it."""
        conversation = self._require_conversation(conversation_id)
        self._active_conversation_id = conversation.id
        return conversation

    def get_chat(self, conversation_id: str) -> Conversation:
        """Return an existing conversation without changing the active chat."""
        return self._require_conversation(conversation_id)

    def get_active_chat(self) -> Conversation:
        """Return the active chat, creating one when no chat is selected."""
        if self._active_conversation_id is None:
            return self.initialize()

        conversation = self._repository.get_conversation(self._active_conversation_id)
        if conversation is None:
            # This can happen if a chat was removed by a future sync/import feature.
            self._active_conversation_id = None
            return self.initialize()
        return conversation

    def rename_chat(self, conversation_id: str, title: str) -> Conversation:
        """Rename a chat after validating its user-provided title."""
        clean_title = self._normalise_title(title)
        if not self._repository.rename_conversation(conversation_id, clean_title):
            raise ChatNotFoundError(f"Conversation '{conversation_id}' was not found.")
        return self._require_conversation(conversation_id)

    def delete_chat(self, conversation_id: str) -> Conversation:
        """Delete a chat and return the chat that should become active next."""
        self._require_conversation(conversation_id)
        self._repository.delete_conversation(conversation_id)

        if self._active_conversation_id != conversation_id:
            return self.get_active_chat()

        self._active_conversation_id = None
        remaining_chats = self.list_conversations()
        if remaining_chats:
            self._active_conversation_id = remaining_chats[0].id
            return remaining_chats[0]
        return self.create_new_chat()

    # Messages ----------------------------------------------------------

    def add_user_message(
        self,
        content: str,
        conversation_id: str | None = None,
        attachments: Sequence[AttachmentInput] = (),
    ) -> Message:
        """Save a user message and auto-title an untouched conversation."""
        return self._add_message("user", content, conversation_id, attachments)

    def add_assistant_message(
        self,
        content: str,
        conversation_id: str | None = None,
    ) -> Message:
        """Save an assistant response in the specified conversation."""
        return self._add_message("assistant", content, conversation_id)

    def add_system_message(
        self,
        content: str,
        conversation_id: str | None = None,
    ) -> Message:
        """Save an internal/system message in the specified conversation."""
        return self._add_message("system", content, conversation_id)

    def delete_message(self, message_id: str) -> bool:
        """Remove a message when its surrounding operation could not finish."""
        return self._repository.delete_message(message_id)

    def get_messages(self, conversation_id: str | None = None) -> list[Message]:
        """Return messages for a chat; default to the selected chat."""
        target_id = conversation_id or self.get_active_chat().id
        self._require_conversation(target_id)
        return self._repository.list_messages(target_id)

    def get_conversation_attachments(
        self, conversation_id: str | None = None
    ) -> dict[str, list[Attachment]]:
        """Return each message's persisted attachment metadata for chat history."""
        target_id = conversation_id or self.get_active_chat().id
        self._require_conversation(target_id)
        return self._repository.list_conversation_attachments(target_id)

    def get_api_messages(
        self, conversation_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Return only the selected chat's completed API-compatible turns."""
        target_id = conversation_id or self.get_active_chat().id
        return [
            {"role": message.role, "content": message.content}
            for message in self.get_messages(target_id)
            if message.role in ("user", "assistant")
        ]

    def get_all_stored_attachment_paths(self) -> list[str]:
        """Return every stored_path tracked across all conversations.

        Passed to ``FileService.sweep_orphans()`` at startup so that any file
        on disk that is no longer referenced by the database can be removed.
        """
        return self._repository.list_all_stored_paths()

    # Internal helpers --------------------------------------------------

    def _add_message(
        self,
        role: MessageRole,
        content: str,
        conversation_id: str | None,
        attachments: Sequence[AttachmentInput] = (),
    ) -> Message:
        clean_content = content.strip()
        if not clean_content:
            raise ValueError("A message cannot be empty.")

        target_id = conversation_id or self.get_active_chat().id
        conversation = self._require_conversation(target_id)
        has_no_messages = not self._repository.list_messages(target_id)

        message = self._repository.add_message(
            target_id, role, clean_content, attachments=attachments
        )
        if role == "user" and has_no_messages and conversation.title == self.DEFAULT_TITLE:
            self._repository.rename_conversation(
                target_id,
                self._title_from_message(clean_content),
            )
        return message

    def _require_conversation(self, conversation_id: str) -> Conversation:
        conversation = self._repository.get_conversation(conversation_id)
        if conversation is None:
            raise ChatNotFoundError(f"Conversation '{conversation_id}' was not found.")
        return conversation

    def _normalise_title(self, title: str) -> str:
        clean_title = re.sub(r"\s+", " ", title).strip()
        if not clean_title:
            raise ValueError("Chat title cannot be empty.")
        return clean_title[: self.MAX_TITLE_LENGTH]

    def _title_from_message(self, content: str) -> str:
        title = re.sub(r"\s+", " ", content).strip()
        if len(title) <= self.MAX_TITLE_LENGTH:
            return title
        return f"{title[: self.MAX_TITLE_LENGTH - 1].rstrip()}…"

"""Immutable export-domain snapshots independent of UI and file formats."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from app.models.attachment import Attachment
from app.models.conversation import Conversation
from app.models.message import Message, MessageRole


@dataclass(frozen=True, slots=True)
class ExportAttachment:
    """Attachment details captured when a conversation is exported."""

    id: str
    original_name: str
    stored_path: str
    extension: str
    size_bytes: int
    media_type: str
    is_image: bool
    created_at: str

    @classmethod
    def from_attachment(cls, attachment: Attachment) -> "ExportAttachment":
        """Create an export-safe snapshot from a persisted attachment."""
        return cls(
            id=attachment.id,
            original_name=attachment.original_name,
            stored_path=attachment.stored_path,
            extension=attachment.extension,
            size_bytes=attachment.size_bytes,
            media_type=attachment.media_type,
            is_image=attachment.is_image,
            created_at=attachment.created_at,
        )


@dataclass(frozen=True, slots=True)
class ExportMessage:
    """Message content and attachments prepared for every exporter."""

    id: str
    role: MessageRole
    content: str
    created_at: str
    attachments: tuple[ExportAttachment, ...] = ()

    @classmethod
    def from_message(
        cls,
        message: Message,
        attachments: Iterable[Attachment] = (),
    ) -> "ExportMessage":
        """Create a message snapshot without retaining database objects."""
        return cls(
            id=message.id,
            role=message.role,
            content=message.content,
            created_at=message.created_at,
            attachments=tuple(
                ExportAttachment.from_attachment(attachment) for attachment in attachments
            ),
        )


@dataclass(frozen=True, slots=True)
class ExportConversation:
    """Complete, ordered conversation data consumed by format exporters."""

    id: str
    title: str
    created_at: str
    updated_at: str
    messages: tuple[ExportMessage, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)

    @classmethod
    def from_conversation(
        cls,
        conversation: Conversation,
        messages: Iterable[ExportMessage] = (),
        metadata: Mapping[str, str] | None = None,
    ) -> "ExportConversation":
        """Create a portable snapshot from the application's chat domain."""
        return cls(
            id=conversation.id,
            title=conversation.title,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            messages=tuple(messages),
            metadata=dict(metadata or {}),
        )


@dataclass(frozen=True, slots=True)
class ExportResult:
    """Successful export details for the UI and future activity history."""

    destination: Path
    format_id: str
    message_count: int
    attachment_count: int


@dataclass(frozen=True, slots=True)
class ExportFormatInfo:
    """Display and file-dialog metadata supplied by a registered exporter."""

    format_id: str
    display_name: str
    file_extension: str

    @property
    def file_filter(self) -> str:
        """Return the native save-dialog filter for this output format."""
        return f"{self.display_name} (*{self.file_extension});;All files (*.*)"

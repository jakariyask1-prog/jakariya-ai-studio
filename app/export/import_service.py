"""Service to import exported conversation files back into Jakariya AI Studio."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, List, Tuple

from app.chat.chat_manager import ChatManager
from app.models.conversation import Conversation


class ImportService:
    """Parse exported JSON, TXT, or Markdown chat files and import into ChatManager."""

    def __init__(self, chat_manager: ChatManager) -> None:
        self._chat_manager = chat_manager

    def import_conversation_file(self, file_path: Path | str) -> Conversation:
        """Read a file path and create a new persisted conversation with its messages."""
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {path}")

        suffix = path.suffix.lower()
        if suffix == ".json":
            title, messages = self._parse_json(path)
        else:
            title, messages = self._parse_text_or_markdown(path)

        if not title:
            title = path.stem.replace("_", " ").replace("-", " ").capitalize()

        # Create new chat in ChatManager
        conversation = self._chat_manager.create_new_chat(title=title)

        # Populate messages
        for role, content in messages:
            if not content.strip():
                continue
            if role == "user":
                self._chat_manager.add_user_message(content, conversation_id=conversation.id)
            elif role in ("assistant", "bot", "model"):
                self._chat_manager.add_assistant_message(content, conversation_id=conversation.id)
            elif role == "system":
                self._chat_manager.add_system_message(content, conversation_id=conversation.id)

        return conversation

    def _parse_json(self, path: Path) -> Tuple[str, List[Tuple[str, str]]]:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            data = json.load(f)

        title = "Imported Chat"
        messages: List[Tuple[str, str]] = []

        # Handle list of conversations (e.g. Claude full export)
        if isinstance(data, list) and data:
            data = data[0]

        if isinstance(data, dict):
            title = data.get("title") or data.get("name") or title
            
            # AI Studio or standard format
            msg_list = data.get("chat_messages") or data.get("messages") or []
            if isinstance(msg_list, list):
                for item in msg_list:
                    if isinstance(item, dict):
                        role = str(item.get("role", "user")).lower()
                        # Extract text from content (string or list of blocks)
                        raw_content = item.get("content") or item.get("text") or ""
                        content_str = self._extract_text_content(raw_content)
                        if content_str:
                            messages.append((role, content_str))
            
            # Claude export mapping structure (if exported from Claude web)
            elif "mapping" in data and isinstance(data["mapping"], dict):
                for node in data["mapping"].values():
                    if isinstance(node, dict) and "message" in node and node["message"]:
                        msg_node = node["message"]
                        author = msg_node.get("author", {}).get("role", "user")
                        content_parts = msg_node.get("content", {}).get("parts", [])
                        content_text = "\n".join(str(p) for p in content_parts if p)
                        if content_text:
                            messages.append((author, content_text))

        return title, messages

    def _extract_text_content(self, content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, str):
                    parts.append(block)
                elif isinstance(block, dict):
                    if block.get("type") == "text":
                        parts.append(block.get("text", ""))
                    elif "text" in block:
                        parts.append(str(block["text"]))
            return "\n".join(parts)
        return str(content) if content else ""

    def _parse_text_or_markdown(self, path: Path) -> Tuple[str, List[Tuple[str, str]]]:
        content = path.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()

        title = path.stem.replace("_", " ").title()
        messages: List[Tuple[str, str]] = []

        current_role: str | None = None
        current_lines: List[str] = []

        role_pattern = re.compile(r"^(User|Assistant|System|Human|Bot|AI):\s*(.*)", re.IGNORECASE)

        for line in lines:
            match = role_pattern.match(line)
            if match:
                if current_role and current_lines:
                    messages.append((current_role, "\n".join(current_lines).strip()))
                    current_lines = []
                role_str = match.group(1).lower()
                current_role = "user" if role_str in ("user", "human") else ("assistant" if role_str in ("assistant", "bot", "ai") else "system")
                first_line_text = match.group(2)
                if first_line_text:
                    current_lines.append(first_line_text)
            else:
                if current_role:
                    current_lines.append(line)
                elif line.strip() and not current_role:
                    # Default first text to user
                    current_role = "user"
                    current_lines.append(line)

        if current_role and current_lines:
            messages.append((current_role, "\n".join(current_lines).strip()))

        return title, messages

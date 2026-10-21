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
        start_idx = 0
        if lines:
            first_line = lines[0].strip()
            if first_line.startswith("# "):
                title = first_line.lstrip("# ").strip()
                start_idx = 1
            elif len(lines) > 1 and lines[1].strip() and set(lines[1].strip()) <= {"="}:
                title = first_line
                start_idx = 2

        messages: List[Tuple[str, str]] = []

        current_role: str | None = None
        current_lines: List[str] = []

        heading_re = re.compile(r"^#{2,4}\s+(User|Assistant|System|Human|Bot|AI|Model)\b", re.IGNORECASE)
        divider_re = re.compile(r"^---\s*(User|Assistant|System|Human|Bot|AI|Model)(?:\s*\|.*?)?\s*---", re.IGNORECASE)
        colon_re = re.compile(r"^\*{0,2}(User|Assistant|System|Human|Bot|AI|Model)\*{0,2}:\s*(.*)", re.IGNORECASE)

        metadata_re = re.compile(
            r"^(?:"
            r"-\s*\*\*(?:Conversation ID|Created|Updated):\*\*.*"
            r"|(?:Conversation ID|Created|Updated):\s*.*"
            r"|\*[0-9]{4}-[0-9]{2}-[0-9]{2}(?:[T\s][^\*]*)?\*"
            r")$",
            re.IGNORECASE,
        )

        for line in lines[start_idx:]:
            m_head = heading_re.match(line)
            m_div = divider_re.match(line)
            m_col = colon_re.match(line)

            matched_role = None
            first_text = None

            if m_head:
                matched_role = m_head.group(1).lower()
            elif m_div:
                matched_role = m_div.group(1).lower()
            elif m_col:
                matched_role = m_col.group(1).lower()
                first_text = m_col.group(2)

            if matched_role:
                if current_role and current_lines:
                    text = "\n".join(current_lines).strip()
                    if text:
                        messages.append((current_role, text))
                    current_lines = []
                current_role = (
                    "user"
                    if matched_role in ("user", "human")
                    else ("assistant" if matched_role in ("assistant", "bot", "ai", "model") else "system")
                )
                if first_text:
                    current_lines.append(first_text)
            else:
                if current_role is None:
                    stripped = line.strip()
                    if not stripped or stripped.startswith("#") or set(stripped) <= {"=", "-"}:
                        continue
                    if metadata_re.match(stripped):
                        continue
                    current_role = "user"
                    current_lines.append(line)
                else:
                    if metadata_re.match(line.strip()):
                        continue
                    current_lines.append(line)

        if current_role and current_lines:
            text = "\n".join(current_lines).strip()
            if text:
                messages.append((current_role, text))

        return title, messages

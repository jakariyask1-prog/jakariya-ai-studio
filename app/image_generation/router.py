"""Small, deterministic routing helpers for image-generation and enhancement requests."""

from __future__ import annotations

import base64
import re
from typing import Any


_IMAGE_REQUEST_PATTERNS = (
    # Action verb + target (e.g. "create a flower image", "draw a cat", "generate image of flower")
    r"\b(?:generate|generat|gnerate|create|crete|crate|creete|make|mak|draw|draww|design|desing|produce|render|paint|sketch)\b.{0,80}\b(?:image|picture|photo|pic|illustration|artwork|poster|logo|wallpaper|flower|cat|dog|car|landscape)\b",
    r"\b(?:give|show|send|draw|generate|create)\s+me\s+(?:an?\s+)?(?:image|picture|photo|pic|drawing)\b",
    # Target noun + verb (e.g. "flower image please crete", "cat picture generate")
    r"\b(?:image|picture|photo|pic)\b.{0,40}\b(?:generate|generat|gnerate|create|crete|crate|make|draw|design)\b",
    r"\b(?:draw|paint|sketch)\s+(?:a|an|the)\b",
    # Bangla patterns
    r"(?:ছবি|পিকচার|ফটো|ইমেজ)\s*(?:বানাও|তৈরি\s*করো|দাও|কর|বানিয়ে\s*দাও|আঁকো|জেনারেট\s*করো)",
    r"(?:একটা|একটি)\s+(?:ছবি|পিকচার|ফটো|ইমেজ)\s*(?:বানাও|তৈরি\s*করো|দাও|আঁকো|জেনারেট\s*করো)",
    r"(?:তৈরি|বানাও|আঁকো|জেনারেট)\s*(?:করো|করুন)?\s*(?:একটা|একটি)?\s*(?:ছবি|পিকচার|ফটো|ইমেজ)",
)

_IMAGE_ENHANCEMENT_PATTERNS = (
    # Direct enhancement verbs/adjectives (English & common typos)
    r"\b(?:clear|clearer|clarity|sharpen|sharp|sharper|hd|4k|enhance|enhanced|upscale|resolution|restore|restoration)\b",
    r"\b(?:professional|profestional|professonal|clean|brighten|retouch|fix|improve|upgrade)\b",
    r"\b(?:same|this)\s+(?:image|pic|picture|photo)\b.{0,40}\b(?:create|make|clear|clarity|sharpen|professional|profestional)\b",
    r"\b(?:pic|image|photo|picture)\b.{0,30}\b(?:aro|more)\s+(?:clear|sharp|profestional|professional|clean)\b",
    # Bangla enhancement patterns
    r"(?:ক্লিয়ার|পরিষ্কার|শার্প|কোয়ালিটি|রেজোলিউশন|হাই\s*কোয়ালিটি|প্রফেশনাল|এনহ্যান্স|আপস্কেল|রিস্টোর)",
    r"(?:আরো?\s*(?:ক্লিয়ার|শার্প|পরিষ্কার|সুন্দর|ভালো\s*কোয়ালিটি|ব্রাইট|এইচডি))",
    r"(?:ছবি|পিকচার|ফটো|ইমেজ)\s*(?:ক্লিয়ার|শার্প|পরিষ্কার|সুন্দর|ভালো|প্রফেশনাল)\s*(?:করো|করুন|করে\s*দাও|বানাও|বানিয়ে\s*দাও|দাও)",
)


def is_image_generation_request(message: str) -> bool:
    """Return whether a message is an explicit request to create an image.

    This uses pattern matching with support for common typos so image requests
    are properly routed even if mispelled (e.g., "crete a flower image").
    """
    return any(
        re.search(pattern, message, flags=re.IGNORECASE)
        for pattern in _IMAGE_REQUEST_PATTERNS
    )


def is_image_enhancement_request(message: str) -> bool:
    """Return whether a message is a request to clarify, sharpen, upscale, or enhance an image."""
    return any(
        re.search(pattern, message, flags=re.IGNORECASE)
        for pattern in _IMAGE_ENHANCEMENT_PATTERNS
    )


def extract_image_payload(
    message: str | list[dict[str, Any]]
) -> tuple[str, list[bytes]]:
    """Extract prompt text and decoded image bytes from multimodal or plain messages."""
    if isinstance(message, str):
        return message.strip(), []

    text_parts: list[str] = []
    image_bytes_list: list[bytes] = []

    for block in message:
        if not isinstance(block, dict):
            continue

        b_type = block.get("type")
        if b_type == "text":
            text_parts.append(block.get("text", "").strip())
        elif b_type == "image":
            source = block.get("source", {})
            b64_data = source.get("data", "")
            if b64_data:
                try:
                    image_bytes_list.append(base64.b64decode(b64_data))
                except Exception:
                    pass

    full_text = " ".join(t for t in text_parts if t).strip()
    return full_text, image_bytes_list

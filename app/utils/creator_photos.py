"""Utility helpers for loading and displaying creator profile photos."""

from __future__ import annotations

from pathlib import Path

from app.utils.paths import get_base_dir


_SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

# Marker that AI uses in its response to trigger photo display
CREATOR_PHOTO_MARKER = "[SHOW_CREATOR_PHOTOS]"


def get_creator_photos_dir() -> Path:
    """Return the path to the creator photos directory."""
    return get_base_dir() / "assets" / "images" / "creator"


def get_creator_photo_paths() -> list[Path]:
    """Return a sorted list of all creator photo file paths that exist."""
    photos_dir = get_creator_photos_dir()
    if not photos_dir.exists():
        return []

    photos = [
        p for p in sorted(photos_dir.iterdir())
        if p.is_file() and p.suffix.lower() in _SUPPORTED_EXTENSIONS
    ]
    return photos


def build_creator_photos_html(theme: str = "light") -> str:
    """Build a beautiful HTML gallery card showing all creator photos."""
    photos = get_creator_photo_paths()
    if not photos:
        return ""

    is_dark = theme.lower() in ("dark", "oled", "neon")

    # Theme colors
    if is_dark:
        card_bg = "#1E2330"
        card_border = "#3A4460"
        title_color = "#E8EAF0"
        subtitle_color = "#9BA3BF"
        badge_bg = "#2A3350"
        badge_color = "#7C9EFF"
    else:
        card_bg = "#F8FAFF"
        card_border = "#D0DAFF"
        title_color = "#1A2260"
        subtitle_color = "#5A6490"
        badge_bg = "#EEF2FF"
        badge_color = "#3B52C0"

    # Build individual photo tiles
    photo_tiles = []
    for i, photo_path in enumerate(photos, start=1):
        file_uri = photo_path.resolve().as_uri()
        safe_uri = file_uri.replace(" ", "%20")
        photo_tiles.append(
            f'<td align="center" valign="top" style="padding:8px;">'
            f'<div style="'
            f'border-radius:12px; overflow:hidden; '
            f'box-shadow: 0 2px 12px rgba(0,0,0,0.15); '
            f'display:inline-block;">'
            f'<img src="{safe_uri}" '
            f'width="180" height="180" '
            f'style="object-fit:cover; display:block; border-radius:12px;" '
            f'alt="Md. Jakariya Sheikh - Photo {i}"/>'
            f'</div>'
            f'</td>'
        )

    # Arrange photos in rows of 3
    rows_html = ""
    tiles_per_row = 3
    for row_start in range(0, len(photo_tiles), tiles_per_row):
        row_tiles = photo_tiles[row_start:row_start + tiles_per_row]
        # Pad last row if needed
        while len(row_tiles) < tiles_per_row:
            row_tiles.append('<td></td>')
        rows_html += f"<tr>{''.join(row_tiles)}</tr>"

    photo_count = len(photos)

    return f"""
<table width="100%" cellspacing="0" cellpadding="0" style="margin-top:10px; margin-bottom:12px;">
<tr><td>
<table width="100%" cellspacing="0" cellpadding="16" style="
    background-color:{card_bg};
    border:1.5px solid {card_border};
    border-radius:14px;">
<tr><td>
    <!-- Header -->
    <table width="100%" cellspacing="0" cellpadding="0" style="margin-bottom:14px;">
    <tr>
        <td>
            <div style="font-size:13pt; font-weight:700; color:{title_color};">
                🧑‍💼 মোহাম্মদ জাকারিয়া শেখ
            </div>
            <div style="font-size:10pt; color:{subtitle_color}; margin-top:3px;">
                Jakariya AI Studio — নির্মাতা ও স্বত্বাধিকারী
            </div>
        </td>
        <td align="right" valign="top">
            <span style="
                background-color:{badge_bg};
                color:{badge_color};
                border-radius:6px;
                padding:4px 10px;
                font-size:9pt;
                font-weight:700;">
                📸 {photo_count} টি ছবি
            </span>
        </td>
    </tr>
    </table>

    <!-- Photo Grid -->
    <table cellspacing="0" cellpadding="0" style="margin:0 auto;">
        {rows_html}
    </table>

    <!-- Footer info -->
    <div style="margin-top:12px; padding-top:10px; border-top:1px solid {card_border};
                font-size:9.5pt; color:{subtitle_color}; text-align:center;">
        🎓 গণিতের শিক্ষক &nbsp;|&nbsp; 🤖 AI গবেষক &nbsp;|&nbsp; 📐 JRM মডেলের উদ্ভাবক
    </div>
</td></tr>
</table>
</td></tr>
</table>
"""

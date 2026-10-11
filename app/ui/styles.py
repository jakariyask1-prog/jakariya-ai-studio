"""
Jakariya AI Studio — Unified Design System & Styling Tokens (Phase 10.1)

Inspired by ChatGPT, Claude, and Lipika AI.
Provides clean QSS rules, color constants, button variants, and component stylesheets.
"""

from __future__ import annotations

# ==============================================================================
# DESIGN TOKENS & COLOR PALETTE
# ==============================================================================

# Core Colors
COLOR_PRIMARY = "#4F46E5"        # Modern Indigo Primary
COLOR_PRIMARY_HOVER = "#4338CA"
COLOR_PRIMARY_PRESSED = "#3730A3"

COLOR_SECONDARY = "#10B981"      # Emerald / Success / Live Mode
COLOR_SECONDARY_HOVER = "#059669"

COLOR_AGENT = "#6366F1"          # Agent ReAct Blue-Violet Accent
COLOR_AGENT_BG = "#F5F3FF"

# Light Theme Surfaces & Text
COLOR_BG_LIGHT = "#F8FAFC"
COLOR_CARD_LIGHT = "#FFFFFF"
COLOR_SIDEBAR_LIGHT = "#F1F5F9"
COLOR_BORDER_LIGHT = "#E2E8F0"
COLOR_BORDER_FOCUS = "#818CF8"

COLOR_TEXT_PRIMARY = "#0F172A"
COLOR_TEXT_SECONDARY = "#475569"
COLOR_TEXT_MUTED = "#94A3B8"

# Dark Theme & Code Block Surface
COLOR_CODE_BG = "#1E1E2E"
COLOR_CODE_TEXT = "#CDD6F4"

# Smart Document UI Tokens — Light Mode
SMART_DOC_LIGHT_CARD_BG = "#FFFFFF"
SMART_DOC_LIGHT_CARD_BORDER = "#6366F1"
SMART_DOC_LIGHT_TITLE = "#0F172A"
SMART_DOC_LIGHT_MUTED = "#64748B"
SMART_DOC_LIGHT_PREVIEW_BG = "#F8FAFC"
SMART_DOC_LIGHT_PREVIEW_BORDER = "#E2E8F0"
SMART_DOC_LIGHT_PREVIEW_TEXT = "#334155"
SMART_DOC_LIGHT_BADGE_BG = "#EEF2FF"
SMART_DOC_LIGHT_BADGE_TEXT = "#4F46E5"
SMART_DOC_LIGHT_BADGE_BORDER = "#C7D2FE"
SMART_DOC_LIGHT_LINK = "#2563EB"

# Smart Document UI Tokens — Dark Mode
SMART_DOC_DARK_CARD_BG = "#1E1E2E"
SMART_DOC_DARK_CARD_BORDER = "#818CF8"
SMART_DOC_DARK_TITLE = "#F8FAFC"
SMART_DOC_DARK_MUTED = "#94A3B8"
SMART_DOC_DARK_PREVIEW_BG = "#262637"
SMART_DOC_DARK_PREVIEW_BORDER = "#334155"
SMART_DOC_DARK_PREVIEW_TEXT = "#E2E8F0"
SMART_DOC_DARK_BADGE_BG = "#312E81"
SMART_DOC_DARK_BADGE_TEXT = "#C7D2FE"
SMART_DOC_DARK_BADGE_BORDER = "#4338CA"
SMART_DOC_DARK_LINK = "#60A5FA"

# Chat Bubble Tokens (Used by ChatArea)
USER_BUBBLE_COLOR = "#F4F6FF"        # Soft Indigo Tint for User
USER_TEXT_COLOR = "#111827"

ASSISTANT_BUBBLE_COLOR = "#FFFFFF"   # Clean White for Assistant
ASSISTANT_BORDER_COLOR = "#FFFFFF"   # Borderless look (matches background)

SYSTEM_TEXT_COLOR = "#64748B"
ERROR_TEXT_COLOR = "#EF4444"

# ==============================================================================
# THEME PALETTES & DYNAMIC STYLE GENERATOR
# ==============================================================================

THEME_PALETTES: dict[str, dict[str, str]] = {
    "light": {
        "bg_app": "#FFFFFF",
        "bg_sidebar": "#F9F9F9",
        "border_sidebar": "#E5E5E5",
        "bg_header": "#FFFFFF",
        "border_header": "#E5E5E5",
        "text_header_title": "#0D0D0D",
        "bg_capsule": "#FFFFFF",
        "border_capsule": "#CBD5E1",
        "border_capsule_focus": "#10A37F",
        "bg_chat": "#FFFFFF",
        "text_chat": "#0D0D0D",
        "user_bubble": "#F4F4F4",
        "user_text": "#0D0D0D",
        "assistant_bubble": "#FFFFFF",
        "assistant_border": "transparent",
        "assistant_text": "#0D0D0D",
        "status_bg": "#F9F9F9",
        "status_border": "#E5E5E5",
        "status_text": "#6E6E80",
        "btn_secondary_bg": "#F4F4F4",
        "btn_secondary_border": "#E5E5E5",
        "btn_secondary_text": "#202123",
        "btn_secondary_hover": "#ECECF1",
        "item_hover": "#ECECF1",
        "item_selected": "#E5E5E5",
        "item_selected_text": "#0D0D0D",
        "item_selected_border": "#10A37F",
        "combo_bg": "#F4F4F4",
        "combo_border": "#E5E5E5",
        "combo_text": "#0D0D0D",
        "combo_popup_bg": "#FFFFFF",
        "combo_popup_text": "#0D0D0D",
        "input_text": "#0D0D0D",
        "placeholder_text": "#8E8EA0",
        "scroll_handle": "#D9D9E3",
        "scroll_hover": "#ACACBE",
    },
    "dark": {
        "bg_app": "#212121",
        "bg_sidebar": "#171717",
        "border_sidebar": "#2F2F2F",
        "bg_header": "#212121",
        "border_header": "#2F2F2F",
        "text_header_title": "#ECECF1",
        "bg_capsule": "#2F2F2F",
        "border_capsule": "#3E3E3E",
        "border_capsule_focus": "#10A37F",
        "bg_chat": "#212121",
        "text_chat": "#ECECF1",
        "user_bubble": "#2F2F2F",
        "user_text": "#ECECF1",
        "assistant_bubble": "#212121",
        "assistant_border": "transparent",
        "assistant_text": "#ECECF1",
        "status_bg": "#171717",
        "status_border": "#2F2F2F",
        "status_text": "#8E8EA0",
        "btn_secondary_bg": "#2F2F2F",
        "btn_secondary_border": "#3E3E3E",
        "btn_secondary_text": "#ECECF1",
        "btn_secondary_hover": "#3E3E3E",
        "item_hover": "#2F2F2F",
        "item_selected": "#2F2F2F",
        "item_selected_text": "#FFFFFF",
        "item_selected_border": "#10A37F",
        "combo_bg": "#2F2F2F",
        "combo_border": "#3E3E3E",
        "combo_text": "#ECECF1",
        "combo_popup_bg": "#171717",
        "combo_popup_text": "#ECECF1",
        "input_text": "#ECECF1",
        "placeholder_text": "#8E8EA0",
        "scroll_handle": "#424242",
        "scroll_hover": "#565656",
    },
    "oled": {
        "bg_app": "#000000",
        "bg_sidebar": "#0A0A0A",
        "border_sidebar": "#262626",
        "bg_header": "#0A0A0A",
        "border_header": "#262626",
        "text_header_title": "#FFFFFF",
        "bg_capsule": "#121212",
        "border_capsule": "#262626",
        "border_capsule_focus": "#10A37F",
        "bg_chat": "#000000",
        "text_chat": "#FFFFFF",
        "user_bubble": "#1A1A1A",
        "user_text": "#EEF2FF",
        "assistant_bubble": "#000000",
        "assistant_border": "transparent",
        "assistant_text": "#FFFFFF",
        "status_bg": "#0A0A0A",
        "status_border": "#262626",
        "status_text": "#A3A3A3",
        "btn_secondary_bg": "#171717",
        "btn_secondary_border": "#262626",
        "btn_secondary_text": "#E5E5E5",
        "btn_secondary_hover": "#262626",
        "item_hover": "#171717",
        "item_selected": "#171717",
        "item_selected_text": "#FFFFFF",
        "item_selected_border": "#10A37F",
        "combo_bg": "#171717",
        "combo_border": "#262626",
        "combo_text": "#FFFFFF",
        "combo_popup_bg": "#121212",
        "combo_popup_text": "#FFFFFF",
        "input_text": "#FFFFFF",
        "placeholder_text": "#737373",
        "scroll_handle": "#262626",
        "scroll_hover": "#404040",
    },
    "neon": {
        "bg_app": "#090D16",
        "bg_sidebar": "#0F172A",
        "border_sidebar": "#1E293B",
        "bg_header": "#0F172A",
        "border_header": "#1E293B",
        "text_header_title": "#F472B6",
        "bg_capsule": "#0F172A",
        "border_capsule": "#334155",
        "border_capsule_focus": "#F472B6",
        "bg_chat": "#090D16",
        "text_chat": "#F8FAFC",
        "user_bubble": "#831843",
        "user_text": "#FCE7F3",
        "assistant_bubble": "#090D16",
        "assistant_border": "transparent",
        "assistant_text": "#F8FAFC",
        "status_bg": "#0F172A",
        "status_border": "#1E293B",
        "status_text": "#94A3B8",
        "btn_secondary_bg": "#1E293B",
        "btn_secondary_border": "#334155",
        "btn_secondary_text": "#F472B6",
        "btn_secondary_hover": "#334155",
        "item_hover": "#1E293B",
        "item_selected": "#831843",
        "item_selected_text": "#FBCFE8",
        "item_selected_border": "#F472B6",
        "combo_bg": "#1E293B",
        "combo_border": "#334155",
        "combo_text": "#F8FAFC",
        "combo_popup_bg": "#0F172A",
        "combo_popup_text": "#F8FAFC",
        "input_text": "#F8FAFC",
        "placeholder_text": "#64748B",
        "scroll_handle": "#334155",
        "scroll_hover": "#475569",
    }
}


def get_theme_palette(theme_name: str = "light") -> dict[str, str]:
    """Retrieve color palette dictionary for *theme_name* (light, dark, oled, neon)."""
    key = str(theme_name).lower()
    return THEME_PALETTES.get(key, THEME_PALETTES["light"])


def get_pill_combobox_style(theme_name: str = "light") -> str:
    p = get_theme_palette(theme_name)
    return f"""
QComboBox {{
    background-color: {p['combo_bg']};
    color: {p['combo_text']};
    border: 1px solid {p['combo_border']};
    border-radius: 8px;
    padding: 4px 10px;
    font-size: 10pt;
    font-weight: 600;
}}
QComboBox:hover {{
    background-color: {p['btn_secondary_hover']};
    border-color: {p['border_capsule_focus']};
}}
QComboBox:on {{
    border-color: {p['border_capsule_focus']};
    background-color: {p['combo_popup_bg']};
}}
QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 18px;
    border-left: none;
}}
QComboBox QAbstractItemView {{
    background-color: {p['combo_popup_bg']};
    color: {p['combo_popup_text']};
    border: 1px solid {p['combo_border']};
    border-radius: 8px;
    padding: 4px;
    selection-background-color: {p['item_selected']};
    selection-color: {p['item_selected_text']};
    outline: none;
}}
"""


def get_chat_browser_style(theme_name: str = "light") -> str:
    p = get_theme_palette(theme_name)
    return f"""
QTextBrowser {{
    background-color: {p['bg_chat']};
    color: {p['text_chat']};
    border: none;
    padding: 8px 12px;
    font-size: 12.5pt;
    font-family: 'Segoe UI Variable', 'Noto Sans Bengali', 'Inter', system-ui, sans-serif;
    selection-background-color: #818CF8;
    selection-color: #FFFFFF;
}}
"""


def get_document_css(theme_name: str = "light") -> str:
    p = get_theme_palette(theme_name)
    link_color = "#10A37F" if theme_name in ("light", "dark", "oled") else "#F472B6"
    code_inline_bg = "#EAEAEA" if theme_name == "light" else "#2F2F2F"
    return f"""
body, p, div, td {{
    font-size: 12.5pt;
    line-height: 1.6;
    color: {p['text_chat']};
    font-family: 'Segoe UI Variable', 'Noto Sans Bengali', 'Inter', system-ui, sans-serif;
}}
pre {{
    background-color: #1E1E1E;
    color: #D4D4D4;
    border-radius: 8px;
    padding: 10px 14px;
    font-family: 'Fira Code', 'Cascadia Code', 'Consolas', monospace;
    font-size: 10pt;
    margin: 8px 0;
}}
code {{
    font-family: 'Fira Code', 'Cascadia Code', 'Consolas', monospace;
    background-color: {code_inline_bg};
    color: {p['text_chat']};
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 10pt;
}}
pre code {{
    background-color: transparent;
    color: inherit;
    padding: 0;
}}
a {{
    color: {link_color};
    text-decoration: none;
    font-weight: 600;
}}
a:hover {{
    text-decoration: underline;
}}
"""


def get_global_app_style(theme_name: str = "light") -> str:
    p = get_theme_palette(theme_name)
    return f"""
/* Global Application Font & Base Window Background */
QMainWindow, QDialog {{
    background-color: {p['bg_app']};
}}
QWidget {{
    font-family: 'Segoe UI Variable', 'Noto Sans Bengali', 'Inter', system-ui, sans-serif;
}}

QScrollBar:vertical {{
    border: none;
    background: transparent;
    width: 8px;
    margin: 0px;
}}
QScrollBar::handle:vertical {{
    background: {p['scroll_handle']};
    min-height: 24px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical:hover {{
    background: {p['scroll_hover']};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar:horizontal {{
    border: none;
    background: transparent;
    height: 8px;
    margin: 0px;
}}
QScrollBar::handle:horizontal {{
    background: {p['scroll_handle']};
    min-width: 24px;
    border-radius: 4px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {p['scroll_hover']};
}}

/* Modern Context Menus */
QMenu {{
    background-color: {p['combo_popup_bg']};
    border: 1px solid {p['combo_border']};
    border-radius: 10px;
    padding: 6px;
}}
QMenu::item {{
    padding: 8px 16px;
    border-radius: 6px;
    color: {p['combo_popup_text']};
    font-size: 10pt;
}}
QMenu::item:selected {{
    background-color: {p['item_selected']};
    color: {p['item_selected_text']};
    font-weight: 600;
}}

/* Modern ToolTip */
QToolTip {{
    background-color: #0F172A;
    color: #F8FAFC;
    border: none;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 9.5pt;
}}
"""


# Static backward-compatibility exports
INPUT_STYLE = """
QLineEdit {
    background-color: #FFFFFF;
    color: #0F172A;
    border: 1px solid #E2E8F0;
    border-radius: 10px;
    padding: 8px 14px;
    font-size: 11pt;
    font-family: 'Segoe UI Variable', 'Inter', system-ui, sans-serif;
}
QLineEdit:focus { border: 1.5px solid #6366F1; }
"""

CAPSULE_CONTAINER_STYLE = """
QFrame#inputCapsule {
    background-color: #FFFFFF;
    border: 1px solid #CBD5E1;
    border-radius: 18px;
    padding: 2px 6px;
}
QFrame#inputCapsule:focus-within { border: 1.5px solid #6366F1; }
"""

BUTTON_STYLE = """
QPushButton {
    background-color: #4F46E5;
    color: #FFFFFF;
    border: none;
    border-radius: 8px;
    padding: 6px 14px;
    font-size: 10pt;
    font-weight: 600;
}
QPushButton:hover { background-color: #4338CA; }
QPushButton:pressed { background-color: #3730A3; }
QPushButton:disabled { background-color: #CBD5E1; color: #94A3B8; }
"""

ICON_BUTTON_STYLE = """
QPushButton {
    background-color: transparent;
    color: #475569;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 4px;
}
QPushButton:hover { background-color: #F1F5F9; color: #0F172A; border-color: #E2E8F0; }
"""

PILL_COMBOBOX_STYLE = get_pill_combobox_style("light")
CHAT_BROWSER_STYLE = get_chat_browser_style("light")
DOCUMENT_DEFAULT_CSS = get_document_css("light")
GLOBAL_APP_STYLE = get_global_app_style("light")

def get_voice_button_ready_style(theme_name: str = "light") -> str:
    p = get_theme_palette(theme_name)
    return f"""
QPushButton {{
    background-color: {p['btn_secondary_bg']};
    color: {p['btn_secondary_text']};
    border: 1px solid {p['btn_secondary_border']};
    border-radius: 17px;
    padding: 0px;
    font-size: 12pt;
}}
QPushButton:hover {{
    background-color: {p['btn_secondary_hover']};
    color: {p['input_text']};
    border-color: {p['border_capsule_focus']};
}}
"""

VOICE_BUTTON_READY_STYLE = get_voice_button_ready_style("light")

VOICE_BUTTON_LISTENING_STYLE = """
QPushButton {
    background-color: #EF4444;
    color: #FFFFFF;
    border: 1px solid #DC2626;
    border-radius: 17px;
    padding: 0px;
    font-size: 12pt;
    font-weight: 700;
}
QPushButton:hover { background-color: #DC2626; }
"""

VOICE_BUTTON_BUSY_STYLE = """
QPushButton {
    background-color: #F59E0B;
    color: #FFFFFF;
    border: none;
    border-radius: 17px;
    padding: 0px;
    font-size: 12pt;
}
"""

VOICE_BUTTON_SPEAKING_STYLE = """
QPushButton {
    background-color: #10B981;
    color: #FFFFFF;
    border: none;
    border-radius: 17px;
    padding: 0px;
    font-size: 12pt;
    font-weight: 700;
}
QPushButton:hover { background-color: #059669; }
"""

VOICE_BUTTON_ERROR_STYLE = """
QPushButton {
    background-color: #DC2626;
    color: #FFFFFF;
    border: none;
    border-radius: 17px;
    padding: 0px;
    font-size: 12pt;
}
"""

def get_dialog_style(theme_name: str = "light") -> str:
    """Retrieve theme QSS stylesheet for application dialogs (Settings, Voice, Rename, Approval)."""
    p = get_theme_palette(theme_name)
    return f"""
QDialog {{
    background-color: {p['bg_app']};
    color: {p['input_text']};
    border-radius: 12px;
}}
QLabel {{
    color: {p['input_text']};
}}
QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: {p['btn_secondary_bg']};
    color: {p['input_text']};
    border: 1px solid {p['btn_secondary_border']};
    border-radius: 8px;
    padding: 6px 10px;
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border-color: {p['border_capsule_focus']};
    background-color: {p['combo_popup_bg']};
}}
QGroupBox {{
    font-weight: 700;
    font-size: 10.5pt;
    color: {p['input_text']};
    border: 1px solid {p['btn_secondary_border']};
    border-radius: 10px;
    margin-top: 12px;
    padding-top: 16px;
    background-color: {p['status_bg']};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    background-color: {p['bg_app']};
    color: {p['input_text']};
    border-radius: 4px;
}}
QCheckBox {{
    font-size: 10pt;
    color: {p['input_text']};
    spacing: 8px;
    font-weight: 500;
}}
"""
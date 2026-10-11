"""
Utility for WCAG 2.1 Color Contrast calculations and compliance checks.
Calculates relative luminance and contrast ratios between foreground and background colors.
"""

from __future__ import annotations


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert hex color string (e.g. '#4F46E5' or '4F46E5') to RGB tuple (0-255)."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join(c * 2 for c in hex_color)
    if len(hex_color) != 6:
        raise ValueError(f"Invalid hex color: '{hex_color}'")
    return int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)


def _srgb_to_linear(c_255: int) -> float:
    c = c_255 / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(hex_color: str) -> float:
    """
    Calculate W3C WCAG 2.1 relative luminance for a hex color.
    Formula: L = 0.2126 * R + 0.7152 * G + 0.0722 * B (linearized sRGB)
    """
    r, g, b = hex_to_rgb(hex_color)
    r_lin = _srgb_to_linear(r)
    g_lin = _srgb_to_linear(g)
    b_lin = _srgb_to_linear(b)
    return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin


def contrast_ratio(fg_hex: str, bg_hex: str) -> float:
    """
    Calculate WCAG 2.1 contrast ratio between foreground and background hex colors.
    Returns float value between 1.0 and 21.0.
    """
    l1 = relative_luminance(fg_hex)
    l2 = relative_luminance(bg_hex)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return round((lighter + 0.05) / (darker + 0.05), 2)


def is_wcag_aa_compliant(fg_hex: str, bg_hex: str, is_large_text: bool = False) -> bool:
    """
    Check if contrast ratio satisfies WCAG 2.1 AA level.
    - Normal text: >= 4.5:1
    - Large text / UI graphics: >= 3.0:1
    """
    threshold = 3.0 if is_large_text else 4.5
    return contrast_ratio(fg_hex, bg_hex) >= threshold


def is_wcag_aaa_compliant(fg_hex: str, bg_hex: str) -> bool:
    """Check if contrast ratio satisfies WCAG 2.1 AAA level (>= 7.0:1)."""
    return contrast_ratio(fg_hex, bg_hex) >= 7.0

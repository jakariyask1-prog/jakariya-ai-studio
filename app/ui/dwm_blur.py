"""
Windows 11 Mica, Acrylic, and Immersive Dark Mode DWM Backdrop Manager.

Enables native Windows 11 translucent backdrop styling (Mica, Acrylic, Mica Alt)
and dark mode titlebar synchronization with graceful fallback for Windows 10/Linux/Mac.
"""

from __future__ import annotations

import sys
import ctypes
from ctypes import c_int, byref, sizeof
import logging

logger = logging.getLogger(__name__)

# DWM Window Attributes
DWMWA_USE_IMMERSIVE_DARK_MODE_BEFORE_20H1 = 19
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_BORDER_COLOR = 34
DWMWA_CAPTION_COLOR = 35
DWMWA_TEXT_COLOR = 36
DWMWA_SYSTEMBACKDROP_TYPE = 38
DWMWA_MICA_EFFECT = 1029

# Backdrop Type Values (Windows 11 22H2+ build >= 22621)
DWMSBT_AUTO = 0
DWMSBT_NONE = 1
DWMSBT_MAINWINDOW = 2       # Mica
DWMSBT_TRANSIENTWINDOW = 3  # Acrylic
DWMSBT_TABBEDWINDOW = 4     # Mica Alt (Tabbed)


def get_windows_build() -> int:
    """Return the Windows build number or 0 if not on Windows."""
    if sys.platform != "win32":
        return 0
    try:
        return sys.getwindowsversion().build
    except Exception:
        return 0


def apply_dwm_backdrop(
    hwnd: int,
    is_dark: bool = False,
    backdrop_type: str = "mica",
    caption_color: int | None = None,
) -> bool:
    """Apply native Windows 11 Mica / Acrylic effect and dark mode titlebar.

    Args:
        hwnd: Native OS window handle (e.g. ``int(widget.winId())``).
        is_dark: True for dark theme, False for light theme.
        backdrop_type: "mica", "acrylic", "tabbed", or "none".
        caption_color: Optional RGB integer (0x00BBGGRR) for custom titlebar.

    Returns:
        True if successfully applied, False otherwise.
    """
    if sys.platform != "win32" or not hwnd:
        return False

    build = get_windows_build()
    if build < 17763:
        return False

    dwmapi = None
    try:
        dwmapi = ctypes.windll.dwmapi
    except Exception as exc:
        logger.debug("[DWM] Failed to load dwmapi.dll: %s", exc)
        return False

    # 1. Apply Immersive Dark Mode to Window Titlebar
    try:
        dark_mode = c_int(1 if is_dark else 0)
        attr = DWMWA_USE_IMMERSIVE_DARK_MODE if build >= 19041 else DWMWA_USE_IMMERSIVE_DARK_MODE_BEFORE_20H1
        dwmapi.DwmSetWindowAttribute(hwnd, attr, byref(dark_mode), sizeof(dark_mode))
    except Exception as exc:
        logger.debug("[DWM] Could not set immersive dark mode: %s", exc)

    # 2. Apply Custom Caption / Titlebar Color (Windows 11 build >= 22000)
    if build >= 22000 and caption_color is not None:
        try:
            color = c_int(caption_color)
            dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_CAPTION_COLOR, byref(color), sizeof(color))
        except Exception:
            pass

    # 3. Apply Native Mica / Acrylic Backdrop (Windows 11)
    if build >= 22621:
        # Windows 11 22H2+ supports DWMWA_SYSTEMBACKDROP_TYPE
        type_map = {
            "mica": DWMSBT_MAINWINDOW,
            "acrylic": DWMSBT_TRANSIENTWINDOW,
            "tabbed": DWMSBT_TABBEDWINDOW,
            "none": DWMSBT_NONE,
        }
        backdrop_val = c_int(type_map.get(backdrop_type.lower(), DWMSBT_MAINWINDOW))
        try:
            res = dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_SYSTEMBACKDROP_TYPE, byref(backdrop_val), sizeof(backdrop_val)
            )
            return res == 0
        except Exception as exc:
            logger.debug("[DWM] DWMWA_SYSTEMBACKDROP_TYPE failed: %s", exc)
    elif build >= 22000:
        # Windows 11 21H2 supports DWMWA_MICA_EFFECT
        try:
            mica_val = c_int(1 if backdrop_type.lower() in ("mica", "acrylic") else 0)
            res = dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_MICA_EFFECT, byref(mica_val), sizeof(mica_val)
            )
            return res == 0
        except Exception as exc:
            logger.debug("[DWM] DWMWA_MICA_EFFECT failed: %s", exc)

    return True

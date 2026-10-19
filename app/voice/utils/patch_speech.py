"""Speech recognition binary resolver and windowed mode subprocess patcher.

Provides reliable resolution of flac-win32.exe in both source environments
and PyInstaller one-file / one-folder frozen executables without WinError 6
(invalid handle in --noconsole mode) or WinError 2 (file not found).
"""

from __future__ import annotations

import os
import sys
import shutil
import logging
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)

_PATCH_APPLIED: bool = False
_CACHED_FLAC_PATH: Optional[str] = None


def find_flac_converter() -> str:
    """Find and return the absolute path to a working FLAC converter executable."""
    global _CACHED_FLAC_PATH
    if _CACHED_FLAC_PATH and os.path.isfile(_CACHED_FLAC_PATH):
        return _CACHED_FLAC_PATH

    candidates: list[str] = []

    # 1. System PATH
    sys_flac = shutil.which("flac")
    if sys_flac and os.path.isfile(sys_flac):
        _CACHED_FLAC_PATH = sys_flac
        return sys_flac

    # 2. PyInstaller _MEIPASS extraction directory
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        exe_dir = os.path.dirname(sys.executable)
        candidates.extend([
            os.path.join(meipass, "flac-win32.exe"),
            os.path.join(meipass, "speech_recognition", "flac-win32.exe"),
            os.path.join(meipass, "assets", "bin", "flac-win32.exe"),
            os.path.join(exe_dir, "flac-win32.exe"),
            os.path.join(exe_dir, "speech_recognition", "flac-win32.exe"),
            os.path.join(exe_dir, "assets", "bin", "flac-win32.exe"),
        ])

    # 3. Workspace assets/bin directory
    try:
        from app.utils.paths import get_resource_path
        asset_flac = str(get_resource_path("assets", "bin", "flac-win32.exe"))
        candidates.append(asset_flac)
    except Exception:
        pass

    # 4. speech_recognition package folder
    try:
        import speech_recognition as sr
        sr_dir = os.path.dirname(os.path.abspath(sr.__file__))
        candidates.append(os.path.join(sr_dir, "flac-win32.exe"))
    except Exception:
        pass

    # Search candidates
    for cand in candidates:
        if cand and os.path.isfile(cand):
            _CACHED_FLAC_PATH = os.path.abspath(cand)
            return _CACHED_FLAC_PATH

    # Return default fallback
    return "flac"


def patch_speech_recognition() -> bool:
    """Safely patch SpeechRecognition's FLAC converter and AudioData.get_flac_data.

    Ensures that subprocess.Popen never fails with WinError 6 in --noconsole
    mode and always finds the bundled flac-win32.exe binary.
    """
    global _PATCH_APPLIED
    if _PATCH_APPLIED:
        return True

    try:
        import speech_recognition as sr

        flac_bin = find_flac_converter()
        logger.info("SpeechRecognition FLAC converter located at: %s", flac_bin)

        # Patch get_flac_converter
        sr.get_flac_converter = find_flac_converter

        # Patch AudioData.get_flac_data
        def patched_get_flac_data(self, convert_rate=None, convert_width=None):
            assert convert_width is None or (
                convert_width % 1 == 0 and 1 <= convert_width <= 3
            ), "Sample width to convert to must be between 1 and 3 inclusive"

            if self.sample_width > 3 and convert_width is None:
                convert_width = 3

            wav_data = self.get_wav_data(convert_rate, convert_width)
            flac_converter = find_flac_converter()

            startup_info = None
            creationflags = 0
            if os.name == "nt":
                startup_info = subprocess.STARTUPINFO()
                startup_info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startup_info.wShowWindow = subprocess.SW_HIDE
                creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

            try:
                process = subprocess.Popen(
                    [
                        flac_converter,
                        "--stdout",
                        "--totally-silent",
                        "-1",
                        "--fast",
                        "-",
                    ],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    startupinfo=startup_info,
                    creationflags=creationflags,
                )
                flac_data, _ = process.communicate(wav_data)
                if not flac_data:
                    logger.warning("[patch_speech] FLAC converter returned empty data for wav input (%d bytes)", len(wav_data))
                return flac_data
            except Exception as exc:
                logger.exception("[patch_speech] FLAC converter execution failed (%s): %s", flac_converter, exc)
                raise

        sr.AudioData.get_flac_data = patched_get_flac_data
        _PATCH_APPLIED = True
        return True

    except Exception as exc:
        logger.warning("Failed to apply speech_recognition patch: %s", exc)
        return False

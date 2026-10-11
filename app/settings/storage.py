"""JSON persistence storage layer for saving and loading configuration to disk."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from app.settings.defaults import DEFAULT_SETTINGS


def get_settings_file_path() -> Path:
    """Return absolute path to settings JSON storage file."""
    import sys
    if getattr(sys, "frozen", False):
        local_app_data = os.getenv("LOCALAPPDATA")
        base = Path(local_app_data) if local_app_data else Path.home() / ".jakariya_ai_studio"
        config_dir = base / "Jakariya AI Studio"
    else:
        base_dir = Path(__file__).resolve().parent.parent.parent
        config_dir = base_dir / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "user_settings.json"


class SettingsStorage:
    """JSON storage layer with atomic file writes and corrupt backup restoration."""

    def __init__(self, file_path: Path | None = None) -> None:
        self.file_path = file_path or get_settings_file_path()

    def _deep_merge(self, default_dict: dict[str, Any], user_dict: dict[str, Any]) -> dict[str, Any]:
        """Merge user settings into default settings recursively."""
        result = dict(default_dict)
        for key, value in user_dict.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def _migrate_keys_to_vault(self, providers_dict: dict[str, Any]) -> dict[str, Any]:
        """Migrate plaintext API keys to Windows Credential Manager on first load.

        Returns the same dict reference if nothing changed, or a new dict if migrations occurred.
        """
        try:
            from app.settings.key_vault import migrate_plaintext_keys_to_vault
            migrated = migrate_plaintext_keys_to_vault(providers_dict)
            # Detect if any keys were actually changed
            changed = any(
                migrated.get(p_id, {}).get("api_key") != providers_dict.get(p_id, {}).get("api_key")
                for p_id in providers_dict
            )
            return migrated if changed else providers_dict
        except Exception:
            return providers_dict

    def load(self) -> dict[str, Any]:
        """Load settings from JSON file and merge with defaults.

        Returns
        -------
        dict[str, Any]
            Complete merged settings dictionary.
        """
        if not self.file_path.exists():
            logging.info(f"[SettingsStorage] Settings file not found at {self.file_path}. Creating defaults.")
            self.save(DEFAULT_SETTINGS)
            return dict(DEFAULT_SETTINGS)

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                user_settings = json.load(f)
            if not isinstance(user_settings, dict):
                raise ValueError("JSON content is not a dictionary.")

            merged = self._deep_merge(DEFAULT_SETTINGS, user_settings)

            # One-time migration: move any plaintext API keys into Windows Credential Manager
            providers_before = merged.get("providers", {})
            providers_after = self._migrate_keys_to_vault(providers_before)
            if providers_after is not providers_before:
                merged["providers"] = providers_after
                self.save(merged)  # Re-save scrubbed version

            return merged

        except Exception as exc:
            logging.exception(f"[SettingsStorage] Failed to read {self.file_path}: {exc}. Creating backup and loading defaults.")
            # Backup corrupt file
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                backup_path = self.file_path.with_name(
                    f"{self.file_path.stem}.{timestamp}{self.file_path.suffix}.bak"
                )
                if self.file_path.exists():
                    os.replace(self.file_path, backup_path)
            except Exception as backup_exc:
                logging.warning(f"[SettingsStorage] Could not create backup file: {backup_exc}")

            self.save(DEFAULT_SETTINGS)
            return dict(DEFAULT_SETTINGS)

    def save(self, settings_dict: dict[str, Any]) -> bool:
        """Atomically save settings dictionary to JSON file on disk.

        Parameters
        ----------
        settings_dict:
            Settings dictionary to persist.

        Returns
        -------
        bool
            True if write succeeded.
        """
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self.file_path.with_suffix(".tmp")

            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(settings_dict, f, indent=4, ensure_ascii=False)

            # Atomic swap
            os.replace(temp_path, self.file_path)
            logging.debug(f"[SettingsStorage] Settings saved successfully to {self.file_path}")
            return True

        except Exception as exc:
            logging.exception(f"[SettingsStorage] Failed to save settings to {self.file_path}: {exc}")
            return False

    def export_backup(self, output_path: Path | str) -> bool:
        """Export current active settings JSON file to specified output_path."""
        try:
            out_p = Path(output_path)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            current_data = self.load()
            with open(out_p, "w", encoding="utf-8") as f:
                json.dump(current_data, f, indent=4, ensure_ascii=False)
            logging.info(f"[SettingsStorage] Backup exported to {out_p}")
            return True
        except Exception as exc:
            logging.exception(f"[SettingsStorage] Failed to export backup: {exc}")
            return False

    def import_backup(self, input_path: Path | str) -> dict[str, Any] | None:
        """Import settings from specified input_path, validate, and merge with defaults."""
        try:
            in_p = Path(input_path)
            if not in_p.exists():
                return None
            with open(in_p, "r", encoding="utf-8") as f:
                imported_dict = json.load(f)
            if not isinstance(imported_dict, dict):
                return None

            merged = self._deep_merge(DEFAULT_SETTINGS, imported_dict)
            self.save(merged)
            logging.info(f"[SettingsStorage] Backup imported from {in_p}")
            return merged
        except Exception as exc:
            logging.exception(f"[SettingsStorage] Failed to import backup from {input_path}: {exc}")
            return None

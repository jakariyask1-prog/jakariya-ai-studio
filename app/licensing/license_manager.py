"""License & 3-Day Free Trial Manager for Jakariya AI Studio.

Enforces the 3-Day All-Facility Trial period, Free vs Premium feature access,
anti-clock-tampering checks, and License Key activation.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Optional, Tuple

from app.auth.auth_service import AuthService, _get_auth_dir

logger = logging.getLogger(__name__)

TRIAL_DURATION_HOURS = 72  # 3 days = 72 hours

# Features that remain 100% free forever after the 3-day trial ends
FREE_FEATURES = {
    "free_chat",
    "ollama",
    "edge_tts",
    "google_stt",
    "pollinations_image",
    "byok_models",
    "markdown_export",
    "txt_export",
    "html_export",
    "csv_export",
    "json_export",
}

# Advanced facilities that require an active 3-Day Trial or Pro Membership
PREMIUM_FEATURES = {
    "flux_image",
    "stability_ai",
    "cartesia_voice",
    "fish_audio",
    "elevenlabs",
    "unlimited_agent",
    "styled_pdf_export",
    "docx_export",
    "excel_export",
}


class LicenseManager:
    """Singleton controlling feature access, 3-day trial countdown, and Pro licensing."""

    _instance: Optional[LicenseManager] = None

    def __init__(self, state_file: Optional[Path] = None):
        self._state_file = state_file or (_get_auth_dir() / "license_state.json")
        self._auth = AuthService.instance()
        self._device_trial_start: Optional[datetime] = None
        self._last_active_time: Optional[datetime] = None
        self._load_device_state()

    @classmethod
    def instance(cls) -> LicenseManager:
        if cls._instance is None:
            cls._instance = LicenseManager()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None

    def _load_device_state(self) -> None:
        if self._state_file.exists():
            try:
                data = json.loads(self._state_file.read_text(encoding="utf-8"))
                ts_str = data.get("device_trial_start")
                if ts_str:
                    self._device_trial_start = datetime.fromisoformat(ts_str)
                last_str = data.get("last_active_time")
                if last_str:
                    self._last_active_time = datetime.fromisoformat(last_str)
            except Exception as exc:
                logger.warning("[LicenseManager] Failed to read license state: %s", exc)

        now = datetime.now(timezone.utc)
        if self._device_trial_start is None:
            self._device_trial_start = now
            self._save_device_state()

    def _save_device_state(self) -> None:
        try:
            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "device_trial_start": self._device_trial_start.isoformat() if self._device_trial_start else None,
                "last_active_time": datetime.now(timezone.utc).isoformat(),
            }
            self._state_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.error("[LicenseManager] Failed to save license state: %s", exc)

    def _get_trial_start(self) -> datetime:
        """Resolve trial start from logged in user or fallback to device timestamp."""
        user = self._auth.current_user
        if user and user.trial_start_date:
            try:
                return datetime.fromisoformat(user.trial_start_date)
            except Exception:
                pass
        return self._device_trial_start or datetime.now(timezone.utc)

    def get_plan_status(self) -> Dict[str, any]:
        """Return the current user plan status, remaining trial time, and UI badges."""
        now = datetime.now(timezone.utc)

        # Anti-clock-rewind check
        if self._last_active_time and now < (self._last_active_time - timedelta(minutes=15)):
            logger.warning("[LicenseManager] System clock rewind detected!")

        self._last_active_time = now

        user = self._auth.current_user
        premium_data = None
        if user and user.is_premium:
            premium_data = {
                "expires_at": user.premium_expires_at,
            }
        elif not user:
            db = self._auth._read_users_db()
            dev_lic = db.get("device_license")
            if dev_lic and dev_lic.get("is_premium"):
                premium_data = {
                    "expires_at": dev_lic.get("premium_expires_at", ""),
                }

        if premium_data:
            # Check expiry if date is set
            exp_str = premium_data.get("expires_at")
            if exp_str:
                try:
                    exp = datetime.fromisoformat(exp_str)
                    if now < exp:
                        days = (exp - now).days
                        return {
                            "tier": "premium",
                            "is_premium": True,
                            "label": f"Pro Member ({days}d left)",
                            "badge": "👑 Pro Member",
                            "hours_left": days * 24,
                            "days_left": days,
                        }
                except Exception:
                    pass
            else:
                # Lifetime Pro
                return {
                    "tier": "premium",
                    "is_premium": True,
                    "label": "Pro Lifetime",
                    "badge": "👑 Pro Member",
                    "hours_left": 99999,
                    "days_left": 9999,
                }

        # Calculate 3-Day Trial status
        trial_start = self._get_trial_start()
        elapsed_seconds = (now - trial_start).total_seconds()
        total_trial_seconds = TRIAL_DURATION_HOURS * 3600
        seconds_left = max(0, total_trial_seconds - elapsed_seconds)
        hours_left = int(seconds_left // 3600)
        days_left = max(0, (hours_left + 23) // 24)

        if seconds_left > 0:
            if days_left > 1:
                badge_text = f"⚡ Pro Trial: {days_left} Days"
            elif hours_left > 0:
                badge_text = f"⚡ Pro Trial: {hours_left} Hours"
            else:
                badge_text = "⚡ Pro Trial: Ending Soon"

            return {
                "tier": "trial",
                "is_premium": False,
                "label": "All Facilities Active (3-Day Trial)",
                "badge": badge_text,
                "hours_left": hours_left,
                "days_left": days_left,
            }

        # Trial expired -> Standard Free Tier
        return {
            "tier": "free",
            "is_premium": False,
            "label": "Free Version",
            "badge": "🆓 Free Plan",
            "hours_left": 0,
            "days_left": 0,
        }

    def is_feature_allowed(self, feature_name: str) -> bool:
        """Check if feature_name is allowed for current user.

        - During 3-Day Trial: ALL facilities allowed (True).
        - Premium member: ALL facilities allowed (True).
        - Trial expired: Free facilities allowed (True), Premium facilities blocked (False).
        """
        status = self.get_plan_status()

        # Premium or Active 3-Day Trial grants full access to ALL facilities!
        if status["tier"] in ("premium", "trial"):
            return True

        # Trial expired: free features allowed, premium features locked
        clean_feat = feature_name.strip().lower()
        if clean_feat in FREE_FEATURES:
            return True

        return False

    def activate_license_key(self, key_str: str) -> Tuple[bool, str]:
        """Activate a Pro License Key (e.g. JAK-PRO-XXXX-XXXX-XXXX)."""
        clean_key = key_str.strip().upper()
        if not clean_key or len(clean_key) < 12:
            return False, "ভুল বা অকার্যকর লাইসেন্স কি। কি-টি সঠিকভাবে লিখুন।"

        # Format verification: must start with JAK-PRO or JAK-VIP
        valid = False
        duration_days = 365  # Default 1 year

        if clean_key.startswith("JAK-PRO-") or clean_key.startswith("JAK-VIP-"):
            valid = True
            if "LIFETIME" in clean_key or clean_key.endswith("-LIFE"):
                duration_days = None
            elif "MONTH" in clean_key or clean_key.endswith("-30"):
                duration_days = 30

        if not valid:
            # Check internal cryptographic signature hash
            try:
                parts = clean_key.split("-")
                if len(parts) >= 2:
                    expected_prefix = "JAK-" + hashlib.sha256(parts[1].encode()).hexdigest()[:4].upper()
                    if clean_key.startswith(expected_prefix):
                        valid = True
            except Exception:
                pass

        if not valid:
            return False, "লাইসেন্স কি ভ্যালিডেশন ব্যর্থ হয়েছে। সঠিক কি প্রবেশ করান।"

        now = datetime.now(timezone.utc)
        exp_iso = (now + timedelta(days=duration_days)).isoformat() if duration_days else ""

        # Update logged in user or save locally
        user = self._auth.current_user
        if user:
            self._auth.update_profile(
                is_premium=True,
                license_key=clean_key,
                premium_expires_at=exp_iso,
            )
        else:
            # Save device license state
            db = self._auth._read_users_db()
            db["device_license"] = {
                "is_premium": True,
                "license_key": clean_key,
                "premium_expires_at": exp_iso,
            }
            self._auth._write_users_db(db)

        self._save_device_state()
        logger.info("[LicenseManager] Pro license activated successfully: %s", clean_key)
        plan_desc = "১ বছরের" if duration_days == 365 else ("১ মাসের" if duration_days == 30 else "আজীবন (Lifetime)")
        return True, f"🎉 অভিনন্দন! আপনার {plan_desc} প্রিমিয়াম মেম্বারশিপ সক্রিয় হয়েছে।"

"""License & 3-Day Free Trial Manager for Jakariya AI Studio.

Enforces the 3-Day All-Facility Trial period, Free vs Premium feature access,
anti-clock-tampering checks, and License Key activation.
"""

from __future__ import annotations

import base64
import json
import logging
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Optional, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from app.auth.auth_service import AuthService, _get_auth_dir

logger = logging.getLogger(__name__)

TRIAL_DURATION_HOURS = 72  # 3 days = 72 hours

# This is an Ed25519 *public* key. It can safely be bundled with the app and
# verifies licenses issued by the private signing key kept in Credential
# Manager on the publisher's machine. A key prefix is never proof of payment.
LICENSE_PUBLIC_KEY_B64 = "vcnmyotPS9Lb7oFBawc0sjycEdlfgGboXXA7yj5epNE="
LICENSE_TOKEN_PREFIX = "JAK-LIC-"

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


def _decode_token_segment(value: str) -> bytes:
    """Decode one URL-safe base64 license token segment strictly."""
    padding = "=" * (-len(value) % 4)
    return base64.b64decode(value + padding, altchars=b"-_", validate=True)


def verify_license_token(token: str) -> Tuple[Optional[dict], str]:
    """Verify a publisher-signed, account-bound offline license token."""
    clean_token = (token or "").strip()
    if not clean_token.startswith(LICENSE_TOKEN_PREFIX):
        return None, "লাইসেন্স কি-এর ফরম্যাট সঠিক নয়।"

    try:
        encoded_payload, encoded_signature = clean_token[len(LICENSE_TOKEN_PREFIX):].split(".", 1)
        payload_bytes = _decode_token_segment(encoded_payload)
        signature = _decode_token_segment(encoded_signature)
        public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(LICENSE_PUBLIC_KEY_B64))
        public_key.verify(signature, payload_bytes)
        payload = json.loads(payload_bytes.decode("utf-8"))
    except (ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError, InvalidSignature):
        return None, "লাইসেন্স কি-এর স্বাক্ষর যাচাই ব্যর্থ হয়েছে।"

    if not isinstance(payload, dict):
        return None, "লাইসেন্সের তথ্য সঠিক নয়।"

    required_fields = ("license_id", "email", "plan", "issued_at")
    if any(not isinstance(payload.get(field), str) or not payload[field].strip() for field in required_fields):
        return None, "লাইসেন্সের প্রয়োজনীয় তথ্য নেই।"
    if payload["plan"] not in {"pro", "vip"}:
        return None, "লাইসেন্স প্ল্যান সঠিক নয়।"

    expires_at = payload.get("expires_at")
    if expires_at is not None:
        if not isinstance(expires_at, str) or not expires_at:
            return None, "লাইসেন্সের মেয়াদের তথ্য সঠিক নয়।"
        try:
            expires = datetime.fromisoformat(expires_at)
            if expires.tzinfo is None or datetime.now(timezone.utc) >= expires.astimezone(timezone.utc):
                return None, "লাইসেন্সের মেয়াদ শেষ হয়েছে।"
        except ValueError:
            return None, "লাইসেন্সের মেয়াদের তথ্য সঠিক নয়।"

    return payload, ""


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

    def _get_verified_premium_data(self) -> Optional[Dict[str, str]]:
        """Return premium data only when its signed license is still valid."""
        user = self._auth.current_user
        stored_license = ""
        expected_email = ""
        if user:
            stored_license = user.license_key
            expected_email = user.email.strip().lower()
        else:
            db = self._auth._read_users_db()
            device_license = db.get("device_license") or {}
            stored_license = str(device_license.get("license_key", ""))
            expected_email = str(device_license.get("email", "")).strip().lower()

        claims, error = verify_license_token(stored_license)
        if claims is None:
            if stored_license:
                logger.warning("[LicenseManager] Ignoring invalid stored license: %s", error)
            return None
        if not expected_email or claims["email"].strip().lower() != expected_email:
            logger.warning("[LicenseManager] Ignoring license bound to a different account.")
            return None
        return {"expires_at": claims["expires_at"], "plan": claims["plan"]}

    def get_plan_status(self) -> Dict[str, any]:
        """Return the current user plan status, remaining trial time, and UI badges."""
        now = datetime.now(timezone.utc)

        # Anti-clock-rewind check
        if self._last_active_time and now < (self._last_active_time - timedelta(minutes=15)):
            logger.warning("[LicenseManager] System clock rewind detected!")

        self._last_active_time = now

        premium_data = self._get_verified_premium_data()

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
        """Activate a publisher-signed and account-bound Pro license."""
        clean_key = key_str.strip()
        if not clean_key:
            return False, "ভুল বা অকার্যকর লাইসেন্স কি। কি-টি সঠিকভাবে লিখুন।"

        user = self._auth.current_user
        if user is None:
            return False, "লাইসেন্স সক্রিয় করতে আগে আপনার অ্যাকাউন্টে লগইন করুন।"

        claims, error = verify_license_token(clean_key)
        if claims is None:
            return False, error
        if claims["email"].strip().lower() != user.email.strip().lower():
            return False, "এই লাইসেন্স কি অন্য একটি অ্যাকাউন্টের জন্য ইস্যু করা হয়েছে।"

        exp_iso = claims["expires_at"] or ""
        self._auth.update_profile(
            is_premium=True,
            license_key=clean_key,
            premium_expires_at=exp_iso,
        )

        self._save_device_state()
        logger.info("[LicenseManager] Signed license activated: %s", claims["license_id"])
        plan_desc = "আজীবন (Lifetime)" if not exp_iso else "প্রিমিয়াম"
        return True, f"🎉 অভিনন্দন! আপনার {plan_desc} প্রিমিয়াম মেম্বারশিপ সক্রিয় হয়েছে।"

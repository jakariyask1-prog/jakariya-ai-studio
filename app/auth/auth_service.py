"""Authentication Service for Jakariya AI Studio.

Handles user signup, login, password hashing, session tokens,
and persistent user profile management with 3-day trial tracking.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import secrets
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


def _get_auth_dir() -> Path:
    """Return secure writable storage for user auth data."""
    local_app_data = os.getenv("LOCALAPPDATA")
    base = Path(local_app_data) if local_app_data else Path.home() / ".jakariya_ai_studio"
    auth_dir = base / "Jakariya AI Studio"
    auth_dir.mkdir(parents=True, exist_ok=True)
    return auth_dir


def _hash_password(password: str, salt: Optional[bytes] = None) -> Tuple[str, str]:
    """Securely hash password using PBKDF2 with SHA-256."""
    if salt is None:
        salt = secrets.token_bytes(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
    salt_hex = salt.hex()
    hash_hex = key.hex()
    return hash_hex, salt_hex


def _verify_password(password: str, stored_hash: str, salt_hex: str) -> bool:
    """Verify password against stored PBKDF2 hash."""
    salt = bytes.fromhex(salt_hex)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
    return secrets.compare_digest(key.hex(), stored_hash)


@dataclass
class UserProfile:
    user_id: str
    email: str
    name: str
    password_hash: str
    salt: str
    created_at: str  # ISO timestamp
    trial_start_date: str  # ISO timestamp
    is_premium: bool = False
    license_key: str = ""
    premium_expires_at: str = ""  # ISO timestamp or empty for lifetime
    session_token: str = ""


class AuthService:
    """Manages user registration, sign in, trial tracking, and persistent session storage."""

    _instance: Optional[AuthService] = None

    def __init__(self, data_path: Optional[Path] = None):
        self._data_path = data_path or (_get_auth_dir() / "user_auth.json")
        self._current_user: Optional[UserProfile] = None
        self._load_current_session()

    @classmethod
    def instance(cls) -> AuthService:
        if cls._instance is None:
            cls._instance = AuthService()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None

    @property
    def current_user(self) -> Optional[UserProfile]:
        return self._current_user

    @property
    def is_logged_in(self) -> bool:
        return self._current_user is not None

    def _read_users_db(self) -> dict:
        if not self._data_path.exists():
            return {"users": {}, "active_user_id": None}
        try:
            content = self._data_path.read_text(encoding="utf-8")
            return json.loads(content)
        except Exception as exc:
            logger.warning("[AuthService] Failed to read auth database: %s", exc)
            return {"users": {}, "active_user_id": None}

    def _write_users_db(self, db: dict) -> None:
        try:
            self._data_path.parent.mkdir(parents=True, exist_ok=True)
            self._data_path.write_text(json.dumps(db, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.error("[AuthService] Failed to write auth database: %s", exc)

    def _load_current_session(self) -> None:
        """Auto-login if a valid session exists in storage."""
        db = self._read_users_db()
        active_id = db.get("active_user_id")
        if active_id and active_id in db.get("users", {}):
            u_data = db["users"][active_id]
            self._current_user = UserProfile(**u_data)
            logger.info("[AuthService] Restored active session for: %s", self._current_user.email)

    def signup(self, email: str, password: str, name: str = "") -> Tuple[bool, str]:
        """Register a new user account with an automatic 3-Day Full-Access Pro Trial."""
        clean_email = email.strip().lower()
        if not clean_email or "@" not in clean_email or "." not in clean_email:
            return False, "অনুগ্রহ করে একটি সঠিক ইমেইল অ্যাড্রেস লিখুন।"

        if len(password) < 6:
            return False, "পাসওয়ার্ড কমপক্ষে ৬ অক্ষরের হতে হবে।"

        db = self._read_users_db()
        users = db.get("users", {})

        # Check existing user
        for uid, u in users.items():
            if u.get("email", "").lower() == clean_email:
                return False, "এই ইমেইলটি দিয়ে ইতোমধ্যে অ্যাকাউন্ট তৈরি করা হয়েছে। লগইন করুন।"

        now_iso = datetime.now(timezone.utc).isoformat()
        pwd_hash, salt_hex = _hash_password(password)
        user_id = f"usr_{secrets.token_hex(8)}"
        session_token = f"tok_{secrets.token_urlsafe(32)}"

        display_name = name.strip() or clean_email.split("@")[0].capitalize()

        profile = UserProfile(
            user_id=user_id,
            email=clean_email,
            name=display_name,
            password_hash=pwd_hash,
            salt=salt_hex,
            created_at=now_iso,
            trial_start_date=now_iso,
            is_premium=False,
            session_token=session_token,
        )

        users[user_id] = asdict(profile)
        db["users"] = users
        db["active_user_id"] = user_id
        self._write_users_db(db)

        self._current_user = profile
        logger.info("[AuthService] User registered successfully: %s (Trial Started)", clean_email)
        return True, "সাইন-আপ সফল হয়েছে! আপনার ৩ দিনের সম্পূর্ণ ফ্রি প্রিমিয়াম ট্রায়াল শুরু হয়েছে।"

    def login(self, email: str, password: str) -> Tuple[bool, str]:
        """Sign in an existing user with email and password."""
        clean_email = email.strip().lower()
        if not clean_email:
            return False, "ইমেইল প্রদান করা আবশ্যক।"

        db = self._read_users_db()
        users = db.get("users", {})

        target_user = None
        for uid, u in users.items():
            if u.get("email", "").lower() == clean_email:
                target_user = u
                break

        if not target_user:
            return False, "এই ইমেইলে কোনো অ্যাকাউন্ট পাওয়া যায়নি। অনুগ্রহ করে সাইন-আপ করুন।"

        if not _verify_password(password, target_user.get("password_hash", ""), target_user.get("salt", "")):
            return False, "ভুল পাসওয়ার্ড। আবার চেষ্টা করুন।"

        # Refresh session token
        session_token = f"tok_{secrets.token_urlsafe(32)}"
        target_user["session_token"] = session_token
        db["users"][target_user["user_id"]] = target_user
        db["active_user_id"] = target_user["user_id"]
        self._write_users_db(db)

        self._current_user = UserProfile(**target_user)
        logger.info("[AuthService] User logged in: %s", clean_email)
        return True, "লগইন সফল হয়েছে!"

    def logout(self) -> None:
        """Clear the active user session."""
        db = self._read_users_db()
        db["active_user_id"] = None
        self._write_users_db(db)
        self._current_user = None
        logger.info("[AuthService] User logged out.")

    def update_profile(self, **kwargs) -> None:
        """Update fields on current user profile."""
        if not self._current_user:
            return
        db = self._read_users_db()
        uid = self._current_user.user_id
        if uid in db.get("users", {}):
            for k, v in kwargs.items():
                if hasattr(self._current_user, k):
                    setattr(self._current_user, k, v)
                    db["users"][uid][k] = v
            self._write_users_db(db)

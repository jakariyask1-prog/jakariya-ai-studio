"""Authentication Service for Jakariya AI Studio with Google Firebase Cloud Integration.

Handles user signup, login, PBKDF2 password hashing, session tokens,
Google Firebase Auth REST synchronization, and 3-day trial tracking.
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

import requests

logger = logging.getLogger(__name__)

DEFAULT_FIREBASE_API_KEY = "AIzaSyDv4Grk04gibHc9423juW1TdDWXbuuYokQ"
DEFAULT_FIREBASE_PROJECT_ID = "jakariya-ai-studio"


def _get_auth_dir() -> Path:
    """Return secure writable storage for user auth data."""
    local_app_data = os.getenv("LOCALAPPDATA")
    base = Path(local_app_data) if local_app_data else Path.home() / ".jakariya_ai_studio"
    auth_dir = base / "Jakariya AI Studio"
    auth_dir.mkdir(parents=True, exist_ok=True)
    return auth_dir


def _load_firebase_config() -> Tuple[str, str]:
    """Load Firebase API key and project ID from config or bundled fallback."""
    cfg_path = Path("config/firebase_config.json")
    if cfg_path.exists():
        try:
            data = json.loads(cfg_path.read_text(encoding="utf-8"))
            return data.get("apiKey", DEFAULT_FIREBASE_API_KEY), data.get("projectId", DEFAULT_FIREBASE_PROJECT_ID)
        except Exception:
            pass
    return DEFAULT_FIREBASE_API_KEY, DEFAULT_FIREBASE_PROJECT_ID


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
    if not stored_hash or not salt_hex:
        return False
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
    firebase_uid: str = ""


class AuthService:
    """Manages user registration, sign in, trial tracking, Firebase Cloud sync, and persistent sessions."""

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
            # Background cloud check for Pro update
            self.sync_with_cloud()

    def signup(self, email: str, password: str, name: str = "") -> Tuple[bool, str]:
        """Register a new user account with Firebase Auth and 3-Day Pro Trial."""
        clean_email = email.strip().lower()
        if not clean_email or "@" not in clean_email or "." not in clean_email:
            return False, "অনুগ্রহ করে একটি সঠিক ইমেইল অ্যাড্রেস লিখুন।"

        if len(password) < 6:
            return False, "পাসওয়ার্ড কমপক্ষে ৬ অক্ষরের হতে হবে।"

        db = self._read_users_db()
        users = db.get("users", {})

        # Check existing user in local DB
        for uid, u in users.items():
            if u.get("email", "").lower() == clean_email:
                return False, "এই ইমেইলটি দিয়ে ইতোমধ্যে অ্যাকাউন্ট তৈরি করা হয়েছে। লগইন করুন।"

        display_name = name.strip() or clean_email.split("@")[0].capitalize()
        api_key, project_id = _load_firebase_config()
        fb_uid = ""
        fb_token = ""

        # Attempt Firebase Auth Cloud Registration
        if api_key:
            try:
                url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={api_key}"
                resp = requests.post(
                    url,
                    json={"email": clean_email, "password": password, "returnSecureToken": True},
                    timeout=6,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    fb_uid = data.get("localId", "")
                    fb_token = data.get("idToken", "")
                    # Update Display Name in Firebase
                    if fb_token and display_name:
                        up_url = f"https://identitytoolkit.googleapis.com/v1/accounts:update?key={api_key}"
                        requests.post(
                            up_url,
                            json={"idToken": fb_token, "displayName": display_name, "returnSecureToken": True},
                            timeout=4,
                        )
                    logger.info("[AuthService] Firebase cloud registration successful: %s (UID: %s)", clean_email, fb_uid)
                else:
                    err_msg = resp.json().get("error", {}).get("message", "")
                    if "EMAIL_EXISTS" in err_msg:
                        return False, "এই ইমেইলটি দিয়ে ইতোমধ্যে অ্যাকাউন্ট তৈরি করা হয়েছে। লগইন করুন।"
                    elif "WEAK_PASSWORD" in err_msg:
                        return False, "পাসওয়ার্ডটি খুব সহজ। একটু শক্তিশালী পাসওয়ার্ড দিন।"
            except Exception as exc:
                logger.info("[AuthService] Firebase offline/unreachable (%s), proceeding with local registration.", exc)

        now_iso = datetime.now(timezone.utc).isoformat()
        pwd_hash, salt_hex = _hash_password(password)
        user_id = fb_uid or f"usr_{secrets.token_hex(8)}"
        session_token = fb_token or f"tok_{secrets.token_urlsafe(32)}"

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
            firebase_uid=fb_uid,
        )

        users[user_id] = asdict(profile)
        db["users"] = users
        db["active_user_id"] = user_id
        self._write_users_db(db)

        self._current_user = profile
        logger.info("[AuthService] User registered successfully: %s (Trial Started)", clean_email)
        return True, "সাইন-আপ সফল হয়েছে! আপনার ৩ দিনের সম্পূর্ণ ফ্রি প্রিমিয়াম ট্রায়াল শুরু হয়েছে।"

    def login(self, email: str, password: str) -> Tuple[bool, str]:
        """Sign in an existing user with Firebase Auth and fallback to local store."""
        clean_email = email.strip().lower()
        if not clean_email:
            return False, "ইমেইল প্রদান করা আবশ্যক।"

        api_key, project_id = _load_firebase_config()
        fb_uid = ""
        fb_token = ""
        fb_display_name = ""
        firebase_success = False

        # Attempt Firebase Auth Cloud Sign-in
        if api_key:
            try:
                url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"
                resp = requests.post(
                    url,
                    json={"email": clean_email, "password": password, "returnSecureToken": True},
                    timeout=6,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    fb_uid = data.get("localId", "")
                    fb_token = data.get("idToken", "")
                    fb_display_name = data.get("displayName", "")
                    firebase_success = True
                    logger.info("[AuthService] Firebase cloud sign-in successful: %s (UID: %s)", clean_email, fb_uid)
                else:
                    err_msg = resp.json().get("error", {}).get("message", "")
                    if "EMAIL_NOT_FOUND" in err_msg:
                        return False, "এই ইমেইলে কোনো অ্যাকাউন্ট পাওয়া যায়নি। অনুগ্রহ করে সাইন-আপ করুন।"
                    elif "INVALID_PASSWORD" in err_msg or "INVALID_LOGIN_CREDENTIALS" in err_msg:
                        return False, "ভুল পাসওয়ার্ড। আবার চেষ্টা করুন।"
                    elif "USER_DISABLED" in err_msg:
                        return False, "এই অ্যাকাউন্টটি সাময়িকভাবে বন্ধ রাখা হয়েছে।"
            except Exception as exc:
                logger.info("[AuthService] Firebase offline/unreachable (%s), checking local credentials.", exc)

        db = self._read_users_db()
        users = db.get("users", {})

        target_user = None
        for uid, u in users.items():
            if u.get("email", "").lower() == clean_email or (fb_uid and uid == fb_uid):
                target_user = u
                break

        if firebase_success:
            # Successfully authenticated via Firebase Cloud!
            now_iso = datetime.now(timezone.utc).isoformat()
            if target_user:
                target_user["session_token"] = fb_token
                if fb_uid:
                    target_user["firebase_uid"] = fb_uid
                if fb_display_name:
                    target_user["name"] = fb_display_name
                db["users"][target_user["user_id"]] = target_user
                self._current_user = UserProfile(**target_user)
            else:
                # First time on this PC with existing Firebase account
                pwd_hash, salt_hex = _hash_password(password)
                profile = UserProfile(
                    user_id=fb_uid,
                    email=clean_email,
                    name=fb_display_name or clean_email.split("@")[0].capitalize(),
                    password_hash=pwd_hash,
                    salt=salt_hex,
                    created_at=now_iso,
                    trial_start_date=now_iso,
                    is_premium=False,
                    session_token=fb_token,
                    firebase_uid=fb_uid,
                )
                users[fb_uid] = asdict(profile)
                db["users"] = users
                self._current_user = profile

            db["active_user_id"] = self._current_user.user_id
            self._write_users_db(db)
            self.sync_with_cloud(fb_token)
            return True, "লগইন সফল হয়েছে!"

        # Fallback to local authentication (when offline)
        if not target_user:
            return False, "এই ইমেইলে কোনো অ্যাকাউন্ট পাওয়া যায়নি। অনুগ্রহ করে সাইন-আপ করুন।"

        if not _verify_password(password, target_user.get("password_hash", ""), target_user.get("salt", "")):
            return False, "ভুল পাসওয়ার্ড। আবার চেষ্টা করুন।"

        # Refresh local session token
        session_token = f"tok_{secrets.token_urlsafe(32)}"
        target_user["session_token"] = session_token
        db["users"][target_user["user_id"]] = target_user
        db["active_user_id"] = target_user["user_id"]
        self._write_users_db(db)

        self._current_user = UserProfile(**target_user)
        logger.info("[AuthService] Local user logged in: %s", clean_email)
        return True, "লগইন সফল হয়েছে!"

    def sync_with_cloud(self, token: str = "") -> None:
        """Sync user's Pro status from Cloud Firestore if enabled."""
        if not self._current_user:
            return
        api_key, project_id = _load_firebase_config()
        uid = self._current_user.firebase_uid or self._current_user.user_id
        tok = token or self._current_user.session_token
        if not tok or not project_id:
            return
        try:
            url = f"https://firestore.googleapis.com/v1/projects/{project_id}/databases/(default)/documents/users/{uid}"
            headers = {"Authorization": f"Bearer {tok}"}
            resp = requests.get(url, headers=headers, timeout=4)
            if resp.status_code == 200:
                fields = resp.json().get("fields", {})
                is_prem = fields.get("is_premium", {}).get("booleanValue", False)
                exp_date = fields.get("premium_expires_at", {}).get("stringValue", "")
                if is_prem:
                    self.update_profile(is_premium=True, premium_expires_at=exp_date)
                    logger.info("[AuthService] Synced Pro status from Firebase Cloud: True")
        except Exception:
            pass

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

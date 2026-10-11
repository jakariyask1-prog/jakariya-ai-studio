"""Comprehensive Unit Tests for User Authentication and 3-Day Trial / Freemium System."""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pytest

from app.auth.auth_service import AuthService, _hash_password, _verify_password
from app.licensing.license_manager import LicenseManager, TRIAL_DURATION_HOURS, FREE_FEATURES, PREMIUM_FEATURES


@pytest.fixture
def isolated_auth_and_license(tmp_path: Path):
    """Provide isolated file paths and reset singleton instances."""
    AuthService.reset_instance()
    LicenseManager.reset_instance()

    auth_file = tmp_path / "user_auth.json"
    license_file = tmp_path / "license_state.json"

    auth_svc = AuthService(data_path=auth_file)
    lic_mgr = LicenseManager(state_file=license_file)

    # Monkeypatch singletons to use the isolated instances
    AuthService._instance = auth_svc
    LicenseManager._instance = lic_mgr
    lic_mgr._auth = auth_svc

    yield auth_svc, lic_mgr

    AuthService.reset_instance()
    LicenseManager.reset_instance()


def test_password_hashing_and_verification():
    pwd = "SecureSecretPassword123!"
    hash_hex, salt_hex = _hash_password(pwd)

    assert hash_hex != pwd
    assert len(salt_hex) == 32  # 16 bytes hex
    assert _verify_password(pwd, hash_hex, salt_hex) is True
    assert _verify_password("WrongPassword", hash_hex, salt_hex) is False


def test_user_signup_and_login_flow(isolated_auth_and_license):
    auth_svc, _ = isolated_auth_and_license

    # Validation errors
    ok, err = auth_svc.signup("invalidemail", "123456")
    assert ok is False
    assert "সঠিক ইমেইল" in err

    ok, err = auth_svc.signup("test@example.com", "123")
    assert ok is False
    assert "৬ অক্ষর" in err

    # Successful signup
    ok, msg = auth_svc.signup("jakariya@studio.ai", "Password@123", name="Jakariya")
    assert ok is True
    assert "সফল" in msg
    assert auth_svc.is_logged_in is True
    assert auth_svc.current_user.email == "jakariya@studio.ai"
    assert auth_svc.current_user.name == "Jakariya"
    assert auth_svc.current_user.trial_start_date != ""

    # Duplicate signup prevented
    ok, err = auth_svc.signup("jakariya@studio.ai", "OtherPassword")
    assert ok is False
    assert "ইতোমধ্যে" in err

    # Logout
    auth_svc.logout()
    assert auth_svc.is_logged_in is False
    assert auth_svc.current_user is None

    # Failed login with wrong password
    ok, err = auth_svc.login("jakariya@studio.ai", "WrongPass123")
    assert ok is False
    assert "ভুল পাসওয়ার্ড" in err

    # Successful login
    ok, msg = auth_svc.login("jakariya@studio.ai", "Password@123")
    assert ok is True
    assert auth_svc.is_logged_in is True
    assert auth_svc.current_user.email == "jakariya@studio.ai"


def test_session_restoration(isolated_auth_and_license, tmp_path: Path):
    auth_svc, _ = isolated_auth_and_license
    auth_svc.signup("persisted@example.com", "MySecretPassword", name="Persisted User")
    assert auth_svc.is_logged_in is True

    # Create a fresh AuthService instance pointing to the same file
    fresh_svc = AuthService(data_path=auth_svc._data_path)
    assert fresh_svc.is_logged_in is True
    assert fresh_svc.current_user.email == "persisted@example.com"
    assert fresh_svc.current_user.name == "Persisted User"


def test_three_day_free_trial_all_facilities_unlocked(isolated_auth_and_license):
    auth_svc, lic_mgr = isolated_auth_and_license

    # Signup starts a 3-day trial
    auth_svc.signup("trial_user@example.com", "SecretTrial123")

    status = lic_mgr.get_plan_status()
    assert status["tier"] == "trial"
    assert status["is_premium"] is False
    assert status["days_left"] >= 2
    assert "⚡ Pro Trial:" in status["badge"]

    # In 3-day trial: ALL facilities are 100% allowed!
    for feat in FREE_FEATURES:
        assert lic_mgr.is_feature_allowed(feat) is True, f"Feature {feat} should be allowed"

    for feat in PREMIUM_FEATURES:
        assert lic_mgr.is_feature_allowed(feat) is True, f"Premium feature {feat} must be allowed during trial"


def test_trial_expiry_falls_back_to_free_version(isolated_auth_and_license):
    auth_svc, lic_mgr = isolated_auth_and_license

    auth_svc.signup("expired_user@example.com", "ExpiredPass123")

    # Fast forward trial start date to 4 days ago (beyond 72 hours)
    four_days_ago = datetime.now(timezone.utc) - timedelta(days=4)
    auth_svc.update_profile(trial_start_date=four_days_ago.isoformat())
    lic_mgr._device_trial_start = four_days_ago

    status = lic_mgr.get_plan_status()
    assert status["tier"] == "free"
    assert status["hours_left"] == 0
    assert status["days_left"] == 0
    assert status["badge"] == "🆓 Free Plan"

    # Free features remain allowed forever
    assert lic_mgr.is_feature_allowed("free_chat") is True
    assert lic_mgr.is_feature_allowed("ollama") is True
    assert lic_mgr.is_feature_allowed("edge_tts") is True
    assert lic_mgr.is_feature_allowed("google_stt") is True
    assert lic_mgr.is_feature_allowed("markdown_export") is True
    assert lic_mgr.is_feature_allowed("txt_export") is True

    # Premium facilities are locked for expired free users
    assert lic_mgr.is_feature_allowed("cartesia_voice") is False
    assert lic_mgr.is_feature_allowed("elevenlabs") is False
    assert lic_mgr.is_feature_allowed("flux_image") is False
    assert lic_mgr.is_feature_allowed("unlimited_agent") is False
    assert lic_mgr.is_feature_allowed("styled_pdf_export") is False
    assert lic_mgr.is_feature_allowed("docx_export") is False
    assert lic_mgr.is_feature_allowed("excel_export") is False


def test_license_key_activation_unlocks_pro_permanently(isolated_auth_and_license):
    auth_svc, lic_mgr = isolated_auth_and_license

    auth_svc.signup("pro_candidate@example.com", "ProCandidatePass123")

    # Expire trial first
    four_days_ago = datetime.now(timezone.utc) - timedelta(days=4)
    auth_svc.update_profile(trial_start_date=four_days_ago.isoformat())
    lic_mgr._device_trial_start = four_days_ago
    assert lic_mgr.get_plan_status()["tier"] == "free"

    # Attempt invalid key
    ok, err = lic_mgr.activate_license_key("INVALID-KEY-123")
    assert ok is False
    assert "ব্যর্থ" in err or "অকার্যকর" in err

    # Activate valid 1-year Pro key
    ok, msg = lic_mgr.activate_license_key("JAK-PRO-2026-X89B-VALID")
    assert ok is True
    assert "অভিনন্দন" in msg
    assert "১ বছরের" in msg

    status = lic_mgr.get_plan_status()
    assert status["tier"] == "premium"
    assert status["is_premium"] is True
    assert "👑 Pro Member" in status["badge"]

    # All premium features are now permanently/subscription unlocked!
    for feat in PREMIUM_FEATURES:
        assert lic_mgr.is_feature_allowed(feat) is True


def test_lifetime_license_key_activation(isolated_auth_and_license):
    auth_svc, lic_mgr = isolated_auth_and_license

    auth_svc.signup("lifetime_user@example.com", "Lifetime123456")

    # Activate lifetime key
    ok, msg = lic_mgr.activate_license_key("JAK-VIP-LIFETIME-PREMIUM-KEY")
    assert ok is True
    assert "আজীবন" in msg

    status = lic_mgr.get_plan_status()
    assert status["tier"] == "premium"
    assert status["label"] == "Pro Lifetime"
    assert status["badge"] == "👑 Pro Member"
    assert lic_mgr.is_feature_allowed("cartesia_voice") is True
    assert lic_mgr.is_feature_allowed("styled_pdf_export") is True

"""Secure API Key storage using Windows Credential Manager via keyring library.

Falls back gracefully to plaintext JSON storage if keyring is unavailable,
ensuring the application always works even without keyring installed.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_KEYRING_SERVICE = "JakariyaAIStudio"
_KEYRING_AVAILABLE: bool | None = None  # None = not yet checked


def _is_keyring_available() -> bool:
    """Check once whether the keyring library is importable and functional."""
    global _KEYRING_AVAILABLE
    if _KEYRING_AVAILABLE is None:
        try:
            import keyring  # noqa: F401
            _KEYRING_AVAILABLE = True
        except ImportError:
            logger.warning(
                "[KeyVault] 'keyring' package not found. "
                "API keys will be stored in plaintext JSON. "
                "Run: pip install keyring"
            )
            _KEYRING_AVAILABLE = False
    return _KEYRING_AVAILABLE


def store_api_key(provider_id: str, api_key: str) -> bool:
    """Store an API key securely in Windows Credential Manager.

    Parameters
    ----------
    provider_id : str
        The provider identifier (e.g. 'google_ai_studio', 'openrouter').
    api_key : str
        The plaintext API key to encrypt and store.

    Returns
    -------
    bool
        True if stored successfully via keyring, False otherwise.
    """
    if not api_key or not api_key.strip():
        return False

    if not _is_keyring_available():
        return False

    try:
        import keyring
        keyring.set_password(_KEYRING_SERVICE, provider_id, api_key.strip())
        logger.debug("[KeyVault] API key stored securely for provider: %s", provider_id)
        return True
    except Exception as exc:
        logger.warning("[KeyVault] Failed to store key for %s: %s", provider_id, exc)
        return False


def retrieve_api_key(provider_id: str) -> str:
    """Retrieve an API key from Windows Credential Manager.

    Parameters
    ----------
    provider_id : str
        The provider identifier.

    Returns
    -------
    str
        The stored API key, or empty string if not found.
    """
    if not _is_keyring_available():
        return ""

    try:
        import keyring
        value = keyring.get_password(_KEYRING_SERVICE, provider_id)
        return (value or "").strip()
    except Exception as exc:
        logger.warning("[KeyVault] Failed to retrieve key for %s: %s", provider_id, exc)
        return ""


def delete_api_key(provider_id: str) -> bool:
    """Delete a stored API key from Windows Credential Manager.

    Parameters
    ----------
    provider_id : str
        The provider identifier.

    Returns
    -------
    bool
        True if deleted successfully.
    """
    if not _is_keyring_available():
        return False

    try:
        import keyring
        keyring.delete_password(_KEYRING_SERVICE, provider_id)
        logger.debug("[KeyVault] API key deleted for provider: %s", provider_id)
        return True
    except Exception:
        return False


def migrate_plaintext_keys_to_vault(providers_dict: dict) -> dict:
    """One-time migration: move plaintext api_key values from JSON into keyring.

    For each provider that has a non-empty api_key in the dict, this stores
    it in the vault and replaces the plaintext value with a sentinel marker
    '__keyring__' so we know the key lives in the vault.

    Parameters
    ----------
    providers_dict : dict
        The raw providers section from user_settings.json.

    Returns
    -------
    dict
        Updated providers dict with api_key fields scrubbed to '__keyring__'.
    """
    if not _is_keyring_available():
        return providers_dict

    updated = {}
    for p_id, conf in providers_dict.items():
        if isinstance(conf, dict):
            conf = dict(conf)  # shallow copy
            key_val = conf.get("api_key", "")
            if key_val and key_val not in ("", "__keyring__"):
                stored = store_api_key(p_id, key_val)
                if stored:
                    conf["api_key"] = "__keyring__"
                    logger.info("[KeyVault] Migrated key for %s to Credential Manager.", p_id)
            updated[p_id] = conf
        else:
            updated[p_id] = conf
    return updated

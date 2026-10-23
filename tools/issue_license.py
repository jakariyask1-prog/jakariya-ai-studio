"""Issue a signed, account-bound Jakariya AI Studio offline license.

Run this only on the publisher's Windows account, where the private signing
key is stored in Windows Credential Manager. The application never contains
or needs this private key.
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone

import keyring
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


KEYRING_SERVICE = "JakariyaAIStudioLicenseIssuer"
KEYRING_USERNAME = "ed25519_private_key_b64"
TOKEN_PREFIX = "JAK-LIC-"


def _encode_token_part(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def main() -> int:
    parser = argparse.ArgumentParser(description="Issue a signed Jakariya AI Studio license.")
    parser.add_argument("--email", required=True, help="Customer account email address")
    parser.add_argument("--plan", choices=("pro", "vip"), default="pro")
    parser.add_argument("--days", type=int, default=365, help="License duration; ignored for --lifetime")
    parser.add_argument("--lifetime", action="store_true", help="Issue a lifetime license")
    args = parser.parse_args()

    if not args.lifetime and args.days <= 0:
        parser.error("--days must be a positive number")

    private_key_b64 = keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)
    if not private_key_b64:
        print("Signing key not found in Windows Credential Manager.", file=sys.stderr)
        return 1

    try:
        private_key = Ed25519PrivateKey.from_private_bytes(base64.b64decode(private_key_b64))
    except (ValueError, TypeError):
        print("Stored signing key is invalid.", file=sys.stderr)
        return 1

    now = datetime.now(timezone.utc)
    payload = {
        "license_id": str(uuid.uuid4()),
        "email": args.email.strip().lower(),
        "plan": args.plan,
        "issued_at": now.isoformat(),
        "expires_at": None if args.lifetime else (now + timedelta(days=args.days)).isoformat(),
    }
    payload_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    signature = private_key.sign(payload_bytes)
    print(TOKEN_PREFIX + _encode_token_part(payload_bytes) + "." + _encode_token_part(signature))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

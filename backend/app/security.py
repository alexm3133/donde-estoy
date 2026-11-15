"""Tokens: unguessable, URL-safe, and stored only as hashes."""

from __future__ import annotations

import hashlib
import hmac
import secrets


def new_token() -> str:
    """128 bits of randomness, 22 URL-safe characters (WhatsApp-friendly)."""
    return secrets.token_urlsafe(16)


def hash_token(token: str) -> str:
    """SHA-256 is enough here: tokens are high-entropy, not human passwords."""
    return hashlib.sha256(token.encode()).hexdigest()


def token_matches(token: str, expected_hash: str) -> bool:
    return hmac.compare_digest(hash_token(token), expected_hash)

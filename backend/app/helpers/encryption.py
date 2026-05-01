"""Symmetric encryption for sensitive data stored in the DB.

Used by :mod:`app.models.llm_config` to keep LLM provider API keys encrypted
at rest. The key is read from the ``LLM_ENCRYPTION_KEY`` env var (base64-
encoded 32 bytes, i.e. a Fernet key). If absent, a key is deterministically
derived from ``JWT_SECRET_KEY`` so existing deployments do not need to change
their configuration. Operators are advised to set ``LLM_ENCRYPTION_KEY``
explicitly: rotating the JWT secret would otherwise make stored keys
unreadable.
"""

from __future__ import annotations

import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_secret


_logger = logging.getLogger(__name__)
_fernet: Fernet | None = None


def _derive_key_from(secret: str) -> bytes:
    """Derive a Fernet-compatible 32-byte url-safe base64 key from ``secret``."""
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is not None:
        return _fernet

    explicit = get_secret("LLM_ENCRYPTION_KEY")
    if explicit:
        try:
            _fernet = Fernet(explicit.encode("utf-8") if isinstance(explicit, str) else explicit)
            return _fernet
        except Exception as exc:
            raise RuntimeError(
                "LLM_ENCRYPTION_KEY is not a valid Fernet key (32 url-safe base64 bytes)."
            ) from exc

    jwt_secret = get_secret("JWT_SECRET_KEY", "super-secret") or "super-secret"
    if jwt_secret == "super-secret":
        _logger.warning(
            "LLM_ENCRYPTION_KEY is not set and JWT_SECRET_KEY uses the default "
            "'super-secret'. LLM API keys will be encrypted with a derived key, "
            "but you should set LLM_ENCRYPTION_KEY (or a strong JWT_SECRET_KEY) "
            "for production use."
        )
    _fernet = Fernet(_derive_key_from(jwt_secret))
    return _fernet


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a secret string and return a url-safe base64 token."""
    if plaintext is None:
        raise ValueError("plaintext must not be None")
    return _get_fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_secret(token: str) -> str:
    """Decrypt a token previously produced by :func:`encrypt_secret`."""
    if token is None:
        raise ValueError("token must not be None")
    try:
        return _get_fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Stored secret is unreadable (wrong encryption key?)") from exc


def reset_for_tests() -> None:
    """Forget the cached Fernet instance so a new key is read. Tests only."""
    global _fernet
    _fernet = None


# Re-export for callers that prefer importing through this module
__all__ = [
    "encrypt_secret",
    "decrypt_secret",
    "reset_for_tests",
]

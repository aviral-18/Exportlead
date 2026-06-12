"""Tests for settings / config validation.

Verifies that:
- Production environment with the default insecure secret_key raises ValueError
- Development environment with the default key is allowed
- A custom key in production is accepted
"""
from __future__ import annotations

import pytest

_DEFAULT_KEY = "change_me_in_production_use_openssl_rand_hex_32"


def test_production_with_default_key_raises():
    """Starting the app in production with the default SECRET_KEY must fail."""
    from pydantic import ValidationError
    from src.core.config import Settings

    with pytest.raises((ValidationError, ValueError)):
        Settings(
            environment="production",
            secret_key=_DEFAULT_KEY,
            database_url="postgresql+asyncpg://u:p@localhost/db",
        )


def test_development_with_default_key_is_allowed():
    """Development mode is allowed to keep the default key (for local dev)."""
    from src.core.config import Settings

    s = Settings(
        environment="development",
        secret_key=_DEFAULT_KEY,
        database_url="postgresql+asyncpg://u:p@localhost/db",
    )
    assert s.environment == "development"


def test_production_with_strong_key_is_allowed():
    """Production + a real key must not raise."""
    import secrets as _secrets
    from src.core.config import Settings

    strong_key = _secrets.token_hex(32)
    s = Settings(
        environment="production",
        secret_key=strong_key,
        database_url="postgresql+asyncpg://u:p@localhost/db",
    )
    assert s.secret_key == strong_key

"""Tests for pydantic-settings configuration."""
import pytest
from pydantic import ValidationError


def test_settings_defaults():
    """Settings class has sensible defaults without any env vars."""
    from main import Settings

    s = Settings()
    assert s.app_name == "FastAPI Starter"
    assert s.debug is False
    assert s.secret_key == "change-me-in-production-not-for-real-use"
    assert "http://localhost:3000" in s.allowed_origins


def test_settings_env_override(monkeypatch):
    """Settings values can be overridden via environment variables."""
    monkeypatch.setenv("APP_NAME", "My Custom App")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("ALLOWED_ORIGINS", '["http://example.com"]')

    from importlib import reload
    import main as main_module

    reload(main_module)
    s = main_module.Settings()
    assert s.app_name == "My Custom App"
    assert s.debug is True
    assert "http://example.com" in s.allowed_origins


def test_cors_uses_settings_not_wildcard():
    """CORS middleware uses allowed_origins from settings, not a hardcoded wildcard."""
    from main import settings

    assert settings.allowed_origins != ["*"], (
        "CORS allowed_origins should not be ["*"] — wildcard requires explicit opt-in"
    )


def test_app_debug_matches_settings():
    """FastAPI app debug flag matches settings.debug."""
    from main import app, settings

    assert app.debug == settings.debug


def test_get_settings_returns_settings_instance():
    """get_settings() returns a Settings instance and is cached."""
    from main import get_settings, Settings

    s1 = get_settings()
    s2 = get_settings()
    assert isinstance(s1, Settings)
    assert s1 is s2  # lru_cache returns same instance


def test_info_route_uses_settings():
    """GET /info returns app_name and debug from settings."""
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)
    response = client.get("/info")
    assert response.status_code == 200
    data = response.json()
    assert "app_name" in data
    assert "debug" in data
    assert data["app_name"] == "FastAPI Starter"
    assert data["debug"] is False


def test_secret_key_too_short_raises_validation_error(monkeypatch):
    """Settings raises ValidationError when SECRET_KEY is shorter than 32 characters."""
    monkeypatch.setenv("SECRET_KEY", "tooshort")

    from main import Settings

    with pytest.raises(ValidationError) as exc_info:
        Settings()

    error_messages = str(exc_info.value)
    assert "SECRET_KEY must be at least 32 characters" in error_messages


def test_secret_key_exactly_32_chars_is_valid(monkeypatch):
    """SECRET_KEY of exactly 32 characters with sufficient entropy passes validation."""
    monkeypatch.setenv("SECRET_KEY", "abcdef0123456789abcdef0123456789")

    from main import Settings

    s = Settings()
    assert len(s.secret_key) == 32


def test_secret_key_longer_than_32_chars_is_valid(monkeypatch):
    """SECRET_KEY longer than 32 characters with sufficient entropy passes validation."""
    monkeypatch.setenv("SECRET_KEY", "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789")

    from main import Settings

    s = Settings()
    assert len(s.secret_key) == 64


def test_secret_key_low_entropy_all_same_char_raises_validation_error(monkeypatch):
    """Settings raises ValidationError when SECRET_KEY is 32 repeated characters (zero entropy)."""
    monkeypatch.setenv("SECRET_KEY", "a" * 32)

    from main import Settings

    with pytest.raises(ValidationError) as exc_info:
        Settings()

    error_messages = str(exc_info.value)
    assert "entropy too low" in error_messages
    assert "secrets.token_hex" in error_messages


def test_secret_key_low_entropy_short_repeat_raises_validation_error(monkeypatch):
    """Settings raises ValidationError when SECRET_KEY is a short repeating pattern."""
    monkeypatch.setenv("SECRET_KEY", "abcdabcdabcdabcdabcdabcdabcdabcd")

    from main import Settings

    with pytest.raises(ValidationError) as exc_info:
        Settings()

    assert "entropy too low" in str(exc_info.value)


def test_secret_key_high_entropy_hex_is_valid(monkeypatch):
    """A randomly-generated hex token passes both length and entropy validation."""
    import secrets
    monkeypatch.setenv("SECRET_KEY", secrets.token_hex(32))

    from main import Settings

    s = Settings()
    assert len(s.secret_key) == 64  # token_hex(32) produces 64 hex chars


async def test_lifespan_warns_on_default_secret_key_in_production(monkeypatch, caplog):
    """Lifespan emits a WARNING when SECRET_KEY is the default value and DEBUG is false."""
    import logging
    from importlib import reload
    import main as main_module

    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("SECRET_KEY", "change-me-in-production-not-for-real-use")
    reload(main_module)

    with caplog.at_level(logging.WARNING):
        async with main_module.lifespan(main_module.app):
            pass

    assert any(
        "SECRET_KEY is set to the publicly known default value" in record.message
        for record in caplog.records
        if record.levelno == logging.WARNING
    )


async def test_lifespan_no_warning_on_default_secret_key_in_debug(monkeypatch, caplog):
    """Lifespan does NOT warn about default SECRET_KEY when DEBUG is true."""
    import logging
    from importlib import reload
    import main as main_module

    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("SECRET_KEY", "change-me-in-production-not-for-real-use")
    reload(main_module)

    with caplog.at_level(logging.WARNING):
        async with main_module.lifespan(main_module.app):
            pass

    assert not any(
        "SECRET_KEY is set to the publicly known default value" in record.message
        for record in caplog.records
    )


async def test_lifespan_no_warning_on_custom_secret_key(monkeypatch, caplog):
    """Lifespan does NOT warn about SECRET_KEY when a custom key is configured."""
    import logging
    import secrets
    from importlib import reload
    import main as main_module

    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("SECRET_KEY", secrets.token_hex(32))
    reload(main_module)

    with caplog.at_level(logging.WARNING):
        async with main_module.lifespan(main_module.app):
            pass

    assert not any(
        "SECRET_KEY is set to the publicly known default value" in record.message
        for record in caplog.records
    )


async def test_lifespan_warns_when_allowed_hosts_wildcard_in_production(caplog):
    """Lifespan emits SECURITY WARNING when ALLOWED_HOSTS is ['*'] in production."""
    import logging
    from unittest.mock import patch
    import main as main_module
    from main import lifespan

    with patch.object(main_module.settings, 'debug', False), \
         patch.object(main_module.settings, 'allowed_hosts', ['*']):
        with caplog.at_level(logging.WARNING):
            async with lifespan(main_module.app):
                pass
    assert any("ALLOWED_HOSTS" in r.message for r in caplog.records)

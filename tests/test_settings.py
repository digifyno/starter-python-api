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
    """SECRET_KEY of exactly 32 characters passes validation."""
    monkeypatch.setenv("SECRET_KEY", "a" * 32)

    from main import Settings

    s = Settings()
    assert len(s.secret_key) == 32


def test_secret_key_longer_than_32_chars_is_valid(monkeypatch):
    """SECRET_KEY longer than 32 characters passes validation."""
    monkeypatch.setenv("SECRET_KEY", "a" * 64)

    from main import Settings

    s = Settings()
    assert len(s.secret_key) == 64

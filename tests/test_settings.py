"""Tests for pydantic-settings configuration."""


def test_settings_defaults():
    """Settings class has sensible defaults without any env vars."""
    from main import Settings

    s = Settings()
    assert s.app_name == "FastAPI Starter"
    assert s.debug is False
    assert s.secret_key == "change-me-in-production"
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
        "CORS allowed_origins should not be ['*'] — use settings"
    )


def test_app_debug_matches_settings():
    """FastAPI app debug flag matches settings.debug."""
    from main import app, settings

    assert app.debug == settings.debug

from app.config import Settings


def test_settings_loads_from_env():
    settings = Settings()
    assert settings.port == 8000
    assert "asyncpg" in settings.database_url

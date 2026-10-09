import pytest

from app.config import Config


def test_broadcast_hour_minute_valid(monkeypatch):
    monkeypatch.setattr(Config, "BROADCAST_TIME", "08:30")
    assert Config.get_broadcast_hour_minute() == (8, 30)


def test_broadcast_hour_minute_fallback(monkeypatch):
    monkeypatch.setattr(Config, "BROADCAST_TIME", "invalid")
    assert Config.get_broadcast_hour_minute() == (7, 0)


def test_config_validate_missing_token(monkeypatch):
    monkeypatch.setattr(Config, "BOT_TOKEN", "")
    with pytest.raises(ValueError, match="BOT_TOKEN не задан"):
        Config.validate()


def test_config_validate_valid(monkeypatch):
    monkeypatch.setattr(Config, "BOT_TOKEN", "123456:ABC-DEF")
    Config.validate()

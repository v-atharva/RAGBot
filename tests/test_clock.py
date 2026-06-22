from datetime import datetime, timezone

from ragbot import clock


def test_mock_now_override(monkeypatch):
    monkeypatch.setenv("MOCK_NOW", "2026-07-15T09:00:00")
    assert clock.now() == datetime(2026, 7, 15, 9, 0, tzinfo=timezone.utc)


def test_real_now_when_unset(monkeypatch):
    monkeypatch.delenv("MOCK_NOW", raising=False)
    before = datetime.now(timezone.utc)
    assert clock.now() >= before

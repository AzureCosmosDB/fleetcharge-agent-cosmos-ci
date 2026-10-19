import pytest

from app.settings import Settings


@pytest.mark.parametrize("endpoint", ["https://example.com", "http://127.0.0.1.evil", "file:///x"])
def test_rejects_non_loopback_endpoints(endpoint):
    with pytest.raises(ValueError):
        Settings(endpoint=endpoint)


def test_rejects_live_mode():
    with pytest.raises(ValueError):
        Settings(mode="live")


def test_rejects_naive_clock():
    with pytest.raises(ValueError):
        Settings(review_at="2026-10-19T12:30:00")


def test_cleanup_requires_owned_database_name():
    with pytest.raises(ValueError):
        Settings(database="production")

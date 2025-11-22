"""Tests for dynamic database configuration."""

from __future__ import annotations

from infrastructure import database as db


def test_configure_database_overrides_url(tmp_path):
    custom_url = f"sqlite:///{tmp_path}/test.db"

    db.configure_database(custom_url, echo=False)

    assert db.DATABASE_URL == custom_url
    assert str(db.engine.url) == custom_url

    session = db.SessionLocal()
    try:
        assert str(session.bind.url) == custom_url
    finally:
        session.close()

    # Restore default so other tests continue using original connection string
    db.configure_database(echo=False)

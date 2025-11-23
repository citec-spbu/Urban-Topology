"""Tests for database configuration safety and test DB factory."""

from __future__ import annotations

from infrastructure import database as db
import pytest


def test_configure_database_second_call_raises():
    # configure_database already called at import; second call should raise
    with pytest.raises(RuntimeError):
        db.configure_database(db.DATABASE_URL, echo=False)


def test_create_test_database_isolated(tmp_path):
    custom_url = f"sqlite:///{tmp_path}/isolated.db"
    engine, session_factory, test_db = db.create_test_database(custom_url)
    try:
        assert str(engine.url) == custom_url
        assert str(test_db.url) == custom_url if hasattr(test_db, "url") else True
        sess = session_factory()
        try:
            assert str(sess.bind.url) == custom_url
        finally:
            sess.close()
    finally:
        engine.dispose()

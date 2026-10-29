"""Fixtures for tests that need a real PostgreSQL database (skipped without TEST_DATABASE_URL)."""
import os

import pytest

URL = os.environ.get("TEST_DATABASE_URL")


@pytest.fixture()
def db():
    if not URL:
        pytest.skip("TEST_DATABASE_URL is not set")
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    import app.models  # noqa: F401
    from app.db.base import Base

    engine = create_engine(URL)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False)()
    session.execute(text(
        "INSERT INTO app_users (user_id, full_name, email, password_hash) "
        "VALUES (1, 'Demo User', 'demo@biziq.local', 'not-a-real-hash')"))
    session.execute(text("SELECT setval(pg_get_serial_sequence('app_users','user_id'), 1)"))
    session.commit()
    yield session
    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()

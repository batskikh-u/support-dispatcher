"""Общая настройка тестов.

Переменные окружения задаются ДО импорта пакета app, так как app.db создаёт
подключение к базе данных в момент импорта. Для тестов используется SQLite
во временном каталоге; рабочая система использует PostgreSQL.
"""
import os
import tempfile

_tmp_dir = tempfile.mkdtemp(prefix="support_tests_")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_dir}/test.db"
os.environ["REDIS_URL"] = "redis://localhost:6379/15"

import pytest  # noqa: E402


@pytest.fixture()
def db():
    """Чистая база данных и сессия для каждого теста."""
    from app import models  # noqa: F401  (регистрация таблиц в metadata)
    from app.db import Base, engine, SessionLocal

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        yield session

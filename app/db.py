import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://support:support_dev_password@db:5432/supportdb",
)
# SQLite (используется только в тестах) по умолчанию запрещает доступ к соединению
# из другого потока, а FastAPI выполняет обработчики в пуле потоков.
if DATABASE_URL.startswith("sqlite"):
    _connect_args = {"check_same_thread": False}
else:
    # Не ждать подключения к недоступной БД дольше 5 секунд: повторные попытки
    # в init_database и worker быстрее, чем системный тайм-аут TCP.
    _connect_args = {"connect_timeout": 5}
engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

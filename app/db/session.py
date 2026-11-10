from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import (AsyncSession, async_sessionmaker,
                                    create_async_engine)

from app.config import BASE_DIR, config
from app.db.models import Base

# Ensure SQLite directory exists if file-based SQLite is used
if "sqlite" in config.DATABASE_URL:
    db_path_str = config.DATABASE_URL.replace(
        "sqlite+aiosqlite:///", ""
    ).replace("sqlite:///", "")
    if db_path_str and not db_path_str.startswith(":memory:"):
        db_file = (
            (BASE_DIR / db_path_str).resolve()
            if not Path(db_path_str).is_absolute()
            else Path(db_path_str)
        )
        db_file.parent.mkdir(parents=True, exist_ok=True)

async_engine = create_async_engine(
    config.DATABASE_URL,
    echo=False,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


def _migrate_columns(connection) -> None:
    """Safe schema migration for existing SQLite databases."""
    inspector = inspect(connection)
    if "users" not in inspector.get_table_names():
        return
    existing_cols = {col["name"] for col in inspector.get_columns("users")}
    new_cols = {
        "city_name": "VARCHAR(100)",
        "latitude": "FLOAT",
        "longitude": "FLOAT",
        "timezone": "VARCHAR(50)",
        "state": "VARCHAR(50)",
    }
    for col_name, col_type in new_cols.items():
        if col_name not in existing_cols:
            connection.execute(
                text(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
            )


async def init_db() -> None:
    """Create all tables in the database and apply column additions."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_migrate_columns)

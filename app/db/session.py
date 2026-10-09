from pathlib import Path

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


async def init_db() -> None:
    """Create all tables in the database."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

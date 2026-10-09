import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (AsyncSession, async_sessionmaker,
                                    create_async_engine)

from app.db import crud
from app.db.models import Base


@pytest_asyncio.fixture
async def test_session(monkeypatch):
    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", echo=False
    )
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    monkeypatch.setattr(crud, "AsyncSessionLocal", session_maker)

    yield session_maker
    await test_engine.dispose()


@pytest.mark.asyncio
async def test_crud_add_and_get_user(test_session):
    user, is_new = await crud.add_or_activate_user(
        telegram_id=999,
        username="test_user",
        first_name="Tester",
    )
    assert is_new is True
    assert user.telegram_id == 999
    assert user.is_subscribed is True

    # Re-activate existing user
    user2, is_new2 = await crud.add_or_activate_user(
        telegram_id=999,
        username="new_username",
        first_name="Tester2",
    )
    assert is_new2 is False
    assert user2.username == "new_username"

    # Fetch user
    fetched = await crud.get_user(999)
    assert fetched is not None
    assert fetched.username == "new_username"


@pytest.mark.asyncio
async def test_crud_deactivate_and_subscribers(test_session):
    await crud.add_or_activate_user(telegram_id=101)
    await crud.add_or_activate_user(telegram_id=102)

    subs = await crud.get_subscribed_users()
    assert len(subs) == 2

    # Deactivate 101
    deactivated = await crud.deactivate_user(101)
    assert deactivated is True

    subs_after = await crud.get_subscribed_users()
    assert len(subs_after) == 1
    assert subs_after[0].telegram_id == 102

    # Deactivating non-existent user returns False
    assert await crud.deactivate_user(9999) is False

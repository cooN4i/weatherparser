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


@pytest.mark.asyncio
async def test_crud_set_user_city_and_state(test_session):
    await crud.add_or_activate_user(telegram_id=555)

    await crud.set_user_state(555, "waiting_city")
    user = await crud.get_user(555)
    assert user is not None
    assert user.state == "waiting_city"

    updated = await crud.set_user_city(
        telegram_id=555,
        city_name="Казань",
        latitude=55.7887,
        longitude=49.1221,
        timezone="Europe/Moscow",
    )
    assert updated is not None
    assert updated.city_name == "Казань"
    assert updated.state is None
    assert updated.timezone == "Europe/Moscow"


@pytest.mark.asyncio
async def test_crud_get_users_for_hourly_broadcast(test_session, monkeypatch):
    await crud.add_or_activate_user(telegram_id=701)
    await crud.set_user_city(
        telegram_id=701,
        city_name="Москва",
        latitude=55.75,
        longitude=37.61,
        timezone="Europe/Moscow",
    )

    # User without city should not be included
    await crud.add_or_activate_user(telegram_id=702)

    from datetime import datetime

    import pytz

    # Mock datetime.now(UTC) such that Europe/Moscow is 07:00
    # Europe/Moscow is UTC+3, so 04:00 UTC == 07:00 MSK
    mock_utc_time = datetime(2026, 10, 10, 4, 0, 0, tzinfo=pytz.UTC)

    class MockDatetime:
        @classmethod
        def now(cls, tz=None):
            return mock_utc_time

    monkeypatch.setattr(crud, "datetime", MockDatetime)

    eligible = await crud.get_users_for_hourly_broadcast(target_local_hour=7)
    assert len(eligible) == 1
    assert eligible[0].telegram_id == 701

    # At 08:00 local time, user 701 is not eligible
    not_eligible = await crud.get_users_for_hourly_broadcast(
        target_local_hour=8
    )
    assert len(not_eligible) == 0

import logging
from datetime import UTC, datetime

import pytz
from sqlalchemy import func, select

from app.db.models import User
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def add_or_activate_user(
    telegram_id: int,
    username: str | None = None,
    first_name: str | None = None,
) -> tuple[User, bool]:
    """Registers a new user or activates an existing one."""
    async with AsyncSessionLocal() as session:
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        is_new = False
        if user is None:
            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                is_subscribed=True,
            )
            session.add(user)
            is_new = True
            logger.info(
                "New user registered: %s (id=%d)",
                username or first_name,
                telegram_id,
            )
        else:
            user.username = username
            user.first_name = first_name
            user.is_subscribed = True
            user.updated_at = datetime.now(UTC)
            logger.info(
                "User re-activated: %s (id=%d)",
                username or first_name,
                telegram_id,
            )

        await session.commit()
        await session.refresh(user)
        return user, is_new


async def set_user_city(
    telegram_id: int,
    city_name: str,
    latitude: float,
    longitude: float,
    timezone: str,
) -> User | None:
    """Updates city and coordinates for a user, clearing state."""
    async with AsyncSessionLocal() as session:
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        if user is not None:
            user.city_name = city_name
            user.latitude = latitude
            user.longitude = longitude
            user.timezone = timezone
            user.state = None
            user.updated_at = datetime.now(UTC)
            await session.commit()
            await session.refresh(user)
            logger.info(
                "User %d updated city to %s (%s)",
                telegram_id,
                city_name,
                timezone,
            )
        return user


async def set_user_state(
    telegram_id: int,
    state: str | None,
) -> None:
    """Updates user conversational state (e.g. waiting_city)."""
    async with AsyncSessionLocal() as session:
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        if user is not None:
            user.state = state
            user.updated_at = datetime.now(UTC)
            await session.commit()


async def deactivate_user(telegram_id: int) -> bool:
    """Sets is_subscribed = False for the user."""
    async with AsyncSessionLocal() as session:
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if user and user.is_subscribed:
            user.is_subscribed = False
            user.updated_at = datetime.now(UTC)
            await session.commit()
            logger.info("User unsubscribed: id=%d", telegram_id)
            return True
        return False


async def get_subscribed_users() -> list[User]:
    """Returns all active subscribers."""
    async with AsyncSessionLocal() as session:
        stmt = select(User).where(User.is_subscribed.is_(True))
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def get_users_for_hourly_broadcast(
    target_local_hour: int = 7,
) -> list[User]:
    """
    Returns active subscribers whose local time matches target_local_hour.
    """
    async with AsyncSessionLocal() as session:
        stmt = select(User).where(
            User.is_subscribed.is_(True),
            User.city_name.isnot(None),
            User.latitude.isnot(None),
            User.longitude.isnot(None),
            User.timezone.isnot(None),
        )
        result = await session.execute(stmt)
        users = list(result.scalars().all())

    now_utc = datetime.now(UTC)
    eligible_users: list[User] = []

    for user in users:
        try:
            tz = pytz.timezone(user.timezone)  # type: ignore[arg-type]
            local_time = now_utc.astimezone(tz)
            if local_time.hour == target_local_hour:
                eligible_users.append(user)
        except Exception:
            continue

    return eligible_users


async def get_user(telegram_id: int) -> User | None:
    """Gets a user by telegram_id."""
    async with AsyncSessionLocal() as session:
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()


async def get_stats() -> dict[str, int]:
    """Returns count of total and active users."""
    async with AsyncSessionLocal() as session:
        total_stmt = select(func.count(User.id))
        active_stmt = select(func.count(User.id)).where(
            User.is_subscribed.is_(True)
        )

        total = (await session.execute(total_stmt)).scalar() or 0
        active = (await session.execute(active_stmt)).scalar() or 0
        return {"total": total, "active": active}

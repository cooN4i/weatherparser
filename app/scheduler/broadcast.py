import asyncio
import logging

from telebot.async_telebot import AsyncTeleBot
from telebot.asyncio_helper import ApiTelegramException

from app.db import crud
from app.db.models import User
from app.services.weather import WeatherService

logger = logging.getLogger(__name__)


async def send_daily_weather_broadcast(bot: AsyncTeleBot) -> None:
    """
    Executes hourly and delivers 07:00 local-time forecast to subscribers.
    Deduplicates requests by city to avoid rate limits (429).
    """
    logger.info("Checking users scheduled for 07:00 local-time broadcast...")

    subscribers = await crud.get_users_for_hourly_broadcast(
        target_local_hour=7
    )
    if not subscribers:
        logger.info("No subscribers scheduled for broadcast this hour.")
        return

    logger.info(
        "Found %d active subscribers at 07:00 local time. Preparing...",
        len(subscribers),
    )

    # Group users by unique location: (lat, lon, city_name, timezone)
    city_groups: dict[tuple[float, float, str, str], list[User]] = {}
    for user in subscribers:
        if (
            user.latitude is None
            or user.longitude is None
            or user.city_name is None
            or user.timezone is None
        ):
            continue
        key = (
            round(user.latitude, 2),
            round(user.longitude, 2),
            user.city_name,
            user.timezone,
        )
        city_groups.setdefault(key, []).append(user)

    sent_count = 0
    deactivated_count = 0
    error_count = 0

    for (lat, lon, city_name, tz), city_users in city_groups.items():
        try:
            forecast_message = (
                await WeatherService.get_today_forecast_message(
                    latitude=lat,
                    longitude=lon,
                    city_name=city_name,
                    timezone=tz,
                )
            )
        except Exception:
            logger.exception(
                "Failed to fetch forecast for %s (%s)", city_name, tz
            )
            error_count += len(city_users)
            continue

        for user in city_users:
            try:
                await bot.send_message(
                    chat_id=user.telegram_id,
                    text=forecast_message,
                    parse_mode="HTML",
                )
                sent_count += 1
                await asyncio.sleep(0.04)
            except ApiTelegramException as e:
                # Error 403: bot blocked, Error 400: chat not found
                if (
                    e.error_code in (403, 400)
                    or "blocked" in str(e).lower()
                    or "not found" in str(e).lower()
                ):
                    logger.warning(
                        "User %d blocked the bot or chat is invalid (%s). "
                        "Deactivating subscription.",
                        user.telegram_id,
                        e.description,
                    )
                    await crud.deactivate_user(user.telegram_id)
                    deactivated_count += 1
                else:
                    logger.error(
                        "Telegram API error sending to %d: %s",
                        user.telegram_id,
                        e,
                    )
                    error_count += 1
            except Exception:
                logger.exception(
                    "Unexpected error sending to user %d", user.telegram_id
                )
                error_count += 1

    logger.info(
        "Broadcast completed: %d sent successfully, "
        "%d deactivated, %d errors across %d cities.",
        sent_count,
        deactivated_count,
        error_count,
        len(city_groups),
    )

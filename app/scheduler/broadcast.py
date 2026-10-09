import asyncio
import logging

from telebot.async_telebot import AsyncTeleBot
from telebot.asyncio_helper import ApiTelegramException

from app.db import crud
from app.services.weather import WeatherService

logger = logging.getLogger(__name__)


async def send_daily_weather_broadcast(bot: AsyncTeleBot) -> None:
    """
    Broadcasts the daily weather forecast to all subscribed users.
    Executed daily at scheduled time (e.g., 07:00 MSK).
    """
    logger.info("Starting scheduled daily weather broadcast...")

    try:
        forecast_message = await WeatherService.get_today_forecast_message()
    except Exception:
        logger.exception("Failed to fetch weather forecast for broadcast")
        return

    subscribers = await crud.get_subscribed_users()
    if not subscribers:
        logger.info("No active subscribers found for weather broadcast.")
        return

    logger.info("Found %d active subscribers. Sending forecasts...", len(subscribers))

    sent_count = 0
    deactivated_count = 0
    error_count = 0

    for user in subscribers:
        try:
            await bot.send_message(
                chat_id=user.telegram_id,
                text=forecast_message,
                parse_mode="HTML",
            )
            sent_count += 1
            # Gentle delay to respect Telegram flood limits (30 msgs/sec max)
            await asyncio.sleep(0.04)
        except ApiTelegramException as e:
            # Error 403: bot was blocked by user / user deactivated
            # Error 400: chat not found
            if (
                e.error_code in (403, 400)
                or "blocked" in str(e).lower()
                or "not found" in str(e).lower()
            ):
                logger.warning(
                    "User %d blocked the bot or chat is invalid (%s). Deactivating subscription.",
                    user.telegram_id,
                    e.description,
                )
                await crud.deactivate_user(user.telegram_id)
                deactivated_count += 1
            else:
                logger.error(
                    "Telegram API error sending to %d: %s", user.telegram_id, e
                )
                error_count += 1
        except Exception:
            logger.exception("Unexpected error sending to user %d", user.telegram_id)
            error_count += 1

    logger.info(
        "Broadcast completed: %d sent successfully, %d deactivated, %d errors.",
        sent_count,
        deactivated_count,
        error_count,
    )

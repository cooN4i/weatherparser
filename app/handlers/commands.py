import logging

from telebot.async_telebot import AsyncTeleBot
from telebot.types import Message

from app.config import config
from app.db import crud
from app.services.weather import WeatherService

logger = logging.getLogger(__name__)


def register_handlers(bot: AsyncTeleBot) -> None:
    """Registers command handlers for the Telegram bot."""

    @bot.message_handler(commands=["start"])
    async def handle_start(message: Message) -> None:
        user_id = message.chat.id
        username = message.from_user.username if message.from_user else None
        first_name = (
            message.from_user.first_name if message.from_user else "друг"
        )

        _, is_new = await crud.add_or_activate_user(
            telegram_id=user_id,
            username=username,
            first_name=first_name,
        )

        greeting = "С возвращением" if not is_new else "Привет"
        welcome_text = (
            f"🌤 <b>{greeting}, {first_name}!</b>\n\n"
            f"Вы подписаны на ежедневный прогноз по г. {config.CITY_NAME} "
            f"в <b>{config.BROADCAST_TIME} (МСК)</b>.\n\n"
            "• /weather — погода прямо сейчас\n"
            "• /stop — отписаться от рассылки\n"
            "• /help — помощь"
        )

        await bot.send_message(user_id, welcome_text, parse_mode="HTML")

        # Send immediate forecast as a welcoming preview
        try:
            forecast_msg = await WeatherService.get_today_forecast_message()
            await bot.send_message(user_id, forecast_msg, parse_mode="HTML")
        except Exception:
            logger.exception("Error sending preview forecast on /start")

    @bot.message_handler(commands=["weather", "today"])
    async def handle_weather(message: Message) -> None:
        user_id = message.chat.id
        try:
            forecast_msg = await WeatherService.get_today_forecast_message()
            await bot.send_message(user_id, forecast_msg, parse_mode="HTML")
        except Exception:
            logger.exception("Error fetching weather for user %d", user_id)
            err_msg = (
                "⚠️ Не удалось получить прогноз погоды. "
                "Попробуйте чуть позже."
            )
            await bot.send_message(user_id, err_msg)

    @bot.message_handler(commands=["stop", "unsubscribe"])
    async def handle_stop(message: Message) -> None:
        user_id = message.chat.id
        was_unsubscribed = await crud.deactivate_user(user_id)

        if was_unsubscribed:
            text = (
                "🔕 <b>Вы отписались от утренней рассылки.</b>\n\n"
                "Чтобы снова подписаться, отправьте /start."
            )
        else:
            text = (
                "Вы не были подписаны на рассылку. "
                "Чтобы подписаться, отправьте /start."
            )

        await bot.send_message(user_id, text, parse_mode="HTML")

    @bot.message_handler(commands=["help"])
    async def handle_help(message: Message) -> None:
        text = (
            f"📖 <b>Команды бота ({config.CITY_NAME}):</b>\n\n"
            f"• /start — подписаться на рассылку в "
            f"{config.BROADCAST_TIME} МСК\n"
            "• /weather — прогноз на сегодня прямо сейчас\n"
            "• /stop — отключить утреннюю рассылку\n"
            "• /help — справка"
        )
        await bot.send_message(message.chat.id, text, parse_mode="HTML")

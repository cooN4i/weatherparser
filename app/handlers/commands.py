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
        first_name = message.from_user.first_name if message.from_user else "друг"

        _, is_new = await crud.add_or_activate_user(
            telegram_id=user_id,
            username=username,
            first_name=first_name,
        )

        greeting = "С возвращением" if not is_new else "Привет"
        welcome_text = (
            f"🌤 <b>{greeting}, {first_name or 'друг'}!</b>\n\n"
            f"Я бот прогноза погоды в <b>г. {config.CITY_NAME}</b>.\n\n"
            f"⏰ <b>Каждое утро в {config.BROADCAST_TIME} (МСК)</b> я буду присылать подробный прогноз на весь день: "
            f"температуру утром, днем и вечером, осадки, силу и направление ветра, а также полезные советы.\n\n"
            f"📌 <b>Доступные команды:</b>\n"
            f"• /weather — узнать погоду на сегодня прямо сейчас\n"
            f"• /stop — временно отписаться от утренней рассылки\n"
            f"• /help — список всех команд и описание\n\n"
            f"<i>Загружаю текущий прогноз на сегодня...</i>"
        )

        await bot.send_message(user_id, welcome_text, parse_mode="HTML")

        # Send immediate forecast as a welcoming preview
        try:
            forecast_msg = await WeatherService.get_today_forecast_message()
            await bot.send_message(user_id, forecast_msg, parse_mode="HTML")
        except Exception as e:
            logger.exception("Error sending preview forecast on /start: %s", e)

    @bot.message_handler(commands=["weather", "today"])
    async def handle_weather(message: Message) -> None:
        user_id = message.chat.id
        try:
            forecast_msg = await WeatherService.get_today_forecast_message()
            await bot.send_message(user_id, forecast_msg, parse_mode="HTML")
        except Exception as e:
            logger.exception("Error fetching weather for user %d: %s", user_id, e)
            await bot.send_message(
                user_id,
                "⚠️ Не удалось получить свежий прогноз погоды. Пожалуйста, попробуйте чуть позже.",
            )

    @bot.message_handler(commands=["stop", "unsubscribe"])
    async def handle_stop(message: Message) -> None:
        user_id = message.chat.id
        was_unsubscribed = await crud.deactivate_user(user_id)

        if was_unsubscribed:
            text = (
                "🔕 <b>Вы отписались от ежедневной рассылки.</b>\n\n"
                "Бот больше не будет присылать утренние сообщения. "
                "Вы в любой момент можете возобновить подписку командой /start "
                "или запросить погоду вручную через /weather."
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
            f"📖 <b>Справка по боту погоды ({config.CITY_NAME}):</b>\n\n"
            f"• /start — подписаться на ежедневную утреннюю рассылку в {config.BROADCAST_TIME} МСК\n"
            f"• /weather — получить подробный прогноз на сегодня прямо сейчас\n"
            f"• /stop — отключить утреннюю рассылку\n"
            f"• /stats — статистика подписчиков бота\n"
            f"• /help — открыть эту справку"
        )
        await bot.send_message(message.chat.id, text, parse_mode="HTML")

    @bot.message_handler(commands=["stats"])
    async def handle_stats(message: Message) -> None:
        stats = await crud.get_stats()
        text = (
            f"📊 <b>Статистика бота:</b>\n\n"
            f"👥 Всего пользователей в базе: <b>{stats['total']}</b>\n"
            f"🔔 Активных подписчиков рассылки: <b>{stats['active']}</b>\n"
            f"⏰ Время утренней рассылки: <b>{config.BROADCAST_TIME} ({config.TIMEZONE})</b>\n"
            f"📍 Город: <b>{config.CITY_NAME}</b>"
        )
        await bot.send_message(message.chat.id, text, parse_mode="HTML")

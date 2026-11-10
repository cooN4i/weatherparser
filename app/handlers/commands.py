import logging

from telebot.async_telebot import AsyncTeleBot
from telebot.types import (CallbackQuery, InlineKeyboardButton,
                           InlineKeyboardMarkup, Message)

from app.db import crud
from app.services.geocoding import CityResult, GeocodingService
from app.services.weather import WeatherService

logger = logging.getLogger(__name__)

# Temporary in-memory cache for multi-match city disambiguation
PENDING_CITY_SEARCHES: dict[int, list[CityResult]] = {}


async def _apply_and_confirm_city(
    bot: AsyncTeleBot,
    chat_id: int,
    user_id: int,
    city: CityResult,
) -> None:
    """Saves city to database and sends confirmation with forecast."""
    await crud.set_user_city(
        telegram_id=user_id,
        city_name=city.name,
        latitude=city.latitude,
        longitude=city.longitude,
        timezone=city.timezone,
    )
    PENDING_CITY_SEARCHES.pop(user_id, None)

    confirm_text = (
        f"✅ Город установлен: <b>{city.display_name}</b>!\n\n"
        "Каждое утро в <b>07:00</b> по местному времени "
        "вы будете получать свежий прогноз погоды.\n\n"
        "<i>Загружаю текущий прогноз...</i>"
    )
    await bot.send_message(chat_id, confirm_text, parse_mode="HTML")

    try:
        forecast_msg = await WeatherService.get_today_forecast_message(
            latitude=city.latitude,
            longitude=city.longitude,
            city_name=city.name,
            timezone=city.timezone,
        )
        await bot.send_message(chat_id, forecast_msg, parse_mode="HTML")
    except Exception:
        logger.exception("Error sending preview forecast for %s", city.name)


async def _handle_city_search_query(
    bot: AsyncTeleBot,
    message: Message,
    query: str,
) -> None:
    """Executes geocoding search and handles 0, 1, or multiple results."""
    user_id = message.from_user.id if message.from_user else message.chat.id
    results = await GeocodingService.search_cities(query, limit=5)

    if not results:
        err_text = (
            f"❌ Город «<b>{query}</b>» не найден.\n\n"
            "Попробуйте написать название иначе или отправьте геопозицию 📎."
        )
        await bot.send_message(message.chat.id, err_text, parse_mode="HTML")
        return

    if len(results) == 1:
        await _apply_and_confirm_city(
            bot=bot,
            chat_id=message.chat.id,
            user_id=user_id,
            city=results[0],
        )
        return

    # Multiple options: show inline buttons
    PENDING_CITY_SEARCHES[user_id] = results
    keyboard = InlineKeyboardMarkup(row_width=1)
    for idx, item in enumerate(results):
        btn = InlineKeyboardButton(
            text=f"📍 {item.display_name}",
            callback_data=f"pick_city:{idx}",
        )
        keyboard.add(btn)

    await bot.send_message(
        message.chat.id,
        "🔍 Найдено несколько вариантов. Выберите ваш город:",
        reply_markup=keyboard,
    )


def register_handlers(bot: AsyncTeleBot) -> None:
    """Registers command, text, callback, and location handlers."""

    @bot.message_handler(commands=["start"])
    async def handle_start(message: Message) -> None:
        user_id = message.chat.id
        username = message.from_user.username if message.from_user else None
        first_name = (
            message.from_user.first_name if message.from_user else "друг"
        )

        user, is_new = await crud.add_or_activate_user(
            telegram_id=user_id,
            username=username,
            first_name=first_name,
        )

        if user.city_name and not is_new:
            welcome_text = (
                f"🌤 <b>С возвращением, {first_name}!</b>\n\n"
                f"Ваш город: <b>{user.city_name}</b> "
                "(рассылка в 07:00 по местному времени).\n\n"
                "• /weather — погода прямо сейчас\n"
                "• /city — изменить город\n"
                "• /stop — отписаться от рассылки\n"
                "• /help — помощь"
            )
            await bot.send_message(user_id, welcome_text, parse_mode="HTML")
            return

        # Prompt new user or user without city to specify city
        await crud.set_user_state(user_id, "waiting_city")
        greeting = "Привет" if is_new else "С возвращением"
        prompt_text = (
            f"🌤 <b>{greeting}, {first_name}!</b>\n\n"
            "Я бот ежедневного прогноза погоды. Чтобы каждое утро в 07:00 "
            "получать актуальную сводку, укажите ваш город.\n\n"
            "📍 <b>Напишите название города</b> (например: <i>Казань</i> или "
            "<i>Екатеринбург</i>) или отправьте геопозицию через скрепку 📎."
        )
        await bot.send_message(user_id, prompt_text, parse_mode="HTML")

    @bot.message_handler(commands=["city"])
    async def handle_city(message: Message) -> None:
        user_id = message.chat.id
        parts = message.text.split(maxsplit=1) if message.text else []
        if len(parts) > 1:
            query = parts[1].strip()
            await _handle_city_search_query(bot, message, query)
            return

        await crud.set_user_state(user_id, "waiting_city")
        prompt = (
            "📍 <b>Напишите название города</b> для прогноза погоды "
            "(или отправьте геопозицию через скрепку 📎):"
        )
        await bot.send_message(user_id, prompt, parse_mode="HTML")

    @bot.callback_query_handler(
        func=lambda call: call.data.startswith("pick_city:")
    )
    async def handle_pick_city(call: CallbackQuery) -> None:
        user_id = call.from_user.id
        pending = PENDING_CITY_SEARCHES.get(user_id)
        if not pending:
            await bot.answer_callback_query(
                call.id,
                "Варианты устарели. Введите город заново через /city.",
                show_alert=True,
            )
            return

        try:
            idx = int(call.data.split(":")[1])
            selected_city = pending[idx]
        except (IndexError, ValueError):
            await bot.answer_callback_query(call.id, "Ошибка выбора города.")
            return

        await bot.answer_callback_query(call.id)
        if call.message:
            await bot.delete_message(
                call.message.chat.id,
                call.message.message_id,
            )
        await _apply_and_confirm_city(
            bot=bot,
            chat_id=call.message.chat.id if call.message else user_id,
            user_id=user_id,
            city=selected_city,
        )

    @bot.message_handler(content_types=["location"])
    async def handle_location(message: Message) -> None:
        if not message.location:
            return
        user_id = (
            message.from_user.id if message.from_user else message.chat.id
        )
        lat = message.location.latitude
        lon = message.location.longitude

        await bot.send_message(
            message.chat.id,
            "🔍 Определяю город по координатам...",
        )
        city = await GeocodingService.reverse_geocode(lat, lon)
        if not city:
            msg_text = (
                "⚠️ Не удалось определить город. "
                "Напишите его название текстом."
            )
            await bot.send_message(message.chat.id, msg_text)
            return

        await _apply_and_confirm_city(
            bot=bot,
            chat_id=message.chat.id,
            user_id=user_id,
            city=city,
        )

    @bot.message_handler(commands=["weather", "today"])
    async def handle_weather(message: Message) -> None:
        user_id = message.chat.id
        user = await crud.get_user(user_id)

        if not user or not user.city_name or user.latitude is None:
            await crud.set_user_state(user_id, "waiting_city")
            prompt = (
                "⚠️ У вас ещё не выбран город.\n\n"
                "Напишите название вашего города или отправьте геопозицию 📎."
            )
            await bot.send_message(user_id, prompt)
            return

        try:
            forecast_msg = await WeatherService.get_today_forecast_message(
                latitude=user.latitude,
                longitude=user.longitude,
                city_name=user.city_name,
                timezone=user.timezone,
            )
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
        user = await crud.get_user(message.chat.id)
        current_city = (
            user.city_name if user and user.city_name else "не задан"
        )
        text = (
            f"📖 <b>Справка по боту погоды:</b>\n"
            f"📍 Ваш текущий город: <b>{current_city}</b>\n\n"
            "• /city — выбрать или изменить город\n"
            "• /weather — прогноз на сегодня прямо сейчас\n"
            "• /stop — отключить утреннюю рассылку в 07:00\n"
            "• /start — перезапустить бота\n"
            "• /help — эта справка\n\n"
            "<i>Вы также можете просто отправить боту геопозицию 📎 "
            "или написать название города.</i>"
        )
        await bot.send_message(message.chat.id, text, parse_mode="HTML")

    @bot.message_handler(
        func=lambda msg: msg.text and not msg.text.startswith("/")
    )
    async def handle_text_city(message: Message) -> None:
        """Handles user text input when searching for a city."""
        user_id = (
            message.from_user.id if message.from_user else message.chat.id
        )
        user = await crud.get_user(user_id)

        # Allow city setting if user state is waiting_city or no city is set
        if user and user.state != "waiting_city" and user.city_name:
            # User already has city and didn't invoke /city
            hint = (
                f"Ваш текущий город: <b>{user.city_name}</b>.\n"
                "Чтобы изменить город, используйте команду /city, "
                "или запросите прогноз через /weather."
            )
            await bot.send_message(message.chat.id, hint, parse_mode="HTML")
            return

        query = message.text.strip()
        await _handle_city_search_query(bot, message, query)

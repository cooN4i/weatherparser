import logging
from dataclasses import dataclass
from datetime import datetime

import httpx

from app.config import config

logger = logging.getLogger(__name__)

# WMO Weather interpretation codes (WW)
WMO_CODES: dict[int, tuple[str, str]] = {
    0: ("Ясно", "☀️"),
    1: ("Преимущественно ясно", "🌤"),
    2: ("Переменная облачность", "⛅"),
    3: ("Пасмурно", "☁️"),
    45: ("Туман", "🌫"),
    48: ("Оседающий туман", "🌫"),
    51: ("Слабая морось", "🌦"),
    53: ("Умеренная морось", "🌦"),
    55: ("Плотная морось", "🌧"),
    56: ("Слабая ледяная морось", "🌨"),
    57: ("Плотная ледяная морось", "🌨"),
    61: ("Небольшой дождь", "🌧"),
    63: ("Умеренный дождь", "🌧"),
    65: ("Сильный дождь", "🌧"),
    66: ("Слабый ледяной дождь", "🌨"),
    67: ("Сильный ледяной дождь", "🌨"),
    71: ("Небольшой снег", "🌨"),
    73: ("Умеренный снегопад", "🌨"),
    75: ("Сильный снегопад", "❄️"),
    77: ("Снежная крупа", "❄️"),
    80: ("Слабый ливень", "🌦"),
    81: ("Умеренный ливень", "🌧"),
    82: ("Очень сильный ливень", "🌧⚡"),
    85: ("Слабый снегопад", "🌨"),
    86: ("Сильный снегопад", "❄️"),
    95: ("Гроза", "⛈"),
    96: ("Гроза с небольшим градом", "⛈"),
    99: ("Гроза с сильным градом", "⛈🌩"),
}

RU_MONTHS = [
    "",
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
]

RU_WEEKDAYS = [
    "понедельник",
    "вторник",
    "среда",
    "четверг",
    "пятница",
    "суббота",
    "воскресенье",
]


def classify_wind(speed_ms: float) -> str:
    """Returns descriptive wind category."""
    if speed_ms < 2.0:
        return "штиль"
    elif speed_ms <= 5.0:
        return "слабый"
    elif speed_ms <= 8.0:
        return "умеренный"
    elif speed_ms <= 11.0:
        return "ощутимый"
    elif speed_ms <= 15.0:
        return "сильный"
    else:
        return "штормовой"


def format_temp(val: float) -> str:
    """Formats temperature with explicit + or - sign."""
    rounded = round(val)
    if rounded > 0:
        return f"+{rounded}°C"
    return f"{rounded}°C"


@dataclass
class PeriodForecast:
    title: str
    icon: str
    temp: float
    feels_like: float
    condition: str
    condition_icon: str
    wind_speed: float

    def format_line(self) -> str:
        wind_desc = classify_wind(self.wind_speed)
        return (
            f"{self.icon} <b>{self.title}</b>: {format_temp(self.temp)} "
            f"(ощущается {format_temp(self.feels_like)}) • "
            f"{self.condition_icon} {self.condition}, ветер {self.wind_speed:.1f} м/с ({wind_desc})"
        )


class WeatherService:
    API_URL = "https://api.open-meteo.com/v1/forecast"

    @classmethod
    async def fetch_forecast(cls) -> dict:
        """Fetches forecast data from Open-Meteo."""
        params = {
            "latitude": config.LATITUDE,
            "longitude": config.LONGITUDE,
            "hourly": "temperature_2m,apparent_temperature,precipitation_probability,precipitation,weather_code,wind_speed_10m,wind_gusts_10m",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,wind_speed_10m_max,wind_gusts_10m_max",
            "wind_speed_unit": "ms",
            "timezone": config.TIMEZONE,
            "forecast_days": 1,
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(cls.API_URL, params=params)
            response.raise_for_status()
            return response.json()

    @classmethod
    async def get_today_forecast_message(cls) -> str:
        """Constructs a beautifully formatted Telegram HTML message with today's weather."""
        data = await cls.fetch_forecast()

        hourly = data.get("hourly", {})
        daily = data.get("daily", {})

        # Indexes for morning (08:00), afternoon (14:00), evening (20:00)
        # hourly['time'] contains 24 elements for today: ['...T00:00', ... '...T23:00']
        times = hourly.get("time", [])

        def get_index_for_hour(target_hour: int) -> int:
            for idx, t in enumerate(times):
                if f"T{target_hour:02d}:" in t:
                    return idx
            return min(target_hour, len(times) - 1)

        idx_morning = get_index_for_hour(8)
        idx_day = get_index_for_hour(14)
        idx_evening = get_index_for_hour(20)

        def make_period(title: str, icon: str, idx: int) -> PeriodForecast:
            w_code = hourly.get("weather_code", [0])[idx]
            cond_text, cond_icon = WMO_CODES.get(w_code, ("Облачно", "⛅"))
            return PeriodForecast(
                title=title,
                icon=icon,
                temp=hourly.get("temperature_2m", [0])[idx],
                feels_like=hourly.get("apparent_temperature", [0])[idx],
                condition=cond_text,
                condition_icon=cond_icon,
                wind_speed=hourly.get("wind_speed_10m", [0])[idx],
            )

        morning = make_period("Утро (08:00)", "🌅", idx_morning)
        day = make_period("День (14:00)", "☀️", idx_day)
        evening = make_period("Вечер (20:00)", "🌆", idx_evening)

        # Daily aggregated metrics
        precip_prob_max = (
            daily.get("precipitation_probability_max", [0])[0]
            if daily.get("precipitation_probability_max")
            else 0
        )
        precip_sum = (
            daily.get("precipitation_sum", [0.0])[0]
            if daily.get("precipitation_sum")
            else 0.0
        )
        wind_max = (
            daily.get("wind_speed_10m_max", [0.0])[0]
            if daily.get("wind_speed_10m_max")
            else 0.0
        )
        wind_gusts_max = (
            daily.get("wind_gusts_10m_max", [0.0])[0]
            if daily.get("wind_gusts_10m_max")
            else wind_max
        )

        wind_overall_desc = classify_wind(wind_max)

        # Build precipitation description
        if precip_prob_max >= 40 or precip_sum > 0.2:
            precip_desc = f"вероятность {precip_prob_max}%, до {precip_sum:.1f} мм"
        elif precip_sum > 0:
            precip_desc = f"маловероятны (до {precip_sum:.1f} мм)"
        else:
            precip_desc = "без существенных осадков"

        # Current date display
        now = datetime.now()
        date_str = f"{now.day} {RU_MONTHS[now.month]}, {RU_WEEKDAYS[now.weekday()]}"

        # Contextual tip
        tips = []
        if precip_prob_max >= 50 or precip_sum >= 1.0:
            tips.append("Не забудьте зонт ☂️")
        if min(morning.feels_like, day.feels_like, evening.feels_like) <= 5:
            tips.append("Одевайтесь теплее 🧣")
        if wind_gusts_max >= 12.0:
            tips.append("Осторожно, порывистый ветер 💨")
        if not tips:
            tips.append("Отличного дня и прекрасного настроения! ✨")

        tip_line = " • ".join(tips)

        message = (
            f"📍 <b>Погода в г. {config.CITY_NAME}</b>\n"
            f"🗓 <i>Сегодня, {date_str}</i>\n\n"
            f"{morning.format_line()}\n"
            f"{day.format_line()}\n"
            f"{evening.format_line()}\n\n"
            f"💧 <b>Осадки:</b> {precip_desc}\n"
            f"💨 <b>Ветер:</b> до {wind_max:.1f} м/с ({wind_overall_desc}), порывы до {wind_gusts_max:.1f} м/с\n\n"
            f"💡 <i>{tip_line}</i>"
        )

        return message

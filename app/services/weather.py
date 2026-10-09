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


def get_precipitation_summary(hourly: dict, daily: dict) -> str:
    """
    Computes precipitation summary with time intervals if expected.
    E.g. 'дождь до 2.1 мм (08:00–20:00)' or 'без осадков'.
    """
    precip_list = hourly.get("precipitation", [])
    prob_list = hourly.get("precipitation_probability", [])
    weather_codes = hourly.get("weather_code", [])

    daily_sum = (
        daily.get("precipitation_sum", [0.0])[0]
        if daily.get("precipitation_sum")
        else 0.0
    )
    daily_prob = (
        daily.get("precipitation_probability_max", [0])[0]
        if daily.get("precipitation_probability_max")
        else 0
    )

    # Detect hours with expected rain or snow
    active_indices = [
        i
        for i in range(len(precip_list))
        if (
            precip_list[i] >= 0.1
            or (prob_list and prob_list[i] >= 50 and precip_list[i] > 0)
        )
    ]

    if not active_indices or (daily_sum < 0.1 and daily_prob < 40):
        return "без осадков"

    snow_codes = (71, 73, 75, 77, 85, 86)
    is_snow = any(weather_codes[i] in snow_codes for i in active_indices)
    precip_type = "снег" if is_snow else "дождь"

    # Group consecutive hours into time ranges
    ranges = []
    start = active_indices[0]
    prev = active_indices[0]
    for h in active_indices[1:]:
        if h == prev + 1:
            prev = h
        else:
            ranges.append((start, prev))
            start = h
            prev = h
    ranges.append((start, prev))

    interval_strs = []
    for s, e in ranges:
        if s == e:
            interval_strs.append(f"около {s:02d}:00")
        else:
            end_h = min(e + 1, 24)
            interval_strs.append(f"{s:02d}:00–{end_h:02d}:00")

    time_desc = ", ".join(interval_strs)
    if daily_sum > 0:
        return f"{precip_type} до {daily_sum:.1f} мм ({time_desc})"
    return f"{precip_type} ({time_desc})"


@dataclass
class PeriodForecast:
    title: str
    icon: str
    temp: float
    feels_like: float
    condition: str
    condition_icon: str

    def format_line(self) -> str:
        return (
            f"{self.icon} <b>{self.title}</b>: {format_temp(self.temp)} "
            f"(ощущ. {format_temp(self.feels_like)}) • "
            f"{self.condition_icon} {self.condition}"
        )


class WeatherService:
    API_URL = "https://api.open-meteo.com/v1/forecast"

    @classmethod
    async def fetch_forecast(cls) -> dict:
        """Fetches forecast data from Open-Meteo."""
        params = {
            "latitude": config.LATITUDE,
            "longitude": config.LONGITUDE,
            "hourly": (
                "temperature_2m,apparent_temperature,"
                "precipitation_probability,precipitation,"
                "weather_code,wind_speed_10m,wind_gusts_10m"
            ),
            "daily": (
                "weather_code,temperature_2m_max,temperature_2m_min,"
                "precipitation_sum,precipitation_probability_max,"
                "wind_speed_10m_max,wind_gusts_10m_max"
            ),
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
        """Constructs formatted Telegram HTML message with today's weather."""
        data = await cls.fetch_forecast()

        hourly = data.get("hourly", {})
        daily = data.get("daily", {})
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
            )

        morning = make_period("Утро", "🌅", idx_morning)
        day = make_period("День", "☀️", idx_day)
        evening = make_period("Вечер", "🌆", idx_evening)

        # Wind metrics
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
        wind_desc = classify_wind(wind_max)
        if wind_gusts_max > wind_max + 1.0:
            wind_line = (
                f"{wind_desc}, до {wind_max:.1f} м/с "
                f"(порывы до {wind_gusts_max:.1f} м/с)"
            )
        else:
            wind_line = f"{wind_desc}, до {wind_max:.1f} м/с"

        # Precipitation summary with intervals
        precip_summary = get_precipitation_summary(hourly, daily)

        # Date string
        now = datetime.now()
        date_str = (
            f"{now.day} {RU_MONTHS[now.month]}, {RU_WEEKDAYS[now.weekday()]}"
        )

        message = (
            f"📍 <b>{config.CITY_NAME} — {date_str}</b>\n\n"
            f"{morning.format_line()}\n"
            f"{day.format_line()}\n"
            f"{evening.format_line()}\n\n"
            f"💧 <b>Осадки:</b> {precip_summary}\n"
            f"💨 <b>Ветер:</b> {wind_line}"
        )

        return message

import pytest

from app.services.weather import (WeatherService, classify_wind, format_temp,
                                  get_precipitation_summary)


def test_classify_wind():
    assert classify_wind(0.5) == "штиль"
    assert classify_wind(3.0) == "слабый"
    assert classify_wind(6.5) == "умеренный"
    assert classify_wind(9.0) == "ощутимый"
    assert classify_wind(13.0) == "сильный"
    assert classify_wind(18.0) == "штормовой"


def test_format_temp():
    assert format_temp(12.3) == "+12°C"
    assert format_temp(0.4) == "0°C"
    assert format_temp(-4.8) == "-5°C"
    assert format_temp(0.0) == "0°C"


def test_get_precipitation_summary_no_rain():
    hourly = {
        "precipitation": [0.0] * 24,
        "precipitation_probability": [5] * 24,
        "weather_code": [0] * 24,
    }
    daily = {
        "precipitation_sum": [0.0],
        "precipitation_probability_max": [5],
    }
    result = get_precipitation_summary(hourly, daily)
    assert result == "без осадков"


def test_get_precipitation_summary_with_intervals():
    precip = [0.0] * 24
    prob = [10] * 24
    # Rain from 08:00 to 11:00 (indices 8, 9, 10)
    for h in (8, 9, 10):
        precip[h] = 0.5
        prob[h] = 85

    hourly = {
        "precipitation": precip,
        "precipitation_probability": prob,
        "weather_code": [61] * 24,
    }
    daily = {
        "precipitation_sum": [1.5],
        "precipitation_probability_max": [85],
    }
    result = get_precipitation_summary(hourly, daily)
    assert "дождь до 1.5 мм (08:00–11:00)" == result


def test_get_precipitation_summary_snow():
    precip = [0.0] * 24
    prob = [10] * 24
    for h in (14, 15):
        precip[h] = 0.8
        prob[h] = 90

    hourly = {
        "precipitation": precip,
        "precipitation_probability": prob,
        "weather_code": [71] * 24,  # Light snow WMO code
    }
    daily = {
        "precipitation_sum": [1.6],
        "precipitation_probability_max": [90],
    }
    result = get_precipitation_summary(hourly, daily)
    assert "снег до 1.6 мм (14:00–16:00)" == result


@pytest.mark.asyncio
async def test_weather_service_message_format(monkeypatch):
    mock_data = {
        "hourly": {
            "time": [f"2026-10-10T{h:02d}:00" for h in range(24)],
            "temperature_2m": [10.0] * 24,
            "apparent_temperature": [7.0] * 24,
            "weather_code": [3] * 24,
            "precipitation": [0.0] * 24,
            "precipitation_probability": [10] * 24,
            "wind_speed_10m": [5.0] * 24,
            "wind_gusts_10m": [8.0] * 24,
        },
        "daily": {
            "temperature_2m_max": [12.0],
            "temperature_2m_min": [6.0],
            "precipitation_sum": [0.0],
            "precipitation_probability_max": [10],
            "wind_speed_10m_max": [5.0],
            "wind_gusts_10m_max": [8.0],
        },
    }

    async def mock_fetch():
        return mock_data

    monkeypatch.setattr(WeatherService, "fetch_forecast", mock_fetch)

    msg = await WeatherService.get_today_forecast_message()
    assert "Санкт-Петербург" in msg
    assert "Утро" in msg
    assert "День" in msg
    assert "Вечер" in msg
    assert "Осадки:</b> без осадков" in msg
    assert "Ветер:" in msg
    # Verify no tips/umbrella present
    assert "зонт" not in msg
    assert "Одевайтесь" not in msg

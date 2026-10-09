import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Config:
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "").strip()

    CITY_NAME: str = os.getenv("CITY_NAME", "Санкт-Петербург")
    LATITUDE: float = float(os.getenv("LATITUDE", "59.9343"))
    LONGITUDE: float = float(os.getenv("LONGITUDE", "30.3351"))
    TIMEZONE: str = os.getenv("TIMEZONE", "Europe/Moscow")

    BROADCAST_TIME: str = os.getenv("BROADCAST_TIME", "07:00")
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "sqlite+aiosqlite:///./data/weather.db"
    )

    @classmethod
    def get_broadcast_hour_minute(cls) -> tuple[int, int]:
        try:
            parts = cls.BROADCAST_TIME.split(":")
            return int(parts[0]), int(parts[1])
        except (ValueError, IndexError, AttributeError):
            return 7, 0

    @classmethod
    def validate(cls):
        if not cls.BOT_TOKEN:
            raise ValueError(
                "BOT_TOKEN не задан! Проверьте файл .env или переменные окружения."
            )


config = Config()

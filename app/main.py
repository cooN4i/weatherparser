import asyncio
import logging
import sys

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telebot.async_telebot import AsyncTeleBot

from app.config import config
from app.db.session import init_db
from app.handlers import register_handlers
from app.scheduler import send_daily_weather_broadcast

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("weatherparser")


async def main() -> None:
    """Main application entry point."""
    logger.info("Starting Weather Parser Bot...")

    # 1. Validate configuration
    config.validate()

    # 2. Initialize database schema
    logger.info("Initializing database: %s", config.DATABASE_URL)
    await init_db()
    logger.info("Database schema initialized successfully.")

    # 3. Create Telegram Bot instance
    bot = AsyncTeleBot(token=config.BOT_TOKEN)

    # 4. Register command handlers
    register_handlers(bot)

    # 5. Setup AsyncIOScheduler with Europe/Moscow timezone
    tz = pytz.timezone(config.TIMEZONE)
    scheduler = AsyncIOScheduler(timezone=tz)

    hour, minute = config.get_broadcast_hour_minute()
    scheduler.add_job(
        send_daily_weather_broadcast,
        trigger=CronTrigger(hour=hour, minute=minute, timezone=tz),
        args=[bot],
        id="daily_weather_broadcast",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.start()
    logger.info(
        "Scheduler started. Daily forecast scheduled at %02d:%02d (%s)",
        hour,
        minute,
        config.TIMEZONE,
    )

    # 6. Retrieve bot information
    try:
        me = await bot.get_me()
        logger.info(
            "Bot authenticated successfully: @%s (ID: %d)",
            me.username,
            me.id,
        )
    except Exception as e:
        logger.error(
            "Failed to connect to Telegram API. Check your BOT_TOKEN: %s",
            e,
        )
        raise

    logger.info("Bot is now listening for messages (polling mode)...")

    try:
        # 7. Start polling
        await bot.infinity_polling(skip_pending=True)
    finally:
        logger.info("Shutting down bot and scheduler...")
        scheduler.shutdown(wait=False)
        await bot.close_session()
        logger.info("Shutdown complete.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Application stopped by user.")
    except Exception as exc:
        logger.critical("Fatal error occurred: %s", exc, exc_info=True)
        sys.exit(1)

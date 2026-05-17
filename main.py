import logging

import disnake
from disnake.ext import commands

from bot.core.bot import Bot
from bot.utils.settings import settings
from bot.utils.logger_setup import setup_logging, get_log

setup_logging(
    level=logging.DEBUG if settings.bot_debug_enabled else logging.INFO,
    keep_days=14,
)

logger = get_log(__name__)

intents = disnake.Intents.default()
intents.guilds = True
intents.members = True

command_sync_flags = commands.CommandSyncFlags.default()
command_sync_flags.sync_commands_debug = False #settings.bot_debug_enabled

bot = Bot(
    intents=intents,
    test_guilds=[settings.bot_guild_id] if settings.bot_debug_enabled else None,
    reload=settings.bot_debug_enabled,
    command_sync_flags=command_sync_flags,
)


def main() -> None:
    try:
        logger.info("Bot is starting up...")
        bot.run(settings.bot_discord_token)
    except KeyboardInterrupt:
        logger.info("Bot is shutting down...")
    finally:
        logger.info("Bot has exited...")


if __name__ == "__main__":
    main()

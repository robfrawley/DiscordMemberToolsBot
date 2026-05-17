from disnake.ext import commands
from disnake.ext.commands import InvokableApplicationCommand

from bot.utils.logger_setup import get_class_log
from bot.utils.settings import settings
from bot.db.database import database
from bot.db.repos.birthday_repo import birthday_repo


class Bot(commands.InteractionBot):
    def __init__(self, *args, **kwargs):
        self.log = get_class_log(__name__, self.__class__)
        kwargs.pop("help_command", None)
        kwargs.pop("command_prefix", None)
        super().__init__(*args, **kwargs)

        self._did_startup = False


    async def on_connect(self) -> None:
        if self._did_startup:
            return

        self._did_startup = True

        self.log.debug("Running startup (on_connect)...")

        settings.log_settings(settings)

        self.log.info("Setting up database...")
        await database.connect()
        await birthday_repo.init_schema()

        self.log.info("Loading extensions...")
        if not settings.bot_enabled_cogs:
            self.log.error("No extensions to load! Enable one in your .env file.")
        for ext in settings.bot_enabled_cogs:
            try:
                self.load_extension(ext)
                self.log.debug(f'-> "{ext}" (success)')
            except Exception as e:
                self.log.warning(f'-> "{ext}" (failure: {e})')

        self.log_commands(self.application_commands)


    async def on_ready(self) -> None:
        if not self.user:
            raise RuntimeError("Bot user information is None.")

        self.log.info(f'Bot user "{self.user.name}" with ID "{self.user.id}" is logged in and ready.')


    async def close(self) -> None:
        self.log.debug("Closing Discord connection...")
        await super().close()

        try:
            self.log.debug("Closing database connection...")
            await database.close()
        except Exception as e:
            self.log.warning(f"Error closing database connection: {e}")


    def log_commands(self, synced: set[InvokableApplicationCommand]) -> None:
        entries: list[tuple[str, str]] = []

        for command in synced:
            scope = "global"
            entries.append((f"-> \"{command.name}\"", scope))

        max_len = max((len(cmd) for cmd, _ in entries), default=0)

        self.log.debug(f'Synced "{len(synced)}" commands...')

        for cmd, scope in entries:
            self.log.debug(f'{cmd.ljust(max_len)} ({scope})')

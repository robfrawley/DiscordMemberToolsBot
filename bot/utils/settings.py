from zoneinfo import ZoneInfo
from pathlib import Path

from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from bot import ENV_FILE_PATH, COGS_DIR_PATH
from bot.utils.logger_setup import get_class_log


class SettingsManager(BaseSettings):
    bot_debug_enabled: bool = Field(default=False)

    bot_discord_token: str = Field()
    bot_sqlite_db_path: str = Field()

    bot_guild_id: int = Field()
    bot_timezone: ZoneInfo = Field(default=ZoneInfo("UTC"))
    bot_defined_cogs: list[str] = sorted([
        f"bot.cogs.{p.name}"
        for p in Path(COGS_DIR_PATH).iterdir()
        if p.is_dir() and (p / "__init__.py").exists()
    ])
    bot_enabled_cogs: list[str] = Field(default_factory=list)
    
    mods_role: int = Field(default_factory=int)

    birthday_tools_enabled: bool = Field(default=True)

    birthday_role: int = Field(default_factory=int)
    birthday_announce_channel: int | None = Field(default=None)
    
    birthday_role_assign_checks_task_frequency_cron_minutes: str = Field("0")
    birthday_role_assign_checks_task_frequency_cron_hours: str = Field("*")
    birthday_embed_announcement_task_frequency_cron_minutes: str = Field("0")
    birthday_embed_announcement_task_frequency_cron_hours: str = Field("*")
    birthday_embed_announcement_peruser_cooldown_hours: int = Field(6)
    birthday_announce_embed_image_url: str | None = Field(default=None)
    birthday_announce_embed_author_icon_url: str | None = Field(default=None)
    birthday_announce_embed_author_name: str | None = Field(default=None)

    model_config = SettingsConfigDict(
        env_file=ENV_FILE_PATH,
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )


    @field_validator("bot_enabled_cogs")
    @classmethod
    def enabled_cogs_must_exist(cls, enabled: list[str], info):
        defined: set[str] = set(info.data.get("bot_defined_cogs", []))
        invalid: set[str] = set([c for c in enabled if c not in defined])

        if invalid:
            raise ValueError(
                f"Unknown cogs in bot_enabled_cogs: {', '.join(sorted(invalid))}. "
                f"Available cogs: {', '.join(sorted(defined))}"
            )

        return sorted(enabled)


    @field_validator(
        "birthday_announce_channel",
        "birthday_announce_embed_image_url",
        "birthday_announce_embed_author_icon_url",
        "birthday_announce_embed_author_name",
        mode="before",
    )
    @classmethod
    def empty_to_none(cls, v):
        if v is None:
            return None
        if isinstance(v, str) and v.strip() == "":
            return None
        return v


    @field_validator("bot_sqlite_db_path", mode="before")
    @classmethod
    def make_bot_sqlite_db_path_absolute(cls, v: str) -> str:
        if not v:
            raise ValueError("bot_sqlite_db_path cannot be empty")

        return str(Path(v).expanduser().resolve())


    @field_validator("bot_timezone", mode="before")
    @classmethod
    def normalize_bot_timezone(cls, v):
        return ZoneInfo(v) if isinstance(v, str) else v


    def log_settings(self, settings: BaseSettings) -> None:
        log = get_class_log(__name__, self.__class__)
        log.info("Loaded configuration...")

        fields = settings.__class__.model_fields.keys()
        values: dict[str, Any] = {field: getattr(settings, field) for field in fields}
        maxlen: int = max(len(name) for name in fields)

        for name, value in values.items():
            if 'bot_discord_token' in name:
                display_value: str = self._redact_token(value)
            else:
                display_value: str = value

            label = f'"{name}"'.ljust(maxlen + 2)
            log.debug(f'-> {label} = "{display_value}"')


    def _redact_token(self, token: str) -> str:
        if not token:
            return token

        half: int = len(token) // 2

        return token[:half] + "*" * (len(token) - half)


settings = SettingsManager() # type: ignore

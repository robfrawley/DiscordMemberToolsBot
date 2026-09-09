from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from bot.db.database import Database, database
from bot.models.birthday import Birthday
from bot.utils.logger_setup import get_class_log


class BirthdayRepo:
    def __init__(self, database: Database):
        self.database = database
        self.log = get_class_log(__name__, self.__class__)


    async def init_schema(self) -> None:
        self.log.debug("Initializing...")

        await self.database.execute(
            """
            CREATE TABLE IF NOT EXISTS birthdays (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                month INTEGER NOT NULL,
                day INTEGER NOT NULL,
                timezone TEXT NOT NULL DEFAULT 'UTC',
                last_announcement_at INTEGER
            );
            """.strip(),
            auto_commit=False,
        )

        cursor = await self.database.execute(
            """
            PRAGMA table_info(birthdays);
            """.strip(),
            auto_commit=False,
        )

        columns = await cursor.fetchall()

        if not any(row[1] == "timezone" for row in columns):
            self.log.info("Migrating birthdays table: adding timezone column.")

            await self.database.execute(
                """
                ALTER TABLE birthdays
                ADD COLUMN timezone TEXT NOT NULL DEFAULT 'UTC';
                """.strip(),
                auto_commit=False,
            )

        if not any(row[1] == "last_announcement_at" for row in columns):
            self.log.info(
                "Migrating birthdays table: adding last_announcement_at column."
            )

            await self.database.execute(
                """
                ALTER TABLE birthdays
                ADD COLUMN last_announcement_at INTEGER;
                """.strip(),
                auto_commit=False,
            )

        await self.database.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_birthdays_user_id_guild_id
            ON birthdays (user_id, guild_id);
            """.strip(),
            auto_commit=False,
        )

        await self.database.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_birthdays_guild_id_month_day
            ON birthdays (guild_id, month, day);
            """.strip(),
            auto_commit=False,
        )

        await self.database.commit()


    async def add(self, payload: Birthday) -> None:
        await self.database.execute(
            """
            INSERT INTO birthdays (user_id, guild_id, month, day, timezone)
            VALUES (?, ?, ?, ?, ?);
            """.strip(),
            (
                int(payload.user_id),
                int(payload.guild_id),
                int(payload.month),
                int(payload.day),
                str(payload.timezone),
            ),
            auto_commit=True,
        )


    async def update(self, payload: Birthday) -> int:
        cursor = await self.database.execute(
            """
            UPDATE birthdays
            SET month = ?, day = ?, timezone = ?
            WHERE user_id = ? AND guild_id = ?;
            """.strip(),
            (
                int(payload.month),
                int(payload.day),
                str(payload.timezone),
                int(payload.user_id),
                int(payload.guild_id),
            ),
            auto_commit=True,
        )

        return int(getattr(cursor, "rowcount", 0) or 0)


    async def upsert(self, payload: Birthday) -> None:
        await self.database.execute(
            """
            INSERT INTO birthdays (user_id, guild_id, month, day, timezone)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, guild_id)
            DO UPDATE SET
                month = excluded.month,
                day = excluded.day,
                timezone = excluded.timezone;
            """.strip(),
            (
                int(payload.user_id),
                int(payload.guild_id),
                int(payload.month),
                int(payload.day),
                str(payload.timezone),
            ),
            auto_commit=True,
        )


    async def delete(
        self,
        *,
        user_id: int,
        guild_id: int,
    ) -> int:
        cursor = await self.database.execute(
            """
            DELETE FROM birthdays
            WHERE user_id = ? AND guild_id = ?;
            """.strip(),
            (
                int(user_id),
                int(guild_id),
            ),
            auto_commit=True,
        )

        return int(getattr(cursor, "rowcount", 0) or 0)


    async def get_by_user(
        self,
        *,
        user_id: int,
        guild_id: int,
    ) -> Birthday | None:
        cursor = await self.database.execute(
            """
            SELECT
                user_id,
                guild_id,
                month,
                day,
                timezone,
                last_announcement_at
            FROM birthdays
            WHERE user_id = ? AND guild_id = ?
            LIMIT 1;
            """.strip(),
            (int(user_id), int(guild_id)),
        )

        row = await cursor.fetchone()

        if not row:
            return None

        return Birthday(
            user_id=int(row[0]),
            guild_id=int(row[1]),
            month=int(row[2]),
            day=int(row[3]),
            timezone=str(row[4]),
            last_announcement_at=(
                int(row[5])
                if row[5] is not None
                else None
            ),
        )


    async def get_current_birthdays(
        self,
        *,
        guild_id: int,
        current_datetime: datetime,
    ) -> list[Birthday]:
        if current_datetime.tzinfo is None:
            raise ValueError("current_datetime must be timezone-aware")

        cursor = await self.database.execute(
            """
            SELECT
                user_id,
                guild_id,
                month,
                day,
                timezone,
                last_announcement_at
            FROM birthdays
            WHERE guild_id = ?
            ORDER BY user_id ASC;
            """.strip(),
            (int(guild_id),),
        )

        rows = await cursor.fetchall()

        birthdays: list[Birthday] = []

        for row in rows:
            birthday = Birthday(
                user_id=int(row[0]),
                guild_id=int(row[1]),
                month=int(row[2]),
                day=int(row[3]),
                timezone=str(row[4]),
                last_announcement_at=(
                    int(row[5])
                    if row[5] is not None
                    else None
                ),
            )

            local_datetime = current_datetime.astimezone(
                ZoneInfo(birthday.timezone)
            )

            if (
                birthday.month == local_datetime.month
                and birthday.day == local_datetime.day
            ):
                birthdays.append(birthday)

        return birthdays


    async def set_last_announcement_at(
        self,
        *,
        user_id: int,
        guild_id: int,
        timestamp: datetime,
    ) -> int:
        cursor = await self.database.execute(
            """
            UPDATE birthdays
            SET last_announcement_at = ?
            WHERE user_id = ? AND guild_id = ?;
            """.strip(),
            (
                int(timestamp.timestamp()),
                int(user_id),
                int(guild_id),
            ),
            auto_commit=True,
        )

        return int(getattr(cursor, "rowcount", 0) or 0)


birthday_repo = BirthdayRepo(database=database)

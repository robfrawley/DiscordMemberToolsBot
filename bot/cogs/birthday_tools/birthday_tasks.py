from __future__ import annotations

import calendar
from datetime import datetime, timedelta, UTC
from zoneinfo import ZoneInfo

import disnake
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.memory import MemoryJobStore
from disnake.ext import commands

from bot.db.repos.birthday_repo import birthday_repo
from bot.utils.settings import settings
from bot.utils.logger_setup import Log, get_class_log


class BirthdayTasks(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot: commands.Bot = bot
        self.log: Log = get_class_log(__name__, self.__class__)

        self.scheduler = AsyncIOScheduler(
            jobstores={
                "birthday_jobs": MemoryJobStore()
            }
        )


    def cog_unload(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)


    @commands.Cog.listener()
    async def on_ready(self) -> None:
        if self.scheduler.running:
            return

        self.log.debug("Setting up birthday task scheduling on ready trigger...")

        self.scheduler.add_job(
            self.run_birthday_role_task,
            CronTrigger(
                minute=settings.birthday_role_assign_checks_task_frequency_cron_minutes,
                hour=settings.birthday_role_assign_checks_task_frequency_cron_hours,
                timezone=settings.bot_timezone,
            ),
            id="birthday_role_task",
            jobstore="birthday_jobs",
            replace_existing=True,
        )

        self.scheduler.add_job(
            self.run_birthday_announcement_task,
            CronTrigger(
                minute=settings.birthday_embed_announcement_task_frequency_cron_minutes,
                hour=settings.birthday_embed_announcement_task_frequency_cron_hours,
                timezone=settings.bot_timezone,
            ),
            id="birthday_announcement_task",
            jobstore="birthday_jobs",
            replace_existing=True,
        )

        self.scheduler.start()
        await self.run_birthday_role_task()
        await self.run_birthday_announcement_task()


    async def run_birthday_role_task(self) -> None:
        self.log.info("Running birthday role task...")
        
        try:
            await self.handle_birthday_role_task()
        except Exception as e:
            self.log.exception("Birthday role task failed.", exc_info=e)
        else:
            self.log.info("Birthday role task completed successfully.")


    async def run_birthday_announcement_task(self) -> None:
        self.log.info("Running birthday announcement task...")

        try:
            await self.handle_birthday_announcement_task()
        except Exception as e:
            self.log.exception("Birthday announcement task failed.", exc_info=e)
        else:
            self.log.info("Birthday announcement task completed successfully.")


    async def handle_birthday_role_task(self) -> None:
        now: datetime = datetime.now(UTC)
        role_id: int = settings.birthday_role

        for guild in self.bot.guilds:
            role = guild.get_role(role_id)

            if role is None:
                self.log.warning(
                    f"Birthday role with ID {role_id} not found in guild '{guild.name}' ({guild.id})."
                )
                continue

            birthdays_today = await birthday_repo.get_current_birthdays(
                guild_id=int(guild.id),
                current_datetime=now,
            )
            
            #self.log.debug(
            #    f"Current birthdays for guild '{guild.name}' ({guild.id}): "
            #    f"{[birthday.user_id for birthday in birthdays_today]}"
            #)

            birthday_user_ids = {
                int(birthday.user_id)
                for birthday in birthdays_today
            }

            for user_id in birthday_user_ids:
                member = guild.get_member(user_id)

                if member is None:
                    try:
                        member = await guild.fetch_member(user_id)

                    except disnake.NotFound:
                        self.log.warning(
                            f"Birthday user {user_id} was not found "
                            f"in guild '{guild.name}' ({guild.id})."
                        )
                        continue

                    except disnake.HTTPException:
                        self.log.exception(
                            f"Failed to fetch birthday user {user_id} "
                            f"in guild '{guild.name}' ({guild.id})."
                        )
                        continue

                if role not in member.roles:
                    try:
                        self.log.info(
                            f"Adding birthday role to user '{member}' ({member.id}) "
                            f"in guild '{guild.name}' ({guild.id})."
                        )

                        await member.add_roles(
                            role,
                            reason="User birthday is today.",
                        )

                    except disnake.Forbidden:
                        self.log.exception(
                            f"Forbidden from adding birthday role "
                            f"'{role.name}' ({role.id}) to user "
                            f"'{member}' ({member.id}) in guild "
                            f"'{guild.name}' ({guild.id})."
                        )
                        continue

                    except disnake.HTTPException:
                        self.log.exception(
                            f"HTTP error while adding birthday role "
                            f"'{role.name}' ({role.id}) to user "
                            f"'{member}' ({member.id}) in guild "
                            f"'{guild.name}' ({guild.id})."
                        )
                        continue

            for member in role.members:
                birthday = await birthday_repo.get_by_user(
                    user_id=int(member.id),
                    guild_id=int(guild.id),
                )

                if birthday is None:
                    is_still_birthday = False
                else:
                    local_now = now.astimezone(ZoneInfo(birthday.timezone))

                    is_still_birthday = (
                        birthday.month == local_now.month
                        and birthday.day == local_now.day
                    )

                if not is_still_birthday:
                    try:
                        self.log.info(
                            f"Removing birthday role from user '{member}' ({member.id}) in guild '{guild.name}' ({guild.id})."
                        )
                        await member.remove_roles(
                            role,
                            reason="User birthday is no longer today.",
                        )
                    except disnake.Forbidden:
                        continue
                    except disnake.HTTPException:
                        continue


    async def handle_birthday_announcement_task(self) -> None:
        now = datetime.now(UTC)
        role_id: int = settings.birthday_role
        channel_id: int | None = settings.birthday_announce_channel

        if channel_id is None:
            self.log.debug(
                "No birthday announcement channel configured, "
                "skipping announcement task."
            )
            return

        announcement_interval = timedelta(hours=settings.birthday_embed_announcement_peruser_cooldown_hours)

        for guild in self.bot.guilds:
            channel = guild.get_channel(channel_id)

            if not isinstance(channel, disnake.TextChannel):
                continue

            birthdays_today = await birthday_repo.get_current_birthdays(
                guild_id=int(guild.id),
                current_datetime=now,
            )

            if not birthdays_today:
                continue

            birthday_mentions: list[str] = []
            announced_user_ids: list[int] = []

            for birthday in birthdays_today:
                user_id = int(birthday.user_id)

                if birthday.last_announcement_at is not None:
                    last_sent = datetime.fromtimestamp(
                        birthday.last_announcement_at,
                        tz=UTC,
                    )

                    if now - last_sent < announcement_interval:
                        self.log.debug(
                            f"Skipping birthday announcement for user '{user_id}' in guild '{guild.name}' ({guild.id}) "
                            f"due to announcement cooldown ({now - last_sent}/{announcement_interval})."
                        )
                        continue

                member = guild.get_member(user_id)

                if member is None:
                    try:
                        member = await guild.fetch_member(user_id)
                    except (disnake.NotFound, disnake.HTTPException):
                        self.log.warning(
                            f"Failed to fetch member '{user_id}' in guild '{guild.name}' ({guild.id}). Not mentioning in birthday announcement."
                        )
                        continue

                birthday_mentions.append(member.mention)
                announced_user_ids.append(user_id)

            if not birthday_mentions:
                continue

            role = guild.get_role(role_id)

            if role is not None:
                description = f"Happy {role.mention}! 🎉 Don't forget to ping the birthday members once, twice, or three times with kind birthday wishes. 🎂"
            else:
                description = "Happy birthday! 🎉 Don't forget to ping the birthday members once, twice, or three times with kind birthday wishes. 🎂"

            embed = disnake.Embed(
                #title="Today's Birthdays!",
                description=description,
                color=disnake.Color.random(),
                timestamp=now,
            )

            embed.set_footer(
                text=f"{calendar.month_name[now.month]} {now.day}"
            )

            if settings.birthday_announce_embed_image_url:
                embed.set_image(
                    url=settings.birthday_announce_embed_image_url
                )

            if (
                settings.birthday_announce_embed_author_name
                and settings.birthday_announce_embed_author_icon_url
            ):
                embed.set_author(
                    name=settings.birthday_announce_embed_author_name,
                    icon_url=settings.birthday_announce_embed_author_icon_url,
                )

            try:
                await channel.send(
                    content=" ".join(birthday_mentions),
                    embed=embed,
                    allowed_mentions=disnake.AllowedMentions(
                        users=True,
                        roles=True,
                    ),
                )
            except (disnake.Forbidden, disnake.HTTPException):
                self.log.warning(
                    f"Failed to send birthday announcement in channel '{channel.name}' ({channel.id}) "
                    f"in guild '{guild.name}' ({guild.id})."
                )
                continue
            
            self.log.info(
                f"Sent birthday announcement in channel '{channel.name}' ({channel.id}) "
                f"in guild '{guild.name}' ({guild.id}) for users {', '.join(map(str, announced_user_ids))}."
            )

            for user_id in announced_user_ids:
                await birthday_repo.set_last_announcement_at(
                    user_id=user_id,
                    guild_id=int(guild.id),
                    timestamp=now,
                )

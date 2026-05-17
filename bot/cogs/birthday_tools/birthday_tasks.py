from __future__ import annotations

import calendar
from datetime import datetime

import disnake
from disnake.ext import commands, tasks

from bot.db.repos.birthday_repo import birthday_repo
from bot.utils.settings import settings
from bot.utils.logger_setup import Log, get_class_log


class BirthdayTasks(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot: commands.Bot = bot
        self.log: Log = get_class_log(__name__, self.__class__)
        self.birthday_role_task.start()
        self.birthday_announcement_task.start()


    def cog_unload(self) -> None:
        self.birthday_role_task.cancel()
        self.birthday_announcement_task.cancel()


    @tasks.loop(minutes=settings.birthday_role_check_frequency_minutes)
    async def birthday_role_task(self) -> None:
        self.log.debug("Running birthday role task...")
        await self.handle_birthday_role_task()


    @tasks.loop(minutes=settings.birthday_announce_embed_frequency_minutes)
    async def birthday_announcement_task(self) -> None:
        self.log.debug("Running birthday announcement task...")
        await self.handle_birthday_announcement_task()


    @birthday_role_task.before_loop
    async def before_birthday_role_task(self) -> None:
        await self.bot.wait_until_ready()


    @birthday_announcement_task.before_loop
    async def before_birthday_announcement_task(self) -> None:
        await self.bot.wait_until_ready()


    async def handle_birthday_role_task(self) -> None:
        now: datetime = datetime.now(tz=settings.bot_timezone)
        month: int = int(now.month)
        day: int = int(now.day)
        role_id: int = settings.birthday_role

        for guild in self.bot.guilds:
            role = guild.get_role(role_id)

            if role is None:
                self.log.warning(
                    f"Birthday role with ID {role_id} not found in guild '{guild.name}' ({guild.id})."
                )
                continue

            birthdays_today = await birthday_repo.get_by_date(
                guild_id=int(guild.id),
                month=month,
                day=day,
            )

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
                        continue
                    except disnake.HTTPException:
                        continue

                if role not in member.roles:
                    try:
                        self.log.info(
                            f"Adding birthday role to user '{member}' ({member.id}) in guild '{guild.name}' ({guild.id})."
                        )
                        await member.add_roles(
                            role,
                            reason="User birthday is today.",
                        )
                    except disnake.Forbidden:
                        continue
                    except disnake.HTTPException:
                        continue

            for member in role.members:
                birthday = await birthday_repo.get_by_user(
                    user_id=int(member.id),
                    guild_id=int(guild.id),
                )

                is_still_birthday = (
                    birthday is not None
                    and int(birthday.month) == month
                    and int(birthday.day) == day
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
        now = datetime.now(tz=settings.bot_timezone)
        month = int(now.month)
        day = int(now.day)
        role_id: int = settings.birthday_role
        channel_id: int | None = settings.birthday_announce_channel
        
        if channel_id is None:
            self.log.debug("No birthday announcement channel configured, skipping announcement task.")
            return

        for guild in self.bot.guilds:
            channel = guild.get_channel(channel_id)

            if not isinstance(channel, disnake.TextChannel):
                continue

            birthdays_today = await birthday_repo.get_by_date(
                guild_id=int(guild.id),
                month=month,
                day=day,
            )

            if not birthdays_today:
                continue

            birthday_mentions: list[str] = []

            for birthday in birthdays_today:
                member = guild.get_member(int(birthday.user_id))

                if member is None:
                    try:
                        member = await guild.fetch_member(int(birthday.user_id))
                    except disnake.NotFound:
                        continue
                    except disnake.HTTPException:
                        continue

                self.log.debug(
                    f"Adding birthday mention for user '{member}' ({member.id}) in guild '{guild.name}' ({guild.id})."
                )
                birthday_mentions.append(member.mention)

            if not birthday_mentions:
                self.log.debug(
                    f"No valid birthday mentions found in guild '{guild.name}' ({guild.id}) for today's birthdays ({month}/{day}), skipping announcement."
                )
                continue

            if len(birthday_mentions) == 1:
                description = (
                    f"🎉 Happy birthday to {birthday_mentions[0]}!"
                )
            else:
                joined_mentions = ", ".join(birthday_mentions[:-1])

                if joined_mentions:
                    joined_mentions += f", and {birthday_mentions[-1]}"
                else:
                    joined_mentions = birthday_mentions[-1]

                description = (
                    f"🎉 Happy birthday to {joined_mentions}!"
                )

            embed = disnake.Embed(
                title="Today's Birthdays!",
                description=description,
                color=disnake.Color.random(),
                timestamp=now,
            )

            embed.set_footer(
                text=f"{calendar.month_name[month]} {day}"
            )

            if settings.birthday_announce_embed_image_url:
                embed.set_image(
                    url=settings.birthday_announce_embed_image_url
                )


            if settings.birthday_announce_embed_author_name and settings.birthday_announce_embed_author_icon_url:
                embed.set_author(
                    name=settings.birthday_announce_embed_author_name,
                    icon_url=settings.birthday_announce_embed_author_icon_url,
                )

            try:
                await channel.send(
                    content=(
                        f"<@&{role_id}>"
                        if guild.get_role(role_id)
                        else None
                    ),
                    embed=embed,
                    allowed_mentions=disnake.AllowedMentions(
                        users=True,
                        roles=True,
                    ),
                )
            except disnake.Forbidden:
                continue
            except disnake.HTTPException:
                continue

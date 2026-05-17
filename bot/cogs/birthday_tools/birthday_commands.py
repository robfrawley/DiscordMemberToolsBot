from __future__ import annotations

import calendar

import disnake
from disnake.ext import commands

from bot.db.repos.birthday_repo import birthday_repo
from bot.models.birthday import Birthday
from bot.utils.settings import settings
from bot.utils.logger_setup import Log, get_class_log


MONTH_CHOICES = {
    "January": 1,
    "February": 2,
    "March": 3,
    "April": 4,
    "May": 5,
    "June": 6,
    "July": 7,
    "August": 8,
    "September": 9,
    "October": 10,
    "November": 11,
    "December": 12,
}


class BirthdayCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot: commands.Bot = bot
        self.log: Log = get_class_log(__name__, self.__class__)


    @commands.slash_command(name="birthday-set")
    async def set_birthday(
        self,
        inter: disnake.ApplicationCommandInteraction,
        month: int = commands.Param(choices=MONTH_CHOICES),
        day: commands.Range[int, 1, 31] = commands.Param(),
    ) -> None:
        if inter.guild_id is None:
            await inter.response.send_message(
                "Birthdays can only be set inside a server.",
                ephemeral=True,
            )
            return

        if settings.birthday_tools_enabled is False:
            await inter.response.send_message(
                "The birthday tools are currently disabled.",
                ephemeral=True,
            )
            return

        _, max_day = calendar.monthrange(2000, int(month))

        if int(day) > max_day:
            await inter.response.send_message(
                f"`{calendar.month_name[int(month)]}` only has `{max_day}` days.",
                ephemeral=True,
            )
            return

        birthday = Birthday(
            user_id=int(inter.author.id),
            guild_id=int(inter.guild_id),
            month=int(month),
            day=int(day),
        )

        await birthday_repo.upsert(birthday)
        
        self.log.info(
            f"Set birthday for user '{inter.author}' ({inter.author.id}) in guild '{inter.guild_id}': "
            f"{calendar.month_name[int(month)]} {int(day)}"
        )

        await inter.response.send_message(
            f"Your birthday has been set to **{calendar.month_name[int(month)]} {int(day)}**.",
            ephemeral=True,
        )


    @commands.slash_command(name="birthday-remove")
    async def remove_birthday(
        self,
        inter: disnake.ApplicationCommandInteraction,
    ) -> None:
        if inter.guild_id is None:
            await inter.response.send_message(
                "Birthdays can only be removed inside a server.",
                ephemeral=True,
            )
            return

        if settings.birthday_tools_enabled is False:
            await inter.response.send_message(
                "The birthday tools are currently disabled.",
                ephemeral=True,
            )
            return

        birthday = Birthday(
            user_id=int(inter.author.id),
            guild_id=int(inter.guild_id),
            month=1,
            day=1,
        )

        deleted_count = await birthday_repo.delete(birthday)

        if deleted_count:
            self.log.info(
                f"Removed birthday for user '{inter.author}' ({inter.author.id}) in guild '{inter.guild_id}'."
            )
            message = "Your birthday has been removed."
        else:
            message = "You don't currently have a birthday set."

        await inter.response.send_message(message, ephemeral=True)


    @commands.slash_command(name="birthday-get")
    async def get_birthday(
        self,
        inter: disnake.ApplicationCommandInteraction,
    ) -> None:
        if inter.guild_id is None:
            await inter.response.send_message(
                "Birthdays can only be checked inside a server.",
                ephemeral=True,
            )
            return

        if settings.birthday_tools_enabled is False:
            await inter.response.send_message(
                "The birthday tools are currently disabled.",
                ephemeral=True,
            )
            return

        birthday = await birthday_repo.get_by_user(
            user_id=int(inter.author.id),
            guild_id=int(inter.guild_id),
        )

        if birthday is None:
            message = "You don't currently have a birthday set."
        else:
            message = (
                "Your birthday is set to "
                f"**{calendar.month_name[int(birthday.month)]} {int(birthday.day)}**."
            )

        await inter.response.send_message(message, ephemeral=True)

from disnake.ext import commands
from bot.cogs.birthday_tools.birthday_commands import BirthdayCommands
from bot.cogs.birthday_tools.birthday_tasks import BirthdayTasks


def setup(bot: commands.Bot) -> None:
    bot.add_cog(BirthdayCommands(bot))
    bot.add_cog(BirthdayTasks(bot))

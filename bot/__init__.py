from pathlib import Path

BASE_DIR: Path = Path(__file__).resolve().parent.parent
ENV_FILE_PATH: Path = BASE_DIR / ".env"
COGS_DIR_PATH: Path = BASE_DIR / "bot" / "cogs"
LOG_FILE_PATH: Path = BASE_DIR / "log" / "bot.log"

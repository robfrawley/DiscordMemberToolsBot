from __future__ import annotations

import logging
import inspect
import os
import sys
import copy
import datetime as dt
from dataclasses import dataclass
from logging.handlers import TimedRotatingFileHandler
from typing import Any, MutableMapping, Mapping, Protocol
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler
from rich.traceback import install as rich_traceback_install

from bot import LOG_FILE_PATH


class ClassLoggerAdapter(logging.LoggerAdapter):
    def __init__(self, logger: logging.Logger, extra: Mapping[str, Any]) -> None:
        super().__init__(logger, dict(extra))

    def process(self, msg: Any, kwargs: MutableMapping[str, Any]) -> tuple[Any, MutableMapping[str, Any]]:
        extra = kwargs.get("extra")

        if extra is None:
            extra_dict: dict[str, Any] = {}
        else:
            extra_dict = dict(extra)

        merged: dict[str, Any] = dict(self.extra) # type: ignore[attr-defined]
        merged.update(extra_dict)

        kwargs["extra"] = merged
        return msg, kwargs


class LoggerProtocol(Protocol):
    def debug(self, msg: Any, *args, **kwargs) -> None: ...
    def info(self, msg: Any, *args, **kwargs) -> None: ...
    def warning(self, msg: Any, *args, **kwargs) -> None: ...
    def error(self, msg: Any, *args, **kwargs) -> None: ...
    def exception(self, msg: Any, *args, **kwargs) -> None: ...


@dataclass(frozen=True)
class Log:
    logger: LoggerProtocol

    def debug(self, msg: str, **fields: Any) -> None:
        self.logger.debug(msg, extra={"fields": fields} if fields else None, stacklevel=2)

    def info(self, msg: str, **fields: Any) -> None:
        self.logger.info(msg, extra={"fields": fields} if fields else None, stacklevel=2)

    def warning(self, msg: str, **fields: Any) -> None:
        self.logger.warning(msg, extra={"fields": fields} if fields else None, stacklevel=2)

    def error(self, msg: str, **fields: Any) -> None:
        self.logger.error(msg, extra={"fields": fields} if fields else None, stacklevel=2)

    def exception(self, msg: str, **fields: Any) -> None:
        self.logger.exception(msg, extra={"fields": fields} if fields else None, stacklevel=2)


class QualifiedNameFilter(logging.Filter):
    def __init__(self, skip_prefixes: tuple[str, ...] = ("logging", "rich")) -> None:
        super().__init__()
        self.skip_prefixes = skip_prefixes

    def _inspect_class_name(self) -> str | None:
        frame = inspect.currentframe()
        if frame is None:
            return None

        frame = frame.f_back
        while frame:
            mod = frame.f_globals.get("__name__", "")

            if any(mod.startswith(p) for p in self.skip_prefixes):
                frame = frame.f_back
                continue

            if mod == __name__:
                frame = frame.f_back
                continue

            locals_ = frame.f_locals

            if "self" in locals_:
                return type(locals_["self"]).__name__

            if "cls" in locals_:
                try:
                    return locals_["cls"].__name__
                except Exception:
                    return None

            break

        return None

    def filter(self, record: logging.LogRecord) -> bool:
        base = record.name
        func = record.funcName

        cls = getattr(record, "class_name", None)

        if not cls:
            cls = self._inspect_class_name()

        if cls:
            record.qualname = f"{base}.{cls}.{func}"
        else:
            record.qualname = f"{base}.{func}"

        return True


class FieldRichHandler(RichHandler):
    def render_message(self, record: logging.LogRecord, message: str):
        fields = getattr(record, "fields", None)

        if fields:
            parts = [f"[bold cyan]{k}[/]=[white]{fields[k]!r}[/]" for k in sorted(fields)]
            message = f"{message}  [dim]|[/] " + " ".join(parts)

        temp_record = copy.copy(record)
        temp_record.msg = message
        temp_record.args = ()
        return super().render_message(temp_record, message)


class FieldsFormatter(logging.Formatter):
    default_msec_format = "%s.%03d"

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        dt_value = dt.datetime.fromtimestamp(record.created)
        if datefmt:
            return dt_value.strftime(datefmt)
        return dt_value.strftime("%Y-%m-%d %H:%M:%S.%f")

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)

        fields = getattr(record, "fields", None)
        if not fields:
            return base

        parts = [f"{k}={fields[k]!r}" for k in sorted(fields)]
        return base + " | " + " ".join(parts)


def setup_logging(
    *,
    level: int = logging.INFO,
    log_file_path: Path = Path(LOG_FILE_PATH),
    keep_days: int = 14,
    disnake_level: int = logging.WARNING,
    aiohttp_level: int = logging.WARNING,
    asyncio_level: int = logging.WARNING,
    aiosqlite_level: int = logging.WARNING,
    pil_level: int = logging.WARNING,
    rich_tracebacks: bool = True,
) -> None:
    os.makedirs(log_file_path.parent, exist_ok=True)

    if rich_tracebacks:
        rich_traceback_install(show_locals=False)

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    if sys.stdout.isatty():
        stdout_handler = FieldRichHandler(
            console=Console(),
            rich_tracebacks=rich_tracebacks,
            tracebacks_show_locals=True,
            log_time_format="[%m/%d/%y %H:%M:%S.%f]",
            show_time=True,
            show_level=True,
            show_path=False,
            markup=True,
            omit_repeated_times=False,
        )
        stdout_handler.setFormatter(logging.Formatter("%(qualname)s: %(message)s"))
    else:
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setFormatter(
            FieldsFormatter(
                fmt="%(asctime)s [%(levelname)s] %(qualname)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )

    stdout_handler.setLevel(level)
    stdout_handler.addFilter(QualifiedNameFilter())

    file_handler = TimedRotatingFileHandler(
        log_file_path,
        when="midnight",
        interval=1,
        backupCount=keep_days,
        encoding="utf-8",
        utc=False,
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(
        FieldsFormatter(fmt="%(asctime)s [%(levelname)s] %(qualname)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    )
    file_handler.addFilter(QualifiedNameFilter())

    root.addHandler(stdout_handler)
    root.addHandler(file_handler)

    logging.getLogger("disnake").setLevel(disnake_level)
    logging.getLogger("disnake.http").setLevel(disnake_level)
    logging.getLogger("disnake.gateway").setLevel(disnake_level)
    logging.getLogger("aiohttp").setLevel(aiohttp_level)
    logging.getLogger("asyncio").setLevel(asyncio_level)
    logging.getLogger("aiosqlite").setLevel(aiosqlite_level)
    logging.getLogger("PIL").setLevel(pil_level)
    logging.getLogger("PIL.PngImagePlugin").setLevel(pil_level)


def get_log(name: str) -> Log:
    return Log(logging.getLogger(name))


def get_class_log(name: str, cls: type) -> Log:
    adapter = ClassLoggerAdapter(logging.getLogger(name), {
        "class_name": cls.__name__
    })
    return Log(adapter)

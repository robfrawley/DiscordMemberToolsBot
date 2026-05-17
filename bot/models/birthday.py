from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Birthday:
    user_id: int
    guild_id: int
    month: int
    day: int

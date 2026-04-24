from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dj_cue_system.library.models import Track

COLOR_MAP: dict[str, int] = {
    "pink": 1, "red": 2, "orange": 3, "yellow": 4,
    "green": 5, "aqua": 6, "blue": 7, "purple": 8,
}


@dataclass
class CuePoint:
    name: str
    position_seconds: float
    bar: int
    color: str | None = None


@dataclass
class LoopPoint:
    name: str
    start_seconds: float
    end_seconds: float
    start_bar: int
    end_bar: int


class CueWriter(ABC):
    @abstractmethod
    def write(
        self,
        track: "Track",
        cues: list[CuePoint],
        loops: list[LoopPoint],
    ) -> None: ...

    @abstractmethod
    def finalize(self) -> None: ...

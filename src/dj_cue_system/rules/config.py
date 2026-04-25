from __future__ import annotations
from typing import Literal
import yaml
from pydantic import BaseModel


class QualifierConfig(BaseModel):
    position: Literal["before_midpoint", "after_midpoint", "first_quarter", "last_quarter"] | None = None
    min_duration_bars: int | None = None
    max_duration_bars: int | None = None
    occurrence: str = "first"


ColorName = Literal["pink", "red", "orange", "yellow", "green", "aqua", "blue", "purple"]


class RuleConfig(BaseModel):
    element: str
    type: Literal["memory_cue", "loop"]
    name: str
    offset_bars: int = 0
    length_bars: int | None = None
    color: ColorName | None = None
    qualifier: QualifierConfig | None = None


class RulesetConfig(BaseModel):
    rules: list[RuleConfig]


class PlaylistConfig(BaseModel):
    rulesets: list[str]


class OnsetThresholds(BaseModel):
    vocal: float = 0.02
    drum: float = 0.05
    bass: float = 0.03
    other: float = 0.02


class SettingsConfig(BaseModel):
    demucs_model: str = "htdemucs"
    onset_window_frames: int = 10
    onset_thresholds: OnsetThresholds = OnsetThresholds()


class AppConfig(BaseModel):
    settings: SettingsConfig = SettingsConfig()
    rulesets: dict[str, RulesetConfig]
    playlists: dict[str, PlaylistConfig] = {}
    defaults: PlaylistConfig = PlaylistConfig(rulesets=[])


def load_config(path: str) -> AppConfig:
    with open(path) as f:
        data = yaml.safe_load(f)
    return AppConfig.model_validate(data)

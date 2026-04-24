from dataclasses import dataclass, field


@dataclass
class ExistingCue:
    position_seconds: float
    cue_type: str   # "memory_cue", "hot_cue", "loop", "hot_loop"
    name: str


@dataclass
class Track:
    id: str
    path: str
    title: str
    artist: str
    analysis_data_path: str | None
    existing_cues: list[ExistingCue] = field(default_factory=list)
    playlists: list[str] = field(default_factory=list)

    @property
    def has_memory_cues(self) -> bool:
        return any(c.cue_type == "memory_cue" for c in self.existing_cues)

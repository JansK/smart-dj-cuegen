from dataclasses import dataclass, field, asdict
import json
from datetime import datetime, timezone


@dataclass
class BackupCue:
    type: str                              # "memory_cue" or "loop"
    name: str
    position_seconds: float | None = None  # memory_cue
    color: str | None = None               # memory_cue
    start_seconds: float | None = None     # loop
    end_seconds: float | None = None       # loop


@dataclass
class BackupTrack:
    id: str
    path: str
    artist: str
    title: str
    cues: list[BackupCue] = field(default_factory=list)


@dataclass
class BackupFile:
    rekordbox_db: str
    tracks: list[BackupTrack]
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )


def serialize_backup(backup: BackupFile, path: str) -> None:
    with open(path, "w") as f:
        json.dump(asdict(backup), f, indent=2)


def deserialize_backup(path: str) -> BackupFile:
    with open(path) as f:
        data = json.load(f)
    tracks = [
        BackupTrack(
            id=t["id"], path=t["path"], artist=t["artist"], title=t["title"],
            cues=[BackupCue(**c) for c in t["cues"]],
        )
        for t in data["tracks"]
    ]
    return BackupFile(
        created_at=data["created_at"],
        rekordbox_db=data["rekordbox_db"],
        tracks=tracks,
    )

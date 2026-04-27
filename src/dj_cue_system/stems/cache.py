from __future__ import annotations
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from dj_cue_system.analysis.models import StemOnsets

_CACHE_DIR = Path.home() / ".dj-cue" / "stems-cache"


def _cache_dir() -> Path:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return _CACHE_DIR


def _cache_key(audio_path: str) -> str:
    abs_path = os.path.abspath(audio_path)
    return hashlib.sha256(abs_path.encode()).hexdigest()[:16]


@dataclass
class CacheEntry:
    audio_path: str
    source: str
    computed_at: str
    vocal: float | None
    drum: float | None
    bass: float | None
    other: float | None


def load(audio_path: str) -> tuple[StemOnsets, str] | None:
    path = _cache_dir() / f"{_cache_key(audio_path)}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    onsets = StemOnsets(
        vocal=data.get("vocal"),
        drum=data.get("drum"),
        bass=data.get("bass"),
        other=data.get("other"),
    )
    return onsets, data["source"]


def save(audio_path: str, onsets: StemOnsets, source: str) -> None:
    path = _cache_dir() / f"{_cache_key(audio_path)}.json"
    data = {
        "audio_path": os.path.abspath(audio_path),
        "source": source,
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "vocal": onsets.vocal,
        "drum": onsets.drum,
        "bass": onsets.bass,
        "other": onsets.other,
    }
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.rename(path)


def list_entries() -> list[CacheEntry]:
    entries = []
    for f in _cache_dir().glob("*.json"):
        try:
            data = json.loads(f.read_text())
            entries.append(CacheEntry(
                audio_path=data["audio_path"],
                source=data["source"],
                computed_at=data["computed_at"],
                vocal=data.get("vocal"),
                drum=data.get("drum"),
                bass=data.get("bass"),
                other=data.get("other"),
            ))
        except Exception:
            continue
    return sorted(entries, key=lambda e: e.audio_path)


def clear(audio_path: str | None = None) -> int:
    count = 0
    if audio_path is not None:
        path = _cache_dir() / f"{_cache_key(audio_path)}.json"
        if path.exists():
            path.unlink()
            count = 1
    else:
        for f in _cache_dir().glob("*.json"):
            f.unlink()
            count += 1
    return count

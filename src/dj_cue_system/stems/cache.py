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


def _hq_path(audio_path: str) -> Path:
    return _cache_dir() / f"{_cache_key(audio_path)}_hq.json"


def _lq_path(audio_path: str) -> Path:
    return _cache_dir() / f"{_cache_key(audio_path)}_lq.json"


@dataclass
class CacheEntry:
    audio_path: str
    source: str
    computed_at: str
    hq: bool
    vocal: float | None
    drum: float | None
    bass: float | None
    other: float | None


def _read_entry(path: Path, abs_path: str) -> tuple[StemOnsets, str] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        if data.get("audio_path") != abs_path:
            return None
        onsets = StemOnsets(
            vocal=data.get("vocal"),
            drum=data.get("drum"),
            bass=data.get("bass"),
            other=data.get("other"),
        )
        return onsets, data["source"]
    except (json.JSONDecodeError, KeyError, OSError):
        return None


def load(audio_path: str, hq: bool = False) -> tuple[StemOnsets, str] | None:
    abs_path = os.path.abspath(audio_path)
    if hq:
        result = _read_entry(_hq_path(audio_path), abs_path)
        if result is not None:
            return result
        return _read_entry(_lq_path(audio_path), abs_path)
    else:
        result = _read_entry(_lq_path(audio_path), abs_path)
        if result is not None:
            return result
        return _read_entry(_hq_path(audio_path), abs_path)


def save(audio_path: str, onsets: StemOnsets, source: str) -> None:
    path = _hq_path(audio_path) if source == "demucs" else _lq_path(audio_path)
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
            is_hq = f.stem.endswith("_hq")
            entries.append(CacheEntry(
                audio_path=data["audio_path"],
                source=data["source"],
                computed_at=data["computed_at"],
                hq=is_hq,
                vocal=data.get("vocal"),
                drum=data.get("drum"),
                bass=data.get("bass"),
                other=data.get("other"),
            ))
        except (json.JSONDecodeError, KeyError, OSError):
            continue
    return sorted(entries, key=lambda e: (e.audio_path, e.hq))


def clear(audio_path: str | None = None) -> int:
    count = 0
    if audio_path is not None:
        for path in (_hq_path(audio_path), _lq_path(audio_path)):
            if path.exists():
                path.unlink()
                count += 1
    else:
        for f in _cache_dir().glob("*.json"):
            f.unlink()
            count += 1
    return count

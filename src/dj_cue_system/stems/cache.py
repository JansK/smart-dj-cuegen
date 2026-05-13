from __future__ import annotations
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from dj_cue_system.analysis.models import BarEnergy, StemOnsets

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
    vocal_first_onset: float | None
    drum_first_onset: float | None
    bass_first_onset: float | None
    other_first_onset: float | None
    drum_bar_energies: list[float] | None = None
    bass_bar_energies: list[float] | None = None
    vocal_bar_energies: list[float] | None = None
    other_bar_energies: list[float] | None = None


def _read_entry(path: Path, abs_path: str) -> tuple[StemOnsets, BarEnergy | None, str] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        if data.get("audio_path") != abs_path:
            return None
        onsets = StemOnsets(
            vocal_first_onset=data.get("vocal_first_onset"),
            drum_first_onset=data.get("drum_first_onset"),
            bass_first_onset=data.get("bass_first_onset"),
            other_first_onset=data.get("other_first_onset"),
        )
        drum_b = data.get("drum_bar_energies")
        bass_b = data.get("bass_bar_energies")
        vocal_b = data.get("vocal_bar_energies")
        other_b = data.get("other_bar_energies")
        bar_energy = (
            BarEnergy(
                drum_bar_energies=drum_b,
                bass_bar_energies=bass_b,
                vocal_bar_energies=vocal_b,
                other_bar_energies=other_b,
            )
            if all(x is not None for x in [drum_b, bass_b, vocal_b, other_b])
            else None
        )
        return onsets, bar_energy, data["source"]
    except (json.JSONDecodeError, KeyError, OSError):
        return None


def load(audio_path: str, hq: bool = False) -> tuple[StemOnsets, BarEnergy | None, str] | None:
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


def save(audio_path: str, onsets: StemOnsets, source: str, bar_energy: BarEnergy | None = None) -> None:
    path = _hq_path(audio_path) if source == "demucs" else _lq_path(audio_path)
    data = {
        "audio_path": os.path.abspath(audio_path),
        "source": source,
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "vocal_first_onset": onsets.vocal_first_onset,
        "drum_first_onset": onsets.drum_first_onset,
        "bass_first_onset": onsets.bass_first_onset,
        "other_first_onset": onsets.other_first_onset,
    }
    if bar_energy is not None:
        data["drum_bar_energies"] = bar_energy.drum_bar_energies
        data["bass_bar_energies"] = bar_energy.bass_bar_energies
        data["vocal_bar_energies"] = bar_energy.vocal_bar_energies
        data["other_bar_energies"] = bar_energy.other_bar_energies
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
                vocal_first_onset=data.get("vocal_first_onset"),
                drum_first_onset=data.get("drum_first_onset"),
                bass_first_onset=data.get("bass_first_onset"),
                other_first_onset=data.get("other_first_onset"),
                drum_bar_energies=data.get("drum_bar_energies"),
                bass_bar_energies=data.get("bass_bar_energies"),
                vocal_bar_energies=data.get("vocal_bar_energies"),
                other_bar_energies=data.get("other_bar_energies"),
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

from dataclasses import dataclass
from pyrekordbox.anlz import AnlzFile


@dataclass
class BeatGridResult:
    bpm: float
    downbeats: list[float]   # seconds
    total_bars: int


@dataclass
class PhraseEntry:
    beat: int        # beat number (1-indexed) where phrase starts
    raw_label: str   # normalized label e.g. "verse", "chorus"
    mood: str        # "low", "mid", "high"


def parse_beat_grid(dat_path: str) -> BeatGridResult:
    anlz = AnlzFile.parse_file(dat_path)
    tag = anlz.getone("PQTZ")
    beats = tag.beats

    downbeats = [b.time / 1000.0 for b in beats if b.beat_number == 1]
    total_bars = len(downbeats)
    bpm = beats[0].tempo / 100.0 if beats else 0.0

    return BeatGridResult(bpm=bpm, downbeats=downbeats, total_bars=total_bars)


_MOOD_INT_TO_STR = {1: "high", 2: "mid", 3: "low"}

_NORMALIZATION_MAP: dict[str, str] = {
    "intro": "intro",
    "chorus": "chorus",
    "bridge": "bridge",
    "outro": "outro",
    "verse1": "verse", "verse1b": "verse", "verse1c": "verse",
    "verse2": "verse", "verse2b": "verse", "verse2c": "verse",
    "verse3": "verse", "verse4": "verse", "verse5": "verse", "verse6": "verse",
    "up": "up",
    "down": "down",
}

_RAW_MAP: dict[str, str] = {
    "up": "up",
    "down": "down",
}


def normalize_phrase_label(label: str, mood: str, normalized: bool = True) -> str:
    key = label.lower()
    if not normalized:
        return _RAW_MAP.get(key, _NORMALIZATION_MAP.get(key, key))
    return _NORMALIZATION_MAP.get(key, key)


def parse_phrases(ext_path: str) -> list[PhraseEntry]:
    anlz = AnlzFile.parse_file(ext_path)
    tag = anlz.getone("PPHD")
    mood_str = _MOOD_INT_TO_STR.get(tag.mood, "mid")

    result = []
    for entry in tag.phrases:
        raw = str(entry.kind).split(".")[-1]
        normalized = normalize_phrase_label(raw, mood_str)
        result.append(PhraseEntry(beat=entry.beat, raw_label=normalized, mood=mood_str))
    return result

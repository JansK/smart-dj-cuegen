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
    tag = anlz.get_tag("PQTZ")

    # .beats is a numpy array of bar-position values (1, 2, 3, 4)
    # .times is a numpy array of timestamps in seconds
    # .bpms is a numpy array of BPM values (already in BPM, not ×100)
    downbeats = [float(t) for b, t in zip(tag.beats, tag.times) if b == 1]
    total_bars = len(downbeats)
    bpm = float(tag.bpms[0]) if len(tag.bpms) > 0 else 0.0

    return BeatGridResult(bpm=bpm, downbeats=downbeats, total_bars=total_bars)


_MOOD_INT_TO_STR = {1: "high", 2: "mid", 3: "low"}

# PSSI kind → phrase label for each mood tier.
# mood=1 (high): 1=intro 2=up 3=down 4=chorus 5=verse 6=bridge 7=outro
# mood=2 (mid):  1=intro 2=verse1 3=verse2 4=bridge 5=outro
# mood=3 (low):  1=intro 2=verse1 3=verse2 4=bridge 5=outro
_PSSI_KIND_TO_LABEL: dict[int, dict[int, str]] = {
    1: {1: "intro", 2: "up", 3: "down", 4: "chorus", 5: "verse1", 6: "bridge", 7: "outro"},
    2: {1: "intro", 2: "verse1", 3: "verse2", 4: "bridge", 5: "outro"},
    3: {1: "intro", 2: "verse1", 3: "verse2", 4: "bridge", 5: "outro"},
}

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
    tag = anlz.get_tag("PSSI")
    mood_int = tag.content.mood
    mood_str = _MOOD_INT_TO_STR.get(mood_int, "mid")
    kind_map = _PSSI_KIND_TO_LABEL.get(mood_int, _PSSI_KIND_TO_LABEL[2])

    result = []
    for entry in tag.content.entries:
        raw = kind_map.get(entry.kind, f"kind{entry.kind}")
        normalized = normalize_phrase_label(raw, mood_str)
        result.append(PhraseEntry(beat=entry.beat, raw_label=normalized, mood=mood_str))
    return result

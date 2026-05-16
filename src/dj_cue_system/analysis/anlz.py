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
    raw_label: str   # raw Rekordbox label e.g. "verse1", "chorus"
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
# Derived from library-wide survey + Pioneer ANLZ format documentation.
# mood=1 (high):  kinds seen in practice: 1,2,3,5,6
# mood=2 (mid):   kinds seen in practice: 1-10
# mood=3 (low):   kinds seen in practice: 1-9
_PSSI_KIND_TO_LABEL: dict[int, dict[int, str]] = {
    1: {
        1: "intro", 2: "up", 3: "down", 4: "verse1",
        5: "chorus", 6: "outro", 7: "bridge",
    },
    2: {
        1: "intro",
        2: "verse1", 3: "verse2", 4: "verse3", 5: "verse4",
        6: "verse5", 7: "verse6", 8: "bridge",
        9: "chorus", 10: "outro",
    },
    3: {
        1: "intro",
        2: "verse1", 3: "verse1", 4: "verse1", 5: "verse2",
        6: "verse2", 7: "verse2", 8: "bridge",
        9: "chorus", 10: "outro",
    },
}

def parse_phrases(ext_path: str) -> list[PhraseEntry]:
    anlz = AnlzFile.parse_file(ext_path)
    tag = anlz.get_tag("PSSI")
    mood_int = tag.content.mood
    mood_str = _MOOD_INT_TO_STR.get(mood_int, "mid")
    kind_map = _PSSI_KIND_TO_LABEL.get(mood_int, _PSSI_KIND_TO_LABEL[2])

    result = []
    for entry in tag.content.entries:
        label = kind_map.get(entry.kind, f"kind{entry.kind}")
        result.append(PhraseEntry(beat=entry.beat, raw_label=label, mood=mood_str))
    return result

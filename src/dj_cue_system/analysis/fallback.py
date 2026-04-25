from __future__ import annotations
from dj_cue_system.analysis.models import AnalysisResult, Section, StemOnsets
from dj_cue_system.analysis.bar_utils import timestamp_to_bar

try:
    import allin1
except Exception:  # pragma: no cover  (madmom not installed in test env)
    allin1 = None  # type: ignore[assignment]


def allin1_available() -> bool:
    return allin1 is not None


def analyze_with_allin1(audio_path: str) -> AnalysisResult:
    if allin1 is None:
        raise RuntimeError(
            "The 'allin1' package is not available (its dependency 'madmom' failed to install — "
            "madmom does not support Python 3.12+).\n\n"
            "For tracks in your Rekordbox library, use --library or --playlist instead of passing "
            "a bare file path. That path uses Rekordbox's own ANLZ analysis files and does not "
            "require allin1.\n\n"
            "For tracks not yet in Rekordbox, analyze them in Rekordbox first, then re-run."
        )
    result = allin1.analyze(audio_path)

    downbeats: list[float] = list(result.downbeats)
    total_bars = len(downbeats)

    sections = []
    for seg in result.segments:
        start_bar = timestamp_to_bar(seg.start, downbeats)
        end_bar = timestamp_to_bar(seg.end, downbeats)
        sections.append(Section(
            label=seg.label,
            start_bar=start_bar,
            end_bar=end_bar,
            start_time=float(seg.start),
            end_time=float(seg.end),
        ))

    return AnalysisResult(
        bpm=float(result.bpm),
        downbeats=downbeats,
        total_bars=total_bars,
        sections=sections,
        stem_onsets=StemOnsets(),
        audio_path=audio_path,
        anlz_source=False,
    )

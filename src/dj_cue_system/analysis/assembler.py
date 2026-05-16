from dj_cue_system.analysis.models import Section
from dj_cue_system.analysis.anlz import BeatGridResult, PhraseEntry
from dj_cue_system.analysis.bar_utils import timestamp_to_bar


def build_sections(
    phrases: list[PhraseEntry],
    beat_grid: BeatGridResult,
    all_beat_times: list[float],
) -> list[Section]:
    """Convert phrase entries (1-indexed beat numbers) into Section objects."""
    if not phrases:
        return []

    def beat_to_time(beat_1indexed: int) -> float:
        idx = beat_1indexed - 1
        if idx < 0:
            return all_beat_times[0] if all_beat_times else 0.0
        if idx >= len(all_beat_times):
            return all_beat_times[-1] if all_beat_times else 0.0
        return all_beat_times[idx]

    raw = []
    for i, phrase in enumerate(phrases):
        start_time = beat_to_time(phrase.beat)
        start_bar = timestamp_to_bar(start_time, beat_grid.downbeats)

        if i + 1 < len(phrases):
            end_time = beat_to_time(phrases[i + 1].beat)
            end_bar = timestamp_to_bar(end_time, beat_grid.downbeats)
        else:
            end_time = beat_grid.downbeats[-1] if beat_grid.downbeats else start_time
            end_bar = beat_grid.total_bars

        raw.append(Section(
            label=phrase.raw_label,
            start_bar=start_bar,
            end_bar=end_bar,
            start_time=start_time,
            end_time=end_time,
        ))

    # Merge consecutive entries with the same label into one section,
    # matching how Rekordbox visually groups adjacent same-kind phrase blocks.
    merged = [raw[0]]
    for s in raw[1:]:
        if s.label == merged[-1].label:
            prev = merged[-1]
            merged[-1] = Section(
                label=prev.label,
                start_bar=prev.start_bar,
                end_bar=s.end_bar,
                start_time=prev.start_time,
                end_time=s.end_time,
            )
        else:
            merged.append(s)
    return merged

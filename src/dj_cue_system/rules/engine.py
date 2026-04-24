import warnings
from dj_cue_system.analysis.models import AnalysisResult, Section
from dj_cue_system.analysis.bar_utils import bar_to_timestamp, timestamp_to_bar
from dj_cue_system.rules.config import AppConfig, RuleConfig, QualifierConfig
from dj_cue_system.writers.base import CuePoint, LoopPoint

_SECTION_ELEMENTS = {
    "intro_start", "intro_end", "verse_start", "chorus_start",
    "bridge_start", "break_start", "outro_start", "outro_end",
    "up_start", "down_start",
}
_STEM_ONSET_ELEMENTS = {
    "first_vocal_onset": "vocal",
    "first_drum_onset": "drum",
    "first_bass_onset": "bass",
    "first_other_onset": "other",
}


def _get_sections_for_element(element: str, sections: list[Section]) -> list[Section]:
    label = element.replace("_start", "").replace("_end", "")
    return [s for s in sections if s.label == label]


def _apply_qualifier(
    candidates: list[Section],
    qualifier: QualifierConfig | None,
    total_bars: int,
) -> Section | None:
    if not candidates:
        return None
    if qualifier is None:
        return candidates[0]

    filtered = list(candidates)
    mid = total_bars / 2
    q1 = total_bars / 4
    q3 = 3 * total_bars / 4

    if qualifier.position:
        if qualifier.position == "after_midpoint":
            filtered = [s for s in filtered if s.start_bar >= mid]
        elif qualifier.position == "before_midpoint":
            filtered = [s for s in filtered if s.start_bar < mid]
        elif qualifier.position == "first_quarter":
            filtered = [s for s in filtered if s.start_bar < q1]
        elif qualifier.position == "last_quarter":
            filtered = [s for s in filtered if s.start_bar >= q3]

    if qualifier.min_duration_bars is not None:
        filtered = [s for s in filtered if s.duration_bars >= qualifier.min_duration_bars]
    if qualifier.max_duration_bars is not None:
        filtered = [s for s in filtered if s.duration_bars <= qualifier.max_duration_bars]

    if not filtered:
        return None

    occ = qualifier.occurrence
    if occ == "first":
        return filtered[0]
    if occ == "last":
        return filtered[-1]
    try:
        idx = int(occ) - 1
        return filtered[idx] if idx < len(filtered) else None
    except (ValueError, IndexError):
        return filtered[0]


def _resolve_rule(
    rule: RuleConfig,
    result: AnalysisResult,
) -> CuePoint | LoopPoint | None:
    downbeats = result.downbeats

    if rule.element in _STEM_ONSET_ELEMENTS:
        stem_name = _STEM_ONSET_ELEMENTS[rule.element]
        onset_time = getattr(result.stem_onsets, stem_name)
        if onset_time is None:
            warnings.warn(f"Rule '{rule.element}': stem onset not detected, skipping")
            return None
        anchor_bar = timestamp_to_bar(onset_time, downbeats)
    elif rule.element in _SECTION_ELEMENTS:
        candidates = _get_sections_for_element(rule.element, result.sections)
        section = _apply_qualifier(candidates, rule.qualifier, result.total_bars)
        if section is None:
            warnings.warn(f"Rule '{rule.element}': no matching section, skipping")
            return None
        use_end = rule.element.endswith("_end")
        anchor_bar = section.end_bar if use_end else section.start_bar
    else:
        warnings.warn(f"Unknown element '{rule.element}', skipping")
        return None

    if rule.type == "memory_cue":
        final_bar = max(0, anchor_bar + rule.offset_bars)
        if final_bar != anchor_bar + rule.offset_bars:
            warnings.warn(
                f"Rule '{rule.name}': offset clamped to bar 0 "
                f"(computed bar {anchor_bar + rule.offset_bars})"
            )
        position_s = bar_to_timestamp(final_bar, downbeats)
        return CuePoint(name=rule.name, position_seconds=position_s, bar=final_bar, color=rule.color)

    if rule.type == "loop":
        length = rule.length_bars or 16
        start_bar = anchor_bar
        end_bar = min(start_bar + length, result.total_bars)
        start_s = bar_to_timestamp(start_bar, downbeats)
        end_s = bar_to_timestamp(end_bar, downbeats)
        return LoopPoint(
            name=rule.name,
            start_seconds=start_s,
            end_seconds=end_s,
            start_bar=start_bar,
            end_bar=end_bar,
        )

    return None


def resolve_cues(
    result: AnalysisResult,
    config: AppConfig,
    playlists: list[str],
    ruleset_override: str | None = None,
) -> tuple[list[CuePoint], list[LoopPoint]]:
    if ruleset_override:
        ruleset_names = [ruleset_override]
    elif playlists:
        ruleset_names = []
        for pl in playlists:
            if pl in config.playlists:
                ruleset_names.extend(config.playlists[pl].rulesets)
        if not ruleset_names:
            ruleset_names = list(config.defaults.rulesets)
    else:
        ruleset_names = list(config.defaults.rulesets)

    cues: list[CuePoint] = []
    loops: list[LoopPoint] = []
    seen_cue_bars: set[int] = set()
    seen_loop_bars: set[int] = set()

    for name in ruleset_names:
        ruleset = config.rulesets.get(name)
        if ruleset is None:
            warnings.warn(f"Ruleset '{name}' not found in config")
            continue
        for rule in ruleset.rules:
            item = _resolve_rule(rule, result)
            if item is None:
                continue
            if isinstance(item, CuePoint):
                if item.bar not in seen_cue_bars:
                    seen_cue_bars.add(item.bar)
                    cues.append(item)
            elif isinstance(item, LoopPoint):
                if item.start_bar not in seen_loop_bars:
                    seen_loop_bars.add(item.start_bar)
                    loops.append(item)

    return cues, loops

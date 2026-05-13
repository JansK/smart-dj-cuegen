import numpy as np
from dj_cue_system.analysis.models import BarEnergy, Section
from dj_cue_system.rules.config import StableDetectionConfig

_INACTIVE_ENERGY_FLOOR = 0.01


def _is_stable_window(
    stems: list[list[float]],
    a: int,
    b: int,
    cv_threshold: float,
) -> bool:
    for s in stems:
        window = np.array(s[a:b], dtype=float)
        mean = float(np.mean(window))
        if mean <= _INACTIVE_ENERGY_FLOOR:
            continue
        if float(np.std(window)) / mean >= cv_threshold:
            return False
    return True


def _find_longest_stable(
    stems: list[list[float]],
    zone_start: int,
    zone_end: int,
    config: StableDetectionConfig,
) -> tuple[int, int] | None:
    """Find the longest stable window via exhaustive O(N²) search."""
    best: tuple[int, int] | None = None
    best_len = 0
    for a in range(zone_start, zone_end):
        for b in range(a + config.min_stable_bars, zone_end + 1):
            if b - a > best_len and _is_stable_window(stems, a, b, config.stability_cv_threshold):
                best_len = b - a
                best = (a, b)
    return best


def detect_stable_regions(
    bar_energy: BarEnergy,
    downbeats: list[float],
    config: StableDetectionConfig,
) -> tuple[Section | None, Section | None]:
    stems = [
        bar_energy.drum_bar_energies,
        bar_energy.bass_bar_energies,
        bar_energy.vocal_bar_energies,
        bar_energy.other_bar_energies,
    ]
    n_bars = len(downbeats)
    intro_zone_end = min(config.max_scan_bars, n_bars)
    outro_zone_start = max(0, n_bars - config.max_scan_bars)

    def make_section(label: str, window: tuple[int, int]) -> Section:
        a, b = window
        return Section(
            label=label,
            start_bar=a,
            end_bar=b,
            start_time=downbeats[a],
            end_time=downbeats[b] if b < len(downbeats) else downbeats[-1],
        )

    intro_win = _find_longest_stable(stems, 0, intro_zone_end, config)
    outro_win = _find_longest_stable(stems, outro_zone_start, n_bars, config)

    return (
        make_section("stable_intro", intro_win) if intro_win else None,
        make_section("stable_outro", outro_win) if outro_win else None,
    )

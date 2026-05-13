import numpy as np
from dj_cue_system.analysis.models import BarEnergy, Section
from dj_cue_system.rules.config import BreakDetectionConfig

_INACTIVE_ENERGY_FLOOR = 0.01


def detect_breaks(
    bar_energy: BarEnergy,
    downbeats: list[float],
    config: BreakDetectionConfig,
) -> list[Section]:
    stems = [
        bar_energy.drum_bar_energies,
        bar_energy.bass_bar_energies,
        bar_energy.vocal_bar_energies,
        bar_energy.other_bar_energies,
    ]

    typical = []
    for s in stems:
        nonzero = [v for v in s if v > 0]
        typical.append(float(np.median(nonzero)) if nonzero else 0.0)

    active = [t > _INACTIVE_ENERGY_FLOOR for t in typical]

    n_bars = len(downbeats)
    silent_counts = []
    for i in range(n_bars):
        count = sum(
            1 for s, t, a in zip(stems, typical, active)
            if a and i < len(s) and s[i] < config.silence_fraction * t
        )
        silent_counts.append(count)

    runs: list[tuple[int, int]] = []
    in_break = False
    start = 0
    for i, count in enumerate(silent_counts):
        if count >= config.min_stems_silent:
            if not in_break:
                in_break = True
                start = i
        else:
            if in_break:
                if i - start >= config.min_bars:
                    runs.append((start, i))
                in_break = False
    if in_break and n_bars - start >= config.min_bars:
        runs.append((start, n_bars))

    return [
        Section(
            label="break",
            start_bar=s,
            end_bar=e,
            start_time=downbeats[s],
            end_time=downbeats[e] if e < len(downbeats) else downbeats[-1],
        )
        for s, e in runs
    ]

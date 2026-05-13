import pytest
from dj_cue_system.analysis.models import BarEnergy
from dj_cue_system.analysis.break_detect import detect_breaks
from dj_cue_system.rules.config import BreakDetectionConfig


def _downbeats(n):
    return [float(i) for i in range(n)]


def _bar_energy(n, drum=None, bass=None, vocal=None, other=None):
    return BarEnergy(
        drum_bar_energies=drum if drum is not None else [1.0] * n,
        bass_bar_energies=bass if bass is not None else [1.0] * n,
        vocal_bar_energies=vocal if vocal is not None else [0.0] * n,
        other_bar_energies=other if other is not None else [1.0] * n,
    )


def test_detect_breaks_single_break():
    n = 16
    drum = [1.0] * n
    bass = [1.0] * n
    for i in range(8, 12):
        drum[i] = 0.05
        bass[i] = 0.05
    breaks = detect_breaks(_bar_energy(n, drum=drum, bass=bass), _downbeats(n), BreakDetectionConfig())
    assert len(breaks) == 1
    assert breaks[0].label == "break"
    assert breaks[0].start_bar == 8
    assert breaks[0].end_bar == 12
    assert breaks[0].start_time == pytest.approx(8.0)
    assert breaks[0].end_time == pytest.approx(12.0)


def test_detect_breaks_no_break_when_only_one_stem_silent():
    n = 16
    drum = [1.0] * n
    bass = [1.0] * n
    for i in range(8, 12):
        drum[i] = 0.05  # only drums drop
    breaks = detect_breaks(_bar_energy(n, drum=drum, bass=bass), _downbeats(n), BreakDetectionConfig())
    assert breaks == []


def test_detect_breaks_too_short():
    n = 16
    drum = [1.0] * n
    bass = [1.0] * n
    for i in range(8, 11):  # 3 bars < min_bars=4
        drum[i] = 0.05
        bass[i] = 0.05
    breaks = detect_breaks(_bar_energy(n, drum=drum, bass=bass), _downbeats(n), BreakDetectionConfig())
    assert breaks == []


def test_detect_breaks_excludes_inactive_stems():
    # Only drums active; dropping drums gives 1 silent stem, below min_stems_silent=2
    n = 16
    drum = [1.0] * n
    for i in range(8, 12):
        drum[i] = 0.05
    be = BarEnergy(
        drum_bar_energies=drum,
        bass_bar_energies=[0.0] * n,
        vocal_bar_energies=[0.0] * n,
        other_bar_energies=[0.0] * n,
    )
    breaks = detect_breaks(be, _downbeats(n), BreakDetectionConfig())
    assert breaks == []


def test_detect_breaks_multiple_breaks():
    n = 32
    drum = [1.0] * n
    bass = [1.0] * n
    for i in range(4, 8):
        drum[i] = 0.05
        bass[i] = 0.05
    for i in range(20, 24):
        drum[i] = 0.05
        bass[i] = 0.05
    breaks = detect_breaks(_bar_energy(n, drum=drum, bass=bass), _downbeats(n), BreakDetectionConfig())
    assert len(breaks) == 2
    assert breaks[0].start_bar == 4
    assert breaks[0].end_bar == 8
    assert breaks[1].start_bar == 20
    assert breaks[1].end_bar == 24


def test_detect_breaks_respects_config():
    n = 16
    drum = [1.0] * n
    bass = [1.0] * n
    other = [1.0] * n
    for i in range(8, 11):  # 3 bars
        drum[i] = 0.05
        bass[i] = 0.05
        other[i] = 0.05
    be = _bar_energy(n, drum=drum, bass=bass, other=other)
    cfg = BreakDetectionConfig(min_bars=3, min_stems_silent=3)
    breaks = detect_breaks(be, _downbeats(n), cfg)
    assert len(breaks) == 1
    assert breaks[0].start_bar == 8

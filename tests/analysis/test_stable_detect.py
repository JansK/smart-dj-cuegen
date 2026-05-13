import pytest
from dj_cue_system.analysis.models import BarEnergy
from dj_cue_system.analysis.stable_detect import detect_stable_regions
from dj_cue_system.rules.config import StableDetectionConfig


def _downbeats(n):
    return [float(i) for i in range(n)]


def test_detect_stable_intro_constant_energy():
    n = 32
    # First 16 bars: constant drums. Last 16: drums drop and spike alternately.
    drum = [1.0] * 16 + [3.0, 0.1] * 8
    be = BarEnergy(
        drum_bar_energies=drum,
        bass_bar_energies=[1.0] * n,
        vocal_bar_energies=[0.0] * n,
        other_bar_energies=[0.0] * n,
    )
    cfg = StableDetectionConfig(max_scan_bars=n, min_stable_bars=8, stability_cv_threshold=0.4)
    intro, _ = detect_stable_regions(be, _downbeats(n), cfg)
    assert intro is not None
    assert intro.label == "stable_intro"
    assert intro.start_bar == 0
    assert intro.end_bar == 16


def test_detect_stable_intro_not_at_bar_zero():
    n = 32
    # Bars 0-3: drums noisy (3.0), bars 4-19: stable (1.0), bars 20-31: stable (3.0).
    # Exhaustive O(N²) search finds [15, 32) as longest (17 bars, CV=0.378 < 0.4),
    # longer than [4, 20) (16 bars).
    drum = [3.0] * 4 + [1.0] * 16 + [3.0] * 12
    be = BarEnergy(
        drum_bar_energies=drum,
        bass_bar_energies=[0.0] * n,
        vocal_bar_energies=[0.0] * n,
        other_bar_energies=[0.0] * n,
    )
    cfg = StableDetectionConfig(max_scan_bars=n, min_stable_bars=8, stability_cv_threshold=0.4)
    intro, _ = detect_stable_regions(be, _downbeats(n), cfg)
    assert intro is not None
    assert intro.start_bar == 15
    assert intro.end_bar == 32


def test_detect_stable_no_intro_when_stable_region_too_short():
    n = 16
    # Only 6 bars of stable energy at the start — below min_stable_bars=8
    drum = [1.0] * 6 + [3.0, 0.1] * 5
    be = BarEnergy(
        drum_bar_energies=drum,
        bass_bar_energies=[0.0] * n,
        vocal_bar_energies=[0.0] * n,
        other_bar_energies=[0.0] * n,
    )
    cfg = StableDetectionConfig(max_scan_bars=n, min_stable_bars=8, stability_cv_threshold=0.4)
    intro, _ = detect_stable_regions(be, _downbeats(n), cfg)
    assert intro is None  # 6 bars < min_stable_bars=8


def test_detect_stable_outro():
    n = 32
    # First 24 bars: chaotic. Last 8 bars: stable.
    drum = [0.1, 3.0] * 12 + [1.0] * 8
    be = BarEnergy(
        drum_bar_energies=drum,
        bass_bar_energies=[0.0] * n,
        vocal_bar_energies=[0.0] * n,
        other_bar_energies=[0.0] * n,
    )
    cfg = StableDetectionConfig(max_scan_bars=n, min_stable_bars=8, stability_cv_threshold=0.4)
    _, outro = detect_stable_regions(be, _downbeats(n), cfg)
    assert outro is not None
    assert outro.label == "stable_outro"
    assert outro.start_bar == 24
    assert outro.end_bar == n


def test_detect_stable_returns_none_for_both_when_all_chaotic():
    n = 32
    # Alternating high/low — high CV everywhere
    drum = [3.0, 0.1] * 16
    be = BarEnergy(
        drum_bar_energies=drum,
        bass_bar_energies=[0.0] * n,
        vocal_bar_energies=[0.0] * n,
        other_bar_energies=[0.0] * n,
    )
    cfg = StableDetectionConfig(max_scan_bars=n, min_stable_bars=8, stability_cv_threshold=0.4)
    intro, outro = detect_stable_regions(be, _downbeats(n), cfg)
    assert intro is None
    assert outro is None


def test_detect_stable_section_times():
    n = 16
    drum = [1.0] * n
    be = BarEnergy(
        drum_bar_energies=drum,
        bass_bar_energies=[0.0] * n,
        vocal_bar_energies=[0.0] * n,
        other_bar_energies=[0.0] * n,
    )
    cfg = StableDetectionConfig(max_scan_bars=n, min_stable_bars=8, stability_cv_threshold=0.4)
    intro, _ = detect_stable_regions(be, _downbeats(n), cfg)
    assert intro is not None
    assert intro.start_time == pytest.approx(0.0)
    assert intro.end_time == pytest.approx(float(n - 1))  # downbeats[-1]

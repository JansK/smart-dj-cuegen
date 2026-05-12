import pytest
import numpy as np
from dj_cue_system.analysis.energy import compute_bar_energy
from dj_cue_system.analysis.models import BarEnergy


def test_compute_bar_energy_returns_bar_energy():
    sr = 100
    downbeats = [0.0, 1.0, 2.0, 3.0]
    audio = np.zeros(400)
    result = compute_bar_energy(audio, audio, audio, audio, sr, downbeats)
    assert isinstance(result, BarEnergy)


def test_compute_bar_energy_correct_bar_count():
    sr = 100
    downbeats = [0.0, 1.0, 2.0, 3.0]
    audio = np.zeros(400)
    result = compute_bar_energy(audio, audio, audio, audio, sr, downbeats)
    assert len(result.drum_bar_energies) == 4
    assert len(result.bass_bar_energies) == 4
    assert len(result.vocal_bar_energies) == 4
    assert len(result.other_bar_energies) == 4


def test_compute_bar_energy_rms_values():
    sr = 100
    downbeats = [0.0, 1.0, 2.0, 3.0]
    drums = np.zeros(400)
    drums[:100] = 0.5  # bar 0 only
    bass = np.zeros(400)
    vocal = np.zeros(400)
    other = np.zeros(400)

    result = compute_bar_energy(drums, bass, vocal, other, sr, downbeats)

    assert result.drum_bar_energies[0] == pytest.approx(0.5)
    assert result.drum_bar_energies[1] == pytest.approx(0.0)
    assert result.drum_bar_energies[2] == pytest.approx(0.0)
    assert result.drum_bar_energies[3] == pytest.approx(0.0)
    assert all(e == pytest.approx(0.0) for e in result.bass_bar_energies)


def test_compute_bar_energy_independent_stems():
    sr = 100
    downbeats = [0.0, 1.0, 2.0]
    drums = np.zeros(200)
    bass = np.zeros(200)
    drums[100:] = 1.0   # bar 1 for drums
    bass[:100] = 0.5    # bar 0 for bass

    result = compute_bar_energy(drums, bass, np.zeros(200), np.zeros(200), sr, downbeats)

    assert result.drum_bar_energies[0] == pytest.approx(0.0)
    assert result.drum_bar_energies[1] == pytest.approx(1.0)
    assert result.bass_bar_energies[0] == pytest.approx(0.5)
    assert result.bass_bar_energies[1] == pytest.approx(0.0)

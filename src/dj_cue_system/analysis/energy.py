import numpy as np
from dj_cue_system.analysis.models import BarEnergy


def compute_bar_energy(
    drums: np.ndarray,
    bass: np.ndarray,
    vocal: np.ndarray,
    other: np.ndarray,
    sr: int,
    downbeats: list[float],
) -> BarEnergy:
    def rms_per_bar(audio: np.ndarray) -> list[float]:
        energies = []
        for i, start_time in enumerate(downbeats):
            end_time = downbeats[i + 1] if i + 1 < len(downbeats) else len(audio) / sr
            start_sample = int(start_time * sr)
            end_sample = int(end_time * sr)
            segment = audio[start_sample:end_sample]
            energies.append(float(np.sqrt(np.mean(segment ** 2))) if len(segment) > 0 else 0.0)
        return energies

    return BarEnergy(
        drum_bar_energies=rms_per_bar(drums),
        bass_bar_energies=rms_per_bar(bass),
        vocal_bar_energies=rms_per_bar(vocal),
        other_bar_energies=rms_per_bar(other),
    )

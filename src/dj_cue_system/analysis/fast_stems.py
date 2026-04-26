import numpy as np
import librosa

from dj_cue_system.analysis.models import StemOnsets
from dj_cue_system.analysis.onset import detect_onset_rms


def _bandpass(y: np.ndarray, sr: int, low_hz: float, high_hz: float) -> np.ndarray:
    D = librosa.stft(y)
    freqs = librosa.fft_frequencies(sr=sr, n_fft=D.shape[0] * 2 - 2)
    mask = (freqs >= low_hz) & (freqs <= high_hz)
    D_filtered = D.copy()
    D_filtered[~mask, :] = 0
    return librosa.istft(D_filtered, length=len(y))


def detect_stem_onsets_fast(
    audio_path: str,
    thresholds,
    window_frames: int,
) -> StemOnsets:
    """Fast stem onset detection via frequency-band filtering (no neural network).

    Runs in seconds vs minutes for Demucs. Accuracy is lower for heavily
    overlapping sources, but sufficient for cue-point placement.
    """
    y, sr = librosa.load(audio_path, sr=None, mono=True)

    # Separate percussive (drums) from harmonic content
    y_harmonic, y_percussive = librosa.effects.hpss(y)

    bass_audio = _bandpass(y, sr, 20, 300)
    vocal_audio = _bandpass(y_harmonic, sr, 300, 3500)
    other_audio = _bandpass(y_harmonic, sr, 3500, 8000)

    return StemOnsets(
        vocal=detect_onset_rms(vocal_audio, sr, thresholds.vocal, window_frames),
        drum=detect_onset_rms(y_percussive, sr, thresholds.drum, window_frames),
        bass=detect_onset_rms(bass_audio, sr, thresholds.bass, window_frames),
        other=detect_onset_rms(other_audio, sr, thresholds.other, window_frames),
    )

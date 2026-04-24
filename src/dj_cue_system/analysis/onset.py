import numpy as np
import librosa


def detect_onset_rms(
    audio: np.ndarray,
    sr: int,
    threshold: float,
    window_frames: int,
    frame_length: int = 2048,
    hop_length: int = 512,
) -> float | None:
    """Return timestamp (seconds) of first sustained onset, or None."""
    rms = librosa.feature.rms(y=audio, frame_length=frame_length, hop_length=hop_length)[0]
    for i in range(len(rms) - window_frames + 1):
        if np.all(rms[i : i + window_frames] > threshold):
            return float(librosa.frames_to_time(i, sr=sr, hop_length=hop_length))
    return None

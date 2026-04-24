import numpy as np
import pytest
import torch
from unittest.mock import patch, MagicMock
from dj_cue_system.analysis.onset import detect_onset_rms
from dj_cue_system.analysis.separation import StemAudio

SR = 22050
HOP = 512


def _make_audio(duration_s: float, onset_s: float, sr: int = SR) -> np.ndarray:
    """Silence before onset_s, then loud tone after."""
    samples = int(duration_s * sr)
    audio = np.zeros(samples, dtype=np.float32)
    onset_sample = int(onset_s * sr)
    audio[onset_sample:] = 0.5
    return audio


def test_detect_onset_finds_vocal():
    audio = _make_audio(10.0, onset_s=3.0)
    onset = detect_onset_rms(audio, sr=SR, threshold=0.02, window_frames=5, hop_length=HOP)
    assert onset is not None
    assert onset == pytest.approx(3.0, abs=0.1)


def test_detect_onset_silent_returns_none():
    audio = np.zeros(SR * 5, dtype=np.float32)
    onset = detect_onset_rms(audio, sr=SR, threshold=0.02, window_frames=5, hop_length=HOP)
    assert onset is None


def test_detect_onset_immediate():
    audio = np.full(SR * 5, 0.5, dtype=np.float32)
    onset = detect_onset_rms(audio, sr=SR, threshold=0.02, window_frames=5, hop_length=HOP)
    assert onset is not None
    assert onset == pytest.approx(0.0, abs=0.1)


def test_separate_stems_mocked():
    sr = 44100
    n = sr * 10
    fake_stems = torch.zeros(1, 4, 2, n)
    fake_stems[0, 3] = 0.5  # vocals channel loud

    with patch("dj_cue_system.analysis.separation.get_model") as mock_get, \
         patch("dj_cue_system.analysis.separation.apply_model", return_value=fake_stems), \
         patch("dj_cue_system.analysis.separation.torchaudio.load",
               return_value=(torch.zeros(2, n), sr)):
        mock_model = MagicMock()
        mock_model.samplerate = sr
        mock_model.eval = MagicMock(return_value=mock_model)
        mock_get.return_value = mock_model
        from dj_cue_system.analysis.separation import separate_stems
        result = separate_stems("/fake/track.mp3")

    assert isinstance(result, StemAudio)
    assert result.vocals.shape == (n,)
    assert result.sample_rate == sr

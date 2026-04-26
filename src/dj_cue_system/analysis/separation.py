from dataclasses import dataclass

import torch
import torchaudio
import numpy as np
from demucs.pretrained import get_model
from demucs.apply import apply_model

# htdemucs stem order
_STEM_NAMES = ["drums", "bass", "other", "vocals"]
_STEM_INDEX = {name: i for i, name in enumerate(_STEM_NAMES)}


@dataclass
class StemAudio:
    vocals: np.ndarray
    drums: np.ndarray
    bass: np.ndarray
    other: np.ndarray
    sample_rate: int


def separate_stems(audio_path: str, model_name: str = "htdemucs") -> StemAudio:
    """Separate audio into 4 stems. Returns numpy arrays (mono, float32)."""
    model = get_model(model_name)
    model.eval()

    wav, sr = torchaudio.load(audio_path)
    if sr != model.samplerate:
        wav = torchaudio.functional.resample(wav, sr, model.samplerate)
        sr = model.samplerate

    if wav.shape[0] == 1:
        wav = wav.repeat(2, 1)

    wav = wav.unsqueeze(0)  # (1, channels, samples)

    # MPS (Apple Silicon) does not support htdemucs (output channels > 65536).
    device = "cuda" if torch.cuda.is_available() else "cpu"

    with torch.no_grad():
        sources = apply_model(model, wav, device=device)
    sources = sources.squeeze(0).cpu()  # (4, channels, samples)

    def to_mono(stem_tensor: torch.Tensor) -> np.ndarray:
        return stem_tensor.mean(dim=0).numpy().astype(np.float32)

    return StemAudio(
        vocals=to_mono(sources[_STEM_INDEX["vocals"]]),
        drums=to_mono(sources[_STEM_INDEX["drums"]]),
        bass=to_mono(sources[_STEM_INDEX["bass"]]),
        other=to_mono(sources[_STEM_INDEX["other"]]),
        sample_rate=sr,
    )

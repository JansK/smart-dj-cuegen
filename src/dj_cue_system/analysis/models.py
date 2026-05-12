from dataclasses import dataclass, field


@dataclass
class Section:
    label: str
    start_bar: int
    end_bar: int
    start_time: float  # seconds
    end_time: float    # seconds

    @property
    def duration_bars(self) -> int:
        return self.end_bar - self.start_bar

    def position_fraction(self, total_bars: int) -> float:
        """Fraction of the track at which this section starts (0.0–1.0)."""
        return self.start_bar / total_bars if total_bars > 0 else 0.0


@dataclass
class StemOnsets:
    vocal_first_onset: float | None = None
    drum_first_onset: float | None = None
    bass_first_onset: float | None = None
    other_first_onset: float | None = None


@dataclass
class BarEnergy:
    drum_bar_energies: list[float]
    bass_bar_energies: list[float]
    vocal_bar_energies: list[float]
    other_bar_energies: list[float]


@dataclass
class AnalysisResult:
    bpm: float
    downbeats: list[float]   # seconds at each bar boundary
    total_bars: int
    sections: list[Section]  # ordered, non-overlapping
    stem_onsets: StemOnsets
    audio_path: str
    anlz_source: bool        # True = ANLZ; False = all-in-one fallback

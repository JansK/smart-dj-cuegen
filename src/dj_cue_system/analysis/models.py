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
    vocal: float | None = None
    drum: float | None = None
    bass: float | None = None
    other: float | None = None


@dataclass
class AnalysisResult:
    bpm: float
    downbeats: list[float]   # seconds at each bar boundary
    total_bars: int
    sections: list[Section]  # ordered, non-overlapping, normalized labels
    stem_onsets: StemOnsets
    audio_path: str
    anlz_source: bool        # True = ANLZ; False = all-in-one fallback

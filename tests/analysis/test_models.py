import pytest
from dj_cue_system.analysis.models import Section, StemOnsets, AnalysisResult


def test_section_duration_bars():
    s = Section(label="verse", start_bar=16, end_bar=48, start_time=32.0, end_time=96.0)
    assert s.duration_bars == 32


def test_section_position_fraction():
    s = Section(label="break", start_bar=80, end_bar=96, start_time=160.0, end_time=192.0)
    assert s.position_fraction(total_bars=128) == pytest.approx(0.625)


def test_stem_onsets_defaults_none():
    onsets = StemOnsets()
    assert onsets.vocal is None
    assert onsets.drum is None
    assert onsets.bass is None
    assert onsets.other is None


def test_analysis_result_fields():
    result = AnalysisResult(
        bpm=126.0,
        downbeats=[0.0, 1.9, 3.8, 5.7],
        total_bars=4,
        sections=[Section("intro", 0, 4, 0.0, 7.6)],
        stem_onsets=StemOnsets(vocal=4.1),
        audio_path="/music/track.mp3",
        anlz_source=True,
    )
    assert result.bpm == 126.0
    assert result.anlz_source is True
    assert len(result.sections) == 1

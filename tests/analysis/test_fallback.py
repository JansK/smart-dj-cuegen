from unittest.mock import MagicMock, patch
from dj_cue_system.analysis.fallback import analyze_with_allin1
from dj_cue_system.analysis.models import AnalysisResult


def _mock_allin1_result():
    seg1 = MagicMock(); seg1.label = "intro"; seg1.start = 0.0; seg1.end = 32.0
    seg2 = MagicMock(); seg2.label = "verse"; seg2.start = 32.0; seg2.end = 96.0
    seg3 = MagicMock(); seg3.label = "outro"; seg3.start = 96.0; seg3.end = 128.0

    r = MagicMock()
    r.bpm = 128.0
    r.downbeats = [i * 1.875 for i in range(68)]
    r.segments = [seg1, seg2, seg3]
    return r


def test_analyze_with_allin1_returns_analysis_result():
    with patch("dj_cue_system.analysis.fallback.allin1") as mock_lib:
        mock_lib.analyze.return_value = _mock_allin1_result()
        result = analyze_with_allin1("/music/track.mp3")

    assert isinstance(result, AnalysisResult)
    assert result.bpm == 128.0
    assert result.anlz_source is False
    assert result.audio_path == "/music/track.mp3"
    assert len(result.sections) == 3
    assert result.sections[0].label == "intro"
    assert result.sections[1].label == "verse"
    assert result.total_bars == len(result.downbeats)


def test_analyze_with_allin1_stem_onsets_empty():
    with patch("dj_cue_system.analysis.fallback.allin1") as mock_lib:
        mock_lib.analyze.return_value = _mock_allin1_result()
        result = analyze_with_allin1("/music/track.mp3")

    assert result.stem_onsets.vocal is None
    assert result.stem_onsets.drum is None

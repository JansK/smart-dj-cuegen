import pytest
from unittest.mock import MagicMock, patch
from dj_cue_system.analysis.anlz import parse_beat_grid, BeatGridResult, parse_phrases, normalize_phrase_label


def _make_beat_entry(beat_number: int, time_ms: int, tempo_x100: int) -> MagicMock:
    e = MagicMock()
    e.beat_number = beat_number
    e.time = time_ms
    e.tempo = tempo_x100
    return e


def test_parse_beat_grid_extracts_downbeats():
    entries = [
        _make_beat_entry(1, 0, 12600),
        _make_beat_entry(2, 476, 12600),
        _make_beat_entry(3, 952, 12600),
        _make_beat_entry(4, 1429, 12600),
        _make_beat_entry(1, 1905, 12600),
        _make_beat_entry(2, 2381, 12600),
    ]
    mock_tag = MagicMock()
    mock_tag.beats = entries
    mock_anlz = MagicMock()
    mock_anlz.getone.return_value = mock_tag

    with patch("dj_cue_system.analysis.anlz.AnlzFile") as MockAnlz:
        MockAnlz.parse_file.return_value = mock_anlz
        result = parse_beat_grid("/fake/ANLZ0000.DAT")

    assert isinstance(result, BeatGridResult)
    assert result.bpm == pytest.approx(126.0)
    assert len(result.downbeats) == 2
    assert result.downbeats[0] == pytest.approx(0.0)
    assert result.downbeats[1] == pytest.approx(1.905)


def test_parse_beat_grid_total_bars():
    entries = [
        _make_beat_entry(1 if i % 4 == 0 else (i % 4) + 1, i * 500, 12000)
        for i in range(16)
    ]
    mock_tag = MagicMock()
    mock_tag.beats = entries
    mock_anlz = MagicMock()
    mock_anlz.getone.return_value = mock_tag

    with patch("dj_cue_system.analysis.anlz.AnlzFile") as MockAnlz:
        MockAnlz.parse_file.return_value = mock_anlz
        result = parse_beat_grid("/fake/ANLZ0000.DAT")

    assert result.total_bars == 4


def _make_phrase_entry(beat: int, label_str: str) -> MagicMock:
    e = MagicMock()
    e.beat = beat
    e.kind = MagicMock()
    e.kind.__str__ = MagicMock(return_value=label_str)
    return e


def test_normalize_low_mood_verse():
    assert normalize_phrase_label("Verse1", "low") == "verse"
    assert normalize_phrase_label("Verse1b", "low") == "verse"
    assert normalize_phrase_label("Verse2c", "low") == "verse"


def test_normalize_mid_mood_verse():
    assert normalize_phrase_label("Verse3", "mid") == "verse"


def test_normalize_high_mood_up_down():
    assert normalize_phrase_label("Up", "high") == "up"
    assert normalize_phrase_label("Down", "high") == "down"


def test_normalize_universal_labels():
    for mood in ("low", "mid", "high"):
        assert normalize_phrase_label("Intro", mood) == "intro"
        assert normalize_phrase_label("Chorus", mood) == "chorus"
        assert normalize_phrase_label("Outro", mood) == "outro"


def test_normalize_preserves_raw_labels():
    assert normalize_phrase_label("Up", "high", normalized=False) == "up"
    assert normalize_phrase_label("Down", "high", normalized=False) == "down"


def test_parse_phrases_returns_entries():
    mock_entries = [
        _make_phrase_entry(1, "Intro"),
        _make_phrase_entry(17, "Verse1"),
        _make_phrase_entry(49, "Chorus"),
    ]
    mock_tag = MagicMock()
    mock_tag.mood = 2  # Mid
    mock_tag.phrases = mock_entries
    mock_anlz = MagicMock()
    mock_anlz.getone.return_value = mock_tag

    with patch("dj_cue_system.analysis.anlz.AnlzFile") as MockAnlz:
        MockAnlz.parse_file.return_value = mock_anlz
        phrases = parse_phrases("/fake/ANLZ0000.EXT")

    assert len(phrases) == 3
    assert phrases[0].beat == 1
    assert phrases[0].raw_label == "intro"
    assert phrases[1].raw_label == "verse"

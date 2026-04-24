import pytest
from unittest.mock import MagicMock, patch
from dj_cue_system.analysis.anlz import parse_beat_grid, BeatGridResult


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

import numpy as np
import pytest
from unittest.mock import MagicMock, patch
from dj_cue_system.analysis.anlz import parse_beat_grid, BeatGridResult, parse_phrases


def _make_pqtz_tag(beat_numbers: list[int], times_s: list[float], bpm: float) -> MagicMock:
    tag = MagicMock()
    tag.beats = np.array(beat_numbers)
    tag.times = np.array(times_s)
    tag.bpms = np.array([bpm] * len(beat_numbers))
    return tag


def test_parse_beat_grid_extracts_downbeats():
    tag = _make_pqtz_tag(
        beat_numbers=[1, 2, 3, 4, 1, 2],
        times_s=[0.0, 0.476, 0.952, 1.429, 1.905, 2.381],
        bpm=126.0,
    )
    mock_anlz = MagicMock()
    mock_anlz.get_tag.return_value = tag

    with patch("dj_cue_system.analysis.anlz.AnlzFile") as MockAnlz:
        MockAnlz.parse_file.return_value = mock_anlz
        result = parse_beat_grid("/fake/ANLZ0000.DAT")

    assert isinstance(result, BeatGridResult)
    assert result.bpm == pytest.approx(126.0)
    assert len(result.downbeats) == 2
    assert result.downbeats[0] == pytest.approx(0.0)
    assert result.downbeats[1] == pytest.approx(1.905)


def test_parse_beat_grid_total_bars():
    beat_numbers = [(i % 4) + 1 for i in range(16)]
    times_s = [i * 0.5 for i in range(16)]
    tag = _make_pqtz_tag(beat_numbers=beat_numbers, times_s=times_s, bpm=120.0)
    mock_anlz = MagicMock()
    mock_anlz.get_tag.return_value = tag

    with patch("dj_cue_system.analysis.anlz.AnlzFile") as MockAnlz:
        MockAnlz.parse_file.return_value = mock_anlz
        result = parse_beat_grid("/fake/ANLZ0000.DAT")

    assert result.total_bars == 4


def _make_pssi_tag(mood_int: int, entries: list[tuple[int, int]]) -> MagicMock:
    """entries: list of (beat, kind) tuples."""
    mock_entries = []
    for beat, kind in entries:
        e = MagicMock()
        e.beat = beat
        e.kind = kind
        mock_entries.append(e)
    content = MagicMock()
    content.mood = mood_int
    content.entries = mock_entries
    tag = MagicMock()
    tag.content = content
    return tag


def test_parse_phrases_returns_entries():
    # mood=1 (high): kind 1=intro, 5=chorus, 4=verse1
    tag = _make_pssi_tag(mood_int=1, entries=[(1, 1), (17, 5), (49, 4)])
    mock_anlz = MagicMock()
    mock_anlz.get_tag.return_value = tag

    with patch("dj_cue_system.analysis.anlz.AnlzFile") as MockAnlz:
        MockAnlz.parse_file.return_value = mock_anlz
        phrases = parse_phrases("/fake/ANLZ0000.EXT")

    assert len(phrases) == 3
    assert phrases[0].beat == 1
    assert phrases[0].raw_label == "intro"
    assert phrases[1].raw_label == "chorus"   # kind=5 → chorus
    assert phrases[2].raw_label == "verse1"   # kind=4 → verse1

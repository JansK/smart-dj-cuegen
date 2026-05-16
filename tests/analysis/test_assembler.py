import pytest
from dj_cue_system.analysis.assembler import build_sections
from dj_cue_system.analysis.anlz import BeatGridResult, PhraseEntry


def test_build_sections_basic():
    downbeats = [i * 2.0 for i in range(8)]
    beat_grid = BeatGridResult(bpm=120.0, downbeats=downbeats, total_bars=8)
    all_beat_times = [i * 0.5 for i in range(32)]

    phrases = [
        PhraseEntry(beat=1, raw_label="intro", mood="mid"),
        PhraseEntry(beat=9, raw_label="verse", mood="mid"),
        PhraseEntry(beat=25, raw_label="outro", mood="mid"),
    ]

    sections = build_sections(phrases, beat_grid, all_beat_times)

    assert len(sections) == 3
    assert sections[0].label == "intro"
    assert sections[0].start_bar == 0
    assert sections[0].end_bar == 2
    assert sections[1].label == "verse"
    assert sections[1].start_bar == 2
    assert sections[2].label == "outro"
    assert sections[2].end_bar == 8


def test_build_sections_single():
    downbeats = [0.0, 2.0, 4.0]
    all_beat_times = [i * 0.5 for i in range(12)]
    beat_grid = BeatGridResult(bpm=120.0, downbeats=downbeats, total_bars=3)
    phrases = [PhraseEntry(beat=1, raw_label="intro", mood="low")]

    sections = build_sections(phrases, beat_grid, all_beat_times)
    assert len(sections) == 1
    assert sections[0].end_bar == 3


def test_build_sections_empty():
    downbeats = [0.0, 2.0]
    beat_grid = BeatGridResult(bpm=120.0, downbeats=downbeats, total_bars=2)
    sections = build_sections([], beat_grid, [])
    assert sections == []


def test_build_sections_merges_consecutive_same_label():
    # Three consecutive "chorus" entries should collapse into one section.
    downbeats = [i * 2.0 for i in range(16)]
    beat_grid = BeatGridResult(bpm=120.0, downbeats=downbeats, total_bars=16)
    all_beat_times = [i * 0.5 for i in range(64)]

    phrases = [
        PhraseEntry(beat=1,  raw_label="intro",  mood="high"),
        PhraseEntry(beat=9,  raw_label="chorus", mood="high"),
        PhraseEntry(beat=17, raw_label="chorus", mood="high"),
        PhraseEntry(beat=25, raw_label="chorus", mood="high"),
        PhraseEntry(beat=33, raw_label="outro",  mood="high"),
    ]

    sections = build_sections(phrases, beat_grid, all_beat_times)

    assert len(sections) == 3
    assert sections[0].label == "intro"
    assert sections[1].label == "chorus"
    assert sections[1].start_bar == 2   # starts at first chorus entry
    assert sections[1].end_bar == 8    # ends where outro begins
    assert sections[2].label == "outro"

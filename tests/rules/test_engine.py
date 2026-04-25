import pytest
import textwrap
import tempfile
import os
from dj_cue_system.analysis.models import AnalysisResult, Section, StemOnsets
from dj_cue_system.rules.config import AppConfig, load_config
from dj_cue_system.rules.engine import resolve_cues
from dj_cue_system.writers.base import CuePoint, LoopPoint


def _make_result(sections=None, vocal_onset=None, drum_onset=None) -> AnalysisResult:
    downbeats = [i * 2.0 for i in range(129)]
    return AnalysisResult(
        bpm=120.0,
        downbeats=downbeats,
        total_bars=128,
        sections=sections or [
            Section("intro", 0, 16, 0.0, 32.0),
            Section("verse", 16, 48, 32.0, 96.0),
            Section("chorus", 48, 80, 96.0, 160.0),
            Section("break", 80, 96, 160.0, 192.0),
            Section("outro", 96, 128, 192.0, 256.0),
        ],
        stem_onsets=StemOnsets(vocal=vocal_onset, drum=drum_onset),
        audio_path="/music/track.mp3",
        anlz_source=True,
    )


def _config_from_yaml(yaml_str: str) -> AppConfig:
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        f.write(yaml_str)
        name = f.name
    cfg = load_config(name)
    os.unlink(name)
    return cfg


def test_resolve_vocal_cue():
    cfg = _config_from_yaml(textwrap.dedent("""
        rulesets:
          vocal-cue:
            rules:
              - element: first_vocal_onset
                type: memory_cue
                offset_bars: -8
                name: "Vox"
                color: blue
        defaults:
          rulesets: [vocal-cue]
    """))
    result = _make_result(vocal_onset=80.0)  # bar 40 (80s / 2s per bar)
    cues, loops = resolve_cues(result, cfg, playlists=[])
    assert len(cues) == 1
    assert cues[0].name == "Vox"
    assert cues[0].bar == 32   # bar 40 - 8 = 32
    assert cues[0].color == "blue"


def test_resolve_clamps_negative_bar():
    cfg = _config_from_yaml(textwrap.dedent("""
        rulesets:
          vocal-cue:
            rules:
              - element: first_vocal_onset
                type: memory_cue
                offset_bars: -64
                name: "Vox"
        defaults:
          rulesets: [vocal-cue]
    """))
    result = _make_result(vocal_onset=10.0)  # bar 5; 5-64=-59 → clamp to 0
    cues, loops = resolve_cues(result, cfg, playlists=[])
    assert cues[0].bar == 0


def test_resolve_loop_on_intro():
    cfg = _config_from_yaml(textwrap.dedent("""
        rulesets:
          loops:
            rules:
              - element: intro_start
                type: loop
                length_bars: 16
                name: "Intro"
        defaults:
          rulesets: [loops]
    """))
    result = _make_result()
    cues, loops = resolve_cues(result, cfg, playlists=[])
    assert len(loops) == 1
    assert loops[0].name == "Intro"
    assert loops[0].start_bar == 0
    assert loops[0].end_bar == 16


def test_resolve_qualifier_after_midpoint():
    cfg = _config_from_yaml(textwrap.dedent("""
        rulesets:
          bh:
            rules:
              - element: break_start
                type: memory_cue
                offset_bars: 0
                name: "Break"
                qualifier:
                  position: after_midpoint
                  min_duration_bars: 8
                  occurrence: last
        defaults:
          rulesets: [bh]
    """))
    result = _make_result()  # break at bar 80-96 (63% of 128)
    cues, loops = resolve_cues(result, cfg, playlists=[])
    assert len(cues) == 1
    assert cues[0].bar == 80


def test_resolve_qualifier_no_match_skips_rule():
    cfg = _config_from_yaml(textwrap.dedent("""
        rulesets:
          bh:
            rules:
              - element: break_start
                type: memory_cue
                offset_bars: 0
                name: "Break"
                qualifier:
                  min_duration_bars: 100
        defaults:
          rulesets: [bh]
    """))
    result = _make_result()
    cues, loops = resolve_cues(result, cfg, playlists=[])
    assert len(cues) == 0


def test_resolve_deduplicates_same_position():
    cfg = _config_from_yaml(textwrap.dedent("""
        rulesets:
          r1:
            rules:
              - element: intro_start
                type: memory_cue
                offset_bars: 0
                name: "A"
          r2:
            rules:
              - element: intro_start
                type: memory_cue
                offset_bars: 0
                name: "A"
        defaults:
          rulesets: [r1, r2]
    """))
    result = _make_result()
    cues, loops = resolve_cues(result, cfg, playlists=[])
    assert len(cues) == 1


def test_playlist_ruleset_used_over_defaults():
    cfg = _config_from_yaml(textwrap.dedent("""
        rulesets:
          default-rule:
            rules:
              - element: intro_start
                type: memory_cue
                offset_bars: 0
                name: "Default"
          playlist-rule:
            rules:
              - element: outro_start
                type: memory_cue
                offset_bars: 0
                name: "PlaylistCue"
        playlists:
          Techno:
            rulesets: [playlist-rule]
        defaults:
          rulesets: [default-rule]
    """))
    result = _make_result()
    cues, loops = resolve_cues(result, cfg, playlists=["Techno"])
    names = [c.name for c in cues]
    assert "PlaylistCue" in names
    assert "Default" not in names


def test_verse_start_matches_high_mood_up():
    """verse_start rules should match 'up' sections (High mood Rekordbox tracks)."""
    cfg = _config_from_yaml(textwrap.dedent("""
        rulesets:
          r:
            rules:
              - element: verse_start
                type: memory_cue
                offset_bars: 0
                name: "Verse"
        defaults:
          rulesets: [r]
    """))
    result = _make_result(sections=[
        Section("intro", 0, 16, 0.0, 32.0),
        Section("up", 16, 48, 32.0, 96.0),   # High-mood track
        Section("outro", 96, 128, 192.0, 256.0),
    ])
    cues, loops = resolve_cues(result, cfg, playlists=[])
    assert len(cues) == 1
    assert cues[0].bar == 16

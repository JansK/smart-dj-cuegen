import pytest
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock
from dj_cue_system.cli import app

runner = CliRunner()


def _mock_result():
    from dj_cue_system.analysis.models import AnalysisResult, Section, StemOnsets
    return AnalysisResult(
        bpm=126.0,
        downbeats=[i * 2.0 for i in range(129)],
        total_bars=128,
        sections=[
            Section("intro", 0, 16, 0.0, 32.0),
            Section("outro", 96, 128, 192.0, 256.0),
        ],
        stem_onsets=StemOnsets(vocal_first_onset=4.0),
        audio_path="/music/track.mp3",
        anlz_source=True,
    )


def _mock_track(has_cues=False):
    from dj_cue_system.library.models import Track, ExistingCue
    return Track(
        id="1", path="/music/track.mp3", title="Test", artist="Artist",
        analysis_data_path=None,
        existing_cues=[ExistingCue(1.0, "memory_cue", "X")] if has_cues else [],
        playlists=["Deep House"],
    )


def test_validate_config_ok(tmp_path):
    cfg = tmp_path / "rules.yaml"
    cfg.write_text("rulesets:\n  r:\n    rules: []\ndefaults:\n  rulesets: []\n")
    result = runner.invoke(app, ["validate-config", "--config", str(cfg)])
    assert result.exit_code == 0
    assert "valid" in result.output.lower()


def test_validate_config_invalid(tmp_path):
    cfg = tmp_path / "rules.yaml"
    cfg.write_text("rulesets:\n  bad:\n    rules:\n      - element: x\n        type: bad_type\n        name: X\ndefaults:\n  rulesets: []\n")
    result = runner.invoke(app, ["validate-config", "--config", str(cfg)])
    assert result.exit_code != 0


def test_show_elements(tmp_path):
    cfg = tmp_path / "rules.yaml"
    cfg.write_text("rulesets: {}\ndefaults:\n  rulesets: []\n")
    with patch("dj_cue_system.cli.run_full_analysis", return_value=(_mock_result(), None)):
        result = runner.invoke(app, ["show-elements", "/music/track.mp3", "--config", str(cfg)])
    assert result.exit_code == 0
    assert "126.0" in result.output
    assert "intro" in result.output


def test_analyze_single_dry_run(tmp_path):
    cfg = tmp_path / "rules.yaml"
    cfg.write_text("rulesets:\n  r:\n    rules: []\ndefaults:\n  rulesets: [r]\n")
    with patch("dj_cue_system.cli.run_full_analysis", return_value=(_mock_result(), None)), \
         patch("dj_cue_system.cli.get_tracks", return_value=[_mock_track()]), \
         patch("dj_cue_system.cli.get_track_playlists", return_value={"1": ["Deep House"]}):
        result = runner.invoke(app, ["analyze", "/music/track.mp3", "--config", str(cfg), "--dry-run"])
    assert result.exit_code == 0


def test_analyze_skips_tracks_with_cues(tmp_path):
    cfg = tmp_path / "rules.yaml"
    cfg.write_text("rulesets:\n  r:\n    rules: []\ndefaults:\n  rulesets: [r]\n")
    with patch("dj_cue_system.cli.run_full_analysis") as mock_analyze, \
         patch("dj_cue_system.cli.get_tracks", return_value=[_mock_track(has_cues=True)]), \
         patch("dj_cue_system.cli.get_track_playlists", return_value={}):
        runner.invoke(app, ["analyze", "--library", "--config", str(cfg), "--dry-run"])
    mock_analyze.assert_not_called()


def test_show_cues_found():
    with patch("dj_cue_system.cli.get_track_by_path", return_value=_mock_track(has_cues=True)):
        result = runner.invoke(app, ["show-cues", "/music/track.mp3"])
    assert result.exit_code == 0
    assert "memory cue" in result.output or "Test" in result.output


def test_show_cues_not_found():
    with patch("dj_cue_system.cli.get_track_by_path", return_value=None):
        result = runner.invoke(app, ["show-cues", "/music/missing.mp3"])
    assert result.exit_code != 0
    assert "not found" in result.output.lower()


def test_show_cues_no_cues():
    with patch("dj_cue_system.cli.get_track_by_path", return_value=_mock_track(has_cues=False)):
        result = runner.invoke(app, ["show-cues", "/music/track.mp3"])
    assert result.exit_code == 0
    assert "no cue" in result.output.lower()


def test_backup_create(tmp_path):
    from dj_cue_system.backup.writer import BackupFile, BackupTrack
    fake_backup = BackupFile(rekordbox_db="/db", tracks=[])
    with patch("dj_cue_system.cli.create_backup", return_value=fake_backup), \
         patch("dj_cue_system.cli.serialize_backup") as mock_save:
        result = runner.invoke(app, ["backup", "create", "--output", str(tmp_path / "b.json")])
    assert result.exit_code == 0
    mock_save.assert_called_once()


def test_restore_produces_xml(tmp_path):
    from dj_cue_system.backup.writer import BackupFile, BackupTrack, BackupCue
    fake_backup = BackupFile(
        rekordbox_db="/db",
        tracks=[BackupTrack(id="1", path="/music/t.mp3", artist="A", title="T",
                            cues=[BackupCue(type="memory_cue", name="Cue", position_seconds=1.0)])]
    )
    out = tmp_path / "restored.xml"
    with patch("dj_cue_system.cli.deserialize_backup", return_value=fake_backup):
        result = runner.invoke(app, ["restore", "fake.json", "--output", str(out)])
    assert result.exit_code == 0
    assert out.exists()


def test_show_elements_cache_annotation(tmp_path):
    """show-elements labels stem onsets as (cached · demucs) when result is cached."""
    cfg = tmp_path / "rules.yaml"
    cfg.write_text("rulesets: {}\ndefaults:\n  rulesets: []\n")
    with patch("dj_cue_system.cli.run_full_analysis", return_value=(_mock_result(), "demucs")):
        result = runner.invoke(app, ["show-elements", "/music/track.mp3", "--config", str(cfg)])
    assert result.exit_code == 0
    assert "cached" in result.output
    assert "demucs" in result.output


def test_get_stem_onsets_returns_cached_result(tmp_path, monkeypatch):
    """_get_stem_onsets returns cached result without running analysis."""
    import dj_cue_system.stems.cache as stems_cache
    from dj_cue_system.analysis.models import BarEnergy, StemOnsets
    from dj_cue_system.cli import _get_stem_onsets
    from dj_cue_system.rules.config import load_config

    monkeypatch.setattr(stems_cache, "_CACHE_DIR", tmp_path)
    bar_energy = BarEnergy(
        drum_bar_energies=[0.1], bass_bar_energies=[0.2],
        vocal_bar_energies=[0.3], other_bar_energies=[0.4],
    )
    stems_cache.save("/music/track.mp3", StemOnsets(vocal_first_onset=1.0), "demucs", bar_energy=bar_energy)

    cfg_file = tmp_path / "rules.yaml"
    cfg_file.write_text("rulesets: {}\ndefaults:\n  rulesets: []\n")
    cfg = load_config(str(cfg_file))

    with patch("dj_cue_system.analysis.fast_stems.detect_stem_onsets_fast") as mock_fast:
        onsets, _, source = _get_stem_onsets("/music/track.mp3", cfg, hq=False)

    mock_fast.assert_not_called()
    assert source == "demucs"
    assert onsets.vocal_first_onset == 1.0


def test_get_stem_onsets_warns_on_librosa_cache_with_hq(tmp_path, monkeypatch):
    """_get_stem_onsets warns and uses cached result when cache has librosa but --hq set."""
    import dj_cue_system.stems.cache as stems_cache
    from dj_cue_system.analysis.models import BarEnergy, StemOnsets
    from dj_cue_system.cli import _get_stem_onsets
    from dj_cue_system.rules.config import load_config

    monkeypatch.setattr(stems_cache, "_CACHE_DIR", tmp_path)
    bar_energy = BarEnergy(
        drum_bar_energies=[0.1], bass_bar_energies=[0.2],
        vocal_bar_energies=[0.3], other_bar_energies=[0.4],
    )
    stems_cache.save("/music/track.mp3", StemOnsets(vocal_first_onset=1.0), "librosa", bar_energy=bar_energy)

    cfg_file = tmp_path / "rules.yaml"
    cfg_file.write_text("rulesets: {}\ndefaults:\n  rulesets: []\n")
    cfg = load_config(str(cfg_file))

    with patch("dj_cue_system.cli.console") as mock_console, \
         patch("dj_cue_system.analysis.separation.separate_stems") as mock_sep:
        onsets, _, source = _get_stem_onsets("/music/track.mp3", cfg, hq=True)

    mock_sep.assert_not_called()
    assert source == "librosa"
    assert onsets.vocal_first_onset == 1.0
    # Warning must have been printed
    printed_args = " ".join(str(c) for c in mock_console.print.call_args_list)
    assert "librosa" in printed_args.lower()
    assert "stems run" in printed_args.lower()


def test_stems_run_skips_matching_slot(tmp_path, monkeypatch):
    """stems run skips a track when the requested slot (LQ) is already cached."""
    import dj_cue_system.stems.cache as stems_cache
    import dj_cue_system.stems.jobs as stems_jobs
    from dj_cue_system.analysis.models import StemOnsets

    monkeypatch.setattr(stems_cache, "_CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(stems_jobs, "_JOBS_DIR", tmp_path / "jobs")

    stems_cache.save("/music/track.mp3", StemOnsets(vocal_first_onset=1.0), "librosa")

    cfg = tmp_path / "rules.yaml"
    cfg.write_text("rulesets: {}\ndefaults:\n  rulesets: []\n")

    with patch("dj_cue_system.analysis.fast_stems.detect_stem_onsets_fast") as mock_fast:
        result = runner.invoke(app, [
            "stems", "run", "--path", "/music/track.mp3",
            "--no-hq", "--config", str(cfg),
        ])

    assert result.exit_code == 0
    mock_fast.assert_not_called()
    assert "cached" in result.output


def test_stems_run_processes_when_only_other_slot_cached(tmp_path, monkeypatch):
    """stems run processes a track when only the opposite slot is cached (HQ cached, --no-hq requested)."""
    import dj_cue_system.stems.cache as stems_cache
    import dj_cue_system.stems.jobs as stems_jobs
    from dj_cue_system.analysis.models import StemOnsets

    monkeypatch.setattr(stems_cache, "_CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(stems_jobs, "_JOBS_DIR", tmp_path / "jobs")

    # Only HQ cached — LQ slot is missing
    stems_cache.save("/music/track.mp3", StemOnsets(vocal_first_onset=1.0), "demucs")

    cfg = tmp_path / "rules.yaml"
    cfg.write_text("rulesets: {}\ndefaults:\n  rulesets: []\n")

    with patch("dj_cue_system.analysis.fast_stems.detect_stem_onsets_fast",
               return_value=(StemOnsets(vocal_first_onset=2.0), None)) as mock_fast:
        result = runner.invoke(app, [
            "stems", "run", "--path", "/music/track.mp3",
            "--no-hq", "--config", str(cfg),
        ])

    assert result.exit_code == 0
    mock_fast.assert_called_once()


def test_stems_run_skips_hq_when_hq_cached(tmp_path, monkeypatch):
    """stems run skips a track when the HQ slot is already cached and --hq is requested."""
    import dj_cue_system.stems.cache as stems_cache
    import dj_cue_system.stems.jobs as stems_jobs
    from dj_cue_system.analysis.models import StemOnsets

    monkeypatch.setattr(stems_cache, "_CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(stems_jobs, "_JOBS_DIR", tmp_path / "jobs")

    stems_cache.save("/music/track.mp3", StemOnsets(vocal_first_onset=1.0), "demucs")

    cfg = tmp_path / "rules.yaml"
    cfg.write_text("rulesets: {}\ndefaults:\n  rulesets: []\n")

    with patch("dj_cue_system.analysis.separation.separate_stems") as mock_sep:
        result = runner.invoke(app, [
            "stems", "run", "--path", "/music/track.mp3",
            "--hq", "--config", str(cfg),
        ])

    assert result.exit_code == 0
    mock_sep.assert_not_called()
    assert "cached" in result.output


def test_get_stem_onsets_lq_returns_bar_energy_when_downbeats_provided(tmp_path, monkeypatch):
    import dj_cue_system.stems.cache as stems_cache
    from dj_cue_system.analysis.models import BarEnergy, StemOnsets
    from dj_cue_system.cli import _get_stem_onsets
    from dj_cue_system.rules.config import load_config

    monkeypatch.setattr(stems_cache, "_CACHE_DIR", tmp_path)
    cfg_file = tmp_path / "rules.yaml"
    cfg_file.write_text("rulesets: {}\ndefaults:\n  rulesets: []\n")
    cfg = load_config(str(cfg_file))

    downbeats = [float(i) for i in range(32)]
    mock_onsets = StemOnsets(drum_first_onset=0.5)
    mock_bar_energy = BarEnergy([0.1]*32, [0.1]*32, [0.0]*32, [0.1]*32)

    with patch("dj_cue_system.analysis.fast_stems.detect_stem_onsets_fast",
               return_value=(mock_onsets, mock_bar_energy)):
        onsets, bar_energy, cache_source = _get_stem_onsets(
            "/music/track.mp3", cfg, hq=False, downbeats=downbeats
        )

    assert bar_energy is not None
    assert bar_energy.drum_bar_energies == pytest.approx([0.1] * 32)
    assert cache_source is None  # freshly computed


def test_analyze_result_includes_detected_breaks(tmp_path, monkeypatch):
    """When bar energy is available, detect_breaks results appear in result.sections."""
    import dj_cue_system.stems.cache as stems_cache
    from dj_cue_system.analysis.models import BarEnergy, StemOnsets
    from dj_cue_system.cli import _get_stem_onsets
    from dj_cue_system.rules.config import load_config

    monkeypatch.setattr(stems_cache, "_CACHE_DIR", tmp_path)
    cfg_file = tmp_path / "rules.yaml"
    cfg_file.write_text("rulesets: {}\ndefaults:\n  rulesets: []\n")
    cfg = load_config(str(cfg_file))

    # 32 bars: bars 8-11 have drums+bass silent → break
    n = 32
    drum = [1.0] * n
    bass = [1.0] * n
    for i in range(8, 12):
        drum[i] = 0.05
        bass[i] = 0.05
    bar_energy = BarEnergy(
        drum_bar_energies=drum,
        bass_bar_energies=bass,
        vocal_bar_energies=[0.0] * n,
        other_bar_energies=[0.0] * n,
    )
    downbeats = [float(i) for i in range(n)]

    with patch("dj_cue_system.analysis.fast_stems.detect_stem_onsets_fast",
               return_value=(StemOnsets(), bar_energy)):
        onsets, returned_bar_energy, _ = _get_stem_onsets(
            "/music/track.mp3", cfg, hq=False, downbeats=downbeats
        )

    from dj_cue_system.analysis.break_detect import detect_breaks
    breaks = detect_breaks(returned_bar_energy, downbeats, cfg.settings.break_detection)
    assert len(breaks) == 1
    assert breaks[0].label == "break"
    assert breaks[0].start_bar == 8


def test_run_full_analysis_appends_break_sections(tmp_path, monkeypatch):
    """run_full_analysis appends detected break sections to result.sections."""
    import dj_cue_system.stems.cache as stems_cache
    from dj_cue_system.analysis.models import AnalysisResult, BarEnergy, Section, StemOnsets
    from dj_cue_system.cli import run_full_analysis
    from dj_cue_system.rules.config import load_config

    monkeypatch.setattr(stems_cache, "_CACHE_DIR", tmp_path)
    cfg_file = tmp_path / "rules.yaml"
    cfg_file.write_text("rulesets: {}\ndefaults:\n  rulesets: []\n")
    cfg = load_config(str(cfg_file))

    n = 32
    downbeats = [float(i) for i in range(n)]
    drum = [1.0] * n
    bass = [1.0] * n
    for i in range(8, 12):
        drum[i] = 0.05
        bass[i] = 0.05
    bar_energy = BarEnergy(
        drum_bar_energies=drum,
        bass_bar_energies=bass,
        vocal_bar_energies=[0.0] * n,
        other_bar_energies=[0.0] * n,
    )
    fake_result = AnalysisResult(
        bpm=120.0,
        downbeats=downbeats,
        total_bars=n,
        sections=[],
        stem_onsets=StemOnsets(),
        audio_path="/music/track.mp3",
        anlz_source=False,
    )

    with patch("dj_cue_system.analysis.fallback.analyze_with_allin1", return_value=fake_result), \
         patch("dj_cue_system.analysis.fast_stems.detect_stem_onsets_fast",
               return_value=(StemOnsets(), bar_energy)):
        result, _ = run_full_analysis("/music/track.mp3", cfg, hq=False)

    break_sections = [s for s in result.sections if s.label == "break"]
    assert len(break_sections) == 1
    assert break_sections[0].start_bar == 8
    assert break_sections[0].end_bar == 12

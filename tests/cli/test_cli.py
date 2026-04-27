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
        stem_onsets=StemOnsets(vocal=4.0),
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

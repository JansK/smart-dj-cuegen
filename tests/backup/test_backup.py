import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from dj_cue_system.backup.writer import (
    BackupCue, BackupTrack, BackupFile, serialize_backup, deserialize_backup
)


def _make_backup_file() -> BackupFile:
    return BackupFile(
        created_at="2026-04-23T22:15:00Z",
        rekordbox_db="/fake/master.db",
        tracks=[
            BackupTrack(
                id="1",
                path="/Music/track.mp3",
                artist="DJ A",
                title="Track One",
                cues=[
                    BackupCue(type="memory_cue", position_seconds=4.1, name="Vox", color="blue"),
                    BackupCue(type="loop", start_seconds=0.0, end_seconds=32.0, name="Intro"),
                ],
            )
        ],
    )


def test_serialize_and_deserialize_roundtrip(tmp_path):
    backup = _make_backup_file()
    path = tmp_path / "backup.json"
    serialize_backup(backup, str(path))

    loaded = deserialize_backup(str(path))
    assert loaded.rekordbox_db == backup.rekordbox_db
    assert len(loaded.tracks) == 1
    assert loaded.tracks[0].title == "Track One"
    assert loaded.tracks[0].cues[0].type == "memory_cue"
    assert loaded.tracks[0].cues[0].position_seconds == pytest.approx(4.1)
    assert loaded.tracks[0].cues[1].type == "loop"
    assert loaded.tracks[0].cues[1].start_seconds == pytest.approx(0.0)


def test_serialize_json_structure(tmp_path):
    backup = _make_backup_file()
    path = tmp_path / "backup.json"
    serialize_backup(backup, str(path))

    raw = json.loads(path.read_text())
    assert "created_at" in raw
    assert "tracks" in raw
    assert raw["tracks"][0]["artist"] == "DJ A"


from dj_cue_system.backup.diff import diff_backups, DiffResult


def _track(title: str, cues: list[BackupCue]) -> BackupTrack:
    return BackupTrack(id="1", path=f"/music/{title}.mp3", artist="A", title=title, cues=cues)


def test_diff_no_changes():
    cues = [BackupCue(type="memory_cue", name="X", position_seconds=1.0)]
    old = BackupFile(rekordbox_db="/db", tracks=[_track("T", cues)])
    new = BackupFile(rekordbox_db="/db", tracks=[_track("T", cues)])
    result = diff_backups(old, new)
    assert result.changed == []
    assert result.added == []
    assert result.removed == []


def test_diff_added_track():
    old = BackupFile(rekordbox_db="/db", tracks=[])
    new = BackupFile(rekordbox_db="/db", tracks=[_track("New", [])])
    result = diff_backups(old, new)
    assert len(result.added) == 1
    assert result.added[0].title == "New"


def test_diff_removed_track():
    old = BackupFile(rekordbox_db="/db", tracks=[_track("Gone", [])])
    new = BackupFile(rekordbox_db="/db", tracks=[])
    result = diff_backups(old, new)
    assert len(result.removed) == 1


def test_diff_changed_cues():
    old_cues = [BackupCue(type="memory_cue", name="Old", position_seconds=1.0)]
    new_cues = [BackupCue(type="memory_cue", name="New", position_seconds=2.0)]
    old = BackupFile(rekordbox_db="/db", tracks=[_track("T", old_cues)])
    new = BackupFile(rekordbox_db="/db", tracks=[_track("T", new_cues)])
    result = diff_backups(old, new)
    assert len(result.changed) == 1
    assert result.changed[0].title == "T"

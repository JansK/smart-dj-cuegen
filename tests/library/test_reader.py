import pytest
from unittest.mock import MagicMock, patch
from dj_cue_system.library.reader import get_tracks, get_track_by_path, get_track_playlists, DEFAULT_DB_PATH
from dj_cue_system.library.models import Track, ExistingCue


def _mock_content(id="1", title="Track", artist="Artist", path="/music/track.mp3", anlz="PIONEER/ANLZ0000.DAT"):
    c = MagicMock()
    c.ID = id; c.Title = title; c.Artist = artist
    c.FolderPath = path; c.AnalysisDataPath = anlz
    return c


def _mock_cue(content_id="1", in_msec=5000, kind=0, comment="Vox"):
    c = MagicMock()
    c.ContentID = content_id; c.InMsec = in_msec
    c.Kind = kind; c.Comment = comment
    return c


def test_get_tracks_returns_track_list():
    with patch("dj_cue_system.library.reader.Rekordbox6Database") as MockDB:
        db = MockDB.return_value
        db.get_content.return_value = [_mock_content()]
        db.get_cue.return_value = [_mock_cue()]
        tracks = get_tracks()

    assert len(tracks) == 1
    assert tracks[0].id == "1"
    assert tracks[0].title == "Track"
    assert tracks[0].path == "/music/track.mp3"


def test_get_tracks_maps_existing_cues():
    with patch("dj_cue_system.library.reader.Rekordbox6Database") as MockDB:
        db = MockDB.return_value
        db.get_content.return_value = [_mock_content()]
        db.get_cue.return_value = [_mock_cue(in_msec=5000, kind=0, comment="Vox")]
        tracks = get_tracks()

    cue = tracks[0].existing_cues[0]
    assert cue.position_seconds == pytest.approx(5.0)
    assert cue.cue_type == "memory_cue"
    assert cue.name == "Vox"


def test_track_has_memory_cues():
    t = Track(id="1", path="/x", title="X", artist="A",
              analysis_data_path=None,
              existing_cues=[ExistingCue(5.0, "memory_cue", "X")])
    assert t.has_memory_cues is True


def test_track_no_memory_cues():
    t = Track(id="1", path="/x", title="X", artist="A",
              analysis_data_path=None,
              existing_cues=[ExistingCue(5.0, "hot_cue", "X")])
    assert t.has_memory_cues is False


def test_default_db_path_mac():
    assert "Pioneer" in DEFAULT_DB_PATH
    assert DEFAULT_DB_PATH.endswith("master.db")


def test_get_track_by_path_found():
    with patch("dj_cue_system.library.reader.Rekordbox6Database") as MockDB:
        db = MockDB.return_value
        db.get_content.return_value = [_mock_content(path="/music/track.mp3")]
        db.get_cue.return_value = [_mock_cue(content_id="1")]
        track = get_track_by_path("/music/track.mp3")
    assert track is not None
    assert track.path == "/music/track.mp3"
    assert len(track.existing_cues) == 1


def test_get_track_by_path_not_found():
    with patch("dj_cue_system.library.reader.Rekordbox6Database") as MockDB:
        db = MockDB.return_value
        db.get_content.return_value = [_mock_content(path="/music/other.mp3")]
        db.get_cue.return_value = []
        track = get_track_by_path("/music/track.mp3")
    assert track is None

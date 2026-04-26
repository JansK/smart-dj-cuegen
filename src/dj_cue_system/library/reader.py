import os
from pyrekordbox import Rekordbox6Database
from dj_cue_system.library.models import Track, ExistingCue

DEFAULT_DB_PATH = os.path.expanduser(
    "~/Library/Pioneer/rekordbox/master.db"
)

_KIND_TO_TYPE = {0: "memory_cue", 1: "hot_cue", 4: "loop", 5: "hot_loop"}


def _build_cues_map(db) -> dict[str, list]:
    cues_by_content: dict[str, list] = {}
    for cue in db.get_cue():
        cues_by_content.setdefault(str(cue.ContentID), []).append(cue)
    return cues_by_content


def _content_to_track(content, raw_cues: list) -> Track:
    existing = [
        ExistingCue(
            position_seconds=c.InMsec / 1000.0,
            cue_type=_KIND_TO_TYPE.get(c.Kind, "unknown"),
            name=c.Comment or "",
        )
        for c in raw_cues
    ]
    return Track(
        id=str(content.ID),
        path=str(content.FolderPath),
        title=str(content.Title or ""),
        artist=str(content.Artist or ""),
        analysis_data_path=content.AnalysisDataPath,
        existing_cues=existing,
    )


def get_tracks(db_path: str | None = None) -> list[Track]:
    db = Rekordbox6Database(db_path or DEFAULT_DB_PATH)
    cues_by_content = _build_cues_map(db)
    return [
        _content_to_track(content, cues_by_content.get(str(content.ID), []))
        for content in db.get_content()
    ]


def get_track_by_path(audio_path: str, db_path: str | None = None) -> Track | None:
    db = Rekordbox6Database(db_path or DEFAULT_DB_PATH)
    cues_by_content = _build_cues_map(db)
    for content in db.get_content():
        if str(content.FolderPath) == audio_path:
            return _content_to_track(content, cues_by_content.get(str(content.ID), []))
    return None


def get_track_playlists(db_path: str | None = None) -> dict[str, list[str]]:
    """Return {track_id: [playlist_name, ...]} mapping."""
    db = Rekordbox6Database(db_path or DEFAULT_DB_PATH)
    result: dict[str, list[str]] = {}
    for playlist in db.get_playlist():
        for content in db.get_playlist_contents(playlist.ID):
            result.setdefault(str(content.ID), []).append(playlist.Name)
    return result

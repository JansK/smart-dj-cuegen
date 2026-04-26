from pyrekordbox import Rekordbox6Database
from dj_cue_system.backup.writer import BackupFile, BackupTrack, BackupCue
from dj_cue_system.library.reader import DEFAULT_DB_PATH, _KIND_TO_TYPE


def create_backup(
    db_path: str | None = None,
    playlist_filter: str | None = None,
) -> BackupFile:
    db_path = db_path or DEFAULT_DB_PATH
    db = Rekordbox6Database(db_path)

    content_ids_in_playlist: set[str] | None = None
    if playlist_filter:
        playlists = {p.ID: p.Name for p in db.get_playlist()}
        target_ids = [pid for pid, name in playlists.items() if name == playlist_filter]
        content_ids_in_playlist = {
            str(content.ID)
            for pid in target_ids
            for content in db.get_playlist_contents(pid)
        }

    all_cues = db.get_cue()
    cues_by_content: dict[str, list] = {}
    for cue in all_cues:
        cues_by_content.setdefault(str(cue.ContentID), []).append(cue)

    tracks = []
    for content in db.get_content():
        cid = str(content.ID)
        if content_ids_in_playlist is not None and cid not in content_ids_in_playlist:
            continue

        raw_cues = cues_by_content.get(cid, [])
        backup_cues = []
        for c in raw_cues:
            cue_type = _KIND_TO_TYPE.get(c.Kind, "unknown")
            if cue_type == "memory_cue":
                backup_cues.append(BackupCue(
                    type="memory_cue",
                    name=c.Comment or "",
                    position_seconds=c.InMsec / 1000.0,
                ))
            elif cue_type == "loop":
                backup_cues.append(BackupCue(
                    type="loop",
                    name=c.Comment or "",
                    start_seconds=c.InMsec / 1000.0,
                    end_seconds=c.OutMsec / 1000.0 if c.OutMsec else None,
                ))

        tracks.append(BackupTrack(
            id=cid,
            path=str(content.FolderPath),
            artist=str(content.Artist or ""),
            title=str(content.Title or ""),
            cues=backup_cues,
        ))

    return BackupFile(rekordbox_db=db_path, tracks=tracks)

from dataclasses import dataclass, asdict
from dj_cue_system.backup.writer import BackupFile, BackupTrack


@dataclass
class DiffResult:
    added: list[BackupTrack]
    removed: list[BackupTrack]
    changed: list[BackupTrack]


def diff_backups(old: BackupFile, new: BackupFile) -> DiffResult:
    old_by_path = {t.path: t for t in old.tracks}
    new_by_path = {t.path: t for t in new.tracks}

    added = [t for path, t in new_by_path.items() if path not in old_by_path]
    removed = [t for path, t in old_by_path.items() if path not in new_by_path]
    changed = [
        new_by_path[path]
        for path in new_by_path
        if path in old_by_path
        and asdict(new_by_path[path])["cues"] != asdict(old_by_path[path])["cues"]
    ]
    return DiffResult(added=added, removed=removed, changed=changed)

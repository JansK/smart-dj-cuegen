from __future__ import annotations
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

_JOBS_DIR = Path.home() / ".dj-cue" / "jobs"


def _jobs_dir() -> Path:
    _JOBS_DIR.mkdir(parents=True, exist_ok=True)
    return _JOBS_DIR


def _job_path(job_id: str) -> Path:
    return _jobs_dir() / f"{job_id}.json"


@dataclass
class JobTrack:
    path: str
    title: str
    status: str  # pending | done | failed | skipped
    source: str = ""
    error: str = ""


@dataclass
class Job:
    id: str
    created_at: str
    hq: bool
    tracks: list[JobTrack] = field(default_factory=list)


def _write(job: Job) -> None:
    path = _job_path(job.id)
    tmp = path.with_suffix(".tmp")
    data = {
        "id": job.id,
        "created_at": job.created_at,
        "hq": job.hq,
        "tracks": [
            {"path": t.path, "title": t.title, "status": t.status,
             "source": t.source, "error": t.error}
            for t in job.tracks
        ],
    }
    tmp.write_text(json.dumps(data, indent=2))
    tmp.rename(path)


def _parse_job(data: dict) -> Job:
    return Job(
        id=data["id"],
        created_at=data["created_at"],
        hq=data["hq"],
        tracks=[
            JobTrack(
                path=t["path"], title=t["title"], status=t["status"],
                source=t.get("source", ""), error=t.get("error", ""),
            )
            for t in data["tracks"]
        ],
    )


def create(tracks: list[tuple[str, str]], hq: bool) -> Job:
    now = datetime.now(timezone.utc)
    job_id = now.strftime("%Y-%m-%dT%H-%M-%S") + f"-{now.microsecond:06d}Z"
    job = Job(
        id=job_id,
        created_at=now.isoformat(),
        hq=hq,
        tracks=[JobTrack(path=p, title=t, status="pending") for p, t in tracks],
    )
    _write(job)
    return job


def update_track(job: Job, path: str, status: str, source: str = "", error: str = "") -> None:
    for t in job.tracks:
        if t.path == path:
            t.status = status
            t.source = source
            t.error = error
            _write(job)
            break


def _safe_load(path: Path) -> Job | None:
    try:
        return _parse_job(json.loads(path.read_text()))
    except (json.JSONDecodeError, KeyError, OSError):
        return None


def load(job_id: str) -> Job | None:
    path = _job_path(job_id)
    if not path.exists():
        return None
    return _safe_load(path)


def latest() -> Job | None:
    for f in sorted(_jobs_dir().glob("*.json"), reverse=True):
        job = _safe_load(f)
        if job is not None:
            return job
    return None


def list_all() -> list[Job]:
    jobs = []
    for f in sorted(_jobs_dir().glob("*.json"), reverse=True):
        job = _safe_load(f)
        if job is not None:
            jobs.append(job)
    return jobs

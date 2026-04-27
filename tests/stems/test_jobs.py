import pytest
import dj_cue_system.stems.jobs as stems_jobs


@pytest.fixture(autouse=True)
def isolated_jobs(tmp_path, monkeypatch):
    monkeypatch.setattr(stems_jobs, "_JOBS_DIR", tmp_path)


def test_create_writes_file():
    tracks = [("/music/a.mp3", "Track A"), ("/music/b.mp3", "Track B")]
    job = stems_jobs.create(tracks, hq=True)
    assert job.hq is True
    assert len(job.tracks) == 2
    assert all(t.status == "pending" for t in job.tracks)
    assert job.tracks[0].path == "/music/a.mp3"
    assert job.tracks[1].title == "Track B"


def test_create_job_file_exists(tmp_path):
    job = stems_jobs.create([("/music/a.mp3", "A")], hq=False)
    assert (tmp_path / f"{job.id}.json").exists()


def test_update_track_done():
    job = stems_jobs.create([("/music/a.mp3", "A"), ("/music/b.mp3", "B")], hq=True)
    stems_jobs.update_track(job, "/music/a.mp3", "done", source="demucs")
    assert job.tracks[0].status == "done"
    assert job.tracks[0].source == "demucs"
    assert job.tracks[1].status == "pending"


def test_update_track_failed():
    job = stems_jobs.create([("/music/a.mp3", "A")], hq=True)
    stems_jobs.update_track(job, "/music/a.mp3", "failed", error="RuntimeError: bad file")
    assert job.tracks[0].status == "failed"
    assert job.tracks[0].error == "RuntimeError: bad file"


def test_update_track_persisted_to_disk(tmp_path):
    job = stems_jobs.create([("/music/a.mp3", "A")], hq=True)
    stems_jobs.update_track(job, "/music/a.mp3", "done", source="demucs")
    reloaded = stems_jobs.load(job.id)
    assert reloaded is not None
    assert reloaded.tracks[0].status == "done"
    assert reloaded.tracks[0].source == "demucs"


def test_load_nonexistent():
    assert stems_jobs.load("2099-01-01T00-00-00Z") is None


def test_latest_none_when_no_jobs():
    assert stems_jobs.latest() is None


def test_latest_returns_most_recent(tmp_path):
    job1 = stems_jobs.create([("/a.mp3", "A")], hq=True)
    job2 = stems_jobs.create([("/b.mp3", "B")], hq=False)
    latest = stems_jobs.latest()
    assert latest is not None
    assert latest.id == job2.id


def test_list_all_newest_first(tmp_path):
    job1 = stems_jobs.create([("/a.mp3", "A")], hq=True)
    job2 = stems_jobs.create([("/b.mp3", "B")], hq=False)
    all_jobs = stems_jobs.list_all()
    assert len(all_jobs) == 2
    assert all_jobs[0].id == job2.id
    assert all_jobs[1].id == job1.id


def test_list_all_empty():
    assert stems_jobs.list_all() == []

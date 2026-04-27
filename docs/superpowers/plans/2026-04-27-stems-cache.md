# Stems Cache & Bulk Processing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `stems` command group that pre-processes tracks with Demucs/librosa and caches results to disk, so `analyze` and `show-elements` reuse cached stems instead of re-running analysis.

**Architecture:** Two new modules (`stems/cache.py`, `stems/jobs.py`) handle file-based persistence. A `_get_stem_onsets()` helper in `cli.py` implements the cache-read-first logic used by existing commands. A new `stems_app` Typer sub-group adds `stems run`, `stems status`, `stems jobs`, `stems cache list`, and `stems cache clear`.

**Tech Stack:** Python stdlib only for new modules (`hashlib`, `json`, `pathlib`, `datetime`). `rich.progress` for `stems run` progress display (already used). `typer` for CLI (already used).

---

### File Map

**Create:**
- `src/dj_cue_system/stems/__init__.py` — empty package marker
- `src/dj_cue_system/stems/cache.py` — `load()`, `save()`, `list_entries()`, `clear()`, `CacheEntry`
- `src/dj_cue_system/stems/jobs.py` — `create()`, `update_track()`, `load()`, `latest()`, `list_all()`, `Job`, `JobTrack`
- `tests/stems/__init__.py` — empty
- `tests/stems/test_cache.py` — cache roundtrip, clear by path, clear all, list entries
- `tests/stems/test_jobs.py` — create, update_track transitions, load, latest

**Modify:**
- `src/dj_cue_system/cli.py` — add `_get_stem_onsets()`, refactor `_analyze_track`/`run_full_analysis` to return `(AnalysisResult, str | None)`, update all callers, add `stems_app`/`stems_cache_app`, add `show-elements` cache annotation
- `tests/cli/test_cli.py` — extend with cache-hit and librosa+hq warning tests

---

### Task 1: `stems/cache.py` — storage layer

**Files:**
- Create: `src/dj_cue_system/stems/__init__.py`
- Create: `src/dj_cue_system/stems/cache.py`
- Create: `tests/stems/__init__.py`
- Create: `tests/stems/test_cache.py`

- [ ] **Step 1: Create the package files**

Create `src/dj_cue_system/stems/__init__.py` (empty) and `tests/stems/__init__.py` (empty).

- [ ] **Step 2: Write the failing tests**

`tests/stems/test_cache.py`:
```python
import pytest
import dj_cue_system.stems.cache as stems_cache
from dj_cue_system.analysis.models import StemOnsets


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(stems_cache, "_CACHE_DIR", tmp_path)


def test_load_miss():
    assert stems_cache.load("/no/such/track.mp3") is None


def test_save_and_load_demucs():
    onsets = StemOnsets(vocal=55.2, drum=4.1, bass=15.8, other=4.0)
    stems_cache.save("/music/track.mp3", onsets, "demucs")
    result = stems_cache.load("/music/track.mp3")
    assert result is not None
    loaded_onsets, source = result
    assert source == "demucs"
    assert loaded_onsets.vocal == 55.2
    assert loaded_onsets.drum == 4.1
    assert loaded_onsets.bass == 15.8
    assert loaded_onsets.other == 4.0


def test_save_and_load_with_none_values():
    onsets = StemOnsets(vocal=None, drum=None, bass=None, other=None)
    stems_cache.save("/music/silent.mp3", onsets, "librosa")
    result = stems_cache.load("/music/silent.mp3")
    assert result is not None
    loaded_onsets, source = result
    assert source == "librosa"
    assert loaded_onsets.vocal is None


def test_same_path_returns_same_cache_key():
    onsets = StemOnsets(vocal=1.0)
    stems_cache.save("/music/track.mp3", onsets, "demucs")
    # Saving again overwrites
    onsets2 = StemOnsets(vocal=2.0)
    stems_cache.save("/music/track.mp3", onsets2, "librosa")
    result = stems_cache.load("/music/track.mp3")
    assert result is not None
    loaded, source = result
    assert loaded.vocal == 2.0
    assert source == "librosa"


def test_list_entries_empty():
    assert stems_cache.list_entries() == []


def test_list_entries_populated():
    stems_cache.save("/music/a.mp3", StemOnsets(vocal=1.0), "demucs")
    stems_cache.save("/music/b.mp3", StemOnsets(vocal=2.0), "librosa")
    entries = stems_cache.list_entries()
    assert len(entries) == 2
    paths = {e.audio_path for e in entries}
    assert "/music/a.mp3" in paths
    assert "/music/b.mp3" in paths
    sources = {e.audio_path: e.source for e in entries}
    assert sources["/music/a.mp3"] == "demucs"
    assert sources["/music/b.mp3"] == "librosa"


def test_clear_all():
    stems_cache.save("/music/a.mp3", StemOnsets(), "demucs")
    stems_cache.save("/music/b.mp3", StemOnsets(), "librosa")
    count = stems_cache.clear()
    assert count == 2
    assert stems_cache.load("/music/a.mp3") is None
    assert stems_cache.load("/music/b.mp3") is None


def test_clear_by_path():
    stems_cache.save("/music/a.mp3", StemOnsets(), "demucs")
    stems_cache.save("/music/b.mp3", StemOnsets(), "demucs")
    count = stems_cache.clear("/music/a.mp3")
    assert count == 1
    assert stems_cache.load("/music/a.mp3") is None
    assert stems_cache.load("/music/b.mp3") is not None


def test_clear_nonexistent_path():
    count = stems_cache.clear("/no/such/track.mp3")
    assert count == 0
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd /Users/kevin_janssen/Code/smart-dj-cuegen && .venv/bin/python -m pytest tests/stems/test_cache.py -v 2>&1 | head -30
```
Expected: `ModuleNotFoundError` or similar — `stems.cache` doesn't exist yet.

- [ ] **Step 4: Write `stems/cache.py`**

`src/dj_cue_system/stems/cache.py`:
```python
from __future__ import annotations
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from dj_cue_system.analysis.models import StemOnsets

_CACHE_DIR = Path.home() / ".dj-cue" / "stems-cache"


def _cache_dir() -> Path:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return _CACHE_DIR


def _cache_key(audio_path: str) -> str:
    abs_path = os.path.abspath(audio_path)
    return hashlib.sha256(abs_path.encode()).hexdigest()[:16]


@dataclass
class CacheEntry:
    audio_path: str
    source: str
    computed_at: str
    vocal: float | None
    drum: float | None
    bass: float | None
    other: float | None


def load(audio_path: str) -> tuple[StemOnsets, str] | None:
    path = _cache_dir() / f"{_cache_key(audio_path)}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    onsets = StemOnsets(
        vocal=data.get("vocal"),
        drum=data.get("drum"),
        bass=data.get("bass"),
        other=data.get("other"),
    )
    return onsets, data["source"]


def save(audio_path: str, onsets: StemOnsets, source: str) -> None:
    path = _cache_dir() / f"{_cache_key(audio_path)}.json"
    data = {
        "audio_path": os.path.abspath(audio_path),
        "source": source,
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "vocal": onsets.vocal,
        "drum": onsets.drum,
        "bass": onsets.bass,
        "other": onsets.other,
    }
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.rename(path)


def list_entries() -> list[CacheEntry]:
    entries = []
    for f in _cache_dir().glob("*.json"):
        try:
            data = json.loads(f.read_text())
            entries.append(CacheEntry(
                audio_path=data["audio_path"],
                source=data["source"],
                computed_at=data["computed_at"],
                vocal=data.get("vocal"),
                drum=data.get("drum"),
                bass=data.get("bass"),
                other=data.get("other"),
            ))
        except Exception:
            continue
    return sorted(entries, key=lambda e: e.audio_path)


def clear(audio_path: str | None = None) -> int:
    count = 0
    if audio_path is not None:
        path = _cache_dir() / f"{_cache_key(audio_path)}.json"
        if path.exists():
            path.unlink()
            count = 1
    else:
        for f in _cache_dir().glob("*.json"):
            f.unlink()
            count += 1
    return count
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest tests/stems/test_cache.py -v
```
Expected: all 9 tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/dj_cue_system/stems/ tests/stems/
git commit -m "feat: add stems cache module with save/load/list/clear"
```

---

### Task 2: `stems/jobs.py` — job state persistence

**Files:**
- Create: `src/dj_cue_system/stems/jobs.py`
- Create: `tests/stems/test_jobs.py`

- [ ] **Step 1: Write the failing tests**

`tests/stems/test_jobs.py`:
```python
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


def test_create_job_file_exists(tmp_path, monkeypatch):
    monkeypatch.setattr(stems_jobs, "_JOBS_DIR", tmp_path)
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


def test_update_track_persisted_to_disk(tmp_path, monkeypatch):
    monkeypatch.setattr(stems_jobs, "_JOBS_DIR", tmp_path)
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


def test_latest_returns_most_recent(tmp_path, monkeypatch):
    monkeypatch.setattr(stems_jobs, "_JOBS_DIR", tmp_path)
    job1 = stems_jobs.create([("/a.mp3", "A")], hq=True)
    job2 = stems_jobs.create([("/b.mp3", "B")], hq=False)
    latest = stems_jobs.latest()
    assert latest is not None
    assert latest.id == job2.id


def test_list_all_newest_first(tmp_path, monkeypatch):
    monkeypatch.setattr(stems_jobs, "_JOBS_DIR", tmp_path)
    job1 = stems_jobs.create([("/a.mp3", "A")], hq=True)
    job2 = stems_jobs.create([("/b.mp3", "B")], hq=False)
    all_jobs = stems_jobs.list_all()
    assert len(all_jobs) == 2
    assert all_jobs[0].id == job2.id
    assert all_jobs[1].id == job1.id


def test_list_all_empty():
    assert stems_jobs.list_all() == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest tests/stems/test_jobs.py -v 2>&1 | head -20
```
Expected: `ModuleNotFoundError` — `stems.jobs` doesn't exist yet.

- [ ] **Step 3: Write `stems/jobs.py`**

`src/dj_cue_system/stems/jobs.py`:
```python
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
    job_id = now.strftime("%Y-%m-%dT%H-%M-%SZ")
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
            break
    _write(job)


def load(job_id: str) -> Job | None:
    path = _job_path(job_id)
    if not path.exists():
        return None
    return _parse_job(json.loads(path.read_text()))


def latest() -> Job | None:
    files = sorted(_jobs_dir().glob("*.json"), reverse=True)
    for f in files:
        try:
            return _parse_job(json.loads(f.read_text()))
        except Exception:
            continue
    return None


def list_all() -> list[Job]:
    jobs = []
    for f in sorted(_jobs_dir().glob("*.json"), reverse=True):
        try:
            jobs.append(_parse_job(json.loads(f.read_text())))
        except Exception:
            continue
    return jobs
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest tests/stems/test_jobs.py -v
```
Expected: all 10 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/dj_cue_system/stems/jobs.py tests/stems/test_jobs.py
git commit -m "feat: add stems jobs module with create/update/load/latest/list"
```

---

### Task 3: `_get_stem_onsets()` + refactor `cli.py` helper functions

`_analyze_track` and `run_full_analysis` are refactored to use `_get_stem_onsets`, which handles the cache read/write and librosa+hq warning. Both now return `(AnalysisResult, str | None)` — the second value is the cache source string if stems came from cache, or `None` if freshly computed. All callers in `analyze` unpack with `result, _ = ...`. `show-elements` captures the second value for the cache annotation.

**Files:**
- Modify: `src/dj_cue_system/cli.py`

- [ ] **Step 1: Add `_get_stem_onsets()` above `_analyze_track`**

In `cli.py`, add this function between the imports and `run_full_analysis` (insert after line 30, `DEFAULT_BACKUP_DIR = ...`):

```python
def _get_stem_onsets(
    audio_path: str,
    config: AppConfig,
    hq: bool,
    force: bool = False,
) -> tuple["StemOnsets", str | None]:
    """Return (StemOnsets, cache_source).

    cache_source is the source string ("demucs" or "librosa") when returning
    a cached result, or None when freshly computed (and saved to cache).
    force=True bypasses the cache read (used by stems run).
    """
    from dj_cue_system.analysis.models import StemOnsets
    from dj_cue_system.stems import cache as stems_cache

    if not force:
        cached = stems_cache.load(audio_path)
        if cached is not None:
            onsets, source = cached
            if hq and source == "librosa":
                console.print(
                    f"[yellow]⚠ Using cached librosa result for "
                    f"{os.path.basename(audio_path)!r}; run "
                    f'`dj-cue stems run --path "{audio_path}"` '
                    f"to compute Demucs stems[/yellow]"
                )
            return onsets, source

    thresholds = config.settings.onset_thresholds
    w = config.settings.onset_window_frames
    if hq:
        from dj_cue_system.analysis.separation import separate_stems
        from dj_cue_system.analysis.onset import detect_onset_rms
        stems = separate_stems(audio_path, model_name=config.settings.demucs_model)
        onsets = StemOnsets(
            vocal=detect_onset_rms(stems.vocals, stems.sample_rate, thresholds.vocal, w),
            drum=detect_onset_rms(stems.drums, stems.sample_rate, thresholds.drum, w),
            bass=detect_onset_rms(stems.bass, stems.sample_rate, thresholds.bass, w),
            other=detect_onset_rms(stems.other, stems.sample_rate, thresholds.other, w),
        )
        source = "demucs"
    else:
        from dj_cue_system.analysis.fast_stems import detect_stem_onsets_fast
        onsets = detect_stem_onsets_fast(audio_path, thresholds, w)
        source = "librosa"

    stems_cache.save(audio_path, onsets, source)
    return onsets, None
```

- [ ] **Step 2: Replace `run_full_analysis`**

Replace the entire `run_full_analysis` function with:

```python
def run_full_analysis(audio_path: str, config: AppConfig, hq: bool = False) -> tuple["AnalysisResult", str | None]:
    """Analyze a bare audio file and return (result, cache_source)."""
    from dj_cue_system.analysis.fallback import analyze_with_allin1

    result = analyze_with_allin1(audio_path)
    onsets, cache_source = _get_stem_onsets(audio_path, config, hq)
    result.stem_onsets = onsets
    return result, cache_source
```

- [ ] **Step 3: Replace `_analyze_track`**

Replace the entire `_analyze_track` function with:

```python
def _analyze_track(
    track: Track,
    config: AppConfig,
    db_path: str | None = None,
    hq: bool = False,
) -> tuple["AnalysisResult", str | None]:
    """ANLZ path if files exist, else all-in-one fallback. Returns (result, cache_source)."""
    from dj_cue_system.analysis.fallback import analyze_with_allin1
    from dj_cue_system.analysis.anlz import parse_beat_grid, parse_phrases
    from dj_cue_system.analysis.assembler import build_sections
    from dj_cue_system.analysis.models import AnalysisResult, StemOnsets

    result = None
    if track.analysis_data_path:
        share_dir = os.path.join(os.path.dirname(db_path or DEFAULT_DB_PATH), "share")
        dat_path = os.path.join(share_dir, track.analysis_data_path.lstrip("/"))
        ext_path = dat_path.replace(".DAT", ".EXT")
        if os.path.exists(dat_path) and os.path.exists(ext_path):
            try:
                from pyrekordbox.anlz import AnlzFile
                beat_grid = parse_beat_grid(dat_path)
                phrases = parse_phrases(ext_path)
                tag = AnlzFile.parse_file(dat_path).get_tag("PQTZ")
                all_beat_times = list(tag.times)
                sections = build_sections(phrases, beat_grid, all_beat_times)
                result = AnalysisResult(
                    bpm=beat_grid.bpm,
                    downbeats=beat_grid.downbeats,
                    total_bars=beat_grid.total_bars,
                    sections=sections,
                    stem_onsets=StemOnsets(),
                    audio_path=track.path,
                    anlz_source=True,
                )
            except Exception:
                pass

    if result is None:
        result = analyze_with_allin1(track.path)

    onsets, cache_source = _get_stem_onsets(track.path, config, hq)
    result.stem_onsets = onsets
    return result, cache_source
```

- [ ] **Step 4: Update `analyze` command callers**

In the `analyze` command body, update the three call sites to unpack the tuple. Find:

```python
                    result = _analyze_track(track, cfg, db_path=db, hq=hq)
                fake_track = _make_fake_track(audio_file, title=track.title, artist=track.artist)
            else:
                result = run_full_analysis(audio_file, cfg, hq=hq)
```

Replace with:

```python
                    result, _ = _analyze_track(track, cfg, db_path=db, hq=hq)
                fake_track = _make_fake_track(audio_file, title=track.title, artist=track.artist)
            else:
                result, _ = run_full_analysis(audio_file, cfg, hq=hq)
```

And the library-loop call site:

```python
                        result = _analyze_track(track, cfg, db_path=db, hq=hq)
```

Replace with:

```python
                        result, _ = _analyze_track(track, cfg, db_path=db, hq=hq)
```

- [ ] **Step 5: Update `show_elements` to capture cache source and show annotation**

In the `show_elements` function, find:

```python
        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter("always")
            warnings.filterwarnings("ignore", message="aifc was removed")
            warnings.filterwarnings("ignore", message="sunau was removed")
            track = get_track_by_path(audio_file)
            if track:
                result = _analyze_track(track, cfg, hq=hq)
            else:
                result = run_full_analysis(audio_file, cfg, hq=hq)
```

Replace with:

```python
        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter("always")
            warnings.filterwarnings("ignore", message="aifc was removed")
            warnings.filterwarnings("ignore", message="sunau was removed")
            track = get_track_by_path(audio_file)
            if track:
                result, cache_source = _analyze_track(track, cfg, hq=hq)
            else:
                result, cache_source = run_full_analysis(audio_file, cfg, hq=hq)
```

Then find:

```python
    console.print("\n[bold]Stem onsets:[/bold]")
```

Replace with:

```python
    cache_label = f"  [dim](cached · {cache_source})[/dim]" if cache_source else ""
    console.print(f"\n[bold]Stem onsets:[/bold]{cache_label}")
```

- [ ] **Step 6: Run existing tests to verify nothing broke**

```bash
.venv/bin/python -m pytest tests/ -v
```
Expected: all existing tests still pass. (The `test_show_elements` and `test_analyze_single_dry_run` tests mock `run_full_analysis` — those mocks return a bare `AnalysisResult`, not a tuple. The tests will now fail because the refactored code expects a tuple. Fix the mocks in Step 7.)

- [ ] **Step 7: Fix CLI test mocks to return tuples**

In `tests/cli/test_cli.py`, update the two mock patches to return `(result, None)`:

Find:
```python
    with patch("dj_cue_system.cli.run_full_analysis", return_value=_mock_result()):
        result = runner.invoke(app, ["show-elements", "/music/track.mp3", "--config", str(cfg)])
```
Replace with:
```python
    with patch("dj_cue_system.cli.run_full_analysis", return_value=(_mock_result(), None)):
        result = runner.invoke(app, ["show-elements", "/music/track.mp3", "--config", str(cfg)])
```

Find:
```python
    with patch("dj_cue_system.cli.run_full_analysis", return_value=_mock_result()), \
```
Replace with:
```python
    with patch("dj_cue_system.cli.run_full_analysis", return_value=(_mock_result(), None)), \
```

- [ ] **Step 8: Run all tests again**

```bash
.venv/bin/python -m pytest tests/ -v
```
Expected: all tests pass.

- [ ] **Step 9: Commit**

```bash
git add src/dj_cue_system/cli.py tests/cli/test_cli.py
git commit -m "feat: add _get_stem_onsets with cache integration; show-elements annotates cached results"
```

---

### Task 4: `stems run` command

**Files:**
- Modify: `src/dj_cue_system/cli.py`

- [ ] **Step 1: Wire `stems_app` and `stems_cache_app` into `app`**

In `cli.py`, add after `backup_app = typer.Typer(...)` and `app.add_typer(backup_app, ...)`:

```python
stems_app = typer.Typer(help="Stem onset detection and caching")
stems_cache_app = typer.Typer(help="Manage the stems cache")
stems_app.add_typer(stems_cache_app, name="cache")
app.add_typer(stems_app, name="stems")
```

- [ ] **Step 2: Write the `stems run` command**

Add this function to `cli.py` (after the `restore` command):

```python
@stems_app.command("run")
def stems_run(
    paths: list[str] = typer.Option([], "--path", help="Audio file paths to process. Repeatable: --path a.mp3 --path b.mp3."),
    library: bool = typer.Option(False, "--library", help="Process all tracks in your Rekordbox library."),
    playlist: list[str] = typer.Option([], "--playlist", help="Limit to tracks in this Rekordbox playlist. Repeatable."),
    hq: bool = typer.Option(True, "--hq/--no-hq", help="Use Demucs (default) or fast librosa for stem detection."),
    force: bool = typer.Option(False, "--force", help="Re-process tracks already in cache."),
    db: Optional[str] = typer.Option(None, "--db", help="Path to Rekordbox master.db. Auto-detected on Mac."),
    config: str = typer.Option(DEFAULT_CONFIG, "--config", help="Path to rules.yaml config file."),
):
    """Pre-process stem onset detection and cache results for later use."""
    from dj_cue_system.stems import cache as stems_cache
    from dj_cue_system.stems import jobs as stems_jobs

    cfg = load_config(config)

    # Build (path, title) list
    track_pairs: list[tuple[str, str]] = []
    if paths:
        for p in paths:
            track_pairs.append((os.path.abspath(p), os.path.splitext(os.path.basename(p))[0]))
    if library or playlist:
        try:
            tracks = get_tracks(db)
            playlist_map = get_track_playlists(db)
            for t in tracks:
                t.playlists = playlist_map.get(t.id, [])
            if playlist:
                tracks = [t for t in tracks if any(p in t.playlists for p in playlist)]
            for t in tracks:
                track_pairs.append((t.path, t.title or os.path.basename(t.path)))
        except FileNotFoundError as e:
            console.print(f"[red]✗ Database not found:[/red] {e}")
            raise typer.Exit(1)

    if not track_pairs:
        console.print("[yellow]No tracks specified. Use --path, --library, or --playlist.[/yellow]")
        raise typer.Exit(1)

    # Mark cached tracks as skipped up front
    initial_statuses: list[str] = []
    for path, _ in track_pairs:
        if not force and stems_cache.load(path) is not None:
            initial_statuses.append("skipped")
        else:
            initial_statuses.append("pending")

    job = stems_jobs.create(track_pairs, hq=hq)
    for (path, _), status in zip(track_pairs, initial_statuses):
        if status == "skipped":
            cached = stems_cache.load(path)
            src = cached[1] if cached else ""
            stems_jobs.update_track(job, path, "skipped", source=src)

    pending_count = initial_statuses.count("pending")
    console.print(f"\nJob [bold]{job.id}[/bold]  ({pending_count} to process, {len(track_pairs) - pending_count} already cached)\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Starting…", total=pending_count)
        processed = 0
        for (path, title), status in zip(track_pairs, initial_statuses):
            if status == "skipped":
                continue
            progress.update(task, description=f"[bold]{title}[/bold]")
            try:
                with warnings.catch_warnings(record=True):
                    onsets, _ = _get_stem_onsets(path, cfg, hq, force=True)
                source = "demucs" if hq else "librosa"
                stems_jobs.update_track(job, path, "done", source=source)
            except Exception as e:
                stems_jobs.update_track(job, path, "failed", error=str(e))
                progress.console.print(f"[red]✗ Failed {title!r}: {e}[/red]")
            processed += 1
            progress.advance(task)

    done = sum(1 for t in job.tracks if t.status == "done")
    failed = sum(1 for t in job.tracks if t.status == "failed")
    skipped = sum(1 for t in job.tracks if t.status == "skipped")
    console.print(f"\n[green]Done.[/green]  {done} processed, {skipped} skipped (cached), {failed} failed")
    console.print(f"Run [bold]dj-cue stems status {job.id}[/bold] to review details.")
```

- [ ] **Step 3: Verify the command registers correctly**

```bash
.venv/bin/python -m dj_cue_system.cli stems --help
```
Expected: shows `run` as a subcommand.

```bash
.venv/bin/python -m dj_cue_system.cli stems run --help
```
Expected: shows `--path`, `--library`, `--playlist`, `--hq/--no-hq`, `--force`, `--db`.

- [ ] **Step 4: Run all tests**

```bash
.venv/bin/python -m pytest tests/ -v
```
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/dj_cue_system/cli.py
git commit -m "feat: add stems run command with job tracking and cache integration"
```

---

### Task 5: `stems status` and `stems jobs` commands

**Files:**
- Modify: `src/dj_cue_system/cli.py`

- [ ] **Step 1: Write `stems status`**

Add after `stems_run`:

```python
@stems_app.command("status")
def stems_status(
    job_id: Optional[str] = typer.Argument(None, help="Job ID to inspect. Defaults to the most recent job."),
):
    """Show the current state of a stems run job."""
    from dj_cue_system.stems import jobs as stems_jobs

    if job_id:
        job = stems_jobs.load(job_id)
        if job is None:
            console.print(f"[red]✗ Job not found:[/red] {job_id}")
            raise typer.Exit(1)
    else:
        job = stems_jobs.latest()
        if job is None:
            console.print("[dim]No jobs found. Run `dj-cue stems run` to start one.[/dim]")
            raise typer.Exit(1)

    mode = "HQ/Demucs" if job.hq else "fast/librosa"
    console.print(f"\nJob [bold]{job.id}[/bold]  ({mode})")
    console.print(f"Created: {job.created_at[:19].replace('T', ' ')}\n")

    done = sum(1 for t in job.tracks if t.status == "done")
    failed = sum(1 for t in job.tracks if t.status == "failed")
    pending = sum(1 for t in job.tracks if t.status == "pending")
    total = len(job.tracks)
    console.print(f"Progress: {done + sum(1 for t in job.tracks if t.status == 'skipped')}/{total}  |  {failed} failed  |  {pending} pending\n")

    for t in job.tracks:
        title = t.title or os.path.basename(t.path)
        if t.status == "done":
            console.print(f"  [green]✓[/green] {title:<40} ({t.source})")
        elif t.status == "skipped":
            console.print(f"  [dim]↷ {title:<40} (skipped — already cached)[/dim]")
        elif t.status == "failed":
            console.print(f"  [red]✗[/red] {title:<40} {t.error}")
        else:
            console.print(f"  [dim]· {title}[/dim]")
```

- [ ] **Step 2: Write `stems jobs`**

Add after `stems_status`:

```python
@stems_app.command("jobs")
def stems_jobs_list():
    """List all stems run jobs, newest first."""
    from dj_cue_system.stems import jobs as stems_jobs

    all_jobs = stems_jobs.list_all()
    if not all_jobs:
        console.print("[dim]No jobs found.[/dim]")
        return

    for job in all_jobs:
        done = sum(1 for t in job.tracks if t.status == "done")
        failed = sum(1 for t in job.tracks if t.status == "failed")
        pending = sum(1 for t in job.tracks if t.status == "pending")
        total = len(job.tracks)
        mode = "HQ" if job.hq else "fast"
        console.print(
            f"  {job.id}   {total} tracks   "
            f"[green]{done} done[/green]   "
            f"[red]{failed} failed[/red]   "
            f"{pending} pending   {mode}"
        )
```

- [ ] **Step 3: Verify commands register**

```bash
.venv/bin/python -m dj_cue_system.cli stems --help
```
Expected: shows `run`, `status`, `jobs`, `cache` as subcommands.

- [ ] **Step 4: Run all tests**

```bash
.venv/bin/python -m pytest tests/ -v
```
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/dj_cue_system/cli.py
git commit -m "feat: add stems status and stems jobs commands"
```

---

### Task 6: `stems cache list` and `stems cache clear` commands

**Files:**
- Modify: `src/dj_cue_system/cli.py`

- [ ] **Step 1: Write `stems cache list`**

Add to `cli.py`:

```python
@stems_cache_app.command("list")
def stems_cache_list():
    """List all cached stem onset results."""
    from dj_cue_system.stems import cache as stems_cache

    entries = stems_cache.list_entries()
    if not entries:
        console.print("[dim]No cached stems found.[/dim]")
        return
    for e in entries:
        date = e.computed_at[:10]
        console.print(f"  {e.audio_path:<60} {e.source:<8} {date}")
```

- [ ] **Step 2: Write `stems cache clear`**

Add after `stems_cache_list`:

```python
@stems_cache_app.command("clear")
def stems_cache_clear(
    path: Optional[str] = typer.Option(None, "--path", help="Clear the cache entry for this specific audio file path."),
):
    """Clear cached stem onset results. Clears all entries unless --path is given."""
    from dj_cue_system.stems import cache as stems_cache

    if path is None:
        typer.confirm("This will delete all cached stem results. Continue?", abort=True)
        count = stems_cache.clear()
        console.print(f"[green]Cleared {count} cache entries.[/green]")
    else:
        count = stems_cache.clear(path)
        if count == 0:
            console.print(f"[yellow]No cache entry found for:[/yellow] {path}")
        else:
            console.print(f"[green]Cleared cache entry for:[/green] {path}")
```

- [ ] **Step 3: Verify commands register**

```bash
.venv/bin/python -m dj_cue_system.cli stems cache --help
```
Expected: shows `list` and `clear` as subcommands.

- [ ] **Step 4: Run all tests**

```bash
.venv/bin/python -m pytest tests/ -v
```
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/dj_cue_system/cli.py
git commit -m "feat: add stems cache list and stems cache clear commands"
```

---

### Task 7: CLI integration tests for cache behavior

**Files:**
- Modify: `tests/cli/test_cli.py`

- [ ] **Step 1: Write failing tests for cache-hit skip and librosa+hq warning**

Add to `tests/cli/test_cli.py`:

```python
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
    from dj_cue_system.analysis.models import StemOnsets
    from dj_cue_system.cli import _get_stem_onsets
    from dj_cue_system.rules.config import load_config

    monkeypatch.setattr(stems_cache, "_CACHE_DIR", tmp_path)
    stems_cache.save("/music/track.mp3", StemOnsets(vocal=1.0), "demucs")

    cfg_file = tmp_path / "rules.yaml"
    cfg_file.write_text("rulesets: {}\ndefaults:\n  rulesets: []\n")
    cfg = load_config(str(cfg_file))

    with patch("dj_cue_system.analysis.fast_stems.detect_stem_onsets_fast") as mock_fast:
        onsets, source = _get_stem_onsets("/music/track.mp3", cfg, hq=False)

    mock_fast.assert_not_called()
    assert source == "demucs"
    assert onsets.vocal == 1.0


def test_get_stem_onsets_warns_on_librosa_cache_with_hq(tmp_path, monkeypatch, capsys):
    """_get_stem_onsets warns when cache has librosa result but --hq is requested."""
    import dj_cue_system.stems.cache as stems_cache
    from dj_cue_system.analysis.models import StemOnsets
    from dj_cue_system.cli import _get_stem_onsets
    from dj_cue_system.rules.config import load_config

    monkeypatch.setattr(stems_cache, "_CACHE_DIR", tmp_path)
    stems_cache.save("/music/track.mp3", StemOnsets(vocal=1.0), "librosa")

    cfg_file = tmp_path / "rules.yaml"
    cfg_file.write_text("rulesets: {}\ndefaults:\n  rulesets: []\n")
    cfg = load_config(str(cfg_file))

    onsets, source = _get_stem_onsets("/music/track.mp3", cfg, hq=True)

    assert source == "librosa"
    assert onsets.vocal == 1.0


def test_stems_run_skips_cached_tracks(tmp_path, monkeypatch):
    """stems run marks already-cached tracks as skipped."""
    import dj_cue_system.stems.cache as stems_cache
    import dj_cue_system.stems.jobs as stems_jobs
    from dj_cue_system.analysis.models import StemOnsets

    monkeypatch.setattr(stems_cache, "_CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(stems_jobs, "_JOBS_DIR", tmp_path / "jobs")

    stems_cache.save("/music/track.mp3", StemOnsets(vocal=1.0), "demucs")

    cfg = tmp_path / "rules.yaml"
    cfg.write_text("rulesets: {}\ndefaults:\n  rulesets: []\nsettings:\n  demucs_model: htdemucs\n  onset_thresholds:\n    vocal: 0.01\n    drum: 0.01\n    bass: 0.01\n    other: 0.01\n  onset_window_frames: 3\n")

    with patch("dj_cue_system.analysis.fast_stems.detect_stem_onsets_fast") as mock_fast:
        result = runner.invoke(app, [
            "stems", "run", "--path", "/music/track.mp3",
            "--no-hq", "--config", str(cfg),
        ])

    assert result.exit_code == 0
    mock_fast.assert_not_called()
    assert "cached" in result.output
```

- [ ] **Step 2: Run tests to verify the new ones fail (existing tests still pass)**

```bash
.venv/bin/python -m pytest tests/cli/test_cli.py -v 2>&1 | tail -20
```
Expected: the 4 new tests fail, all existing tests pass.

- [ ] **Step 3: Run the full test suite to confirm all tests pass**

The new test code tests real behavior — if the implementation in Tasks 1–6 is correct, these tests should already pass without code changes. Run:

```bash
.venv/bin/python -m pytest tests/ -v
```
Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add tests/cli/test_cli.py
git commit -m "test: add CLI integration tests for stems cache hit and hq warning"
```

---

### Task 8: Final verification

- [ ] **Step 1: Run the complete test suite**

```bash
.venv/bin/python -m pytest tests/ -v
```
Expected: all tests pass, 0 failures.

- [ ] **Step 2: Verify full command tree is registered**

```bash
.venv/bin/python -m dj_cue_system.cli --help
```
Expected output includes `stems` in the list of commands.

```bash
.venv/bin/python -m dj_cue_system.cli stems --help
```
Expected: `run`, `status`, `jobs`, `cache`.

```bash
.venv/bin/python -m dj_cue_system.cli stems cache --help
```
Expected: `list`, `clear`.

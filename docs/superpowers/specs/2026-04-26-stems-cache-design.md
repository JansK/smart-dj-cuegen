# Stems Cache & Bulk Processing Design

**Date:** 2026-04-26
**Status:** Approved

## Problem

Demucs stem separation takes 5–10 minutes per track on CPU. Currently it runs inline every time `analyze` or `show-elements` is called with `--hq`, with no way to pre-process a library in bulk or reuse results across runs. The fast librosa path also re-runs on every call.

## Goals

- Bulk-process tracks with Demucs ahead of time via a dedicated `stems run` command
- Persist results so `analyze` and `show-elements` pick them up automatically
- Allow monitoring a running job from a second terminal
- Allow reviewing past job results
- Support resuming interrupted bulk runs implicitly via cache

## Non-Goals

- Sub-track progress granularity during a running job (future)
- Automatic cache expiry / staleness detection (manual clear only)
- Parallel track processing

---

## Storage

### Cache — `~/.dj-cue/stems-cache/<sha256(abs_path)[:16]>.json`

One file per track. Filename is a 16-char hex prefix of the SHA-256 of the absolute audio path, enabling O(1) lookup. Content:

```json
{
  "audio_path": "/abs/path/to/track.mp3",
  "source": "demucs",
  "computed_at": "2025-01-01T12:00:00Z",
  "vocal": 55.2,
  "drum": 4.1,
  "bass": 15.8,
  "other": 4.0
}
```

`source` is `"demucs"` or `"librosa"`. Cache never expires — only invalidated via `stems cache clear`.

### Jobs — `~/.dj-cue/jobs/<timestamp>.json`

One file per `stems run` invocation. Written after each track completes so polling `stems status` from another terminal sees live progress.

```json
{
  "id": "2025-01-01T12-00-00Z",
  "created_at": "2025-01-01T12:00:00Z",
  "hq": true,
  "tracks": [
    {"path": "/abs/path/track1.mp3", "title": "Track 1", "status": "done",    "source": "demucs", "error": ""},
    {"path": "/abs/path/track2.mp3", "title": "Track 2", "status": "failed",  "source": "",       "error": "RuntimeError: ..."},
    {"path": "/abs/path/track3.mp3", "title": "Track 3", "status": "skipped", "source": "demucs", "error": ""},
    {"path": "/abs/path/track4.mp3", "title": "Track 4", "status": "pending", "source": "",       "error": ""}
  ]
}
```

Track statuses: `pending`, `done`, `failed`, `skipped` (already in cache when job was created).

---

## CLI Commands

### `dj-cue stems run [FILE...] [--library] [--playlist X] [--hq/--no-hq] [--force]`

Bulk-processes tracks with stem onset detection and caches results.

- Accepts explicit file paths, `--library` (all Rekordbox tracks), or `--playlist`
- `--hq` defaults to **true** (Demucs); `--no-hq` uses fast librosa
- Tracks already in cache → marked `skipped` in the job, not re-processed
- `--force` bypasses cache and re-processes all tracks
- Creates a job file before starting; prints the job ID
- Updates the job file after each track (enables live polling from another terminal)
- Resume: re-run the same command — cached tracks are skipped instantly

### `dj-cue stems status [JOB_ID]`

Displays the current state of a job by reading its JSON file from disk. No JOB_ID = latest job. Safe to run concurrently with `stems run`.

Output format:
```
Job 2025-01-01T12-00-00Z  (HQ/Demucs)
Created: 2025-01-01 12:00:00

Progress: 47/50  |  1 failed  |  2 pending

  ✓ Track Name 1              (demucs)
  ✓ Track Name 2              (demucs)
  ↷ Track Name 3              (skipped — already cached)
  ✗ Track Name 4              RuntimeError: ...
  · Track Name 5              (pending)
```

### `dj-cue stems jobs`

One-line summary per job, newest first:
```
  2025-01-01T12-00-00Z   50 tracks   47 done   1 failed   2 pending   HQ
  2024-12-31T10-00-00Z   20 tracks   20 done   0 failed   0 pending   fast
```

### `dj-cue stems cache list`

Lists all cached tracks:
```
  /path/to/track1.mp3   demucs   2025-01-01
  /path/to/track2.mp3   librosa  2024-12-31
```

### `dj-cue stems cache clear [--path X]`

- `--path X` — removes the cache entry for that specific file
- No flag — clears all entries; prompts for confirmation first

---

## Integration with Existing Commands

A new helper `_get_stem_onsets(audio_path, cfg, hq, console)` is added to `cli.py`. Both `_analyze_track` and `run_full_analysis` call it instead of the analysis functions directly.

### Cache lookup logic

1. Check cache for this audio path
2. **Cache hit, any source, `--hq` not set** → use cached result
3. **Cache hit with `demucs` source, `--hq` set** → use cached result
4. **Cache hit with `librosa` source, `--hq` set** → print yellow warning:
   > `⚠ Using cached librosa result for "<track>"; run dj-cue stems run "<path>" to compute Demucs stems`
   Then use the cached result. Do not silently re-run Demucs.
5. **No cache** → run appropriate analysis (Demucs if `--hq`, librosa otherwise), save to cache, return

### UI annotation

`show-elements` appends `(cached · demucs)` or `(cached · librosa)` to the stem onsets header when a cached result is used.

---

## Module Structure

```
src/dj_cue_system/stems/
  __init__.py       # empty
  cache.py          # load(), save(), list_entries(), clear()
  jobs.py           # create(), update_track(), load(), latest(), list_all()
```

`cli.py` gains a `stems_app` Typer (parallel to the existing `backup_app`) and the `_get_stem_onsets()` helper. No changes to any `analysis/` module.

### `cache.py` public surface

```python
def load(audio_path: str) -> tuple[StemOnsets, str] | None: ...
    # Returns (onsets, source) or None if not cached

def save(audio_path: str, onsets: StemOnsets, source: str) -> None: ...

def list_entries() -> list[CacheEntry]: ...

def clear(audio_path: str | None = None) -> int: ...
    # Returns count of entries removed
```

### `jobs.py` public surface

```python
def create(tracks: list[tuple[str, str]], hq: bool) -> Job: ...
    # tracks = [(path, title), ...]

def update_track(job: Job, path: str, status: str, source: str = "", error: str = "") -> None: ...
    # Mutates job in-place and writes to disk

def load(job_id: str) -> Job | None: ...

def latest() -> Job | None: ...

def list_all() -> list[Job]: ...
```

---

## Testing Scope

- `tests/stems/test_cache.py` — roundtrip save/load, clear by path, clear all, list entries
- `tests/stems/test_jobs.py` — create, update_track state transitions, load, latest
- `tests/cli/test_cli.py` — extend existing CLI tests: cache hit skips analysis, librosa+`--hq` warning fires

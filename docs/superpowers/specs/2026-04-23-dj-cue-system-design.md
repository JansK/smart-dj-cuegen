# DJ Cue System — Design Spec

**Date:** 2026-04-23  
**Project:** `~/Code/dj-cue-system/`  
**Status:** Approved — ready for implementation planning

---

## Goal

A Python CLI tool that programmatically generates memory cues and loop points for DJ tracks, then writes them in a format readable by Rekordbox (and, in future, Serato). Analysis is driven by Rekordbox's own beat grid and phrase data (read from ANLZ files) combined with Demucs source separation for stem-level onset detection. Rules are configured in YAML and are composable, playlist-aware, and genre-tunable.

---

## High-Level Architecture

Five components, each with one clear job:

```
┌─────────────────────────────────────────────────────────────┐
│  CLI  (Typer)                                               │
│  analyze [file] | --library | --playlist "Deep House"       │
│  --overwrite | --dry-run | --ruleset <name>                 │
└────────────────────┬────────────────────────────────────────┘
                     │
          ┌──────────▼──────────┐
          │   Library Reader    │  reads master.db (read-only via pyrekordbox)
          └──────────┬──────────┘
                     │ per track (skips if cues exist, unless --overwrite)
          ┌──────────▼──────────┐
          │   Audio Analyzer    │
          │  ┌───────────────┐  │
          │  │ ANLZ (primary)│  │  → beat grid + phrase sections
          │  │ all-in-one    │  │  → fallback if ANLZ absent
          │  │ (fallback)    │  │
          │  ├───────────────┤  │
          │  │  Demucs v4    │  │  → isolated stems (always runs)
          │  ├───────────────┤  │
          │  │ Onset Detector│  │  → first-active timestamp per stem
          │  └───────────────┘  │
          └──────────┬──────────┘
                     │ AnalysisResult
          ┌──────────▼──────────┐
          │    Rule Engine      │  looks up playlist → loads rulesets
          └──────────┬──────────┘
                     │ list[CuePoint | LoopPoint]
          ┌──────────▼──────────┐
          │    Writer           │  pluggable — Rekordbox XML or dry-run
          └─────────────────────┘
```

---

## Rekordbox Integration

### Reading

The Library Reader opens `master.db` (Rekordbox's encrypted SQLite database) in **read-only** mode via `pyrekordbox`. It reads:

- `djmdContent` — track metadata and `AnalysisDataPath` (pointer to ANLZ files)
- `djmdCue` — existing cue points (used to determine skip/overwrite)
- Playlist membership tables — which playlists each track belongs to

The database is **never written to**. All writes go through the XML import path.

### Writing

A `rekordbox.xml` file is generated and the user imports it into Rekordbox via **File → Import → rekordbox xml**. Memory cues are `POSITION_MARK` elements with `Num="-1"`. Loops use `Type="4"` with both `Start` and `End`. Times are decimal seconds.

```xml
<!-- Memory cue -->
<POSITION_MARK Name="Vox -64" Type="0" Start="4.100" Num="-1"/>

<!-- Loop -->
<POSITION_MARK Name="Intro" Type="4" Start="0.000" End="63.500" Num="-1"/>
```

### ANLZ Files

Rekordbox writes analysis data to `.DAT` and `.EXT` binary files under `~/Library/Pioneer/rekordbox/share/`. The path per track is stored in `djmdContent.AnalysisDataPath`.

- `.DAT` → `BeatGridTag`: per-beat entries with millisecond timestamps, beat-within-bar position, and local BPM
- `.EXT` → `PhraseTag`: phrase entries with start beat number and phrase label (mood-dependent)

Tracks must have been analyzed by Rekordbox for ANLZ files to exist. If absent, the system falls back to `all-in-one` for beat grid and section detection.

---

## Phrase Normalization

Rekordbox assigns each track a mood (Low, Mid, or High) and the phrase labels depend on it. The system normalizes all labels to a consistent element vocabulary so rules work the same regardless of mood.

| Rekordbox label       | Mood     | Normalized element | Notes                          |
|-----------------------|----------|--------------------|--------------------------------|
| Intro                 | All      | `intro`            |                                |
| Verse 1, 1b, 1c       | Low      | `verse`            |                                |
| Verse 1–6             | Mid      | `verse`            |                                |
| Up                    | High     | `verse`            | Main energetic section         |
| Down                  | High     | `break`            | Lower-energy drop              |
| Bridge                | Low, Mid | `bridge`           |                                |
| Chorus                | All      | `chorus`           |                                |
| Outro                 | All      | `outro`            |                                |

The raw Rekordbox labels `up_start` / `down_start` are also available as elements for rules that need to explicitly target High-mood tracks without the normalization applied.

---

## Audio Analysis Pipeline

### AnalysisResult

The central data structure passed from the Analyzer to the Rule Engine:

```python
@dataclass
class Section:
    label: str          # normalized: "intro", "verse", "chorus", "break", "outro", etc.
    start_bar: int
    end_bar: int
    start_time: float   # seconds
    end_time: float     # seconds

@dataclass
class StemOnsets:
    vocal: float | None   # seconds; None if stem never activates
    drum: float | None
    bass: float | None
    other: float | None

@dataclass
class AnalysisResult:
    bpm: float
    downbeats: list[float]     # seconds at each bar boundary (bar 0 = first downbeat)
    total_bars: int
    sections: list[Section]    # ordered, non-overlapping, normalized labels
    stem_onsets: StemOnsets
    audio_path: str
    anlz_source: bool          # True = Rekordbox ANLZ; False = all-in-one fallback
```

### Beat Grid

Bar arithmetic (timestamp → bar number, bar number → timestamp) uses binary search on `downbeats`. This correctly handles tempo drift — the downbeat grid is derived from Rekordbox's per-beat millisecond timestamps rather than a fixed BPM calculation.

### Stem Onset Detection

Demucs v4 (`htdemucs` model) separates audio into four stems: vocals, drums, bass, other. Each stem is written to a temporary directory, analyzed for RMS energy per frame, and then deleted. The first frame where RMS exceeds the configured threshold for `onset_window_frames` consecutive frames is the onset timestamp.

Thresholds are configurable per stem in `rules.yaml` (see Settings below).

### Fallback (no ANLZ)

When ANLZ files are absent, `all-in-one` (`allin1` package) provides the beat grid and section labels. Its output maps directly to `AnalysisResult` with `anlz_source: False`. Demucs always runs regardless of which beat/section path was taken.

---

## Rule Configuration

All configuration lives in `config/rules.yaml`.

### Settings

```yaml
settings:
  demucs_model: htdemucs
  bar_snap: true              # snap cue positions to nearest downbeat
  onset_window_frames: 10     # consecutive frames must exceed threshold
  onset_thresholds:
    vocal: 0.02
    drum: 0.05
    bass: 0.03
    other: 0.02
```

### Named Rulesets

Rulesets are defined once and referenced by name. They are the unit of reuse.

```yaml
rulesets:

  standard-loops:
    rules:
      - element: intro_start
        type: loop
        length_bars: 16
        name: "Intro"
      - element: outro_start
        type: loop
        length_bars: 16
        name: "Outro"

  vocal-cue:
    rules:
      - element: first_vocal_onset
        type: memory_cue
        offset_bars: -64
        name: "Vox -64"
        color: blue

  break-hunter:
    rules:
      - element: break_start
        qualifier:
          position: after_midpoint
          min_duration_bars: 16
          occurrence: last
        type: memory_cue
        offset_bars: -8
        name: "Big Break -8"
        color: purple
```

### Playlist Mapping

Playlists reference named rulesets. Multiple rulesets are applied in order; cues at the same position are deduplicated.

```yaml
playlists:
  Deep House:
    rulesets: [vocal-cue, standard-loops]
  Euphoric Techno:
    rulesets: [vocal-cue, break-hunter, standard-loops]
  Hardgroove:
    rulesets: [drum-cue, short-loops]
  Melodic Techno:
    rulesets: [vocal-cue, break-hunter, standard-loops]

defaults:
  rulesets: [standard-loops]
```

### Available Elements

| Element | Source | Description |
|---|---|---|
| `first_vocal_onset` | Demucs + onset | First frame vocal stem energy exceeds threshold |
| `first_drum_onset` | Demucs + onset | First frame drum stem energy exceeds threshold |
| `first_bass_onset` | Demucs + onset | First frame bass stem energy exceeds threshold |
| `first_other_onset` | Demucs + onset | First frame other-instruments stem is active |
| `intro_start` / `intro_end` | ANLZ / all-in-one | Start/end of intro section |
| `verse_start` | ANLZ / all-in-one | Start of first verse (includes Up in High mood) |
| `chorus_start` | ANLZ / all-in-one | Start of first chorus |
| `bridge_start` | ANLZ / all-in-one | Start of first bridge |
| `break_start` | ANLZ / all-in-one | Start of first break (includes Down in High mood) |
| `outro_start` / `outro_end` | ANLZ / all-in-one | Start/end of outro |
| `up_start` | ANLZ (High mood only) | Raw Rekordbox Up label, unnormalized |
| `down_start` | ANLZ (High mood only) | Raw Rekordbox Down label, unnormalized |

### Rule Fields

| Field | Applies to | Description |
|---|---|---|
| `element` | both | Which detected event to anchor to |
| `type` | both | `memory_cue` or `loop` |
| `offset_bars` | memory_cue | Bars relative to element (negative = before) |
| `length_bars` | loop | Loop duration in bars from the anchor point |
| `name` | both | Label shown in Rekordbox |
| `color` | memory_cue | One of: `pink`, `red`, `orange`, `yellow`, `green`, `aqua`, `blue`, `purple` |
| `qualifier` | both | Optional — filter which instance of the element to use |

### Qualifier Fields

| Field | Values | Description |
|---|---|---|
| `position` | `before_midpoint`, `after_midpoint`, `first_quarter`, `last_quarter` | Where in the track the section must fall |
| `min_duration_bars` | integer | Section must be at least this long |
| `max_duration_bars` | integer | Section must be no longer than this |
| `occurrence` | `first`, `last`, `2`, `3`, … | Which qualifying match to select |

If no sections match a qualifier, or if `occurrence` specifies an index that exceeds the number of matches, the rule is skipped (no cue placed) and a warning is emitted.

---

## CLI

Built with Typer. All commands auto-generate `--help`.

```
dj-cue analyze <audio_file>                 # single track
dj-cue analyze --library                    # entire Rekordbox library
dj-cue analyze --playlist "Deep House"      # one or more playlists
dj-cue analyze --ruleset break-hunter       # override: apply one named ruleset to all tracks

Options:
  --overwrite          Re-analyze tracks that already have memory cues
  --dry-run            Print what would be written, don't produce XML
  --config PATH        Path to rules.yaml  (default: config/rules.yaml)
  --output PATH        Output rekordbox.xml (default: ./output.xml)
  --db PATH            Path to master.db   (auto-detected on Mac)

dj-cue show-elements <audio_file>           # print raw AnalysisResult
dj-cue show-elements <audio_file> \
  --apply-rules                             # also preview cue placements
dj-cue validate-config                      # validate rules.yaml, report errors
```

### `show-elements --apply-rules` output

```
BPM: 126.0 | Bars: 128 | Duration: 6:02 | Source: ANLZ

Sections:
  [  0 -  16] intro
  [ 16 -  48] verse
  [ 48 -  80] chorus
  [ 80 -  96] break     ← 16 bars, starts at 63% of track
  [ 96 - 112] verse
  [112 - 128] outro

Stem onsets:
  vocal:  bar 14  (55.2s)
  drum:   bar 1   (4.1s)
  bass:   bar 4   (15.8s)
  other:  bar 1   (4.0s)

Matched playlist: "Melodic Techno"
Applied rulesets: vocal-cue, break-hunter, standard-loops

Would place:
  memory cue  "Vox -64"    bar 0    (0.0s)    [vocal onset bar 14 − 64, clamped]  blue
  memory cue  "Big Break"  bar 72   (343.2s)  [break at bar 80 − 8 offset]        purple
  loop        "Intro"      bar 0  → bar 16    (0.0s → 63.5s)
  loop        "Outro"      bar 112 → bar 128  (443.2s → 503.0s)

  ⚠ Rule "first_vocal_onset offset -64": clamped to bar 0 (computed bar -50)
```

---

## Writer Extension Point

```python
from abc import ABC, abstractmethod

class CueWriter(ABC):
    @abstractmethod
    def write(self, track: Track, cues: list[CuePoint], loops: list[LoopPoint]) -> None: ...

    @abstractmethod
    def finalize(self) -> None:
        """Called once after all tracks are processed."""
        ...
```

Writers shipped now:
- `RekordboxXmlWriter` — generates `rekordbox.xml` for import
- `DryRunWriter` — prints to stdout, writes nothing

Future writer (not in scope):
- `SeratoWriter` — writes `Serato Markers2` GEOB ID3 tags directly into audio files

---

## Project Structure

```
dj-cue-system/
├── pyproject.toml
├── config/
│   └── rules.yaml
├── src/
│   └── dj_cue_system/
│       ├── __init__.py
│       ├── cli.py
│       ├── library/
│       │   ├── reader.py       # reads master.db via pyrekordbox (read-only)
│       │   └── models.py       # Track, Playlist, ExistingCue dataclasses
│       ├── analysis/
│       │   ├── anlz.py         # parses .DAT/.EXT ANLZ binary files
│       │   ├── fallback.py     # all-in-one wrapper (used when ANLZ absent)
│       │   ├── separation.py   # Demucs wrapper + temp file management
│       │   ├── onset.py        # per-stem RMS onset detection + bar arithmetic
│       │   └── models.py       # AnalysisResult, Section, StemOnsets dataclasses
│       ├── rules/
│       │   ├── config.py       # YAML loading + Pydantic validation
│       │   └── engine.py       # resolves rulesets → CuePoint/LoopPoint list
│       └── writers/
│           ├── base.py         # CueWriter ABC + CuePoint/LoopPoint dataclasses
│           ├── rekordbox_xml.py
│           └── dry_run.py
└── tests/
    ├── analysis/
    ├── rules/
    └── writers/
```

---

## Dependencies

| Package | Purpose | Notes |
|---|---|---|
| `pyrekordbox` | Read `master.db` + parse ANLZ | Read-only; requires `sqlcipher3-wheels` |
| `demucs` | Source separation | Pulls PyTorch; ~2 GB install |
| `allin1` | Fallback beat/section analysis | The `all-in-one` PyPI package |
| `librosa` | RMS computation, bar arithmetic | Lightweight |
| `pydantic` | `rules.yaml` validation + config models | Clean error messages |
| `typer` | CLI | Auto `--help` generation |
| `rich` | Progress bars, colored terminal output | Pairs with Typer |

PyTorch (via Demucs) uses Apple Silicon MPS automatically on M1/M2/M3 Mac, CUDA on Linux/NVIDIA. CPU fallback works but is slow (~10 min/track). Processing speed note belongs in README.

---

## Out of Scope (this iteration)

- Serato writer (`SeratoWriter` — extension point is designed, implementation deferred)
- Custom tag detection (e.g., auto-tagging "Vocal Heavy", "Heavy Kick" from stem analysis)
- Extensibility to custom Rekordbox tags as rule buckets (playlists only for now)
- GUI

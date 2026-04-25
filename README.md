# smart-dj-cuegen

Programmatically generates memory cues and loop points for DJ tracks and writes them as an importable `rekordbox.xml`. Analysis is driven by Rekordbox's own beat grid and phrase data (ANLZ files), with Demucs source separation for detecting when specific stems — vocals, drums, bass — first enter.

Rules are defined in YAML and are playlist-aware: you configure which rulesets apply to each genre playlist, then run the tool across your library.

## How it works

For each track, the tool:

1. **Reads Rekordbox's ANLZ files** (`.DAT`/`.EXT`) for the beat grid and phrase labels (intro, verse, chorus, break, outro). Falls back to the `all-in-one` model if ANLZ files don't exist.
2. **Runs Demucs v4** to separate the track into stems (vocals, drums, bass, other) and detects the first frame where each stem becomes active.
3. **Resolves your rules** — e.g. "place a memory cue 64 bars before first vocal onset", "set a 16-bar loop on the intro section".
4. **Writes a `rekordbox.xml`** file you import into Rekordbox.

Tracks that already have memory cues are skipped by default (use `--overwrite` to re-process them).

## Requirements

- Python 3.11+
- Rekordbox 6 or 7 installed on Mac (for `master.db` and ANLZ files)
- Apple Silicon (M1/M2/M3) recommended — Demucs runs on MPS. CPU fallback works but is slow (~10 min/track).

## Installation

```bash
git clone https://github.com/youruser/smart-dj-cuegen
cd smart-dj-cuegen
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Verify the install:

```bash
dj-cue --help
```

## Quick start

**1. Validate your config**

```bash
dj-cue validate-config
```

**2. Inspect what the tool detects for a track**

```bash
dj-cue show-elements "/path/to/track.mp3"
```

Output:
```
BPM: 126.0 | Bars: 128 | Source: ANLZ

Sections:
  [   0 -   16] intro  (16 bars, 0%)
  [  16 -   48] verse  (32 bars, 12%)
  [  48 -   80] chorus (32 bars, 37%)
  [  80 -   96] break  (16 bars, 62%)
  [  96 -  128] outro  (32 bars, 75%)

Stem onsets:
  vocal : bar  14  (55.2s)
  drum  : bar   1  (4.1s)
  bass  : bar   4  (15.8s)
  other : bar   1  (4.0s)
```

**3. Preview what cues would be placed**

```bash
dj-cue show-elements "/path/to/track.mp3" --apply-rules
```

**4. See what cues a track already has in Rekordbox**

```bash
dj-cue show-cues "/path/to/track.mp3"
```

**5. Back up your existing cues before running**

```bash
dj-cue backup create
```

**6. Dry run across your library**

```bash
dj-cue analyze --library --dry-run
```

**7. Generate the XML and import**

```bash
dj-cue analyze --library --output output.xml
```

Then in Rekordbox: **File → Import → rekordbox xml** → select `output.xml`.

## Configuration

All rules live in `config/rules.yaml`. The structure is:

```yaml
settings:
  demucs_model: htdemucs
  onset_window_frames: 10        # frames that must exceed threshold for a stem to count as "active"
  onset_thresholds:
    vocal: 0.02                  # RMS energy threshold per stem — tune per your library
    drum: 0.05
    bass: 0.03
    other: 0.02

rulesets:
  vocal-cue:
    rules:
      - element: first_vocal_onset
        type: memory_cue
        offset_bars: -64         # 64 bars before vocals enter
        name: "Vox -64"
        color: blue

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

  break-hunter:
    rules:
      - element: break_start
        qualifier:
          position: after_midpoint   # only breaks in the second half
          min_duration_bars: 16      # at least 16 bars long
          occurrence: last           # take the last qualifying one
        type: memory_cue
        offset_bars: -8
        name: "Big Break -8"
        color: purple

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
  rulesets: [standard-loops]    # applied to tracks not in any mapped playlist
```

### Available elements

| Element | Source | Description |
|---|---|---|
| `first_vocal_onset` | Demucs | First frame vocal stem is active |
| `first_drum_onset` | Demucs | First frame drum stem is active |
| `first_bass_onset` | Demucs | First frame bass stem is active |
| `first_other_onset` | Demucs | First frame other-instruments stem is active |
| `intro_start` / `intro_end` | ANLZ / all-in-one | Start/end of intro section |
| `verse_start` | ANLZ / all-in-one | Start of first verse (also matches High-mood "Up" sections) |
| `chorus_start` | ANLZ / all-in-one | Start of first chorus |
| `bridge_start` | ANLZ / all-in-one | Start of first bridge |
| `break_start` | ANLZ / all-in-one | Start of first break (also matches High-mood "Down" sections) |
| `outro_start` / `outro_end` | ANLZ / all-in-one | Start/end of outro |
| `up_start` | ANLZ (High mood) | Raw Rekordbox "Up" label — targets High-mood tracks specifically |
| `down_start` | ANLZ (High mood) | Raw Rekordbox "Down" label — targets High-mood tracks specifically |

### Rule fields

| Field | Applies to | Description |
|---|---|---|
| `element` | both | Which detected event to anchor to |
| `type` | both | `memory_cue` or `loop` |
| `offset_bars` | memory_cue | Bars relative to element (negative = before) |
| `length_bars` | loop | Loop duration in bars from the anchor point |
| `name` | both | Label shown in Rekordbox |
| `color` | memory_cue | `pink`, `red`, `orange`, `yellow`, `green`, `aqua`, `blue`, `purple` |
| `qualifier` | both | Optional filter — see below |

### Qualifier fields

Qualifiers let you target specific instances of a section, not just the first one.

| Field | Values | Description |
|---|---|---|
| `position` | `before_midpoint`, `after_midpoint`, `first_quarter`, `last_quarter` | Where in the track the section must start |
| `min_duration_bars` | integer | Section must be at least this long |
| `max_duration_bars` | integer | Section must be no longer than this |
| `occurrence` | `first`, `last`, `2`, `3`, … | Which qualifying match to use |

If no sections match a qualifier, the rule is skipped and a warning is shown.

### Rekordbox phrase normalization

Rekordbox assigns tracks a mood (Low, Mid, High) and the phrase labels depend on it. The tool normalizes these consistently:

| Rekordbox label | Mood | Normalized to |
|---|---|---|
| Intro | All | `intro` |
| Verse 1/1b/1c, Verse 1–6 | Low, Mid | `verse` |
| Up | High | `up` (matches `verse_start` via alias) |
| Down | High | `down` (matches `break_start` via alias) |
| Bridge | Low, Mid | `bridge` |
| Chorus | All | `chorus` |
| Outro | All | `outro` |

## CLI reference

### `dj-cue analyze`

Generate cues for one track, a playlist, or the full library.

```bash
# Single track
dj-cue analyze "/path/to/track.mp3" --dry-run

# Specific playlist
dj-cue analyze --playlist "Deep House" --output cues.xml

# Multiple playlists
dj-cue analyze --playlist "Deep House" --playlist "Melodic Techno" --output cues.xml

# Full library, skip tracks that already have cues
dj-cue analyze --library --output output.xml

# Re-process tracks that already have cues
dj-cue analyze --library --overwrite --output output.xml

# Apply a single named ruleset to everything, ignoring playlist mappings
dj-cue analyze --library --ruleset break-hunter --dry-run
```

| Option | Description |
|---|---|
| `--library` | Process all tracks in Rekordbox |
| `--playlist NAME` | Filter to tracks in this playlist (repeatable) |
| `--ruleset NAME` | Override playlist mapping, apply one ruleset to all tracks |
| `--overwrite` | Re-process tracks that already have memory cues |
| `--dry-run` | Print what would be written without producing XML |
| `--config PATH` | Path to rules.yaml (default: `config/rules.yaml`) |
| `--output PATH` | Output XML path (default: `./output.xml`) |
| `--db PATH` | Path to Rekordbox master.db (auto-detected on Mac) |

### `dj-cue show-elements`

Inspect what the tool detects for any audio file — useful for tuning onset thresholds and writing rules.

```bash
dj-cue show-elements "/path/to/track.mp3"
dj-cue show-elements "/path/to/track.mp3" --apply-rules
```

`--apply-rules` additionally shows which cues and loops would be placed, including any offset-clamping warnings.

### `dj-cue show-cues`

Show cue and loop points already stored in Rekordbox for a track, with bar numbers if ANLZ files are available.

```bash
dj-cue show-cues "/path/to/track.mp3"
```

### `dj-cue validate-config`

Check `rules.yaml` for structural errors and unresolved ruleset references.

```bash
dj-cue validate-config
dj-cue validate-config --config /path/to/other-rules.yaml
```

### `dj-cue backup`

Back up cue points from Rekordbox before running the tool.

```bash
dj-cue backup create                              # full library
dj-cue backup create --playlist "Deep House"     # one playlist
dj-cue backup create --output ~/my-backup.json   # custom path
dj-cue backup list                               # list all backups
dj-cue backup diff backup-a.json backup-b.json   # diff two backups
```

Backups are JSON files saved to `~/.dj-cue/backups/` by default.

### `dj-cue restore`

Regenerate a `rekordbox.xml` from a backup to undo a previous run.

```bash
dj-cue restore ~/.dj-cue/backups/2026-04-23T22-15-00Z.json
dj-cue restore backup.json --output restored.xml
dj-cue restore backup.json --tracks "/Music/track.mp3"   # single track only
```

Then import the XML in Rekordbox: **File → Import → rekordbox xml**.

## Recommended workflow

```
1. dj-cue validate-config
2. dj-cue show-elements "a representative track.mp3" --apply-rules
   → tune onset_thresholds and rules until output looks right
3. dj-cue backup create
4. dj-cue analyze --playlist "Deep House" --dry-run
5. dj-cue analyze --playlist "Deep House" --output output.xml
6. Import output.xml in Rekordbox
7. If something's wrong: dj-cue restore <backup-file>
```

## Rekordbox file locations (Mac)

| File / Directory | Path | Purpose |
|---|---|---|
| `master.db` | `~/Library/Pioneer/rekordbox/master.db` | Encrypted SQLite database — tracks, playlists, existing cues. Opened read-only by this tool. |
| ANLZ share directory | `~/Library/Pioneer/rekordbox/share/` | Root for all ANLZ analysis files. Rekordbox writes here when you analyze a track. |
| ANLZ files per track | `~/Library/Pioneer/rekordbox/share/<AnalysisDataPath>` | The exact path is stored in `master.db` per track (e.g. `PIONEER/USBANLZ/ab/cd1234/ANLZ0000.DAT`). |
| `.DAT` ANLZ file | same directory as above | Beat grid (per-beat timestamps + BPM). Used by this tool for bar arithmetic. |
| `.EXT` ANLZ file | same directory, `.EXT` extension | Phrase analysis (section labels: intro, verse, chorus…). Used for section-based rules. |
| Rekordbox XML export | wherever you save it | Human-readable XML of your collection — an alternative read path if needed. |
| This tool's output | `./output.xml` (configurable) | What you import back into Rekordbox via **File → Import → rekordbox xml**. |
| Backups | `~/.dj-cue/backups/` | JSON snapshots created by `dj-cue backup create`. |

ANLZ files are created automatically when you analyze a track in Rekordbox (Analysis → Analyze Track, or on import if auto-analysis is enabled). Tracks that have never been analyzed won't have ANLZ files; the tool falls back to `all-in-one` for those.

## Running tests

```bash
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Notes

- The Rekordbox database (`master.db`) is opened **read-only**. The tool never writes to it.
- All writes go through XML import, which is reversible.
- Demucs (`htdemucs`) requires ~2 GB of model weights downloaded on first run.
- Tracks must be analyzed by Rekordbox first for ANLZ files to exist. Unanalyzed tracks fall back to `all-in-one` for beat and phrase detection.
- `show-elements` always uses the `all-in-one` fallback (it works from a bare file path with no DB context). The `analyze` command uses ANLZ when available.

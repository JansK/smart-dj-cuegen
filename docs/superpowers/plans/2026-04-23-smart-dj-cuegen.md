# Smart DJ CueGen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python CLI tool that reads Rekordbox ANLZ analysis files and Demucs stem separation to generate memory cues and loop points, writing results as importable `rekordbox.xml`.

**Architecture:** Library reader pulls tracks/playlists from `master.db` read-only. Per track: ANLZ files supply the beat grid and phrase sections (with `all-in-one` as fallback); Demucs separates stems for onset detection. Rule engine maps named rulesets to playlists and resolves element references to timestamps. Pluggable writers emit `rekordbox.xml` or dry-run stdout.

**Tech Stack:** Python 3.11+, pyrekordbox, demucs, allin1, librosa, pydantic v2, typer, rich, pytest, pytest-mock

---

### Task 1: Project scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `src/dj_cue_system/__init__.py`
- Create: `config/rules.yaml`
- Create: `tests/__init__.py`
- Create: `.gitignore`

- [ ] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "smart-dj-cuegen"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "pyrekordbox>=0.4.4",
    "sqlcipher3-wheels",
    "demucs>=4.0.0",
    "allin1>=0.1.0",
    "librosa>=0.10.0",
    "pydantic>=2.0.0",
    "typer>=0.12.0",
    "rich>=13.0.0",
    "pyyaml>=6.0",
    "numpy>=1.24.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-mock>=3.12"]

[project.scripts]
dj-cue = "dj_cue_system.cli:app"

[tool.hatch.build.targets.wheel]
packages = ["src/dj_cue_system"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

- [ ] **Step 2: Create src/dj_cue_system/__init__.py**

```python
```

(empty file)

- [ ] **Step 3: Create directory structure**

```bash
mkdir -p src/dj_cue_system/{analysis,library,rules,writers,backup}
touch src/dj_cue_system/{analysis,library,rules,writers,backup}/__init__.py
mkdir -p tests/{analysis,library,rules,writers,backup,cli}
touch tests/{analysis,library,rules,writers,backup,cli}/__init__.py
touch tests/__init__.py
```

- [ ] **Step 4: Create config/rules.yaml**

```yaml
settings:
  demucs_model: htdemucs
  bar_snap: true
  onset_window_frames: 10
  onset_thresholds:
    vocal: 0.02
    drum: 0.05
    bass: 0.03
    other: 0.02

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

  drum-cue:
    rules:
      - element: first_drum_onset
        type: memory_cue
        offset_bars: -32
        name: "Drums -32"
        color: red

  short-loops:
    rules:
      - element: intro_start
        type: loop
        length_bars: 8
        name: "Intro"
      - element: outro_start
        type: loop
        length_bars: 8
        name: "Outro"

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

- [ ] **Step 5: Create .gitignore**

```
__pycache__/
*.py[cod]
*.egg-info/
dist/
.venv/
.env
*.DS_Store
output.xml
~/.dj-cue/
```

- [ ] **Step 6: Install dependencies and verify**

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -c "import typer, pydantic, librosa, yaml; print('OK')"
```

Expected: `OK`

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml src/ config/ tests/ .gitignore
git commit -m "chore: project scaffold"
```

---

### Task 2: Analysis data models

**Files:**
- Create: `src/dj_cue_system/analysis/models.py`
- Create: `tests/analysis/test_models.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/analysis/test_models.py
from dj_cue_system.analysis.models import Section, StemOnsets, AnalysisResult


def test_section_duration_bars():
    s = Section(label="verse", start_bar=16, end_bar=48, start_time=32.0, end_time=96.0)
    assert s.duration_bars == 32


def test_section_midpoint():
    s = Section(label="break", start_bar=80, end_bar=96, start_time=160.0, end_time=192.0)
    # 80 bars start out of 128 total bars = 62.5% — after midpoint
    assert s.position_fraction(total_bars=128) == pytest.approx(0.625)


def test_stem_onsets_defaults_none():
    onsets = StemOnsets()
    assert onsets.vocal is None
    assert onsets.drum is None
    assert onsets.bass is None
    assert onsets.other is None


def test_analysis_result_fields():
    result = AnalysisResult(
        bpm=126.0,
        downbeats=[0.0, 1.9, 3.8, 5.7],
        total_bars=4,
        sections=[Section("intro", 0, 4, 0.0, 7.6)],
        stem_onsets=StemOnsets(vocal=4.1),
        audio_path="/music/track.mp3",
        anlz_source=True,
    )
    assert result.bpm == 126.0
    assert result.anlz_source is True
    assert len(result.sections) == 1
```

Add `import pytest` at the top.

- [ ] **Step 2: Run — verify FAIL**

```bash
pytest tests/analysis/test_models.py -v
```

Expected: `ImportError` or `ModuleNotFoundError`

- [ ] **Step 3: Implement models**

```python
# src/dj_cue_system/analysis/models.py
from dataclasses import dataclass, field


@dataclass
class Section:
    label: str
    start_bar: int
    end_bar: int
    start_time: float  # seconds
    end_time: float    # seconds

    @property
    def duration_bars(self) -> int:
        return self.end_bar - self.start_bar

    def position_fraction(self, total_bars: int) -> float:
        """Fraction of the track at which this section starts (0.0–1.0)."""
        return self.start_bar / total_bars if total_bars > 0 else 0.0


@dataclass
class StemOnsets:
    vocal: float | None = None
    drum: float | None = None
    bass: float | None = None
    other: float | None = None


@dataclass
class AnalysisResult:
    bpm: float
    downbeats: list[float]   # seconds at each bar boundary
    total_bars: int
    sections: list[Section]  # ordered, non-overlapping, normalized labels
    stem_onsets: StemOnsets
    audio_path: str
    anlz_source: bool        # True = ANLZ; False = all-in-one fallback
```

- [ ] **Step 4: Run — verify PASS**

```bash
pytest tests/analysis/test_models.py -v
```

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/dj_cue_system/analysis/models.py tests/analysis/test_models.py
git commit -m "feat: analysis data models"
```

---

### Task 3: Bar arithmetic

**Files:**
- Create: `src/dj_cue_system/analysis/bar_utils.py`
- Create: `tests/analysis/test_bar_utils.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/analysis/test_bar_utils.py
import pytest
from dj_cue_system.analysis.bar_utils import timestamp_to_bar, bar_to_timestamp, snap_to_bar

DOWNBEATS = [0.0, 2.0, 4.0, 6.0, 8.0]  # 5 bars, 2s each


def test_timestamp_to_bar_exact():
    assert timestamp_to_bar(4.0, DOWNBEATS) == 2


def test_timestamp_to_bar_between():
    # 3.0s is between bar 1 (2.0s) and bar 2 (4.0s)
    assert timestamp_to_bar(3.0, DOWNBEATS) == 1


def test_timestamp_to_bar_before_start():
    assert timestamp_to_bar(-1.0, DOWNBEATS) == 0


def test_timestamp_to_bar_after_end():
    assert timestamp_to_bar(100.0, DOWNBEATS) == 4


def test_bar_to_timestamp_normal():
    assert bar_to_timestamp(2, DOWNBEATS) == pytest.approx(4.0)


def test_bar_to_timestamp_clamped_negative():
    assert bar_to_timestamp(-5, DOWNBEATS) == pytest.approx(0.0)


def test_bar_to_timestamp_clamped_over():
    assert bar_to_timestamp(99, DOWNBEATS) == pytest.approx(8.0)


def test_snap_to_bar():
    # 3.1s is between bar 1 (2.0) and bar 2 (4.0) — snaps to nearest
    assert snap_to_bar(3.1, DOWNBEATS) == pytest.approx(4.0)
    assert snap_to_bar(2.9, DOWNBEATS) == pytest.approx(2.0)
```

- [ ] **Step 2: Run — verify FAIL**

```bash
pytest tests/analysis/test_bar_utils.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Implement**

```python
# src/dj_cue_system/analysis/bar_utils.py
import bisect


def timestamp_to_bar(timestamp: float, downbeats: list[float]) -> int:
    """Return 0-indexed bar number for a timestamp (clamped to valid range)."""
    idx = bisect.bisect_right(downbeats, timestamp) - 1
    return max(0, min(idx, len(downbeats) - 1))


def bar_to_timestamp(bar: int, downbeats: list[float]) -> float:
    """Return seconds for start of bar (0-indexed, clamped)."""
    clamped = max(0, min(bar, len(downbeats) - 1))
    return downbeats[clamped]


def snap_to_bar(timestamp: float, downbeats: list[float]) -> float:
    """Snap timestamp to the nearest downbeat."""
    if not downbeats:
        return timestamp
    nearest = min(downbeats, key=lambda db: abs(db - timestamp))
    return nearest
```

- [ ] **Step 4: Run — verify PASS**

```bash
pytest tests/analysis/test_bar_utils.py -v
```

Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add src/dj_cue_system/analysis/bar_utils.py tests/analysis/test_bar_utils.py
git commit -m "feat: bar arithmetic utilities"
```

---

### Task 4: ANLZ parser — beat grid

**Files:**
- Create: `src/dj_cue_system/analysis/anlz.py`
- Create: `tests/analysis/test_anlz.py`

Background: pyrekordbox parses `.DAT` files via `AnlzFile`. The beat grid tag type is `"PQTZ"`. Each entry has `beat_number` (1–4 within bar), `time` (milliseconds from track start), and `tempo` (BPM × 100). We extract downbeats by filtering `beat_number == 1`.

**Verify field names before coding** by running:
```bash
python -c "
from pyrekordbox.anlz import AnlzFile
import inspect
# inspect tag fields after parsing a real DAT file
"
```
The field names used below (`beat_number`, `time`, `tempo`) match pyrekordbox 0.4.x. If they differ, update the wrapper.

- [ ] **Step 1: Write failing tests**

```python
# tests/analysis/test_anlz.py
from unittest.mock import MagicMock, patch
from dj_cue_system.analysis.anlz import parse_beat_grid, BeatGridResult


def _make_beat_entry(beat_number: int, time_ms: int, tempo_x100: int) -> MagicMock:
    e = MagicMock()
    e.beat_number = beat_number
    e.time = time_ms
    e.tempo = tempo_x100
    return e


def test_parse_beat_grid_extracts_downbeats():
    entries = [
        _make_beat_entry(1, 0, 12600),    # bar 0, downbeat, 126 BPM
        _make_beat_entry(2, 476, 12600),
        _make_beat_entry(3, 952, 12600),
        _make_beat_entry(4, 1429, 12600),
        _make_beat_entry(1, 1905, 12600),  # bar 1, downbeat
        _make_beat_entry(2, 2381, 12600),
    ]
    mock_tag = MagicMock()
    mock_tag.beats = entries

    mock_anlz = MagicMock()
    mock_anlz.getone.return_value = mock_tag

    with patch("dj_cue_system.analysis.anlz.AnlzFile") as MockAnlz:
        MockAnlz.parse_file.return_value = mock_anlz
        result = parse_beat_grid("/fake/ANLZ0000.DAT")

    assert isinstance(result, BeatGridResult)
    assert result.bpm == pytest.approx(126.0)
    assert len(result.downbeats) == 2
    assert result.downbeats[0] == pytest.approx(0.0)
    assert result.downbeats[1] == pytest.approx(1.905)


def test_parse_beat_grid_total_bars():
    entries = [_make_beat_entry(1 if i % 4 == 0 else (i % 4) + 1, i * 500, 12000)
               for i in range(16)]
    mock_tag = MagicMock()
    mock_tag.beats = entries
    mock_anlz = MagicMock()
    mock_anlz.getone.return_value = mock_tag

    with patch("dj_cue_system.analysis.anlz.AnlzFile") as MockAnlz:
        MockAnlz.parse_file.return_value = mock_anlz
        result = parse_beat_grid("/fake/ANLZ0000.DAT")

    assert result.total_bars == 4  # 16 beats / 4 = 4 bars
```

Add `import pytest` at top.

- [ ] **Step 2: Run — verify FAIL**

```bash
pytest tests/analysis/test_anlz.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Implement**

```python
# src/dj_cue_system/analysis/anlz.py
from dataclasses import dataclass
from pyrekordbox.anlz import AnlzFile


@dataclass
class BeatGridResult:
    bpm: float
    downbeats: list[float]   # seconds
    total_bars: int


@dataclass
class PhraseEntry:
    beat: int        # beat number (1-indexed) where phrase starts
    raw_label: str   # raw Rekordbox label e.g. "Verse1", "Chorus"
    mood: str        # "low", "mid", "high"


def parse_beat_grid(dat_path: str) -> BeatGridResult:
    anlz = AnlzFile.parse_file(dat_path)
    tag = anlz.getone("PQTZ")
    beats = tag.beats

    downbeats = [b.time / 1000.0 for b in beats if b.beat_number == 1]
    total_bars = len(downbeats)

    # BPM from first beat entry (tempo is BPM * 100)
    bpm = beats[0].tempo / 100.0 if beats else 0.0

    return BeatGridResult(bpm=bpm, downbeats=downbeats, total_bars=total_bars)
```

- [ ] **Step 4: Run — verify PASS**

```bash
pytest tests/analysis/test_anlz.py -v
```

Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/dj_cue_system/analysis/anlz.py tests/analysis/test_anlz.py
git commit -m "feat: ANLZ beat grid parser"
```

---

### Task 5: ANLZ phrase parser + normalization

**Files:**
- Modify: `src/dj_cue_system/analysis/anlz.py`
- Modify: `tests/analysis/test_anlz.py`

Background: Phrases live in the `.EXT` file under tag `"PPHD"`. Each entry has a `beat` number and a kind/label that depends on `mood` (1=High, 2=Mid, 3=Low in pyrekordbox). We normalize all labels to: `intro`, `verse`, `bridge`, `chorus`, `break`, `outro`. `Up` (High mood) → `verse`; `Down` (High mood) → `break`.

- [ ] **Step 1: Write failing tests — append to test_anlz.py**

```python
from dj_cue_system.analysis.anlz import parse_phrases, normalize_phrase_label


def _make_phrase_entry(beat: int, label_str: str) -> MagicMock:
    e = MagicMock()
    e.beat = beat
    e.kind = MagicMock()
    e.kind.__str__ = MagicMock(return_value=label_str)
    return e


def test_normalize_low_mood_verse():
    assert normalize_phrase_label("Verse1", "low") == "verse"
    assert normalize_phrase_label("Verse1b", "low") == "verse"
    assert normalize_phrase_label("Verse2c", "low") == "verse"


def test_normalize_mid_mood_verse():
    assert normalize_phrase_label("Verse3", "mid") == "verse"


def test_normalize_high_mood_up_down():
    assert normalize_phrase_label("Up", "high") == "verse"
    assert normalize_phrase_label("Down", "high") == "break"


def test_normalize_universal_labels():
    for mood in ("low", "mid", "high"):
        assert normalize_phrase_label("Intro", mood) == "intro"
        assert normalize_phrase_label("Chorus", mood) == "chorus"
        assert normalize_phrase_label("Outro", mood) == "outro"


def test_normalize_preserves_raw_labels():
    # up_start / down_start still accessible via raw
    assert normalize_phrase_label("Up", "high", normalized=False) == "up"
    assert normalize_phrase_label("Down", "high", normalized=False) == "down"


def test_parse_phrases_returns_entries():
    mock_entries = [
        _make_phrase_entry(1, "Intro"),
        _make_phrase_entry(17, "Verse1"),
        _make_phrase_entry(49, "Chorus"),
    ]
    mock_tag = MagicMock()
    mock_tag.mood = 2  # Mid
    mock_tag.phrases = mock_entries

    mock_anlz = MagicMock()
    mock_anlz.getone.return_value = mock_tag

    with patch("dj_cue_system.analysis.anlz.AnlzFile") as MockAnlz:
        MockAnlz.parse_file.return_value = mock_anlz
        phrases = parse_phrases("/fake/ANLZ0000.EXT")

    assert len(phrases) == 3
    assert phrases[0].beat == 1
    assert phrases[0].raw_label == "intro"
    assert phrases[1].raw_label == "verse"
```

- [ ] **Step 2: Run — verify FAIL**

```bash
pytest tests/analysis/test_anlz.py -v
```

Expected: failures on new tests only

- [ ] **Step 3: Implement — extend anlz.py**

```python
# Add to src/dj_cue_system/analysis/anlz.py

_MOOD_INT_TO_STR = {1: "high", 2: "mid", 3: "low"}

_NORMALIZATION_MAP: dict[str, str] = {
    "intro": "intro",
    "chorus": "chorus",
    "bridge": "bridge",
    "outro": "outro",
    # Low/Mid verse variants
    "verse1": "verse", "verse1b": "verse", "verse1c": "verse",
    "verse2": "verse", "verse2b": "verse", "verse2c": "verse",
    "verse3": "verse", "verse4": "verse", "verse5": "verse", "verse6": "verse",
    # High mood
    "up": "verse",
    "down": "break",
}

_RAW_MAP: dict[str, str] = {
    "up": "up",
    "down": "down",
}


def normalize_phrase_label(label: str, mood: str, normalized: bool = True) -> str:
    key = label.lower()
    if not normalized:
        return _RAW_MAP.get(key, _NORMALIZATION_MAP.get(key, key))
    return _NORMALIZATION_MAP.get(key, key)


def parse_phrases(ext_path: str) -> list[PhraseEntry]:
    anlz = AnlzFile.parse_file(ext_path)
    tag = anlz.getone("PPHD")
    mood_str = _MOOD_INT_TO_STR.get(tag.mood, "mid")

    result = []
    for entry in tag.phrases:
        raw = str(entry.kind).split(".")[-1]   # e.g. "MoodMidPhrase.Verse1" → "Verse1"
        normalized = normalize_phrase_label(raw, mood_str)
        result.append(PhraseEntry(beat=entry.beat, raw_label=normalized, mood=mood_str))
    return result
```

- [ ] **Step 4: Run — verify PASS**

```bash
pytest tests/analysis/test_anlz.py -v
```

Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add src/dj_cue_system/analysis/anlz.py tests/analysis/test_anlz.py
git commit -m "feat: ANLZ phrase parser and normalization"
```

---

### Task 6: ANLZ → AnalysisResult assembler

**Files:**
- Create: `src/dj_cue_system/analysis/assembler.py`
- Create: `tests/analysis/test_assembler.py`

This combines BeatGridResult + PhraseEntry list into the `Section` list inside `AnalysisResult`. Phrases give us beat numbers; the beat grid gives us timestamps per beat. We compute `start_time` by looking up the beat in the full beat list (not just downbeats).

- [ ] **Step 1: Write failing tests**

```python
# tests/analysis/test_assembler.py
import pytest
from dj_cue_system.analysis.assembler import build_sections
from dj_cue_system.analysis.anlz import BeatGridResult, PhraseEntry


def test_build_sections_basic():
    # 8 bars, 2s each → downbeats at 0,2,4,6,8,10,12,14
    downbeats = [i * 2.0 for i in range(8)]
    beat_grid = BeatGridResult(bpm=120.0, downbeats=downbeats, total_bars=8)

    # All beats (4 per bar)
    all_beat_times = [i * 0.5 for i in range(32)]  # 32 beats, 0.5s each

    phrases = [
        PhraseEntry(beat=1, raw_label="intro", mood="mid"),   # beat 1 = bar 0
        PhraseEntry(beat=9, raw_label="verse", mood="mid"),   # beat 9 = bar 2
        PhraseEntry(beat=25, raw_label="outro", mood="mid"),  # beat 25 = bar 6
    ]

    sections = build_sections(phrases, beat_grid, all_beat_times)

    assert len(sections) == 3
    assert sections[0].label == "intro"
    assert sections[0].start_bar == 0
    assert sections[0].end_bar == 2
    assert sections[1].label == "verse"
    assert sections[1].start_bar == 2
    assert sections[2].label == "outro"
    assert sections[2].end_bar == 8


def test_build_sections_single():
    downbeats = [0.0, 2.0, 4.0]
    all_beat_times = [i * 0.5 for i in range(12)]
    beat_grid = BeatGridResult(bpm=120.0, downbeats=downbeats, total_bars=3)
    phrases = [PhraseEntry(beat=1, raw_label="intro", mood="low")]

    sections = build_sections(phrases, beat_grid, all_beat_times)
    assert len(sections) == 1
    assert sections[0].end_bar == 3
```

- [ ] **Step 2: Run — verify FAIL**

```bash
pytest tests/analysis/test_assembler.py -v
```

- [ ] **Step 3: Implement**

```python
# src/dj_cue_system/analysis/assembler.py
from dj_cue_system.analysis.models import Section
from dj_cue_system.analysis.anlz import BeatGridResult, PhraseEntry
from dj_cue_system.analysis.bar_utils import timestamp_to_bar


def build_sections(
    phrases: list[PhraseEntry],
    beat_grid: BeatGridResult,
    all_beat_times: list[float],
) -> list[Section]:
    """Convert phrase entries (1-indexed beat numbers) into Section objects."""
    if not phrases:
        return []

    def beat_to_time(beat_1indexed: int) -> float:
        idx = beat_1indexed - 1
        if idx < 0:
            return all_beat_times[0] if all_beat_times else 0.0
        if idx >= len(all_beat_times):
            return all_beat_times[-1] if all_beat_times else 0.0
        return all_beat_times[idx]

    sections = []
    for i, phrase in enumerate(phrases):
        start_time = beat_to_time(phrase.beat)
        start_bar = timestamp_to_bar(start_time, beat_grid.downbeats)

        if i + 1 < len(phrases):
            end_time = beat_to_time(phrases[i + 1].beat)
            end_bar = timestamp_to_bar(end_time, beat_grid.downbeats)
        else:
            end_time = beat_grid.downbeats[-1] if beat_grid.downbeats else start_time
            end_bar = beat_grid.total_bars

        sections.append(Section(
            label=phrase.raw_label,
            start_bar=start_bar,
            end_bar=end_bar,
            start_time=start_time,
            end_time=end_time,
        ))
    return sections
```

- [ ] **Step 4: Run — verify PASS**

```bash
pytest tests/analysis/test_assembler.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/dj_cue_system/analysis/assembler.py tests/analysis/test_assembler.py
git commit -m "feat: ANLZ sections assembler"
```

---

### Task 7: all-in-one fallback wrapper

**Files:**
- Create: `src/dj_cue_system/analysis/fallback.py`
- Create: `tests/analysis/test_fallback.py`

`allin1.analyze()` returns an object with `.bpm`, `.downbeats` (list of seconds), and `.segments` (list with `.label`, `.start`, `.end`). We map this directly to `BeatGridResult` + sections.

- [ ] **Step 1: Write failing tests**

```python
# tests/analysis/test_fallback.py
from unittest.mock import MagicMock, patch
from dj_cue_system.analysis.fallback import analyze_with_allin1
from dj_cue_system.analysis.models import AnalysisResult


def _mock_allin1_result():
    seg1 = MagicMock(); seg1.label = "intro"; seg1.start = 0.0; seg1.end = 32.0
    seg2 = MagicMock(); seg2.label = "verse"; seg2.start = 32.0; seg2.end = 96.0
    seg3 = MagicMock(); seg3.label = "outro"; seg3.start = 96.0; seg3.end = 128.0

    r = MagicMock()
    r.bpm = 128.0
    r.downbeats = [i * 1.875 for i in range(68)]  # ~128 bars at 128 BPM
    r.segments = [seg1, seg2, seg3]
    return r


def test_analyze_with_allin1_returns_analysis_result():
    with patch("dj_cue_system.analysis.fallback.allin1") as mock_lib:
        mock_lib.analyze.return_value = _mock_allin1_result()
        result = analyze_with_allin1("/music/track.mp3")

    assert isinstance(result, AnalysisResult)
    assert result.bpm == 128.0
    assert result.anlz_source is False
    assert result.audio_path == "/music/track.mp3"
    assert len(result.sections) == 3
    assert result.sections[0].label == "intro"
    assert result.sections[1].label == "verse"
    assert result.total_bars == len(result.downbeats)


def test_analyze_with_allin1_stem_onsets_empty():
    with patch("dj_cue_system.analysis.fallback.allin1") as mock_lib:
        mock_lib.analyze.return_value = _mock_allin1_result()
        result = analyze_with_allin1("/music/track.mp3")

    # Fallback does not run Demucs — onsets are None
    assert result.stem_onsets.vocal is None
    assert result.stem_onsets.drum is None
```

- [ ] **Step 2: Run — verify FAIL**

```bash
pytest tests/analysis/test_fallback.py -v
```

- [ ] **Step 3: Implement**

```python
# src/dj_cue_system/analysis/fallback.py
import allin1
from dj_cue_system.analysis.models import AnalysisResult, Section, StemOnsets
from dj_cue_system.analysis.bar_utils import timestamp_to_bar


def analyze_with_allin1(audio_path: str) -> AnalysisResult:
    result = allin1.analyze(audio_path)

    downbeats: list[float] = list(result.downbeats)
    total_bars = len(downbeats)

    sections = []
    for seg in result.segments:
        start_bar = timestamp_to_bar(seg.start, downbeats)
        end_bar = timestamp_to_bar(seg.end, downbeats)
        sections.append(Section(
            label=seg.label,
            start_bar=start_bar,
            end_bar=end_bar,
            start_time=float(seg.start),
            end_time=float(seg.end),
        ))

    return AnalysisResult(
        bpm=float(result.bpm),
        downbeats=downbeats,
        total_bars=total_bars,
        sections=sections,
        stem_onsets=StemOnsets(),
        audio_path=audio_path,
        anlz_source=False,
    )
```

- [ ] **Step 4: Run — verify PASS**

```bash
pytest tests/analysis/test_fallback.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/dj_cue_system/analysis/fallback.py tests/analysis/test_fallback.py
git commit -m "feat: all-in-one fallback wrapper"
```

---

### Task 8: Demucs separation + onset detection

**Files:**
- Create: `src/dj_cue_system/analysis/separation.py`
- Create: `src/dj_cue_system/analysis/onset.py`
- Create: `tests/analysis/test_onset.py`

Demucs `htdemucs` stem order: `["drums", "bass", "other", "vocals"]`. Separation writes stems to a temp dir and returns paths. Onset detector computes per-frame RMS and returns the first timestamp where `window_frames` consecutive frames all exceed the threshold.

- [ ] **Step 1: Write failing tests for onset detection**

```python
# tests/analysis/test_onset.py
import numpy as np
import pytest
from dj_cue_system.analysis.onset import detect_onset_rms


SR = 22050
HOP = 512


def _make_audio(duration_s: float, onset_s: float, sr: int = SR) -> np.ndarray:
    """Silence before onset_s, then loud tone after."""
    samples = int(duration_s * sr)
    audio = np.zeros(samples, dtype=np.float32)
    onset_sample = int(onset_s * sr)
    audio[onset_sample:] = 0.5  # loud enough to exceed any reasonable threshold
    return audio


def test_detect_onset_finds_vocal():
    audio = _make_audio(10.0, onset_s=3.0)
    onset = detect_onset_rms(audio, sr=SR, threshold=0.02, window_frames=5, hop_length=HOP)
    assert onset is not None
    assert onset == pytest.approx(3.0, abs=0.1)


def test_detect_onset_silent_returns_none():
    audio = np.zeros(SR * 5, dtype=np.float32)
    onset = detect_onset_rms(audio, sr=SR, threshold=0.02, window_frames=5, hop_length=HOP)
    assert onset is None


def test_detect_onset_immediate():
    audio = np.full(SR * 5, 0.5, dtype=np.float32)
    onset = detect_onset_rms(audio, sr=SR, threshold=0.02, window_frames=5, hop_length=HOP)
    assert onset is not None
    assert onset == pytest.approx(0.0, abs=0.1)
```

- [ ] **Step 2: Run — verify FAIL**

```bash
pytest tests/analysis/test_onset.py -v
```

- [ ] **Step 3: Implement onset.py**

```python
# src/dj_cue_system/analysis/onset.py
import numpy as np
import librosa


def detect_onset_rms(
    audio: np.ndarray,
    sr: int,
    threshold: float,
    window_frames: int,
    frame_length: int = 2048,
    hop_length: int = 512,
) -> float | None:
    """Return timestamp (seconds) of first sustained onset, or None."""
    rms = librosa.feature.rms(y=audio, frame_length=frame_length, hop_length=hop_length)[0]
    for i in range(len(rms) - window_frames + 1):
        if np.all(rms[i : i + window_frames] > threshold):
            return float(librosa.frames_to_time(i, sr=sr, hop_length=hop_length))
    return None
```

- [ ] **Step 4: Run onset tests — verify PASS**

```bash
pytest tests/analysis/test_onset.py -v
```

Expected: 3 passed

- [ ] **Step 5: Implement separation.py**

```python
# src/dj_cue_system/analysis/separation.py
import tempfile
import shutil
from dataclasses import dataclass
from pathlib import Path

import torch
import torchaudio
import numpy as np
from demucs.pretrained import get_model
from demucs.apply import apply_model

# htdemucs stem order
_STEM_NAMES = ["drums", "bass", "other", "vocals"]
_STEM_INDEX = {name: i for i, name in enumerate(_STEM_NAMES)}


@dataclass
class StemAudio:
    vocals: np.ndarray
    drums: np.ndarray
    bass: np.ndarray
    other: np.ndarray
    sample_rate: int


def separate_stems(audio_path: str, model_name: str = "htdemucs") -> StemAudio:
    """Separate audio into 4 stems. Returns numpy arrays (mono, float32)."""
    model = get_model(model_name)
    model.eval()

    wav, sr = torchaudio.load(audio_path)
    if sr != model.samplerate:
        wav = torchaudio.functional.resample(wav, sr, model.samplerate)
        sr = model.samplerate

    # Ensure stereo
    if wav.shape[0] == 1:
        wav = wav.repeat(2, 1)

    wav = wav.unsqueeze(0)  # (1, channels, samples)

    device = (
        "mps" if torch.backends.mps.is_available()
        else "cuda" if torch.cuda.is_available()
        else "cpu"
    )

    with torch.no_grad():
        sources = apply_model(model, wav, device=device)
    # sources: (1, 4, channels, samples)
    sources = sources.squeeze(0).cpu()  # (4, channels, samples)

    def to_mono(stem_tensor: torch.Tensor) -> np.ndarray:
        return stem_tensor.mean(dim=0).numpy().astype(np.float32)

    return StemAudio(
        vocals=to_mono(sources[_STEM_INDEX["vocals"]]),
        drums=to_mono(sources[_STEM_INDEX["drums"]]),
        bass=to_mono(sources[_STEM_INDEX["bass"]]),
        other=to_mono(sources[_STEM_INDEX["other"]]),
        sample_rate=sr,
    )
```

- [ ] **Step 6: Write separation mock test**

```python
# Append to tests/analysis/test_onset.py
from unittest.mock import patch, MagicMock
import numpy as np
from dj_cue_system.analysis.separation import StemAudio


def test_separate_stems_mocked():
    """Verify separation.py calls demucs and returns StemAudio shape."""
    sr = 44100
    n = sr * 10
    mock_sources = MagicMock()

    fake_stems = torch.zeros(1, 4, 2, n)  # (batch, stems, channels, samples)
    fake_stems[0, 3] = 0.5  # vocals channel loud

    with patch("dj_cue_system.analysis.separation.get_model") as mock_get, \
         patch("dj_cue_system.analysis.separation.apply_model", return_value=fake_stems), \
         patch("dj_cue_system.analysis.separation.torchaudio.load",
               return_value=(torch.zeros(2, n), sr)):
        mock_get.return_value = MagicMock(samplerate=sr, eval=MagicMock())
        from dj_cue_system.analysis.separation import separate_stems
        result = separate_stems("/fake/track.mp3")

    assert isinstance(result, StemAudio)
    assert result.vocals.shape == (n,)
    assert result.sample_rate == sr
```

Add `import torch` at top of test file.

- [ ] **Step 7: Run all onset/separation tests**

```bash
pytest tests/analysis/test_onset.py -v
```

Expected: 4 passed

- [ ] **Step 8: Commit**

```bash
git add src/dj_cue_system/analysis/onset.py src/dj_cue_system/analysis/separation.py tests/analysis/test_onset.py
git commit -m "feat: Demucs separation and RMS onset detection"
```

---

### Task 9: Rule config — Pydantic models + YAML loading

**Files:**
- Create: `src/dj_cue_system/rules/config.py`
- Create: `tests/rules/test_config.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/rules/test_config.py
import pytest
import textwrap
from dj_cue_system.rules.config import load_config, AppConfig


MINIMAL_YAML = textwrap.dedent("""
    rulesets:
      vocal-cue:
        rules:
          - element: first_vocal_onset
            type: memory_cue
            offset_bars: -64
            name: "Vox -64"
            color: blue
    playlists:
      Deep House:
        rulesets: [vocal-cue]
    defaults:
      rulesets: [vocal-cue]
""")


def test_load_config_parses_ruleset(tmp_path):
    cfg_file = tmp_path / "rules.yaml"
    cfg_file.write_text(MINIMAL_YAML)
    config = load_config(str(cfg_file))

    assert isinstance(config, AppConfig)
    assert "vocal-cue" in config.rulesets
    rules = config.rulesets["vocal-cue"].rules
    assert len(rules) == 1
    assert rules[0].element == "first_vocal_onset"
    assert rules[0].type == "memory_cue"
    assert rules[0].offset_bars == -64
    assert rules[0].color == "blue"


def test_load_config_playlist_mapping(tmp_path):
    cfg_file = tmp_path / "rules.yaml"
    cfg_file.write_text(MINIMAL_YAML)
    config = load_config(str(cfg_file))

    assert "Deep House" in config.playlists
    assert config.playlists["Deep House"].rulesets == ["vocal-cue"]


def test_load_config_defaults(tmp_path):
    cfg_file = tmp_path / "rules.yaml"
    cfg_file.write_text(MINIMAL_YAML)
    config = load_config(str(cfg_file))
    assert config.defaults.rulesets == ["vocal-cue"]


def test_load_config_settings_defaults(tmp_path):
    cfg_file = tmp_path / "rules.yaml"
    cfg_file.write_text(MINIMAL_YAML)
    config = load_config(str(cfg_file))
    assert config.settings.demucs_model == "htdemucs"
    assert config.settings.bar_snap is True
    assert config.settings.onset_thresholds.vocal == pytest.approx(0.02)


def test_qualifier_parsed(tmp_path):
    yaml = textwrap.dedent("""
        rulesets:
          break-hunter:
            rules:
              - element: break_start
                type: memory_cue
                offset_bars: -8
                name: "Break"
                qualifier:
                  position: after_midpoint
                  min_duration_bars: 16
                  occurrence: last
        defaults:
          rulesets: []
    """)
    cfg_file = tmp_path / "rules.yaml"
    cfg_file.write_text(yaml)
    config = load_config(str(cfg_file))

    rule = config.rulesets["break-hunter"].rules[0]
    assert rule.qualifier is not None
    assert rule.qualifier.position == "after_midpoint"
    assert rule.qualifier.min_duration_bars == 16
    assert rule.qualifier.occurrence == "last"


def test_invalid_color_raises(tmp_path):
    yaml = textwrap.dedent("""
        rulesets:
          bad:
            rules:
              - element: intro_start
                type: memory_cue
                offset_bars: 0
                name: "X"
                color: chartreuse
        defaults:
          rulesets: []
    """)
    cfg_file = tmp_path / "rules.yaml"
    cfg_file.write_text(yaml)
    with pytest.raises(Exception):
        load_config(str(cfg_file))
```

- [ ] **Step 2: Run — verify FAIL**

```bash
pytest tests/rules/test_config.py -v
```

- [ ] **Step 3: Implement**

```python
# src/dj_cue_system/rules/config.py
from __future__ import annotations
from typing import Literal
import yaml
from pydantic import BaseModel, field_validator


class QualifierConfig(BaseModel):
    position: Literal["before_midpoint", "after_midpoint", "first_quarter", "last_quarter"] | None = None
    min_duration_bars: int | None = None
    max_duration_bars: int | None = None
    occurrence: str = "first"


ColorName = Literal["pink", "red", "orange", "yellow", "green", "aqua", "blue", "purple"]


class RuleConfig(BaseModel):
    element: str
    type: Literal["memory_cue", "loop"]
    name: str
    offset_bars: int = 0
    length_bars: int | None = None
    color: ColorName | None = None
    qualifier: QualifierConfig | None = None


class RulesetConfig(BaseModel):
    rules: list[RuleConfig]


class PlaylistConfig(BaseModel):
    rulesets: list[str]


class OnsetThresholds(BaseModel):
    vocal: float = 0.02
    drum: float = 0.05
    bass: float = 0.03
    other: float = 0.02


class SettingsConfig(BaseModel):
    demucs_model: str = "htdemucs"
    bar_snap: bool = True
    onset_window_frames: int = 10
    onset_thresholds: OnsetThresholds = OnsetThresholds()


class AppConfig(BaseModel):
    settings: SettingsConfig = SettingsConfig()
    rulesets: dict[str, RulesetConfig]
    playlists: dict[str, PlaylistConfig] = {}
    defaults: PlaylistConfig = PlaylistConfig(rulesets=[])


def load_config(path: str) -> AppConfig:
    with open(path) as f:
        data = yaml.safe_load(f)
    return AppConfig.model_validate(data)
```

- [ ] **Step 4: Run — verify PASS**

```bash
pytest tests/rules/test_config.py -v
```

Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add src/dj_cue_system/rules/config.py tests/rules/test_config.py
git commit -m "feat: rule config Pydantic models and YAML loader"
```

---

### Task 10: Rule engine

**Files:**
- Create: `src/dj_cue_system/rules/engine.py`
- Create: `src/dj_cue_system/writers/base.py` (needed for CuePoint/LoopPoint)
- Create: `tests/rules/test_engine.py`

- [ ] **Step 1: Create writers/base.py first (engine depends on it)**

```python
# src/dj_cue_system/writers/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dj_cue_system.library.models import Track

COLOR_MAP: dict[str, int] = {
    "pink": 1, "red": 2, "orange": 3, "yellow": 4,
    "green": 5, "aqua": 6, "blue": 7, "purple": 8,
}


@dataclass
class CuePoint:
    name: str
    position_seconds: float
    bar: int
    color: str | None = None  # color name from COLOR_MAP


@dataclass
class LoopPoint:
    name: str
    start_seconds: float
    end_seconds: float
    start_bar: int
    end_bar: int


class CueWriter(ABC):
    @abstractmethod
    def write(
        self,
        track: "Track",
        cues: list[CuePoint],
        loops: list[LoopPoint],
    ) -> None: ...

    @abstractmethod
    def finalize(self) -> None: ...
```

- [ ] **Step 2: Write failing tests for engine**

```python
# tests/rules/test_engine.py
import pytest
from dj_cue_system.analysis.models import AnalysisResult, Section, StemOnsets
from dj_cue_system.rules.config import AppConfig, load_config
from dj_cue_system.rules.engine import resolve_cues
from dj_cue_system.writers.base import CuePoint, LoopPoint
import textwrap


def _make_result(sections=None, vocal_onset=None, drum_onset=None) -> AnalysisResult:
    downbeats = [i * 2.0 for i in range(129)]  # 128 bars, 2s each
    return AnalysisResult(
        bpm=120.0,
        downbeats=downbeats,
        total_bars=128,
        sections=sections or [
            Section("intro", 0, 16, 0.0, 32.0),
            Section("verse", 16, 48, 32.0, 96.0),
            Section("chorus", 48, 80, 96.0, 160.0),
            Section("break", 80, 96, 160.0, 192.0),
            Section("outro", 96, 128, 192.0, 256.0),
        ],
        stem_onsets=StemOnsets(vocal=vocal_onset, drum=drum_onset),
        audio_path="/music/track.mp3",
        anlz_source=True,
    )


def _config_from_yaml(yaml_str: str) -> AppConfig:
    import tempfile, os
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        f.write(yaml_str)
        name = f.name
    cfg = load_config(name)
    os.unlink(name)
    return cfg


def test_resolve_vocal_cue():
    cfg = _config_from_yaml(textwrap.dedent("""
        rulesets:
          vocal-cue:
            rules:
              - element: first_vocal_onset
                type: memory_cue
                offset_bars: -8
                name: "Vox"
                color: blue
        defaults:
          rulesets: [vocal-cue]
    """))
    result = _make_result(vocal_onset=80.0)  # bar 40 (80s / 2s per bar)
    cues, loops = resolve_cues(result, cfg, playlists=[])
    assert len(cues) == 1
    assert cues[0].name == "Vox"
    assert cues[0].bar == 32   # bar 40 - 8 = 32
    assert cues[0].color == "blue"


def test_resolve_clamps_negative_bar():
    cfg = _config_from_yaml(textwrap.dedent("""
        rulesets:
          vocal-cue:
            rules:
              - element: first_vocal_onset
                type: memory_cue
                offset_bars: -64
                name: "Vox"
        defaults:
          rulesets: [vocal-cue]
    """))
    result = _make_result(vocal_onset=10.0)  # bar 5; 5-64 = -59 → clamp to 0
    cues, loops = resolve_cues(result, cfg, playlists=[])
    assert cues[0].bar == 0


def test_resolve_loop_on_intro():
    cfg = _config_from_yaml(textwrap.dedent("""
        rulesets:
          loops:
            rules:
              - element: intro_start
                type: loop
                length_bars: 16
                name: "Intro"
        defaults:
          rulesets: [loops]
    """))
    result = _make_result()
    cues, loops = resolve_cues(result, cfg, playlists=[])
    assert len(loops) == 1
    assert loops[0].name == "Intro"
    assert loops[0].start_bar == 0
    assert loops[0].end_bar == 16


def test_resolve_qualifier_after_midpoint():
    cfg = _config_from_yaml(textwrap.dedent("""
        rulesets:
          bh:
            rules:
              - element: break_start
                type: memory_cue
                offset_bars: 0
                name: "Break"
                qualifier:
                  position: after_midpoint
                  min_duration_bars: 8
                  occurrence: last
        defaults:
          rulesets: [bh]
    """))
    result = _make_result()  # break at bar 80-96 (63% of 128)
    cues, loops = resolve_cues(result, cfg, playlists=[])
    assert len(cues) == 1
    assert cues[0].bar == 80


def test_resolve_qualifier_no_match_skips_rule():
    cfg = _config_from_yaml(textwrap.dedent("""
        rulesets:
          bh:
            rules:
              - element: break_start
                type: memory_cue
                offset_bars: 0
                name: "Break"
                qualifier:
                  min_duration_bars: 100   # break is only 16 bars — no match
        defaults:
          rulesets: [bh]
    """))
    result = _make_result()
    cues, loops = resolve_cues(result, cfg, playlists=[])
    assert len(cues) == 0


def test_resolve_deduplicates_same_position():
    cfg = _config_from_yaml(textwrap.dedent("""
        rulesets:
          r1:
            rules:
              - element: intro_start
                type: memory_cue
                offset_bars: 0
                name: "A"
          r2:
            rules:
              - element: intro_start
                type: memory_cue
                offset_bars: 0
                name: "A"
        defaults:
          rulesets: [r1, r2]
    """))
    result = _make_result()
    cues, loops = resolve_cues(result, cfg, playlists=[])
    assert len(cues) == 1


def test_playlist_ruleset_used_over_defaults():
    cfg = _config_from_yaml(textwrap.dedent("""
        rulesets:
          default-rule:
            rules:
              - element: intro_start
                type: memory_cue
                offset_bars: 0
                name: "Default"
          playlist-rule:
            rules:
              - element: outro_start
                type: memory_cue
                offset_bars: 0
                name: "PlaylistCue"
        playlists:
          Techno:
            rulesets: [playlist-rule]
        defaults:
          rulesets: [default-rule]
    """))
    result = _make_result()
    cues, loops = resolve_cues(result, cfg, playlists=["Techno"])
    names = [c.name for c in cues]
    assert "PlaylistCue" in names
    assert "Default" not in names
```

- [ ] **Step 3: Run — verify FAIL**

```bash
pytest tests/rules/test_engine.py -v
```

- [ ] **Step 4: Implement engine**

```python
# src/dj_cue_system/rules/engine.py
import warnings
from dj_cue_system.analysis.models import AnalysisResult, Section
from dj_cue_system.analysis.bar_utils import bar_to_timestamp
from dj_cue_system.rules.config import AppConfig, RuleConfig, QualifierConfig
from dj_cue_system.writers.base import CuePoint, LoopPoint

_SECTION_ELEMENTS = {
    "intro_start", "intro_end", "verse_start", "chorus_start",
    "bridge_start", "break_start", "outro_start", "outro_end",
    "up_start", "down_start",
}
_STEM_ONSET_ELEMENTS = {
    "first_vocal_onset": "vocal",
    "first_drum_onset": "drum",
    "first_bass_onset": "bass",
    "first_other_onset": "other",
}


def _get_sections_for_element(element: str, sections: list[Section]) -> list[Section]:
    label = element.replace("_start", "").replace("_end", "")
    return [s for s in sections if s.label == label]


def _apply_qualifier(
    candidates: list[Section],
    qualifier: QualifierConfig | None,
    total_bars: int,
) -> Section | None:
    if not candidates:
        return None
    if qualifier is None:
        return candidates[0]

    filtered = list(candidates)

    if qualifier.position:
        mid = total_bars / 2
        q1 = total_bars / 4
        q3 = 3 * total_bars / 4
        if qualifier.position == "after_midpoint":
            filtered = [s for s in filtered if s.start_bar >= mid]
        elif qualifier.position == "before_midpoint":
            filtered = [s for s in filtered if s.start_bar < mid]
        elif qualifier.position == "first_quarter":
            filtered = [s for s in filtered if s.start_bar < q1]
        elif qualifier.position == "last_quarter":
            filtered = [s for s in filtered if s.start_bar >= q3]

    if qualifier.min_duration_bars is not None:
        filtered = [s for s in filtered if s.duration_bars >= qualifier.min_duration_bars]
    if qualifier.max_duration_bars is not None:
        filtered = [s for s in filtered if s.duration_bars <= qualifier.max_duration_bars]

    if not filtered:
        return None

    occ = qualifier.occurrence
    if occ == "first":
        return filtered[0]
    if occ == "last":
        return filtered[-1]
    try:
        idx = int(occ) - 1
        return filtered[idx] if idx < len(filtered) else None
    except (ValueError, IndexError):
        return filtered[0]


def _resolve_rule(
    rule: RuleConfig,
    result: AnalysisResult,
) -> CuePoint | LoopPoint | None:
    downbeats = result.downbeats

    if rule.element in _STEM_ONSET_ELEMENTS:
        stem_name = _STEM_ONSET_ELEMENTS[rule.element]
        onset_time = getattr(result.stem_onsets, stem_name)
        if onset_time is None:
            warnings.warn(f"Rule '{rule.element}': stem onset not detected, skipping")
            return None
        from dj_cue_system.analysis.bar_utils import timestamp_to_bar
        anchor_bar = timestamp_to_bar(onset_time, downbeats)
    elif rule.element in _SECTION_ELEMENTS:
        candidates = _get_sections_for_element(rule.element, result.sections)
        section = _apply_qualifier(candidates, rule.qualifier, result.total_bars)
        if section is None:
            warnings.warn(f"Rule '{rule.element}': no matching section, skipping")
            return None
        use_end = rule.element.endswith("_end")
        anchor_bar = section.end_bar if use_end else section.start_bar
    else:
        warnings.warn(f"Unknown element '{rule.element}', skipping")
        return None

    if rule.type == "memory_cue":
        final_bar = max(0, anchor_bar + rule.offset_bars)
        if final_bar != anchor_bar + rule.offset_bars:
            warnings.warn(
                f"Rule '{rule.name}': offset clamped to bar 0 "
                f"(computed bar {anchor_bar + rule.offset_bars})"
            )
        position_s = bar_to_timestamp(final_bar, downbeats)
        return CuePoint(name=rule.name, position_seconds=position_s, bar=final_bar, color=rule.color)

    elif rule.type == "loop":
        length = rule.length_bars or 16
        start_bar = anchor_bar
        end_bar = min(start_bar + length, result.total_bars)
        start_s = bar_to_timestamp(start_bar, downbeats)
        end_s = bar_to_timestamp(end_bar, downbeats)
        return LoopPoint(
            name=rule.name,
            start_seconds=start_s,
            end_seconds=end_s,
            start_bar=start_bar,
            end_bar=end_bar,
        )

    return None


def resolve_cues(
    result: AnalysisResult,
    config: AppConfig,
    playlists: list[str],
    ruleset_override: str | None = None,
) -> tuple[list[CuePoint], list[LoopPoint]]:
    if ruleset_override:
        ruleset_names = [ruleset_override]
    elif playlists:
        ruleset_names = []
        for pl in playlists:
            if pl in config.playlists:
                ruleset_names.extend(config.playlists[pl].rulesets)
        if not ruleset_names:
            ruleset_names = list(config.defaults.rulesets)
    else:
        ruleset_names = list(config.defaults.rulesets)

    cues: list[CuePoint] = []
    loops: list[LoopPoint] = []
    seen_cue_bars: set[int] = set()
    seen_loop_bars: set[int] = set()

    for name in ruleset_names:
        ruleset = config.rulesets.get(name)
        if ruleset is None:
            warnings.warn(f"Ruleset '{name}' not found in config")
            continue
        for rule in ruleset.rules:
            item = _resolve_rule(rule, result)
            if item is None:
                continue
            if isinstance(item, CuePoint):
                if item.bar not in seen_cue_bars:
                    seen_cue_bars.add(item.bar)
                    cues.append(item)
            elif isinstance(item, LoopPoint):
                if item.start_bar not in seen_loop_bars:
                    seen_loop_bars.add(item.start_bar)
                    loops.append(item)

    return cues, loops
```

- [ ] **Step 5: Run — verify PASS**

```bash
pytest tests/rules/test_engine.py -v
```

Expected: 7 passed

- [ ] **Step 6: Commit**

```bash
git add src/dj_cue_system/rules/engine.py src/dj_cue_system/writers/base.py tests/rules/test_engine.py
git commit -m "feat: rule engine and writer base"
```

---

### Task 11: RekordboxXmlWriter + DryRunWriter

**Files:**
- Create: `src/dj_cue_system/writers/rekordbox_xml.py`
- Create: `src/dj_cue_system/writers/dry_run.py`
- Create: `tests/writers/test_rekordbox_xml.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/writers/test_rekordbox_xml.py
import xml.etree.ElementTree as ET
import pytest
from dj_cue_system.writers.rekordbox_xml import RekordboxXmlWriter
from dj_cue_system.writers.base import CuePoint, LoopPoint


def _make_track():
    from unittest.mock import MagicMock
    t = MagicMock()
    t.id = "42"
    t.path = "/Music/track.mp3"
    t.title = "Test Track"
    t.artist = "DJ Test"
    return t


def test_memory_cue_position_mark(tmp_path):
    output = tmp_path / "out.xml"
    writer = RekordboxXmlWriter(str(output))
    track = _make_track()
    cues = [CuePoint(name="Vox -64", position_seconds=4.1, bar=2, color="blue")]
    loops = []
    writer.write(track, cues, loops)
    writer.finalize()

    tree = ET.parse(output)
    root = tree.getroot()
    marks = root.findall(".//POSITION_MARK")
    assert len(marks) == 1
    assert marks[0].get("Name") == "Vox -64"
    assert marks[0].get("Type") == "0"
    assert marks[0].get("Num") == "-1"
    assert float(marks[0].get("Start")) == pytest.approx(4.1)
    assert marks[0].get("Color") == "7"  # blue = 7


def test_loop_position_mark(tmp_path):
    output = tmp_path / "out.xml"
    writer = RekordboxXmlWriter(str(output))
    track = _make_track()
    cues = []
    loops = [LoopPoint(name="Intro", start_seconds=0.0, end_seconds=32.0, start_bar=0, end_bar=16)]
    writer.write(track, cues, loops)
    writer.finalize()

    tree = ET.parse(output)
    marks = tree.getroot().findall(".//POSITION_MARK")
    assert len(marks) == 1
    assert marks[0].get("Type") == "4"
    assert float(marks[0].get("Start")) == pytest.approx(0.0)
    assert float(marks[0].get("End")) == pytest.approx(32.0)
    assert marks[0].get("Num") == "-1"


def test_multiple_tracks(tmp_path):
    output = tmp_path / "out.xml"
    writer = RekordboxXmlWriter(str(output))
    for i in range(3):
        t = _make_track()
        t.id = str(i)
        writer.write(t, [CuePoint("Cue", float(i), i)], [])
    writer.finalize()

    tree = ET.parse(output)
    tracks = tree.getroot().findall(".//TRACK")
    assert len(tracks) == 3
```

- [ ] **Step 2: Run — verify FAIL**

```bash
pytest tests/writers/test_rekordbox_xml.py -v
```

- [ ] **Step 3: Implement RekordboxXmlWriter**

```python
# src/dj_cue_system/writers/rekordbox_xml.py
import xml.etree.ElementTree as ET
from dj_cue_system.writers.base import CueWriter, CuePoint, LoopPoint, COLOR_MAP
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dj_cue_system.library.models import Track


class RekordboxXmlWriter(CueWriter):
    def __init__(self, output_path: str) -> None:
        self._output_path = output_path
        self._root = ET.Element("DJ_PLAYLISTS", Version="1.0.0")
        self._collection = ET.SubElement(self._root, "COLLECTION")

    def write(self, track: "Track", cues: list[CuePoint], loops: list[LoopPoint]) -> None:
        track_el = ET.SubElement(
            self._collection, "TRACK",
            TrackID=str(track.id),
            Name=str(track.title),
            Artist=str(track.artist),
            Location=f"file://localhost{track.path}",
        )
        for cue in cues:
            attrs = {
                "Name": cue.name,
                "Type": "0",
                "Start": f"{cue.position_seconds:.3f}",
                "Num": "-1",
            }
            if cue.color and cue.color in COLOR_MAP:
                attrs["Color"] = str(COLOR_MAP[cue.color])
            ET.SubElement(track_el, "POSITION_MARK", **attrs)

        for loop in loops:
            ET.SubElement(track_el, "POSITION_MARK",
                Name=loop.name,
                Type="4",
                Start=f"{loop.start_seconds:.3f}",
                End=f"{loop.end_seconds:.3f}",
                Num="-1",
            )

    def finalize(self) -> None:
        ET.indent(self._root)
        tree = ET.ElementTree(self._root)
        tree.write(self._output_path, encoding="utf-8", xml_declaration=True)
```

- [ ] **Step 4: Implement DryRunWriter**

```python
# src/dj_cue_system/writers/dry_run.py
from rich.console import Console
from dj_cue_system.writers.base import CueWriter, CuePoint, LoopPoint
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dj_cue_system.library.models import Track

console = Console()


class DryRunWriter(CueWriter):
    def write(self, track: "Track", cues: list[CuePoint], loops: list[LoopPoint]) -> None:
        console.print(f"\n[bold]{track.title}[/bold] — {track.path}")
        for cue in cues:
            color_str = f" [dim]{cue.color}[/dim]" if cue.color else ""
            console.print(f"  memory cue  [cyan]{cue.name!r}[/cyan]  bar {cue.bar}  ({cue.position_seconds:.1f}s){color_str}")
        for loop in loops:
            console.print(f"  loop        [green]{loop.name!r}[/green]  bar {loop.start_bar} → {loop.end_bar}")

    def finalize(self) -> None:
        console.print("\n[dim]Dry run — no files written.[/dim]")
```

- [ ] **Step 5: Run — verify PASS**

```bash
pytest tests/writers/test_rekordbox_xml.py -v
```

Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add src/dj_cue_system/writers/ tests/writers/
git commit -m "feat: RekordboxXmlWriter and DryRunWriter"
```

---

### Task 12: Library models + reader

**Files:**
- Create: `src/dj_cue_system/library/models.py`
- Create: `src/dj_cue_system/library/reader.py`
- Create: `tests/library/test_reader.py`

Background: pyrekordbox `Rekordbox6Database` auto-detects `master.db` on Mac at `~/Library/Pioneer/rekordbox/master.db`. Key tables: `djmdContent` (tracks), `djmdCue` (cues), `djmdPlaylist`/`djmdPlaylistTrack` (playlists). Verify these field names via `python -c "from pyrekordbox import Rekordbox6Database; db = Rekordbox6Database(); c = db.get_content()[0]; print(dir(c))"` before implementation.

- [ ] **Step 1: Write failing tests**

```python
# tests/library/test_reader.py
from unittest.mock import MagicMock, patch
from dj_cue_system.library.reader import get_tracks, get_track_playlists, get_track_by_path, DEFAULT_DB_PATH
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
    mock_content = [_mock_content()]
    mock_cues = [_mock_cue()]

    with patch("dj_cue_system.library.reader.Rekordbox6Database") as MockDB:
        db = MockDB.return_value
        db.get_content.return_value = mock_content
        db.get_cue.return_value = mock_cues
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
    from dj_cue_system.library.models import Track, ExistingCue
    t = Track(id="1", path="/x", title="X", artist="A",
              analysis_data_path=None,
              existing_cues=[ExistingCue(5.0, "memory_cue", "X")])
    assert t.has_memory_cues is True


def test_default_db_path_mac():
    import os
    assert "Pioneer" in DEFAULT_DB_PATH
    assert DEFAULT_DB_PATH.endswith("master.db")
```

Add `import pytest` at top.

- [ ] **Step 2: Run — verify FAIL**

```bash
pytest tests/library/test_reader.py -v
```

- [ ] **Step 3: Implement models.py**

```python
# src/dj_cue_system/library/models.py
from dataclasses import dataclass, field


@dataclass
class ExistingCue:
    position_seconds: float
    cue_type: str   # "memory_cue" or "loop"
    name: str


@dataclass
class Track:
    id: str
    path: str
    title: str
    artist: str
    analysis_data_path: str | None
    existing_cues: list[ExistingCue] = field(default_factory=list)
    playlists: list[str] = field(default_factory=list)

    @property
    def has_memory_cues(self) -> bool:
        return any(c.cue_type == "memory_cue" for c in self.existing_cues)
```

- [ ] **Step 4: Implement reader.py**

```python
# src/dj_cue_system/library/reader.py
import os
from pyrekordbox import Rekordbox6Database
from dj_cue_system.library.models import Track, ExistingCue

DEFAULT_DB_PATH = os.path.expanduser(
    "~/Library/Pioneer/rekordbox/master.db"
)

# djmdCue.Kind: 0 = memory cue, 1 = hot cue, 4 = memory loop, 5 = hot loop
_KIND_TO_TYPE = {0: "memory_cue", 1: "hot_cue", 4: "loop", 5: "hot_loop"}


def get_tracks(db_path: str | None = None) -> list[Track]:
    db = Rekordbox6Database(db_path or DEFAULT_DB_PATH)

    all_cues = db.get_cue()
    cues_by_content: dict[str, list] = {}
    for cue in all_cues:
        cues_by_content.setdefault(cue.ContentID, []).append(cue)

    tracks = []
    for content in db.get_content():
        raw_cues = cues_by_content.get(content.ID, [])
        existing = [
            ExistingCue(
                position_seconds=c.InMsec / 1000.0,
                cue_type=_KIND_TO_TYPE.get(c.Kind, "unknown"),
                name=c.Comment or "",
            )
            for c in raw_cues
        ]
        tracks.append(Track(
            id=str(content.ID),
            path=str(content.FolderPath),
            title=str(content.Title or ""),
            artist=str(content.Artist or ""),
            analysis_data_path=content.AnalysisDataPath,
            existing_cues=existing,
        ))
    return tracks


def get_track_playlists(db_path: str | None = None) -> dict[str, list[str]]:
    """Return {track_id: [playlist_name, ...]} mapping."""
    db = Rekordbox6Database(db_path or DEFAULT_DB_PATH)

    playlists_by_id = {p.ID: p.Name for p in db.get_playlist()}
    result: dict[str, list[str]] = {}
    for pt in db.get_playlist_track():
        pl_name = playlists_by_id.get(pt.PlaylistID, "")
        result.setdefault(str(pt.ContentID), []).append(pl_name)
    return result


def get_track_by_path(audio_path: str, db_path: str | None = None) -> Track | None:
    """Return a Track matching the given file path, or None if not in library."""
    db = Rekordbox6Database(db_path or DEFAULT_DB_PATH)

    all_cues = db.get_cue()
    cues_by_content: dict[str, list] = {}
    for cue in all_cues:
        cues_by_content.setdefault(str(cue.ContentID), []).append(cue)

    for content in db.get_content():
        if str(content.FolderPath) == audio_path:
            raw_cues = cues_by_content.get(str(content.ID), [])
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
    return None
```

- [ ] **Step 5: Add get_track_by_path test — append to test_reader.py**

```python
def test_get_track_by_path_found():
    with patch("dj_cue_system.library.reader.Rekordbox6Database") as MockDB:
        db = MockDB.return_value
        db.get_content.return_value = [_mock_content(path="/music/track.mp3")]
        db.get_cue.return_value = [_mock_cue(content_id="1")]
        from dj_cue_system.library.reader import get_track_by_path
        track = get_track_by_path("/music/track.mp3")
    assert track is not None
    assert track.path == "/music/track.mp3"
    assert len(track.existing_cues) == 1


def test_get_track_by_path_not_found():
    with patch("dj_cue_system.library.reader.Rekordbox6Database") as MockDB:
        db = MockDB.return_value
        db.get_content.return_value = [_mock_content(path="/music/other.mp3")]
        db.get_cue.return_value = []
        from dj_cue_system.library.reader import get_track_by_path
        track = get_track_by_path("/music/track.mp3")
    assert track is None
```

- [ ] **Step 6: Run — verify PASS**

```bash
pytest tests/library/test_reader.py -v
```

Expected: 6 passed

- [ ] **Step 7: Commit**

```bash
git add src/dj_cue_system/library/ tests/library/
git commit -m "feat: library models and reader"
```

---

### Task 13: Backup — models, JSON writer/reader, and reader from DB

**Files:**
- Create: `src/dj_cue_system/backup/writer.py`
- Create: `src/dj_cue_system/backup/reader.py`
- Create: `tests/backup/test_backup.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/backup/test_backup.py
import json
import pytest
from pathlib import Path
from dj_cue_system.backup.writer import (
    BackupCue, BackupTrack, BackupFile, serialize_backup, deserialize_backup
)


def _make_backup_file() -> BackupFile:
    return BackupFile(
        created_at="2026-04-23T22:15:00Z",
        rekordbox_db="/fake/master.db",
        tracks=[
            BackupTrack(
                id="1",
                path="/Music/track.mp3",
                artist="DJ A",
                title="Track One",
                cues=[
                    BackupCue(type="memory_cue", position_seconds=4.1, name="Vox", color="blue"),
                    BackupCue(type="loop", start_seconds=0.0, end_seconds=32.0, name="Intro"),
                ],
            )
        ],
    )


def test_serialize_and_deserialize_roundtrip(tmp_path):
    backup = _make_backup_file()
    path = tmp_path / "backup.json"
    serialize_backup(backup, str(path))

    loaded = deserialize_backup(str(path))
    assert loaded.rekordbox_db == backup.rekordbox_db
    assert len(loaded.tracks) == 1
    assert loaded.tracks[0].title == "Track One"
    assert loaded.tracks[0].cues[0].type == "memory_cue"
    assert loaded.tracks[0].cues[0].position_seconds == pytest.approx(4.1)
    assert loaded.tracks[0].cues[1].type == "loop"
    assert loaded.tracks[0].cues[1].start_seconds == pytest.approx(0.0)


def test_serialize_json_structure(tmp_path):
    backup = _make_backup_file()
    path = tmp_path / "backup.json"
    serialize_backup(backup, str(path))

    raw = json.loads(path.read_text())
    assert "created_at" in raw
    assert "tracks" in raw
    assert raw["tracks"][0]["artist"] == "DJ A"
```

- [ ] **Step 2: Run — verify FAIL**

```bash
pytest tests/backup/test_backup.py -v
```

- [ ] **Step 3: Implement writer.py (models + JSON)**

```python
# src/dj_cue_system/backup/writer.py
from dataclasses import dataclass, field, asdict
import json
from datetime import datetime, timezone


@dataclass
class BackupCue:
    type: str                          # "memory_cue" or "loop"
    name: str
    position_seconds: float | None = None   # memory_cue
    color: str | None = None               # memory_cue
    start_seconds: float | None = None     # loop
    end_seconds: float | None = None       # loop


@dataclass
class BackupTrack:
    id: str
    path: str
    artist: str
    title: str
    cues: list[BackupCue] = field(default_factory=list)


@dataclass
class BackupFile:
    rekordbox_db: str
    tracks: list[BackupTrack]
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )


def serialize_backup(backup: BackupFile, path: str) -> None:
    with open(path, "w") as f:
        json.dump(asdict(backup), f, indent=2)


def deserialize_backup(path: str) -> BackupFile:
    with open(path) as f:
        data = json.load(f)
    tracks = [
        BackupTrack(
            id=t["id"], path=t["path"], artist=t["artist"], title=t["title"],
            cues=[BackupCue(**c) for c in t["cues"]],
        )
        for t in data["tracks"]
    ]
    return BackupFile(
        created_at=data["created_at"],
        rekordbox_db=data["rekordbox_db"],
        tracks=tracks,
    )
```

- [ ] **Step 4: Implement reader.py (reads from DB)**

```python
# src/dj_cue_system/backup/reader.py
from pyrekordbox import Rekordbox6Database
from dj_cue_system.backup.writer import BackupFile, BackupTrack, BackupCue
from dj_cue_system.library.reader import DEFAULT_DB_PATH, _KIND_TO_TYPE


def create_backup(
    db_path: str | None = None,
    playlist_filter: str | None = None,
) -> BackupFile:
    db_path = db_path or DEFAULT_DB_PATH
    db = Rekordbox6Database(db_path)

    # Build playlist filter set if requested
    content_ids_in_playlist: set[str] | None = None
    if playlist_filter:
        playlists = {p.ID: p.Name for p in db.get_playlist()}
        target_ids = {pid for pid, name in playlists.items() if name == playlist_filter}
        content_ids_in_playlist = {
            str(pt.ContentID)
            for pt in db.get_playlist_track()
            if pt.PlaylistID in target_ids
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
                    color=None,
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
```

- [ ] **Step 5: Run — verify PASS**

```bash
pytest tests/backup/test_backup.py -v
```

Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git add src/dj_cue_system/backup/writer.py src/dj_cue_system/backup/reader.py tests/backup/test_backup.py
git commit -m "feat: backup models, JSON writer, and DB reader"
```

---

### Task 14: Backup diff

**Files:**
- Create: `src/dj_cue_system/backup/diff.py`
- Modify: `tests/backup/test_backup.py`

- [ ] **Step 1: Write failing tests — append to test_backup.py**

```python
from dj_cue_system.backup.diff import diff_backups, DiffResult, TrackDiff


def _track(title: str, cues: list[BackupCue]) -> BackupTrack:
    return BackupTrack(id="1", path=f"/music/{title}.mp3", artist="A", title=title, cues=cues)


def test_diff_no_changes():
    cues = [BackupCue(type="memory_cue", name="X", position_seconds=1.0)]
    old = BackupFile(rekordbox_db="/db", tracks=[_track("T", cues)])
    new = BackupFile(rekordbox_db="/db", tracks=[_track("T", cues)])
    result = diff_backups(old, new)
    assert result.changed == []
    assert result.added == []
    assert result.removed == []


def test_diff_added_track():
    old = BackupFile(rekordbox_db="/db", tracks=[])
    new = BackupFile(rekordbox_db="/db", tracks=[_track("New", [])])
    result = diff_backups(old, new)
    assert len(result.added) == 1
    assert result.added[0].title == "New"


def test_diff_removed_track():
    old = BackupFile(rekordbox_db="/db", tracks=[_track("Gone", [])])
    new = BackupFile(rekordbox_db="/db", tracks=[])
    result = diff_backups(old, new)
    assert len(result.removed) == 1


def test_diff_changed_cues():
    old_cues = [BackupCue(type="memory_cue", name="Old", position_seconds=1.0)]
    new_cues = [BackupCue(type="memory_cue", name="New", position_seconds=2.0)]
    old = BackupFile(rekordbox_db="/db", tracks=[_track("T", old_cues)])
    new = BackupFile(rekordbox_db="/db", tracks=[_track("T", new_cues)])
    result = diff_backups(old, new)
    assert len(result.changed) == 1
    assert result.changed[0].title == "T"
```

- [ ] **Step 2: Run — verify FAIL**

```bash
pytest tests/backup/test_backup.py::test_diff_no_changes -v
```

- [ ] **Step 3: Implement diff.py**

```python
# src/dj_cue_system/backup/diff.py
from dataclasses import dataclass, asdict
from dj_cue_system.backup.writer import BackupFile, BackupTrack


@dataclass
class TrackDiff:
    title: str
    path: str


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
```

- [ ] **Step 4: Run — verify PASS**

```bash
pytest tests/backup/test_backup.py -v
```

Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add src/dj_cue_system/backup/diff.py tests/backup/test_backup.py
git commit -m "feat: backup diff"
```

---

### Task 15: CLI — scaffold, analyze single file, and analyze --library/--playlist

**Files:**
- Create: `src/dj_cue_system/cli.py`
- Create: `tests/cli/test_cli.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/cli/test_cli.py
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock
from dj_cue_system.cli import app

runner = CliRunner()


def _mock_analysis_result():
    from dj_cue_system.analysis.models import AnalysisResult, Section, StemOnsets
    return AnalysisResult(
        bpm=126.0,
        downbeats=[i * 2.0 for i in range(129)],
        total_bars=128,
        sections=[
            Section("intro", 0, 16, 0.0, 32.0),
            Section("outro", 96, 128, 192.0, 256.0),
        ],
        stem_onsets=StemOnsets(vocal=4.0),
        audio_path="/music/track.mp3",
        anlz_source=True,
    )


def _mock_track(has_cues=False):
    from dj_cue_system.library.models import Track, ExistingCue
    return Track(
        id="1", path="/music/track.mp3", title="Test", artist="Artist",
        analysis_data_path=None,
        existing_cues=[ExistingCue(1.0, "memory_cue", "X")] if has_cues else [],
        playlists=["Deep House"],
    )


def test_validate_config_ok(tmp_path):
    cfg = tmp_path / "rules.yaml"
    cfg.write_text("rulesets:\n  r:\n    rules: []\ndefaults:\n  rulesets: []\n")
    result = runner.invoke(app, ["validate-config", "--config", str(cfg)])
    assert result.exit_code == 0
    assert "valid" in result.output.lower()


def test_validate_config_invalid(tmp_path):
    cfg = tmp_path / "rules.yaml"
    cfg.write_text("rulesets:\n  bad:\n    rules:\n      - element: x\n        type: bad_type\n        name: X\ndefaults:\n  rulesets: []\n")
    result = runner.invoke(app, ["validate-config", "--config", str(cfg)])
    assert result.exit_code != 0


def test_show_elements(tmp_path):
    cfg = tmp_path / "rules.yaml"
    cfg.write_text("rulesets: {}\ndefaults:\n  rulesets: []\n")
    with patch("dj_cue_system.cli.run_full_analysis", return_value=_mock_analysis_result()):
        result = runner.invoke(app, ["show-elements", "/music/track.mp3", "--config", str(cfg)])
    assert result.exit_code == 0
    assert "126.0" in result.output
    assert "intro" in result.output


def test_analyze_single_dry_run(tmp_path):
    cfg = tmp_path / "rules.yaml"
    cfg.write_text("rulesets:\n  r:\n    rules: []\ndefaults:\n  rulesets: [r]\n")
    with patch("dj_cue_system.cli.run_full_analysis", return_value=_mock_analysis_result()), \
         patch("dj_cue_system.cli.get_tracks", return_value=[_mock_track()]), \
         patch("dj_cue_system.cli.get_track_playlists", return_value={"1": ["Deep House"]}):
        result = runner.invoke(app, [
            "analyze", "/music/track.mp3",
            "--config", str(cfg), "--dry-run"
        ])
    assert result.exit_code == 0


def test_analyze_skips_tracks_with_cues(tmp_path):
    cfg = tmp_path / "rules.yaml"
    cfg.write_text("rulesets:\n  r:\n    rules: []\ndefaults:\n  rulesets: [r]\n")
    with patch("dj_cue_system.cli.run_full_analysis") as mock_analyze, \
         patch("dj_cue_system.cli.get_tracks", return_value=[_mock_track(has_cues=True)]), \
         patch("dj_cue_system.cli.get_track_playlists", return_value={}):
        runner.invoke(app, ["analyze", "--library", "--config", str(cfg), "--dry-run"])
    mock_analyze.assert_not_called()


def test_show_cues_found():
    track = _mock_track(has_cues=True)
    with patch("dj_cue_system.cli.get_track_by_path", return_value=track):
        result = runner.invoke(app, ["show-cues", "/music/track.mp3"])
    assert result.exit_code == 0
    assert "memory cue" in result.output or "Test" in result.output


def test_show_cues_not_found():
    with patch("dj_cue_system.cli.get_track_by_path", return_value=None):
        result = runner.invoke(app, ["show-cues", "/music/missing.mp3"])
    assert result.exit_code != 0
    assert "not found" in result.output.lower()


def test_show_cues_no_cues():
    track = _mock_track(has_cues=False)
    with patch("dj_cue_system.cli.get_track_by_path", return_value=track):
        result = runner.invoke(app, ["show-cues", "/music/track.mp3"])
    assert result.exit_code == 0
    assert "no cue" in result.output.lower()
```

- [ ] **Step 2: Run — verify FAIL**

```bash
pytest tests/cli/test_cli.py -v
```

- [ ] **Step 3: Implement cli.py**

```python
# src/dj_cue_system/cli.py
from __future__ import annotations
import os
import warnings
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table

from dj_cue_system.rules.config import load_config, AppConfig
from dj_cue_system.rules.engine import resolve_cues
from dj_cue_system.library.reader import get_tracks, get_track_playlists, get_track_by_path, DEFAULT_DB_PATH
from dj_cue_system.library.models import Track
from dj_cue_system.writers.rekordbox_xml import RekordboxXmlWriter
from dj_cue_system.writers.dry_run import DryRunWriter
from dj_cue_system.backup.reader import create_backup
from dj_cue_system.backup.writer import serialize_backup, deserialize_backup
from dj_cue_system.backup.diff import diff_backups

app = typer.Typer(name="dj-cue", help="Smart DJ cue point generator")
backup_app = typer.Typer(help="Backup and restore cue points")
app.add_typer(backup_app, name="backup")

console = Console()

DEFAULT_CONFIG = "config/rules.yaml"
DEFAULT_BACKUP_DIR = os.path.expanduser("~/.dj-cue/backups")


def run_full_analysis(audio_path: str, config: AppConfig) -> "AnalysisResult":
    """Run ANLZ + Demucs analysis for a single track."""
    from dj_cue_system.analysis.onset import detect_onset_rms
    from dj_cue_system.analysis.separation import separate_stems
    from dj_cue_system.analysis.models import StemOnsets

    # Try ANLZ first, fall back to all-in-one
    result = _try_anlz_analysis(audio_path, config)

    # Always run Demucs for stem onsets
    stems = separate_stems(audio_path, model_name=config.settings.demucs_model)
    thresholds = config.settings.onset_thresholds
    w = config.settings.onset_window_frames

    result.stem_onsets = StemOnsets(
        vocal=detect_onset_rms(stems.vocals, stems.sample_rate, thresholds.vocal, w),
        drum=detect_onset_rms(stems.drums, stems.sample_rate, thresholds.drum, w),
        bass=detect_onset_rms(stems.bass, stems.sample_rate, thresholds.bass, w),
        other=detect_onset_rms(stems.other, stems.sample_rate, thresholds.other, w),
    )
    return result


def _try_anlz_analysis(audio_path: str, config: AppConfig):
    from dj_cue_system.analysis.fallback import analyze_with_allin1
    # ANLZ path requires knowing the track's AnalysisDataPath.
    # When called with a bare audio file, fall back to all-in-one.
    # When called via --library, ANLZ path is wired in _analyze_track().
    return analyze_with_allin1(audio_path)


def _analyze_track(track: Track, config: AppConfig):
    """Run analysis using ANLZ if available, else all-in-one fallback."""
    from dj_cue_system.analysis.fallback import analyze_with_allin1
    from dj_cue_system.analysis.anlz import parse_beat_grid, parse_phrases
    from dj_cue_system.analysis.assembler import build_sections
    from dj_cue_system.analysis.models import AnalysisResult, StemOnsets
    from dj_cue_system.analysis.separation import separate_stems
    from dj_cue_system.analysis.onset import detect_onset_rms
    from dj_cue_system.analysis.bar_utils import timestamp_to_bar

    anlz_path = track.analysis_data_path
    share_dir = os.path.join(os.path.dirname(DEFAULT_DB_PATH), "share")

    if anlz_path:
        dat_path = os.path.join(share_dir, anlz_path)
        ext_path = dat_path.replace(".DAT", ".EXT")
        if os.path.exists(dat_path) and os.path.exists(ext_path):
            beat_grid = parse_beat_grid(dat_path)
            phrases = parse_phrases(ext_path)

            # Build all_beat_times from DAT file (needed for assembler)
            from pyrekordbox.anlz import AnlzFile
            anlz = AnlzFile.parse_file(dat_path)
            tag = anlz.getone("PQTZ")
            all_beat_times = [b.time / 1000.0 for b in tag.beats]

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
        else:
            result = analyze_with_allin1(track.path)
    else:
        result = analyze_with_allin1(track.path)

    # Stem onset detection (always)
    stems = separate_stems(track.path, model_name=config.settings.demucs_model)
    thresholds = config.settings.onset_thresholds
    w = config.settings.onset_window_frames
    from dj_cue_system.analysis.models import StemOnsets as SO
    result.stem_onsets = SO(
        vocal=detect_onset_rms(stems.vocals, stems.sample_rate, thresholds.vocal, w),
        drum=detect_onset_rms(stems.drums, stems.sample_rate, thresholds.drum, w),
        bass=detect_onset_rms(stems.bass, stems.sample_rate, thresholds.bass, w),
        other=detect_onset_rms(stems.other, stems.sample_rate, thresholds.other, w),
    )
    return result


@app.command()
def analyze(
    audio_file: Optional[str] = typer.Argument(None),
    library: bool = typer.Option(False, "--library"),
    playlist: list[str] = typer.Option([], "--playlist"),
    ruleset: Optional[str] = typer.Option(None, "--ruleset"),
    overwrite: bool = typer.Option(False, "--overwrite"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    config: str = typer.Option(DEFAULT_CONFIG, "--config"),
    output: str = typer.Option("./output.xml", "--output"),
    db: Optional[str] = typer.Option(None, "--db"),
):
    """Generate memory cues and loop points."""
    cfg = load_config(config)
    writer = DryRunWriter() if dry_run else RekordboxXmlWriter(output)

    if audio_file and not library and not playlist:
        # Single file mode — no DB needed
        result = run_full_analysis(audio_file, cfg)
        fake_track = _make_fake_track(audio_file)
        cues, loops = resolve_cues(result, cfg, playlists=[], ruleset_override=ruleset)
        writer.write(fake_track, cues, loops)
    else:
        tracks = get_tracks(db)
        playlist_map = get_track_playlists(db)
        for t in tracks:
            t.playlists = playlist_map.get(t.id, [])

        if playlist:
            tracks = [t for t in tracks if any(p in t.playlists for p in playlist)]

        for track in tracks:
            if track.has_memory_cues and not overwrite:
                continue
            with warnings.catch_warnings(record=True):
                result = _analyze_track(track, cfg)
                cues, loops = resolve_cues(result, cfg, playlists=track.playlists, ruleset_override=ruleset)
            writer.write(track, cues, loops)

    writer.finalize()
    if not dry_run:
        console.print(f"\n[green]Written to {output}[/green]. Import via File → Import → rekordbox xml.")


def _make_fake_track(path: str):
    from dj_cue_system.library.models import Track
    name = os.path.splitext(os.path.basename(path))[0]
    return Track(id="0", path=path, title=name, artist="", analysis_data_path=None)


@app.command("show-elements")
def show_elements(
    audio_file: str = typer.Argument(...),
    apply_rules: bool = typer.Option(False, "--apply-rules"),
    config: str = typer.Option(DEFAULT_CONFIG, "--config"),
):
    """Show detected elements for an audio file."""
    cfg = load_config(config)

    with warnings.catch_warnings(record=True) as caught_warnings:
        warnings.simplefilter("always")
        result = run_full_analysis(audio_file, cfg)

    source = "ANLZ" if result.anlz_source else "all-in-one"
    console.print(f"\n[bold]BPM:[/bold] {result.bpm:.1f} | [bold]Bars:[/bold] {result.total_bars} | [bold]Source:[/bold] {source}\n")

    console.print("[bold]Sections:[/bold]")
    for s in result.sections:
        pct = int(s.position_fraction(result.total_bars) * 100)
        console.print(f"  [{s.start_bar:4} - {s.end_bar:4}] {s.label}  ({s.duration_bars} bars, {pct}%)")

    console.print("\n[bold]Stem onsets:[/bold]")
    so = result.stem_onsets
    for name, val in [("vocal", so.vocal), ("drum", so.drum), ("bass", so.bass), ("other", so.other)]:
        if val is not None:
            bar = result.downbeats.index(min(result.downbeats, key=lambda d: abs(d - val)))
            console.print(f"  {name:6}: bar {bar:3}  ({val:.1f}s)")
        else:
            console.print(f"  {name:6}: not detected")

    if apply_rules:
        cues, loops = resolve_cues(result, cfg, playlists=[])
        console.print("\n[bold]Would place:[/bold]")
        for cue in cues:
            console.print(f"  memory cue  {cue.name!r:20} bar {cue.bar:4}  ({cue.position_seconds:.1f}s)")
        for loop in loops:
            console.print(f"  loop        {loop.name!r:20} bar {loop.start_bar} → {loop.end_bar}")
        for w in caught_warnings:
            console.print(f"  [yellow]⚠ {w.message}[/yellow]")


@app.command("validate-config")
def validate_config(config: str = typer.Option(DEFAULT_CONFIG, "--config")):
    """Validate rules.yaml and report errors."""
    try:
        cfg = load_config(config)
        # Check all playlist rulesets reference defined rulesets
        errors = []
        for pl_name, pl in cfg.playlists.items():
            for rs in pl.rulesets:
                if rs not in cfg.rulesets:
                    errors.append(f"Playlist '{pl_name}' references undefined ruleset '{rs}'")
        for rs in cfg.defaults.rulesets:
            if rs not in cfg.rulesets:
                errors.append(f"Defaults references undefined ruleset '{rs}'")
        if errors:
            for e in errors:
                console.print(f"[red]✗ {e}[/red]")
            raise typer.Exit(1)
        console.print(f"[green]✓ Config is valid.[/green] {len(cfg.rulesets)} rulesets, {len(cfg.playlists)} playlists.")
    except Exception as e:
        console.print(f"[red]✗ Invalid config: {e}[/red]")
        raise typer.Exit(1)


@backup_app.command("create")
def backup_create(
    playlist: Optional[str] = typer.Option(None, "--playlist"),
    output: Optional[str] = typer.Option(None, "--output"),
    db: Optional[str] = typer.Option(None, "--db"),
):
    """Backup cue points from master.db."""
    os.makedirs(DEFAULT_BACKUP_DIR, exist_ok=True)
    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    path = output or os.path.join(DEFAULT_BACKUP_DIR, f"{ts}.json")

    backup = create_backup(db_path=db, playlist_filter=playlist)
    serialize_backup(backup, path)
    console.print(f"[green]Backup saved to {path}[/green] ({len(backup.tracks)} tracks)")


@backup_app.command("list")
def backup_list():
    """List all backups in ~/.dj-cue/backups/."""
    backup_dir = Path(DEFAULT_BACKUP_DIR)
    if not backup_dir.exists():
        console.print("[dim]No backups found.[/dim]")
        return
    files = sorted(backup_dir.glob("*.json"), reverse=True)
    if not files:
        console.print("[dim]No backups found.[/dim]")
        return
    for f in files:
        size_kb = f.stat().st_size // 1024
        console.print(f"  {f.name}  ({size_kb} KB)")


@backup_app.command("diff")
def backup_diff(file_a: str = typer.Argument(...), file_b: str = typer.Argument(...)):
    """Show what changed between two backups."""
    old = deserialize_backup(file_a)
    new = deserialize_backup(file_b)
    result = diff_backups(old, new)

    if result.added:
        console.print(f"\n[green]Added ({len(result.added)} tracks):[/green]")
        for t in result.added:
            console.print(f"  + {t.title} — {t.path}")
    if result.removed:
        console.print(f"\n[red]Removed ({len(result.removed)} tracks):[/red]")
        for t in result.removed:
            console.print(f"  - {t.title} — {t.path}")
    if result.changed:
        console.print(f"\n[yellow]Changed ({len(result.changed)} tracks):[/yellow]")
        for t in result.changed:
            console.print(f"  ~ {t.title} — {t.path}")
    if not any([result.added, result.removed, result.changed]):
        console.print("[dim]No differences.[/dim]")


@app.command("show-cues")
def show_cues(
    audio_file: str = typer.Argument(...),
    db: Optional[str] = typer.Option(None, "--db"),
):
    """Show cue and loop points already stored in Rekordbox for a track."""
    track = get_track_by_path(audio_file, db_path=db)
    if track is None:
        console.print(f"[red]✗ Track not found in Rekordbox library:[/red] {audio_file}")
        raise typer.Exit(1)

    console.print(f"\n[bold]Track:[/bold]  {track.artist} — {track.title}")
    console.print(f"[bold]Path:[/bold]   {track.path}\n")

    memory_cues = [c for c in track.existing_cues if c.cue_type == "memory_cue"]
    loops = [c for c in track.existing_cues if c.cue_type == "loop"]

    if not memory_cues and not loops:
        console.print("[dim]No cue or loop points found.[/dim]")
        return

    # Optionally load bar numbers from ANLZ if available
    bar_map: dict[float, int] = {}
    share_dir = os.path.join(os.path.dirname(db or DEFAULT_DB_PATH), "share")
    if track.analysis_data_path:
        dat_path = os.path.join(share_dir, track.analysis_data_path)
        if os.path.exists(dat_path):
            try:
                from dj_cue_system.analysis.anlz import parse_beat_grid
                from dj_cue_system.analysis.bar_utils import timestamp_to_bar
                bg = parse_beat_grid(dat_path)
                for cue in track.existing_cues:
                    t = cue.position_seconds
                    bar_map[t] = timestamp_to_bar(t, bg.downbeats)
            except Exception:
                pass

    def bar_str(t: float) -> str:
        return f"  bar {bar_map[t]}" if t in bar_map else ""

    if memory_cues:
        console.print(f"[bold]Cue points ({len(memory_cues)}):[/bold]")
        for c in memory_cues:
            console.print(f"  memory cue  {c.name!r:20} {c.position_seconds:.3f}s{bar_str(c.position_seconds)}")

    if loops:
        console.print(f"\n[bold]Loop points ({len(loops)}):[/bold]")
        for c in loops:
            console.print(f"  loop  {c.name!r:20} {c.position_seconds:.3f}s")


@app.command()
def restore(
    backup_file: str = typer.Argument(...),
    output: str = typer.Option("./restored.xml", "--output"),
    tracks: list[str] = typer.Option([], "--tracks"),
):
    """Generate rekordbox.xml from a backup file."""
    backup = deserialize_backup(backup_file)
    writer = RekordboxXmlWriter(output)

    for bt in backup.tracks:
        if tracks and bt.path not in tracks:
            continue
        fake_track = _make_fake_track(bt.path)
        fake_track.title = bt.title
        fake_track.artist = bt.artist

        from dj_cue_system.writers.base import CuePoint, LoopPoint
        cues = [
            CuePoint(name=c.name, position_seconds=c.position_seconds or 0.0,
                     bar=0, color=c.color)
            for c in bt.cues if c.type == "memory_cue"
        ]
        loops = [
            LoopPoint(name=c.name, start_seconds=c.start_seconds or 0.0,
                      end_seconds=c.end_seconds or 0.0, start_bar=0, end_bar=0)
            for c in bt.cues if c.type == "loop"
        ]
        writer.write(fake_track, cues, loops)

    writer.finalize()
    console.print(f"[green]Restored to {output}[/green]. Import via File → Import → rekordbox xml.")
```

- [ ] **Step 4: Run — verify PASS**

```bash
pytest tests/cli/test_cli.py -v
```

Expected: 5 passed

- [ ] **Step 5: Run full suite**

```bash
pytest -v
```

Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add src/dj_cue_system/cli.py tests/cli/test_cli.py
git commit -m "feat: CLI — analyze, show-elements, validate-config, backup, restore"
```

---

### Task 16: Final wiring — verify end-to-end with a real track

This task has no automated test — it's a smoke test with real audio.

- [ ] **Step 1: Run show-elements on a real track**

```bash
dj-cue show-elements "/path/to/any/track.mp3" --config config/rules.yaml
```

Expected: BPM, bars, sections, stem onsets printed. No crash.

- [ ] **Step 2: Run show-elements --apply-rules**

```bash
dj-cue show-elements "/path/to/track.mp3" --apply-rules --config config/rules.yaml
```

Expected: "Would place:" section with cue positions printed.

- [ ] **Step 3: Run analyze dry-run on a single track**

```bash
dj-cue analyze "/path/to/track.mp3" --dry-run --config config/rules.yaml
```

Expected: cue preview printed, no file written.

- [ ] **Step 4: Run analyze and produce XML**

```bash
dj-cue analyze "/path/to/track.mp3" --output /tmp/test_cues.xml --config config/rules.yaml
cat /tmp/test_cues.xml
```

Expected: valid XML with `<POSITION_MARK>` elements.

- [ ] **Step 5: Run validate-config**

```bash
dj-cue validate-config --config config/rules.yaml
```

Expected: `✓ Config is valid.`

- [ ] **Step 6: Run backup create + list (requires Rekordbox installed)**

```bash
dj-cue backup create --output /tmp/test_backup.json
dj-cue backup list
```

- [ ] **Step 7: Final commit**

```bash
git add -A
git commit -m "chore: smoke test verified end-to-end"
```

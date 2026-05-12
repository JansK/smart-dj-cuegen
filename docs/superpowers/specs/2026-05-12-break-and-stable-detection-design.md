# Break & Stable Region Detection Design

**Date:** 2026-05-12  
**Status:** Approved

## Overview

Extend the analysis pipeline to detect two new types of structural region from audio:

1. **Breaks** — consecutive bars where a significant number of stems drop to near-silence simultaneously.
2. **Stable intro / outro regions** — stretches at the start and end of a track where all active stems hold at a consistent energy level (no gradual builds, no drops, no new elements entering or exiting).

Both are computed from per-bar RMS energy arrays for each stem. These arrays are derived from the same stem separation already used for onset detection (Librosa HPSS for LQ, Demucs for HQ) and stored alongside the existing onset timestamps in the stems cache.

Detected sections are appended to `AnalysisResult.sections` and automatically available to the rules engine.

---

## 1. Per-Bar Energy Computation

**Module:** `analysis/energy.py`

```python
def compute_bar_energy(
    drums: np.ndarray,
    bass: np.ndarray,
    vocal: np.ndarray,
    other: np.ndarray,
    sr: int,
    downbeats: list[float],
) -> BarEnergy
```

For each bar `i` (defined by `downbeats[i]` to `downbeats[i+1]`), slice each stem's audio array and compute:

```
bar_rms[i] = sqrt(mean(segment²))
```

The final bar uses `len(audio) / sr` as its end time. Returns a `BarEnergy` dataclass (see Data Model).

This is called:
- In the LQ path: immediately after `detect_stem_onsets_fast` separates the stems, reusing the same in-memory arrays.
- In the HQ path: immediately after `separate_stems` returns `StemAudio`, reusing those arrays.

Downbeats are passed in from the calling context (`_analyze_track` or `run_full_analysis`), both of which have the beat grid available before stems are computed.

---

## 2. Break Detection

**Module:** `analysis/break_detect.py`

```python
def detect_breaks(
    bar_energy: BarEnergy,
    downbeats: list[float],
    config: BreakDetectionConfig,
) -> list[Section]
```

**Algorithm:**

1. For each stem, compute **typical energy** = median of non-zero bar RMS values across the track (median is robust to loud intros/outros skewing the baseline).
2. Identify **active stems**: those with `typical_energy > 0.01` (absolute floor). Stems below this floor are excluded from all counting — they are neither "silent" nor "present". This prevents absent stems (e.g., vocals in an instrumental) from inflating the silent stem count.
3. For each bar, count how many active stems have `bar_rms < silence_fraction × typical_energy`. Call this the bar's **silent stem count**.
4. Find consecutive runs of bars where:
   - `silent_stem_count >= min_stems_silent`
   - Run length `>= min_bars`
5. Each qualifying run → `Section(label="break", start_bar=..., end_bar=..., start_time=..., end_time=...)`.

**Config** (`BreakDetectionConfig` in `rules/config.py`):

| Parameter | Default | Meaning |
|---|---|---|
| `silence_fraction` | `0.3` | Fraction of typical energy below which a stem is "silent" |
| `min_stems_silent` | `2` | Minimum number of simultaneously silent stems |
| `min_bars` | `4` | Minimum break duration in bars |

---

## 3. Stable Region Detection

**Module:** `analysis/stable_detect.py`

```python
def detect_stable_regions(
    bar_energy: BarEnergy,
    downbeats: list[float],
    config: StableDetectionConfig,
) -> tuple[Section | None, Section | None]  # (stable_intro, stable_outro)
```

**Algorithm:**

For a candidate window `[start, end]`:

1. Identify **active stems**: stems whose mean `bar_rms` within the window exceeds `0.01` (same absolute floor as break detection). Stems below this floor are excluded.
2. For each active stem, compute `CV = std(bar_rms) / mean(bar_rms)` across the window.
3. **Stable condition**: `max(CV across active stems) < stability_cv_threshold`.

**Stable intro**: Search all candidate windows `[a, b]` within bars `[0, max_scan_bars]` where `b - a ≥ min_stable_bars`. Evaluate the stable condition over each candidate window. Return the longest qualifying window as `Section(label="stable_intro", start_bar=a, end_bar=b)`. The region does not have to start at bar 0.

**Stable outro**: Same O(N²) search within bars `[total_bars - max_scan_bars, total_bars]`. Returns `Section(label="stable_outro", start_bar=a, end_bar=b)`. The region does not have to end at the last bar.

The search space is at most 128 bars per zone (≤ 16,384 candidate windows) — fast enough to enumerate exhaustively.

This correctly handles gradual buildups: a stem entering from silence to full energy over 32 bars will produce a high std relative to its mean in that window, failing the stability condition.

**Config** (`StableDetectionConfig` in `rules/config.py`):

| Parameter | Default | Meaning |
|---|---|---|
| `stability_cv_threshold` | `0.4` | Max coefficient of variation (std/mean) per active stem |
| `min_stable_bars` | `8` | Minimum qualifying region length |
| `max_scan_bars` | `128` | Only scan within first/last N bars |

---

## 4. Data Model

**`analysis/models.py`** — new `BarEnergy` dataclass:

```python
@dataclass
class BarEnergy:
    drum_bar_energies: list[float]
    bass_bar_energies: list[float]
    vocal_bar_energies: list[float]
    other_bar_energies: list[float]
```

No changes to `AnalysisResult` or `Section`. Detected breaks and stable regions are appended to `result.sections` (sorted by `start_bar`) in the same list as ANLZ-sourced phrase sections.

---

## 5. Stems Cache Extension

**`stems/cache.py`** — four optional fields added to `CacheEntry` and the JSON format (named `<stem>_bar_energies`):

```json
{
  "audio_path": "...",
  "source": "demucs",
  "computed_at": "...",
  "vocal_first_onset": 0.246,
  "drum_first_onset": 0.012,
  "bass_first_onset": null,
  "other_first_onset": 0.244,
  "drum_bar_energies": [0.12, 0.15, 0.14, ...],
  "bass_bar_energies": [0.02, 0.03, 0.02, ...],
  "vocal_bar_energies": [0.00, 0.01, 0.01, ...],
  "other_bar_energies": [0.05, 0.08, 0.06, ...]
}
```

Storage estimate: ~65 KB per cache file for a 7-minute track. ~34 MB total across all current entries once rebuilt.

**Backward compatibility:** Old cache entries without bar energy fields are treated as a cache miss for bar energy. On the next full analysis run, the cache entry is recomputed from scratch (both onset timestamps and bar energy arrays) and overwritten. This is an accepted trade-off per design decision.

---

## 6. Module Change Summary

| Module | Change |
|---|---|
| `analysis/energy.py` | **New.** `compute_bar_energy(...)` → `BarEnergy` |
| `analysis/break_detect.py` | **New.** `detect_breaks(...)` → `list[Section]` |
| `analysis/stable_detect.py` | **New.** `detect_stable_regions(...)` → `(Section \| None, Section \| None)` |
| `analysis/models.py` | Add `BarEnergy` dataclass |
| `rules/config.py` | Add `BreakDetectionConfig`, `StableDetectionConfig`; nest both in `SettingsConfig` |
| `analysis/fast_stems.py` | Accept optional `downbeats` param; return `(StemOnsets, BarEnergy \| None)` |
| `stems/cache.py` | Extend `CacheEntry`, `save()`, `_read_entry()` with bar energy fields |
| `cli.py` | `_get_stem_onsets` accepts `downbeats`, returns `(StemOnsets, BarEnergy \| None, str \| None)`; callers pass downbeats; call `detect_breaks` and `detect_stable_regions` and append results to `result.sections` |

`separation.py` is unchanged — Demucs stem arrays are consumed directly in `cli.py`'s HQ path.

---

## 7. Rules Engine Integration

**`rules/engine.py`** — new entries in `_SECTION_ELEMENTS`:

```python
_SECTION_ELEMENTS = {
    # existing...
    "stable_intro_start", "stable_intro_end",
    "stable_outro_start", "stable_outro_end",
}
```

No alias mapping needed. Existing `break_start` / `break_end` elements already resolve to sections with label `"break"` via `_LABEL_ALIASES`. Audio-detected break sections use `label="break"` and are picked up automatically.

Example rule using stable regions:

```yaml
- element: stable_intro_end
  type: loop
  name: "mix in"
  offset_bars: -16
  length_bars: 16
```

The `show-elements` command displays all detected sections (breaks and stable regions) in its sections table without any changes — they appear as regular entries.

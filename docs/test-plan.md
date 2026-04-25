# Manual CLI Test Plan

Validates every `dj-cue` command and option against a real Rekordbox library and audio files. Run from `/Users/kevin_janssen/Code/smart-dj-cuegen` with `.venv/bin/dj-cue` on the path.

## Fixtures

| Name | Value |
|---|---|
| `$WITH_CUES` | `/Users/kevin_janssen/Music/Tracks/Theus Mago - Terremoto Valley Express (Original Mix).aiff` |
| `$NO_CUES` | `/Users/kevin_janssen/Music/Tracks/14157512_La Femme Fantastique_(KiNK & KEi Extended Remix).wav` |
| `$PL_MIXED` | `playlist_mixed_cues` (some tracks have cues, some don't) |
| `$PL_ALL` | `playlist_all_cued` (all tracks have cues) |
| `$PL_NONE` | `playlist_no_cues` (no tracks have cues) |
| `$NONEXISTENT` | `/tmp/does-not-exist.mp3` |

## Execution Order (safety-first)

Run groups in this order. **Group 0 must succeed before any other group runs** — it establishes a known-good safety net so any later test that touches cues can be undone. The tool only reads `master.db` directly, but `analyze` and `restore` produce XML you may import into Rekordbox.

```
Group 0  Pre-flight backup/restore (MUST run first)
Group 1  Help & Discovery
Group 2  validate-config
Group 3  show-cues
Group 4  show-elements
Group 5  analyze single file
Group 6  analyze with playlists
Group 7  backup (additional coverage)
Group 8  restore (additional coverage)
Teardown
```

Status legend: ⏳ pending · ✅ pass · ❌ fail · ⚠️ pass with issue

---

## Group 0 — Pre-flight Safety (run first)

Establish and validate a backup before anything else. If any later test causes you to import a bad XML into Rekordbox, restore from `bk_safety.json`.

| # | Command | Expected | Status | Notes |
|---|---|---|---|---|
| 0.1 | `dj-cue backup create --output /tmp/bk_safety.json` | JSON written, "Backup saved to … (N tracks)" with N > 0 | ⏳ | Establishes safety net |
| 0.2 | `python3 -c "import json; d=json.load(open('/tmp/bk_safety.json')); print('tracks:', len(d['tracks'])); assert len(d['tracks'])>0"` | "tracks: N" with N > 0, no AssertionError | ⏳ | Validates backup is non-empty |
| 0.3 | `dj-cue restore /tmp/bk_safety.json --output /tmp/bk_safety_restored.xml` | "Restored to /tmp/bk_safety_restored.xml" | ⏳ | Round-trip validation |
| 0.4 | `grep -c "POSITION_MARK" /tmp/bk_safety_restored.xml` | Count > 0, equal to total cue+loop count from 0.2 | ⏳ | Verify XML structure is correct |
| 0.5 | `grep -c "<TRACK " /tmp/bk_safety_restored.xml` | Count equals N from 0.2 | ⏳ | Verify all tracks roundtripped |

**Stop if Group 0 fails.** Do not proceed to any other group until backup/restore round-trip is proven.

---

## Group 1 — Help & Discovery (instant, no side effects)

| # | Command | Expected | Status | Notes |
|---|---|---|---|---|
| 1.1 | `dj-cue --help` | Lists 6 commands: analyze, show-elements, show-cues, validate-config, restore, backup | ⏳ | |
| 1.2 | `dj-cue analyze --help` | All 9 options shown with descriptions | ⏳ | --library, --playlist, --ruleset, --overwrite, --dry-run, --config, --output, --db, --help |
| 1.3 | `dj-cue show-elements --help` | audio_file arg + --apply-rules, --config | ⏳ | |
| 1.4 | `dj-cue show-cues --help` | audio_file arg + --db | ⏳ | |
| 1.5 | `dj-cue validate-config --help` | --config option | ⏳ | |
| 1.6 | `dj-cue backup --help` | 3 subcommands: create, list, diff | ⏳ | |
| 1.7 | `dj-cue backup create --help` | --playlist, --output, --db | ⏳ | |
| 1.8 | `dj-cue backup list --help` | No options beyond --help | ⏳ | |
| 1.9 | `dj-cue backup diff --help` | 2 positional args (file_a, file_b) | ⏳ | |
| 1.10 | `dj-cue restore --help` | backup_file arg + --output, --tracks | ⏳ | |

---

## Group 2 — validate-config (instant)

| # | Command | Expected | Status | Notes |
|---|---|---|---|---|
| 2.1 | `dj-cue validate-config` | "✓ Config is valid. N rulesets, M playlists" exit 0 | ⏳ | uses default config/rules.yaml |
| 2.2 | `dj-cue validate-config --config /tmp/missing.yaml; echo "exit=$?"` | "✗ Config file not found" exit=1 | ⏳ | |
| 2.3 | `printf "rulesets: not-a-dict\n" > /tmp/malformed.yaml && dj-cue validate-config --config /tmp/malformed.yaml; echo "exit=$?"` | "✗ Invalid config: …" exit=1 | ⏳ | Structurally invalid YAML |
| 2.4 | `printf "rulesets:\n  x:\n    rules: []\nplaylists:\n  P1:\n    rulesets: [undefined_ruleset]\ndefaults:\n  rulesets: []\n" > /tmp/dangling.yaml && dj-cue validate-config --config /tmp/dangling.yaml; echo "exit=$?"` | "✗ Playlist 'P1' references undefined ruleset 'undefined_ruleset'" exit=1 | ⏳ | Dangling reference (separate code path from 2.3) |

---

## Group 3 — show-cues (fast, DB read only)

| # | Command | Expected | Status | Notes |
|---|---|---|---|---|
| 3.1 | `dj-cue show-cues "$WITH_CUES"; echo "exit=$?"` | Track info + "Cue points (N):" header + bar numbers, exit=0 | ⏳ | |
| 3.2 | `dj-cue show-cues "$NO_CUES"; echo "exit=$?"` | Track info + "No cue or loop points found." exit=0 | ⏳ | |
| 3.3 | `dj-cue show-cues "$NONEXISTENT"; echo "exit=$?"` | "✗ Track not found in Rekordbox library: …" exit=1 | ⏳ | |
| 3.4 | `dj-cue show-cues "$WITH_CUES" --db /tmp/missing.db; echo "exit=$?"` | Error from pyrekordbox, non-zero exit | ⏳ | Bad --db path |

---

## Group 4 — show-elements (slow, runs Demucs ~1 min/track)

| # | Command | Expected | Status | Notes |
|---|---|---|---|---|
| 4.1 | `dj-cue show-elements "$WITH_CUES"` | "BPM: X.X \| Bars: N \| Source: ANLZ" + Sections + Stem onsets | ⏳ | Library track → ANLZ path |
| 4.2 | `dj-cue show-elements "$WITH_CUES" --apply-rules` | Above + "Would place:" preview with cues/loops | ⏳ | |
| 4.3 | `dj-cue show-elements "$NO_CUES"` | "BPM: X.X \| Bars: N \| Source: ANLZ" (if in library) or "all-in-one"; sections + stem onsets non-empty | ⏳ | Confirm source matches whether track is in library |
| 4.4 | `dj-cue show-elements "$NO_CUES" --apply-rules` | Above + "Would place:" preview | ⏳ | |
| 4.5 | `dj-cue show-elements "$WITH_CUES" --config /tmp/dangling.yaml` | Analysis runs but rules likely warn or skip | ⏳ | Custom config, reuses 2.4's fixture |

---

## Group 5 — analyze single file (slow per track)

| # | Command | Expected | Status | Notes |
|---|---|---|---|---|
| 5.1 | `dj-cue analyze "$NO_CUES" --dry-run` | DryRunWriter output, no XML written | ⏳ | |
| 5.2 | `dj-cue analyze "$NO_CUES" --output /tmp/single.xml` | "Written to /tmp/single.xml" | ⏳ | |
| 5.3 | `grep -c "POSITION_MARK" /tmp/single.xml` | Count > 0 | ⏳ | Verify XML content from 5.2 |
| 5.4 | `grep -c "<TRACK " /tmp/single.xml` | Count = 1 | ⏳ | Verify one track in output |
| 5.5 | `dj-cue analyze "$WITH_CUES" --dry-run` | Dry-run preview, no XML | ⏳ | Confirm in-library file uses ANLZ path |
| 5.6 | `dj-cue analyze; echo "exit=$?"` | Error or no-op (no audio_file, no --library, no --playlist) | ⏳ | Document what happens |
| 5.7 | `dj-cue analyze "$NO_CUES" --ruleset nonexistent-ruleset --dry-run` | Warning "Ruleset 'nonexistent-ruleset' not found" + 0 cues placed | ⏳ | |
| 5.8 | `dj-cue analyze --library --dry-run 2>&1 \| head -50` | All library tracks iterated; tracks with cues skipped, tracks without cues processed | ⏳ | Only --library test in plan |
| 5.9 | `dj-cue analyze --library --playlist $PL_NONE --dry-run` | Document behavior — does --library override --playlist or vice versa? | ⏳ | Conflicting flags |

---

## Group 6 — analyze with playlists (slow per track in playlist)

| # | Command | Expected | Status | Notes |
|---|---|---|---|---|
| 6.1 | `dj-cue analyze --playlist $PL_NONE --dry-run` | All tracks processed, dry run output | ⏳ | |
| 6.2 | `dj-cue analyze --playlist $PL_ALL --dry-run` | "0 written" or all tracks skipped (have cues) | ⏳ | |
| 6.3 | `dj-cue analyze --playlist $PL_ALL --overwrite --dry-run` | All tracks processed (overwrite forces) | ⏳ | |
| 6.4 | `dj-cue analyze --playlist $PL_MIXED --dry-run` | Some skipped, some processed | ⏳ | |
| 6.5 | `dj-cue analyze --playlist $PL_NONE --ruleset break-hunter --dry-run` | Only break-hunter rules applied to each track | ⏳ | |
| 6.6 | `dj-cue analyze --playlist $PL_NONE --output /tmp/pl.xml` | XML written | ⏳ | |
| 6.7 | `grep -c "<TRACK " /tmp/pl.xml` | Count > 0, matches tracks-in-PL_NONE count | ⏳ | Verify 6.6 output |
| 6.8 | `dj-cue analyze --playlist $PL_NONE --playlist $PL_MIXED --dry-run` | Tracks from union of both playlists processed | ⏳ | Multi-playlist filter |
| 6.9 | `dj-cue analyze --playlist "playlist_does_not_exist" --dry-run` | 0 tracks processed (empty filter result) | ⏳ | Non-existent playlist name |
| 6.10 | `dj-cue analyze --playlist $PL_NONE --output /tmp/pl_overwrite.xml && dj-cue analyze --playlist $PL_NONE --output /tmp/pl_overwrite.xml` | Second run overwrites without error | ⏳ | Output file exists |

---

## Group 7 — backup additional coverage (fast)

| # | Command | Expected | Status | Notes |
|---|---|---|---|---|
| 7.1 | `dj-cue backup create --output /tmp/bk1.json` | JSON, "N tracks" message | ⏳ | |
| 7.2 | `dj-cue backup create --playlist $PL_ALL --output /tmp/bk_pl.json` | JSON, fewer tracks than 7.1 | ⏳ | |
| 7.3 | `python3 -c "import json; print(len(json.load(open('/tmp/bk_pl.json'))['tracks']))" < `python3 -c "import json; print(len(json.load(open('/tmp/bk1.json'))['tracks']))"` | bk_pl.json has fewer tracks than bk1.json | ⏳ | Verify --playlist filter actually filtered |
| 7.4 | `BACKUP_FILE=$(dj-cue backup create 2>&1 \| grep -oE '/[^ ]+\.json'); echo $BACKUP_FILE; ls -la "$BACKUP_FILE"` | File exists in `~/.dj-cue/backups/` with timestamp name | ⏳ | Default path; record filename for cleanup |
| 7.5 | `dj-cue backup list` | Lists files in `~/.dj-cue/backups/` including the one from 7.4 | ⏳ | |
| 7.6 | `dj-cue backup diff /tmp/bk1.json /tmp/bk1.json` | "No differences." exit=0 | ⏳ | Self-diff |
| 7.7 | `dj-cue backup diff /tmp/bk1.json /tmp/bk_pl.json` | Removed tracks shown (those in bk1 but not bk_pl) | ⏳ | Diff direction: removed = present in old, absent in new |
| 7.8 | `dj-cue backup diff /tmp/missing_a.json /tmp/bk1.json; echo "exit=$?"` | FileNotFoundError, non-zero exit | ⏳ | |
| 7.9 | `dj-cue backup create --playlist "playlist_does_not_exist" --output /tmp/bk_empty.json && python3 -c "import json; print(len(json.load(open('/tmp/bk_empty.json'))['tracks']))"` | "0" tracks, valid JSON written | ⏳ | Non-existent playlist filter |

---

## Group 8 — restore additional coverage (fast)

| # | Command | Expected | Status | Notes |
|---|---|---|---|---|
| 8.1 | `dj-cue restore /tmp/bk1.json --output /tmp/restored.xml` | "Restored to …" | ⏳ | Depends on 7.1 |
| 8.2 | `grep -c "POSITION_MARK" /tmp/restored.xml` | Count = total cue+loop count in bk1.json | ⏳ | Verify 8.1 |
| 8.3 | `dj-cue restore /tmp/bk1.json --output /tmp/r2.xml --tracks "$WITH_CUES"` | XML with only that track | ⏳ | |
| 8.4 | `grep -c "<TRACK " /tmp/r2.xml` | Count = 1 | ⏳ | Verify 8.3 single-track filter |
| 8.5 | `dj-cue restore /tmp/bk1.json --output /tmp/r3.xml --tracks "$WITH_CUES" --tracks "$NO_CUES" && grep -c "<TRACK " /tmp/r3.xml` | Count = 2 (or however many of those paths are in bk1.json) | ⏳ | Multi-value --tracks |
| 8.6 | `dj-cue restore /tmp/bk1.json --output /tmp/r4.xml --tracks "/path/not/in/backup.aiff" && grep -c "<TRACK " /tmp/r4.xml` | Count = 0 (XML has no TRACK elements) | ⏳ | --tracks path absent from backup |
| 8.7 | `dj-cue restore /tmp/missing_backup.json; echo "exit=$?"` | FileNotFoundError, non-zero exit | ⏳ | |

---

## Teardown

Clean up test artifacts.

| # | Command | Status | Notes |
|---|---|---|---|
| T.1 | `rm -f /tmp/bk_safety.json /tmp/bk_safety_restored.xml /tmp/bk1.json /tmp/bk_pl.json /tmp/bk_empty.json /tmp/single.xml /tmp/pl.xml /tmp/pl_overwrite.xml /tmp/restored.xml /tmp/r2.xml /tmp/r3.xml /tmp/r4.xml /tmp/dangling.yaml /tmp/malformed.yaml` | ⏳ | Remove /tmp artifacts |
| T.2 | `rm "$BACKUP_FILE"` (using filename recorded in 7.4) | ⏳ | Remove default-location backup |
| T.3 | If any test caused the user to import a bad XML to Rekordbox: `dj-cue restore /tmp/bk_safety.json --output /tmp/recovery.xml` then re-import in Rekordbox | ⏳ | Recovery path |

---

## Issues Found

| # | Status | Test | Description | Resolution |
|---|---|---|---|---|
| _none yet_ | | | | |

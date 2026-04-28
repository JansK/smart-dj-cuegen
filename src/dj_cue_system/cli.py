from __future__ import annotations
import os
import warnings
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn

from dj_cue_system.rules.config import load_config, AppConfig
from dj_cue_system.rules.engine import resolve_cues
from dj_cue_system.library.reader import (
    get_tracks, get_track_playlists, get_track_by_path, DEFAULT_DB_PATH,
)
from dj_cue_system.library.models import Track
from dj_cue_system.writers.rekordbox_xml import RekordboxXmlWriter
from dj_cue_system.writers.dry_run import DryRunWriter
from dj_cue_system.backup.reader import create_backup
from dj_cue_system.backup.writer import serialize_backup, deserialize_backup
from dj_cue_system.backup.diff import diff_backups

app = typer.Typer(name="dj-cue", help="Smart DJ cue point generator")
backup_app = typer.Typer(help="Backup and restore cue points")
app.add_typer(backup_app, name="backup")
stems_app = typer.Typer(help="Stem onset detection and caching")
stems_cache_app = typer.Typer(help="Manage the stems cache")
stems_app.add_typer(stems_cache_app, name="cache")
app.add_typer(stems_app, name="stems")

console = Console()

DEFAULT_CONFIG = "config/rules.yaml"
DEFAULT_BACKUP_DIR = os.path.expanduser("~/.dj-cue/backups")


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
        cached = stems_cache.load(audio_path, hq=hq)
        if cached is not None:
            onsets, source = cached
            if hq and source == "librosa":
                console.print(
                    f'[yellow]⚠ Using cached librosa result for '
                    f'"{os.path.basename(audio_path)}"; run '
                    f'`dj-cue stems run --path "{audio_path}"` '
                    f'to compute Demucs stems[/yellow]'
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


def run_full_analysis(audio_path: str, config: AppConfig, hq: bool = False) -> tuple["AnalysisResult", str | None]:
    """Analyze a bare audio file and return (result, cache_source)."""
    from dj_cue_system.analysis.fallback import analyze_with_allin1

    result = analyze_with_allin1(audio_path)
    onsets, cache_source = _get_stem_onsets(audio_path, config, hq)
    result.stem_onsets = onsets
    return result, cache_source


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


def _make_fake_track(path: str, title: str | None = None, artist: str = "") -> Track:
    name = title or os.path.splitext(os.path.basename(path))[0]
    return Track(id="0", path=path, title=name, artist=artist, analysis_data_path=None)


@app.command()
def analyze(
    audio_file: Optional[str] = typer.Argument(None, help="Path to the audio file to analyze (as it appears in your Rekordbox library). Omit when using --library or --playlist."),
    library: bool = typer.Option(False, "--library", help="Process all tracks in your Rekordbox library. Skips tracks that already have memory cues unless --overwrite is set."),
    playlist: list[str] = typer.Option([], "--playlist", help="Limit processing to tracks in this Rekordbox playlist. Repeatable: --playlist 'Deep House' --playlist 'Techno'."),
    ruleset: Optional[str] = typer.Option(None, "--ruleset", help="Apply a single named ruleset from rules.yaml to all processed tracks, ignoring playlist mappings."),
    overwrite: bool = typer.Option(False, "--overwrite", help="Re-analyze and overwrite cues on tracks that already have memory cues set."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print what cues and loops would be placed without writing any output file."),
    config: str = typer.Option(DEFAULT_CONFIG, "--config", help="Path to rules.yaml config file."),
    output: str = typer.Option("./output.xml", "--output", help="Path for the generated rekordbox.xml. Import this file in Rekordbox via File → Import → rekordbox xml."),
    db: Optional[str] = typer.Option(None, "--db", help="Path to Rekordbox master.db. Auto-detected at ~/Library/Pioneer/rekordbox/master.db on Mac."),
    hq: bool = typer.Option(False, "--hq", help="Use Demucs neural-network stem separation for higher-accuracy onset detection (slow — several minutes per track)."),
):
    """Generate memory cues and loop points."""
    cfg = load_config(config)
    writer = DryRunWriter() if dry_run else RekordboxXmlWriter(output)

    try:
        if audio_file and not library and not playlist:
            # Try the Rekordbox library first so ANLZ files are used when available.
            # Falls back to allin1 only if the track is not in the library.
            track = get_track_by_path(audio_file, db_path=db)
            if track:
                with warnings.catch_warnings(record=True):
                    result, _ = _analyze_track(track, cfg, db_path=db, hq=hq)
                fake_track = _make_fake_track(audio_file, title=track.title, artist=track.artist)
            else:
                result, _ = run_full_analysis(audio_file, cfg, hq=hq)
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
                try:
                    with warnings.catch_warnings(record=True):
                        result, _ = _analyze_track(track, cfg, db_path=db, hq=hq)
                        cues, loops = resolve_cues(result, cfg, playlists=track.playlists, ruleset_override=ruleset)
                    writer.write(track, cues, loops)
                except RuntimeError as e:
                    console.print(f"[yellow]⚠ Skipping {track.title!r}: {e}[/yellow]")
    except FileNotFoundError as e:
        console.print(f"[red]✗ Database not found:[/red] {e}")
        raise typer.Exit(1)

    writer.finalize()
    if not dry_run:
        console.print(f"\n[green]Written to {output}[/green]. Import via File → Import → rekordbox xml.")


@app.command("show-elements")
def show_elements(
    audio_file: str = typer.Argument(..., help="Path to the audio file to inspect."),
    apply_rules: bool = typer.Option(False, "--apply-rules", help="Also preview which cues and loops would be placed based on the current rules config."),
    config: str = typer.Option(DEFAULT_CONFIG, "--config", help="Path to rules.yaml config file."),
    hq: bool = typer.Option(False, "--hq", help="Use Demucs neural-network stem separation for higher-accuracy onset detection (slow — several minutes per track)."),
):
    """Show detected elements for an audio file."""
    cfg = load_config(config)
    with warnings.catch_warnings(record=True) as caught_warnings:
        warnings.simplefilter("always")
        track = get_track_by_path(audio_file)
        if track:
            result, cache_source = _analyze_track(track, cfg, hq=hq)
        else:
            result, cache_source = run_full_analysis(audio_file, cfg, hq=hq)

    source = "ANLZ" if result.anlz_source else "all-in-one"
    console.print(f"\n[bold]BPM:[/bold] {result.bpm:.1f} | [bold]Bars:[/bold] {result.total_bars} | [bold]Source:[/bold] {source}\n")
    console.print("[bold]Sections:[/bold]")
    for s in result.sections:
        pct = int(s.position_fraction(result.total_bars) * 100)
        console.print(f"  [{s.start_bar:4} - {s.end_bar:4}] {s.label}  ({s.duration_bars} bars, {pct}%)")

    cache_label = f"  [dim](cached · {cache_source})[/dim]" if cache_source else ""
    console.print(f"\n[bold]Stem onsets:[/bold]{cache_label}")
    so = result.stem_onsets
    for stem_name, val in [("vocal", so.vocal), ("drum", so.drum), ("bass", so.bass), ("other", so.other)]:
        if val is not None:
            from dj_cue_system.analysis.bar_utils import timestamp_to_bar
            bar = timestamp_to_bar(val, result.downbeats)
            console.print(f"  {stem_name:6}: bar {bar:3}  ({val:.1f}s)")
        else:
            console.print(f"  {stem_name:6}: not detected")

    for w in caught_warnings:
        console.print(f"[yellow]⚠ {w.message}[/yellow]")

    if apply_rules:
        cues, loops = resolve_cues(result, cfg, playlists=[])
        console.print("\n[bold]Would place:[/bold]")
        for cue in cues:
            console.print(f"  memory cue  {cue.name!r:20} bar {cue.bar:4}  ({cue.position_seconds:.1f}s)")
        for loop in loops:
            console.print(f"  loop        {loop.name!r:20} bar {loop.start_bar} → {loop.end_bar}")


@app.command("show-cues")
def show_cues(
    audio_file: str = typer.Argument(..., help="Path to the audio file (as it appears in your Rekordbox library)."),
    db: Optional[str] = typer.Option(None, "--db", help="Path to Rekordbox master.db. Auto-detected at ~/Library/Pioneer/rekordbox/master.db on Mac."),
):
    """Show cue and loop points already stored in Rekordbox for a track."""
    try:
        track = get_track_by_path(audio_file, db_path=db)
    except FileNotFoundError as e:
        console.print(f"[red]✗ Database not found:[/red] {e}")
        raise typer.Exit(1)
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

    bar_map: dict[float, int] = {}
    if track.analysis_data_path:
        share_dir = os.path.join(os.path.dirname(db or DEFAULT_DB_PATH), "share")
        dat_path = os.path.join(share_dir, track.analysis_data_path.lstrip("/"))
        if os.path.exists(dat_path):
            try:
                from dj_cue_system.analysis.anlz import parse_beat_grid
                from dj_cue_system.analysis.bar_utils import timestamp_to_bar
                bg = parse_beat_grid(dat_path)
                for cue in track.existing_cues:
                    bar_map[cue.position_seconds] = timestamp_to_bar(cue.position_seconds, bg.downbeats)
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


@app.command("validate-config")
def validate_config(config: str = typer.Option(DEFAULT_CONFIG, "--config", help="Path to rules.yaml config file.")):
    """Validate rules.yaml and report errors."""
    try:
        cfg = load_config(config)
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
        console.print(
            f"[green]✓ Config is valid.[/green] "
            f"{len(cfg.rulesets)} rulesets, {len(cfg.playlists)} playlists."
        )
    except typer.Exit:
        raise
    except FileNotFoundError:
        console.print(f"[red]✗ Config file not found: {config}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]✗ Invalid config: {e}[/red]")
        raise typer.Exit(1)


@backup_app.command("create")
def backup_create(
    playlist: Optional[str] = typer.Option(None, "--playlist", help="Only back up tracks in this Rekordbox playlist. Omit to back up the full library."),
    output: Optional[str] = typer.Option(None, "--output", help="Path for the backup JSON file. Defaults to ~/.dj-cue/backups/<timestamp>.json."),
    db: Optional[str] = typer.Option(None, "--db", help="Path to Rekordbox master.db. Auto-detected at ~/Library/Pioneer/rekordbox/master.db on Mac."),
):
    """Backup cue points from master.db."""
    os.makedirs(DEFAULT_BACKUP_DIR, exist_ok=True)
    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    path = output or os.path.join(DEFAULT_BACKUP_DIR, f"{ts}.json")
    try:
        backup = create_backup(db_path=db, playlist_filter=playlist)
    except FileNotFoundError as e:
        console.print(f"[red]✗ Database not found:[/red] {e}")
        raise typer.Exit(1)
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
def backup_diff(
    file_a: str = typer.Argument(..., help="Path to the older backup JSON file."),
    file_b: str = typer.Argument(..., help="Path to the newer backup JSON file."),
):
    """Show what changed between two backups."""
    try:
        old = deserialize_backup(file_a)
        new = deserialize_backup(file_b)
    except FileNotFoundError as e:
        console.print(f"[red]✗ Backup file not found:[/red] {e}")
        raise typer.Exit(1)
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


@app.command()
def restore(
    backup_file: str = typer.Argument(..., help="Path to the backup JSON file to restore from."),
    output: str = typer.Option("./restored.xml", "--output", help="Path for the generated rekordbox.xml. Import in Rekordbox via File → Import → rekordbox xml."),
    tracks: list[str] = typer.Option([], "--tracks", help="Only restore cues for this audio file path. Repeatable. Omit to restore all tracks in the backup."),
):
    """Generate rekordbox.xml from a backup file."""
    try:
        backup = deserialize_backup(backup_file)
    except FileNotFoundError as e:
        console.print(f"[red]✗ Backup file not found:[/red] {e}")
        raise typer.Exit(1)
    writer = RekordboxXmlWriter(output)
    from dj_cue_system.writers.base import CuePoint, LoopPoint
    for bt in backup.tracks:
        if tracks and bt.path not in tracks:
            continue
        fake_track = _make_fake_track(bt.path, title=bt.title, artist=bt.artist)
        cues = [
            CuePoint(name=c.name, position_seconds=c.position_seconds or 0.0, bar=0, color=c.color)
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

    # Deduplicate by absolute path, preserving order
    seen: set[str] = set()
    deduped: list[tuple[str, str]] = []
    for p, t in track_pairs:
        abs_p = os.path.abspath(p)
        if abs_p not in seen:
            seen.add(abs_p)
            deduped.append((abs_p, t))
    track_pairs = deduped

    if not track_pairs:
        console.print("[yellow]No tracks specified. Use --path, --library, or --playlist.[/yellow]")
        raise typer.Exit(1)

    # Mark cached tracks as skipped up front; cache result to avoid double lookup
    initial_states: list[tuple[str, str]] = []  # (status, source)
    for path, _ in track_pairs:
        if not force:
            cached = stems_cache.load(path, hq=hq)
            expected_source = "demucs" if hq else "librosa"
            if cached is not None and cached[1] == expected_source:
                initial_states.append(("skipped", cached[1]))
                continue
        initial_states.append(("pending", ""))

    job = stems_jobs.create(track_pairs, hq=hq)
    for (path, _), (status, src) in zip(track_pairs, initial_states):
        if status == "skipped":
            stems_jobs.update_track(job, path, "skipped", source=src)

    pending_count = sum(1 for status, _ in initial_states if status == "pending")
    console.print(f"\nJob [bold]{job.id}[/bold]  ({pending_count} to process, {len(track_pairs) - pending_count} already cached)\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Starting…", total=pending_count)
        for (path, title), (status, _src) in zip(track_pairs, initial_states):
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
            progress.advance(task)

    done = sum(1 for t in job.tracks if t.status == "done")
    failed = sum(1 for t in job.tracks if t.status == "failed")
    skipped = sum(1 for t in job.tracks if t.status == "skipped")
    console.print(f"\n[green]Done.[/green]  {done} processed, {skipped} skipped (cached), {failed} failed")
    console.print(f"Run [bold]dj-cue stems status {job.id}[/bold] to review details.")


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
            return

    mode = "HQ/Demucs" if job.hq else "fast/librosa"
    console.print(f"\nJob [bold]{job.id}[/bold]  ({mode})")
    console.print(f"Created: {job.created_at[:19].replace('T', ' ')}\n")

    done = sum(1 for t in job.tracks if t.status == "done")
    failed = sum(1 for t in job.tracks if t.status == "failed")
    pending = sum(1 for t in job.tracks if t.status == "pending")
    skipped = sum(1 for t in job.tracks if t.status == "skipped")
    total = len(job.tracks)
    completed = done + skipped
    console.print(f"Progress: {completed}/{total}  |  {failed} failed  |  {pending} pending\n")

    for t in job.tracks:
        title = t.title or os.path.basename(t.path)
        if t.status == "done":
            console.print(f"  [green]✓[/green] {title:<40} ({t.source})")
        elif t.status == "skipped":
            console.print(f"  [dim]↷ {title:<40} (skipped — already cached)[/dim]")
        elif t.status == "failed":
            error_preview = t.error.splitlines()[0][:80] if t.error else ""
            console.print(f"  [red]✗[/red] {title:<40} {error_preview}")
        else:
            console.print(f"  [dim]· {title}[/dim]")


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

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

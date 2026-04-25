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

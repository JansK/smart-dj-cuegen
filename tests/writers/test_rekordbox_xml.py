import xml.etree.ElementTree as ET
import pytest
from unittest.mock import MagicMock
from dj_cue_system.writers.rekordbox_xml import RekordboxXmlWriter
from dj_cue_system.writers.base import CuePoint, LoopPoint


def _make_track():
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
    writer.write(track, cues, [])
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
    loops = [LoopPoint(name="Intro", start_seconds=0.0, end_seconds=32.0, start_bar=0, end_bar=16)]
    writer.write(track, [], loops)
    writer.finalize()

    tree = ET.parse(output)
    marks = tree.getroot().findall(".//POSITION_MARK")
    assert len(marks) == 1
    assert marks[0].get("Type") == "4"
    assert float(marks[0].get("Start")) == pytest.approx(0.0)
    assert float(marks[0].get("End")) == pytest.approx(32.0)
    assert marks[0].get("Num") == "-1"


def test_no_color_no_color_attr(tmp_path):
    output = tmp_path / "out.xml"
    writer = RekordboxXmlWriter(str(output))
    track = _make_track()
    cues = [CuePoint(name="X", position_seconds=1.0, bar=0, color=None)]
    writer.write(track, cues, [])
    writer.finalize()

    tree = ET.parse(output)
    marks = tree.getroot().findall(".//POSITION_MARK")
    assert marks[0].get("Color") is None


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

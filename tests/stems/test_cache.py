import pytest
import dj_cue_system.stems.cache as stems_cache
from dj_cue_system.analysis.models import StemOnsets


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(stems_cache, "_CACHE_DIR", tmp_path)


def test_load_miss():
    assert stems_cache.load("/no/such/track.mp3") is None


def test_load_miss_hq():
    assert stems_cache.load("/no/such/track.mp3", hq=True) is None


def test_save_and_load_demucs():
    onsets = StemOnsets(vocal=55.2, drum=4.1, bass=15.8, other=4.0)
    stems_cache.save("/music/track.mp3", onsets, "demucs")
    result = stems_cache.load("/music/track.mp3", hq=True)
    assert result is not None
    loaded_onsets, source = result
    assert source == "demucs"
    assert loaded_onsets.vocal == 55.2
    assert loaded_onsets.drum == 4.1
    assert loaded_onsets.bass == 15.8
    assert loaded_onsets.other == 4.0


def test_save_and_load_librosa():
    onsets = StemOnsets(vocal=1.0, drum=2.0, bass=3.0, other=4.0)
    stems_cache.save("/music/track.mp3", onsets, "librosa")
    result = stems_cache.load("/music/track.mp3", hq=False)
    assert result is not None
    loaded_onsets, source = result
    assert source == "librosa"
    assert loaded_onsets.vocal == 1.0


def test_both_slots_coexist():
    hq_onsets = StemOnsets(vocal=10.0)
    lq_onsets = StemOnsets(vocal=1.0)
    stems_cache.save("/music/track.mp3", hq_onsets, "demucs")
    stems_cache.save("/music/track.mp3", lq_onsets, "librosa")

    hq_result = stems_cache.load("/music/track.mp3", hq=True)
    assert hq_result is not None
    assert hq_result[0].vocal == 10.0
    assert hq_result[1] == "demucs"

    lq_result = stems_cache.load("/music/track.mp3", hq=False)
    assert lq_result is not None
    assert lq_result[0].vocal == 1.0
    assert lq_result[1] == "librosa"


def test_hq_requested_falls_back_to_lq():
    stems_cache.save("/music/track.mp3", StemOnsets(vocal=1.0), "librosa")
    result = stems_cache.load("/music/track.mp3", hq=True)
    assert result is not None
    onsets, source = result
    assert source == "librosa"
    assert onsets.vocal == 1.0


def test_lq_requested_falls_back_to_hq():
    stems_cache.save("/music/track.mp3", StemOnsets(vocal=9.0), "demucs")
    result = stems_cache.load("/music/track.mp3", hq=False)
    assert result is not None
    onsets, source = result
    assert source == "demucs"
    assert onsets.vocal == 9.0


def test_no_fallback_when_neither_slot_exists():
    assert stems_cache.load("/music/track.mp3", hq=True) is None
    assert stems_cache.load("/music/track.mp3", hq=False) is None


def test_save_and_load_with_none_values():
    onsets = StemOnsets(vocal=None, drum=None, bass=None, other=None)
    stems_cache.save("/music/silent.mp3", onsets, "librosa")
    result = stems_cache.load("/music/silent.mp3", hq=False)
    assert result is not None
    loaded_onsets, source = result
    assert source == "librosa"
    assert loaded_onsets.vocal is None


def test_hq_slot_overwritten_by_second_demucs_save():
    stems_cache.save("/music/track.mp3", StemOnsets(vocal=1.0), "demucs")
    stems_cache.save("/music/track.mp3", StemOnsets(vocal=2.0), "demucs")
    result = stems_cache.load("/music/track.mp3", hq=True)
    assert result is not None
    loaded, source = result
    assert loaded.vocal == 2.0
    assert source == "demucs"


def test_list_entries_empty():
    assert stems_cache.list_entries() == []


def test_list_entries_populated():
    stems_cache.save("/music/a.mp3", StemOnsets(vocal=1.0), "demucs")
    stems_cache.save("/music/b.mp3", StemOnsets(vocal=2.0), "librosa")
    entries = stems_cache.list_entries()
    assert len(entries) == 2
    paths = {e.audio_path for e in entries}
    assert "/music/a.mp3" in paths
    assert "/music/b.mp3" in paths


def test_list_entries_hq_field():
    stems_cache.save("/music/a.mp3", StemOnsets(vocal=1.0), "demucs")
    stems_cache.save("/music/a.mp3", StemOnsets(vocal=0.5), "librosa")
    entries = stems_cache.list_entries()
    assert len(entries) == 2
    by_hq = {e.hq: e for e in entries}
    assert by_hq[True].source == "demucs"
    assert by_hq[False].source == "librosa"


def test_clear_all():
    stems_cache.save("/music/a.mp3", StemOnsets(), "demucs")
    stems_cache.save("/music/a.mp3", StemOnsets(), "librosa")
    stems_cache.save("/music/b.mp3", StemOnsets(), "librosa")
    count = stems_cache.clear()
    assert count == 3
    assert stems_cache.load("/music/a.mp3") is None
    assert stems_cache.load("/music/b.mp3") is None


def test_clear_by_path_removes_both_slots():
    stems_cache.save("/music/a.mp3", StemOnsets(), "demucs")
    stems_cache.save("/music/a.mp3", StemOnsets(), "librosa")
    stems_cache.save("/music/b.mp3", StemOnsets(), "demucs")
    count = stems_cache.clear("/music/a.mp3")
    assert count == 2
    assert stems_cache.load("/music/a.mp3") is None
    assert stems_cache.load("/music/b.mp3") is not None


def test_clear_by_path_only_hq_exists():
    stems_cache.save("/music/a.mp3", StemOnsets(), "demucs")
    count = stems_cache.clear("/music/a.mp3")
    assert count == 1
    assert stems_cache.load("/music/a.mp3") is None


def test_clear_nonexistent_path():
    count = stems_cache.clear("/no/such/track.mp3")
    assert count == 0

import pytest
from dj_cue_system.analysis.bar_utils import timestamp_to_bar, bar_to_timestamp, snap_to_bar

DOWNBEATS = [0.0, 2.0, 4.0, 6.0, 8.0]  # 5 bars, 2s each


def test_timestamp_to_bar_exact():
    assert timestamp_to_bar(4.0, DOWNBEATS) == 2


def test_timestamp_to_bar_between():
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
    assert snap_to_bar(3.1, DOWNBEATS) == pytest.approx(4.0)
    assert snap_to_bar(2.9, DOWNBEATS) == pytest.approx(2.0)

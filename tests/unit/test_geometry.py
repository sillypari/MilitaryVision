from persistent_tracker.utils.geometry import (
    box_center,
    box_iou,
    clamp_box,
    outside_ratio,
)


def test_box_center_uses_xywh_coordinates() -> None:
    assert box_center((10, 20, 30, 40)) == (25.0, 40.0)


def test_iou_is_symmetric() -> None:
    left = (0, 0, 10, 10)
    right = (5, 5, 10, 10)
    assert box_iou(left, right) == box_iou(right, left)
    assert box_iou(left, right) == 25 / 175


def test_clamp_box_keeps_box_inside_frame() -> None:
    assert clamp_box((-10, -4, 30, 20), 100, 80) == (0, 0, 20, 16)


def test_outside_ratio_reports_partial_visibility() -> None:
    ratio = outside_ratio((-5, 0, 10, 10), 100, 100)
    assert ratio == 0.5


def test_outside_ratio_reports_fully_outside_box() -> None:
    assert outside_ratio((120, 20, 10, 10), 100, 100) == 1.0

from __future__ import annotations

from persistent_tracker.domain.models import BoundingBox


def clamp_box(box: BoundingBox, frame_width: int, frame_height: int) -> BoundingBox:
    x, y, width, height = box
    x1 = max(0, min(int(x), frame_width - 1))
    y1 = max(0, min(int(y), frame_height - 1))
    x2 = max(x1 + 1, min(int(x + width), frame_width))
    y2 = max(y1 + 1, min(int(y + height), frame_height))
    return x1, y1, x2 - x1, y2 - y1


def box_center(box: BoundingBox) -> tuple[float, float]:
    x, y, width, height = box
    return x + width / 2.0, y + height / 2.0


def box_area(box: BoundingBox) -> float:
    return float(max(0, box[2]) * max(0, box[3]))


def box_iou(left: BoundingBox, right: BoundingBox) -> float:
    lx, ly, lw, lh = left
    rx, ry, rw, rh = right
    intersection_left = max(lx, rx)
    intersection_top = max(ly, ry)
    intersection_right = min(lx + lw, rx + rw)
    intersection_bottom = min(ly + lh, ry + rh)
    intersection_width = max(0, intersection_right - intersection_left)
    intersection_height = max(0, intersection_bottom - intersection_top)
    intersection = intersection_width * intersection_height
    union = box_area(left) + box_area(right) - intersection
    return float(intersection / union) if union > 0 else 0.0


def outside_ratio(box: BoundingBox, frame_width: int, frame_height: int) -> float:
    original_area = box_area(box)
    if original_area <= 0:
        return 1.0
    x, y, width, height = box
    visible_width = max(0, min(x + width, frame_width) - max(x, 0))
    visible_height = max(0, min(y + height, frame_height) - max(y, 0))
    visible_area = float(visible_width * visible_height)
    return max(0.0, min(1.0, 1.0 - visible_area / original_area))


def normalized_distance(
    left: tuple[float, float],
    right: tuple[float, float],
    frame_width: int,
    frame_height: int,
) -> float:
    diagonal = max(1.0, (frame_width**2 + frame_height**2) ** 0.5)
    return (((left[0] - right[0]) ** 2 + (left[1] - right[1]) ** 2) ** 0.5) / diagonal


def interpolate_box(box: BoundingBox, center: tuple[float, float]) -> BoundingBox:
    _, _, width, height = box
    return (
        int(round(center[0] - width / 2.0)),
        int(round(center[1] - height / 2.0)),
        width,
        height,
    )

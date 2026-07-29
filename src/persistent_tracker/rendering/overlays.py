from __future__ import annotations

import cv2
import numpy as np

from persistent_tracker.domain.models import (
    BoundingBox,
    TrackingResult,
    TrackingState,
    TrajectoryPoint,
)

STATE_STYLE: dict[TrackingState, tuple[tuple[int, int, int], str]] = {
    TrackingState.IDLE: ((145, 153, 164), "NO TARGET"),
    TrackingState.SELECTING: ((225, 185, 75), "SELECTING"),
    TrackingState.INITIALIZING: ((225, 185, 75), "INITIALIZING"),
    TrackingState.LOCKED: ((124, 220, 108), "CONFIRMED"),
    TrackingState.OCCLUDED: ((70, 176, 245), "PREDICTED"),
    TrackingState.REACQUIRING: ((210, 128, 205), "UNVERIFIED"),
    TrackingState.LOST: ((96, 96, 235), "NO LOCATION - SEARCHING"),
}


def _draw_dashed_line(
    frame: np.ndarray,
    start: tuple[int, int],
    end: tuple[int, int],
    colour: tuple[int, int, int],
    thickness: int = 2,
    dash: int = 8,
) -> None:
    vector = np.array(end, dtype=float) - np.array(start, dtype=float)
    length = float(np.linalg.norm(vector))
    if length < 1.0:
        return
    direction = vector / length
    for offset in range(0, int(length), dash * 2):
        segment_start = np.array(start, dtype=float) + direction * offset
        segment_end = np.array(start, dtype=float) + direction * min(offset + dash, length)
        cv2.line(
            frame,
            tuple(segment_start.astype(int)),
            tuple(segment_end.astype(int)),
            colour,
            thickness,
            cv2.LINE_AA,
        )


def _draw_dashed_box(
    frame: np.ndarray,
    box: BoundingBox,
    colour: tuple[int, int, int],
) -> None:
    x, y, width, height = box
    corners = [
        ((x, y), (x + width, y)),
        ((x + width, y), (x + width, y + height)),
        ((x + width, y + height), (x, y + height)),
        ((x, y + height), (x, y)),
    ]
    for start, end in corners:
        _draw_dashed_line(frame, start, end, colour)


def _draw_trajectory(frame: np.ndarray, points: list[TrajectoryPoint]) -> None:
    for previous, current in zip(points, points[1:]):
        if current.segment_start:
            continue
        start = (int(round(previous.x)), int(round(previous.y)))
        end = (int(round(current.x)), int(round(current.y)))
        if previous.predicted or current.predicted:
            _draw_dashed_line(frame, start, end, (70, 176, 245), thickness=2, dash=5)
        else:
            cv2.line(frame, start, end, (124, 220, 108), 2, cv2.LINE_AA)


def _draw_label(
    frame: np.ndarray,
    text: str,
    anchor: tuple[int, int],
    colour: tuple[int, int, int],
) -> None:
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.52
    thickness = 1
    (width, height), _ = cv2.getTextSize(text, font, scale, thickness)
    x, y = anchor
    x = max(0, min(x, frame.shape[1] - width - 12))
    y = max(height + 10, min(y, frame.shape[0] - 4))
    cv2.rectangle(frame, (x, y - height - 9), (x + width + 10, y + 4), (18, 22, 29), -1)
    cv2.putText(
        frame,
        text,
        (x + 5, y - 3),
        font,
        scale,
        colour,
        thickness,
        cv2.LINE_AA,
    )


def render_tracking_overlay(result: TrackingResult, processing_fps: float) -> np.ndarray:
    frame = result.frame.copy()
    colour, state_text = STATE_STYLE[result.state]
    _draw_trajectory(frame, result.trajectory)

    if result.state == TrackingState.LOCKED and result.box is not None:
        x, y, width, height = result.box
        cv2.rectangle(frame, (x, y), (x + width, y + height), colour, 2, cv2.LINE_AA)
        _draw_label(
            frame,
            f"{state_text}  {result.confidence:.0%}",
            (x, y - 5),
            colour,
        )
    elif result.predicted_box is not None:
        _draw_dashed_box(frame, result.predicted_box, colour)
        x, y, _, _ = result.predicted_box
        _draw_label(frame, state_text, (x, y - 5), colour)

    if result.candidate_box is not None:
        _draw_dashed_box(frame, result.candidate_box, (210, 128, 205))
        x, y, _, _ = result.candidate_box
        _draw_label(frame, "CANDIDATE - NOT CONFIRMED", (x, y - 28), (210, 128, 205))

    header = frame.copy()
    cv2.rectangle(header, (0, 0), (frame.shape[1], 38), (12, 15, 21), -1)
    cv2.addWeighted(header, 0.86, frame, 0.14, 0, frame)
    cv2.putText(
        frame,
        f"STATE  {state_text}",
        (14, 25),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        colour,
        1,
        cv2.LINE_AA,
    )
    metrics = (
        f"CONF {result.confidence:.0%}   "
        f"ID {result.identity_confidence:.0%}   "
        f"FPS {processing_fps:.1f}"
    )
    metrics_width, _ = cv2.getTextSize(
        metrics,
        cv2.FONT_HERSHEY_SIMPLEX,
        0.48,
        1,
    )
    cv2.putText(
        frame,
        metrics,
        (max(14, frame.shape[1] - metrics_width[0] - 14), 25),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.48,
        (213, 218, 226),
        1,
        cv2.LINE_AA,
    )
    return frame

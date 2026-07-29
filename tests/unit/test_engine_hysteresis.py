from dataclasses import replace

import cv2
import numpy as np

from persistent_tracker.config import load_config
from persistent_tracker.domain.models import FrameMetadata
from persistent_tracker.tracking.engine import TrackingEngine
from persistent_tracker.utils.geometry import box_center


def metadata(frame_number: int) -> FrameMetadata:
    return FrameMetadata(
        frame_number=frame_number,
        timestamp=frame_number / 30.0,
        width=200,
        height=150,
        source_fps=30.0,
    )


def test_weak_continuity_is_bounded_instead_of_failing_one_frame() -> None:
    base_config = load_config()
    tracking_config = replace(
        base_config.tracking,
        locked_minimum=1.1,
        minimum_identity_confidence=1.1,
        minimum_tracking_quality=1.1,
        locked_exit_identity_confidence=0.0,
        locked_exit_tracking_quality=0.0,
        occlusion_threshold=0.0,
        weak_observation_grace_frames=2,
    )
    engine = TrackingEngine(replace(base_config, tracking=tracking_config))
    frame = np.random.default_rng(19).integers(
        0,
        256,
        (150, 200, 3),
        dtype=np.uint8,
    )
    box = (60, 45, 50, 40)
    engine.begin_selection(metadata(0))
    engine.initialize(frame, box, metadata(0))
    predicted_center = box_center(box)

    assert engine._accept_short_term_observation(
        frame,
        box,
        predicted_center,
        metadata(1),
    )
    assert engine._accept_short_term_observation(
        frame,
        box,
        predicted_center,
        metadata(2),
    )
    assert not engine._accept_short_term_observation(
        frame,
        box,
        predicted_center,
        metadata(3),
    )


def test_default_thresholds_bridge_camera_blur_and_recover() -> None:
    generator = np.random.default_rng(909)
    frame = generator.integers(0, 35, (150, 200, 3), dtype=np.uint8)
    target = generator.integers(40, 230, (60, 70, 3), dtype=np.uint8)
    cv2.rectangle(target, (4, 4), (65, 55), (220, 50, 210), 3)
    box = (65, 45, 70, 60)
    frame[45:105, 65:135] = target
    blurred = frame.copy()
    blurred[45:105, 65:135] = cv2.GaussianBlur(target, (9, 9), 0)

    engine = TrackingEngine(load_config())
    engine.begin_selection(metadata(0))
    engine.initialize(frame, box, metadata(0))
    predicted_center = box_center(box)

    for frame_number in range(1, 9):
        assert engine._accept_short_term_observation(
            blurred,
            box,
            predicted_center,
            metadata(frame_number),
        )

    assert engine._accept_short_term_observation(
        frame,
        box,
        predicted_center,
        metadata(9),
    )
    assert engine._weak_observation_frames == 0


def test_default_thresholds_reject_unrelated_replacement() -> None:
    generator = np.random.default_rng(919)
    frame = np.zeros((150, 200, 3), dtype=np.uint8)
    target = generator.integers(60, 230, (60, 70, 3), dtype=np.uint8)
    box = (65, 45, 70, 60)
    frame[45:105, 65:135] = target
    replacement = frame.copy()
    replacement[45:105, 65:135] = (10, 240, 10)

    engine = TrackingEngine(load_config())
    engine.begin_selection(metadata(0))
    engine.initialize(frame, box, metadata(0))

    assert not engine._accept_short_term_observation(
        replacement,
        box,
        box_center(box),
        metadata(1),
    )

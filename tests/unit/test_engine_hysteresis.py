from dataclasses import replace

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

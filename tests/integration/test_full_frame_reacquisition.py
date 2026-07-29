import cv2
import numpy as np

from persistent_tracker.config import load_config
from persistent_tracker.domain.models import FrameMetadata, TrackingState
from persistent_tracker.tracking.engine import TrackingEngine


def metadata(frame_number: int) -> FrameMetadata:
    return FrameMetadata(
        frame_number=frame_number,
        timestamp=frame_number / 30.0,
        width=640,
        height=360,
        source_fps=30.0,
    )


def test_target_can_reacquire_far_from_last_and_predicted_positions() -> None:
    generator = np.random.default_rng(77)
    background = generator.integers(0, 35, (360, 640, 3), dtype=np.uint8)
    target = generator.integers(45, 230, (70, 90, 3), dtype=np.uint8)
    initial = background.copy()
    initial[130:200, 60:150] = target
    reappeared = background.copy()
    reappeared[210:280, 470:560] = target

    engine = TrackingEngine(load_config())
    engine.begin_selection(metadata(0))
    engine.initialize(initial, (60, 130, 90, 70), metadata(0))
    engine.short_tracker.update = lambda _frame: (False, None)  # type: ignore[method-assign]

    results = [
        engine.update(reappeared, metadata(frame_number))
        for frame_number in range(1, 4)
    ]

    assert results[0].state == TrackingState.REACQUIRING
    assert results[0].candidate_box is not None
    assert results[0].candidate_box[0] > 400
    assert results[0].predicted_box is None
    assert results[-1].state == TrackingState.LOCKED
    assert results[-1].box is not None
    assert results[-1].box[0] > 400
    assert not any(point.predicted for point in engine.trajectory.points)


def test_changed_target_reacquires_in_opposite_quadrant() -> None:
    generator = np.random.default_rng(333)
    background = generator.integers(0, 30, (360, 640, 3), dtype=np.uint8)
    target = generator.integers(50, 225, (72, 92, 3), dtype=np.uint8)
    cv2.rectangle(target, (3, 3), (88, 68), (20, 220, 220), 3)
    cv2.line(target, (5, 60), (84, 10), (230, 40, 40), 4)
    initial = background.copy()
    initial[240:312, 500:592] = target

    changed_target = cv2.convertScaleAbs(target, alpha=0.92, beta=12)
    changed_target[20:38, 35:58] = background[55:73, 80:103]
    reappeared = background.copy()
    reappeared[35:107, 45:137] = changed_target

    engine = TrackingEngine(load_config())
    engine.begin_selection(metadata(0))
    engine.initialize(initial, (500, 240, 92, 72), metadata(0))
    engine.short_tracker.update = lambda _frame: (False, None)  # type: ignore[method-assign]

    results = [
        engine.update(reappeared, metadata(frame_number))
        for frame_number in range(1, 4)
    ]

    assert results[0].state == TrackingState.REACQUIRING
    assert results[0].candidate_box is not None
    assert results[0].candidate_box[0] < 100
    assert results[0].candidate_box[1] < 100
    assert results[-1].state == TrackingState.LOCKED
    assert results[-1].box is not None
    assert results[-1].box[0] < 100
    assert results[-1].box[1] < 100


def test_two_equally_plausible_full_frame_targets_are_rejected() -> None:
    generator = np.random.default_rng(358)
    background = generator.integers(0, 30, (360, 640, 3), dtype=np.uint8)
    target = generator.integers(50, 225, (72, 92, 3), dtype=np.uint8)
    initial = background.copy()
    initial[240:312, 500:592] = target
    ambiguous_scene = background.copy()
    ambiguous_scene[35:107, 45:137] = target
    ambiguous_scene[120:192, 260:352] = target

    engine = TrackingEngine(load_config())
    engine.begin_selection(metadata(0))
    identity = engine.initialize(initial, (500, 240, 92, 72), metadata(0))
    identity.missed_frames = 1

    matches, accepted = engine.candidate_matcher.find(
        ambiguous_scene,
        identity,
        (500, 240, 92, 72),
    )

    assert len(matches) >= 2
    assert accepted is None


def test_immediate_full_frame_search_does_not_extend_prediction_trail() -> None:
    generator = np.random.default_rng(91)
    initial = generator.integers(0, 256, (360, 640, 3), dtype=np.uint8)
    empty_scene = np.zeros_like(initial)
    engine = TrackingEngine(load_config())
    engine.begin_selection(metadata(0))
    engine.initialize(initial, (80, 100, 90, 70), metadata(0))
    engine.short_tracker.update = lambda _frame: (False, None)  # type: ignore[method-assign]

    result = engine.update(empty_scene, metadata(1))

    assert result.state == TrackingState.REACQUIRING
    assert result.predicted_box is None
    assert len(engine.trajectory.points) == 1
    assert not engine.trajectory.points[0].predicted


def test_scaled_full_frame_search_maps_candidate_to_processing_coordinates() -> None:
    generator = np.random.default_rng(118)
    background = generator.integers(0, 35, (720, 1280, 3), dtype=np.uint8)
    target = generator.integers(45, 230, (70, 90, 3), dtype=np.uint8)
    initial = background.copy()
    initial[140:210, 80:170] = target
    reappeared = background.copy()
    reappeared[430:500, 1010:1100] = target
    large_metadata = FrameMetadata(
        frame_number=0,
        timestamp=0.0,
        width=1280,
        height=720,
        source_fps=30.0,
    )

    engine = TrackingEngine(load_config())
    engine.begin_selection(large_metadata)
    identity = engine.initialize(initial, (80, 140, 90, 70), large_metadata)
    identity.missed_frames = 1

    _matches, accepted = engine.candidate_matcher.find(
        reappeared,
        identity,
        (80, 140, 90, 70),
    )

    assert engine.candidate_matcher.last_search_was_full_frame
    assert accepted is not None
    assert abs(accepted.box[0] - 1010) <= 2
    assert abs(accepted.box[1] - 430) <= 2

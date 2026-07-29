import cv2
import numpy as np

from persistent_tracker.config import load_config
from persistent_tracker.domain.models import FrameMetadata, TrackingState
from persistent_tracker.tracking.engine import TrackingEngine


def test_gradual_motion_rotation_and_lighting_remain_locked() -> None:
    generator = np.random.default_rng(41)
    background = generator.integers(0, 45, (300, 520, 3), dtype=np.uint8)
    target = generator.integers(40, 225, (56, 76, 3), dtype=np.uint8)
    cv2.rectangle(target, (2, 2), (73, 53), (240, 230, 50), 2)

    def frame_at(frame_number: int) -> np.ndarray:
        frame = background.copy()
        transform = cv2.getRotationMatrix2D(
            (38, 28),
            4.0 * np.sin(frame_number / 12.0),
            1.0 + 0.04 * np.sin(frame_number / 15.0),
        )
        transformed = cv2.warpAffine(
            target,
            transform,
            (76, 56),
            borderMode=cv2.BORDER_REFLECT,
        )
        brightness = int(14 * np.sin(frame_number / 10.0))
        adjustment = np.full_like(transformed, abs(brightness))
        transformed = (
            cv2.add(transformed, adjustment)
            if brightness >= 0
            else cv2.subtract(transformed, adjustment)
        )
        x = 70 + frame_number * 3
        y = 115 + int(15 * np.sin(frame_number / 8.0))
        frame[y : y + 56, x : x + 76] = transformed
        return frame

    engine = TrackingEngine(load_config())
    initial_metadata = FrameMetadata(0, 0.0, 520, 300, 30.0)
    engine.begin_selection(initial_metadata)
    engine.initialize(frame_at(0), (70, 115, 76, 56), initial_metadata)

    states: list[TrackingState] = []
    for frame_number in range(1, 36):
        result = engine.update(
            frame_at(frame_number),
            FrameMetadata(
                frame_number,
                frame_number / 30.0,
                520,
                300,
                30.0,
            ),
        )
        states.append(result.state)

    assert set(states) == {TrackingState.LOCKED}
    assert len(engine.identity.references) >= 3

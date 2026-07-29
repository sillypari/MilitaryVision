import time

import cv2
import numpy as np

from persistent_tracker.config import load_config
from persistent_tracker.domain.models import SourceState
from persistent_tracker.video.source import VideoSource


class FakeCapture:
    def __init__(self, frame: np.ndarray) -> None:
        self.frame = frame

    def read(self) -> tuple[bool, np.ndarray]:
        return True, self.frame.copy()


def test_horizontal_mirror_is_applied_before_tracking() -> None:
    frame = np.zeros((20, 30, 3), dtype=np.uint8)
    frame[:, :10] = (10, 20, 240)
    source = VideoSource(load_config().video)
    source.capture = FakeCapture(frame)  # type: ignore[assignment]
    source.state = SourceState.READY
    source.is_local_file = False
    source.source_fps = 30.0
    source._opened_monotonic = time.monotonic()
    source.mirror_horizontal = True

    packet = source.read()

    assert packet is not None
    mirrored, _metadata = packet
    assert np.array_equal(mirrored, cv2.flip(frame, 1))

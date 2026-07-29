import time

import cv2
import numpy as np
import pytest

from persistent_tracker.config import load_config
from persistent_tracker.domain.models import SourceState
from persistent_tracker.video.source import VideoSource, redact_source_credentials


class FakeCapture:
    def __init__(
        self,
        frame: np.ndarray,
        properties: dict[int, float] | None = None,
    ) -> None:
        self.frame = frame
        self.properties = properties or {}
        self.set_calls: list[tuple[int, float]] = []

    def read(self) -> tuple[bool, np.ndarray]:
        return True, self.frame.copy()

    def get(self, property_id: int) -> float:
        return self.properties.get(property_id, 0.0)

    def set(self, property_id: int, value: float) -> bool:
        self.set_calls.append((property_id, value))
        return True

    def isOpened(self) -> bool:
        return True

    def release(self) -> None:
        pass


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


def test_live_camera_requests_single_frame_capture_buffer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame = np.zeros((20, 30, 3), dtype=np.uint8)
    capture = FakeCapture(
        frame,
        {cv2.CAP_PROP_FPS: 30.0},
    )
    monkeypatch.setattr(cv2, "VideoCapture", lambda _source: capture)
    source = VideoSource(load_config().video)

    source.open(0)

    assert (cv2.CAP_PROP_BUFFERSIZE, 1) in capture.set_calls


def test_stream_credentials_are_redacted_for_logs() -> None:
    source = "rtsp://camera-user:camera-password@192.0.2.10:554/stream1"

    redacted = redact_source_credentials(source)

    assert redacted == "rtsp://<credentials-redacted>@192.0.2.10:554/stream1"
    assert "camera-user" not in redacted
    assert "camera-password" not in redacted


def test_local_video_exposes_frame_count_and_duration() -> None:
    frame = np.zeros((20, 30, 3), dtype=np.uint8)
    source = VideoSource(load_config().video)
    source.capture = FakeCapture(  # type: ignore[assignment]
        frame,
        {cv2.CAP_PROP_FRAME_COUNT: 300.0},
    )
    source.is_local_file = True
    source.source_fps = 30.0

    assert source.frame_count == 300
    assert source.duration_seconds == 10.0

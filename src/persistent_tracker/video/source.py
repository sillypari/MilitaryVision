from __future__ import annotations

import logging
import re
import time
from pathlib import Path

import cv2
import numpy as np

from persistent_tracker.config import VideoConfig
from persistent_tracker.domain.models import FrameMetadata, SourceState

LOGGER = logging.getLogger(__name__)
SOURCE_CREDENTIALS_PATTERN = re.compile(
    r"(?P<scheme>^[a-zA-Z][a-zA-Z0-9+.-]*://)[^/@\s]+@"
)


def redact_source_credentials(source: str | int) -> str:
    if isinstance(source, int):
        return str(source)
    return SOURCE_CREDENTIALS_PATTERN.sub(
        r"\g<scheme><credentials-redacted>@",
        source,
    )


class VideoSourceError(RuntimeError):
    pass


class VideoSource:
    def __init__(self, config: VideoConfig) -> None:
        self.config = config
        self.capture: cv2.VideoCapture | None = None
        self.state = SourceState.CLOSED
        self.source: str | int | None = None
        self.source_name = ""
        self.is_local_file = False
        self.source_fps = 0.0
        self.mirror_horizontal = False
        self._stream_frame_number = 0
        self._opened_monotonic = 0.0

    def open(self, source: str | int) -> None:
        self.close()
        self.state = SourceState.OPENING
        self.source = source
        self.is_local_file = isinstance(source, str) and Path(source).is_file()
        self.mirror_horizontal = (
            self.config.mirror_camera_default if isinstance(source, int) else False
        )
        self.source_name = str(source)
        capture = cv2.VideoCapture(source)
        if not capture.isOpened():
            capture.release()
            self.state = SourceState.ERROR
            safe_source = redact_source_credentials(source)
            raise VideoSourceError(f"Unable to open video source: {safe_source}")
        if not self.is_local_file:
            buffer_requested = bool(capture.set(cv2.CAP_PROP_BUFFERSIZE, 1))
            LOGGER.info(
                "Requested one-frame live capture buffer accepted=%s",
                buffer_requested,
            )
        self.capture = capture
        self.source_fps = float(capture.get(cv2.CAP_PROP_FPS))
        if not 1.0 <= self.source_fps <= 240.0:
            self.source_fps = 0.0
        self._stream_frame_number = 0
        self._opened_monotonic = time.monotonic()
        self.state = SourceState.READY
        LOGGER.info(
            "Opened source=%s fps=%.3f",
            redact_source_credentials(source),
            self.source_fps,
        )

    def read(self) -> tuple[np.ndarray, FrameMetadata] | None:
        if self.capture is None or self.state != SourceState.READY:
            return None
        success, frame = self.capture.read()
        if not success or frame is None:
            return None

        if self.is_local_file:
            frame_number = max(
                0,
                int(self.capture.get(cv2.CAP_PROP_POS_FRAMES)) - 1,
            )
            media_timestamp = self.capture.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
            timestamp = (
                float(media_timestamp)
                if media_timestamp > 0
                else frame_number / max(1.0, self.source_fps)
            )
        else:
            frame_number = self._stream_frame_number
            timestamp = time.monotonic() - self._opened_monotonic
            self._stream_frame_number += 1

        frame = self._resize_for_processing(frame)
        if self.mirror_horizontal:
            frame = cv2.flip(frame, 1)
        height, width = frame.shape[:2]
        return frame, FrameMetadata(
            frame_number=frame_number,
            timestamp=timestamp,
            width=width,
            height=height,
            source_fps=self.source_fps,
        )

    def seek_frame(self, frame_number: int) -> bool:
        if self.capture is None or not self.is_local_file:
            return False
        return bool(self.capture.set(cv2.CAP_PROP_POS_FRAMES, max(0, frame_number)))

    @property
    def current_frame_number(self) -> int:
        if self.capture is None:
            return 0
        if self.is_local_file:
            return max(0, int(self.capture.get(cv2.CAP_PROP_POS_FRAMES)) - 1)
        return self._stream_frame_number

    @property
    def frame_count(self) -> int:
        if self.capture is None or not self.is_local_file:
            return 0
        return max(0, int(self.capture.get(cv2.CAP_PROP_FRAME_COUNT)))

    @property
    def duration_seconds(self) -> float:
        if self.frame_count <= 0 or self.source_fps <= 0.0:
            return 0.0
        return self.frame_count / self.source_fps

    @property
    def resolution(self) -> tuple[int, int]:
        if self.capture is None:
            return 0, 0
        return (
            int(self.capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
            int(self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        )

    def close(self) -> None:
        if self.capture is not None:
            self.capture.release()
        self.capture = None
        self.state = SourceState.CLOSED

    def _resize_for_processing(self, frame: np.ndarray) -> np.ndarray:
        height, width = frame.shape[:2]
        scale = min(
            1.0,
            self.config.processing_width / max(1, width),
            self.config.processing_height / max(1, height),
        )
        if scale >= 1.0:
            return frame
        return cv2.resize(
            frame,
            (int(round(width * scale)), int(round(height * scale))),
            interpolation=cv2.INTER_AREA,
        )

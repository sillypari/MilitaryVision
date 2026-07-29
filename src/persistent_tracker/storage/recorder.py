from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


class AnnotatedVideoRecorder:
    def __init__(self) -> None:
        self._writer: cv2.VideoWriter | None = None
        self.path: Path | None = None

    @property
    def active(self) -> bool:
        return self._writer is not None

    def start(
        self,
        path: str | Path,
        *,
        width: int,
        height: int,
        fps: float,
        codec: str,
    ) -> None:
        self.stop()
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fourcc = cv2.VideoWriter_fourcc(*codec)
        writer = cv2.VideoWriter(
            str(output_path),
            fourcc,
            max(1.0, fps),
            (width, height),
        )
        if not writer.isOpened():
            writer.release()
            raise RuntimeError(f"Unable to create annotated video: {output_path}")
        self._writer = writer
        self.path = output_path

    def write(self, frame: np.ndarray) -> None:
        if self._writer is not None:
            self._writer.write(frame)

    def stop(self) -> None:
        if self._writer is not None:
            self._writer.release()
        self._writer = None

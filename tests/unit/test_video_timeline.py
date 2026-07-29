import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import cv2
import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from persistent_tracker.config import load_config
from persistent_tracker.domain.models import TrackingState
from persistent_tracker.ui.main_window import MainWindow


def create_test_video(path: Path) -> None:
    writer = cv2.VideoWriter(
        str(path),
        cv2.VideoWriter_fourcc(*"MJPG"),
        10.0,
        (96, 64),
    )
    if not writer.isOpened():
        pytest.skip("MJPG test video writer is unavailable")
    for frame_number in range(6):
        frame = np.full(
            (64, 96, 3),
            frame_number * 30,
            dtype=np.uint8,
        )
        cv2.rectangle(
            frame,
            (10 + frame_number, 20),
            (35 + frame_number, 45),
            (40, 180, 230),
            -1,
        )
        writer.write(frame)
    writer.release()


def test_local_video_timeline_seeks_and_clears_temporal_state(
    tmp_path: Path,
) -> None:
    application = QApplication.instance() or QApplication([])
    video_path = tmp_path / "timeline.avi"
    create_test_video(video_path)
    window = MainWindow(load_config())

    window._open_source(str(video_path))

    assert window.timeline_slider.isEnabled()
    assert window.timeline_slider.minimum() == 0
    assert window.timeline_slider.maximum() == 5
    assert window.current_metadata is not None
    window.engine.begin_selection(window.current_metadata)
    assert window.engine.state == TrackingState.SELECTING

    window._seek_to_frame(3, resume_playback=False)

    assert window.current_metadata is not None
    assert window.current_metadata.frame_number == 3
    assert window.timeline_slider.value() == 3
    assert window.engine.state == TrackingState.IDLE
    assert "Tracking cleared" in window.selection_notice.text()
    window.close()
    application.processEvents()

from __future__ import annotations

import logging
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from persistent_tracker.config import (
    AppConfig,
    default_config_path,
    project_root,
    save_config,
)
from persistent_tracker.domain.models import (
    BoundingBox,
    FrameMetadata,
    PlaybackState,
    TrackingResult,
    TrackingState,
)
from persistent_tracker.rendering import render_tracking_overlay
from persistent_tracker.storage import AnnotatedVideoRecorder, export_csv, export_json
from persistent_tracker.tracking import TrackingEngine
from persistent_tracker.ui.video_widget import VideoWidget
from persistent_tracker.ui.settings_dialog import SettingsDialog
from persistent_tracker.video import VideoSource, VideoSourceError

LOGGER = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self.config = config
        self.engine = TrackingEngine(config)
        self.source = VideoSource(config.video)
        self.recorder = AnnotatedVideoRecorder()
        self.playback_state = PlaybackState.STOPPED
        self.current_frame: np.ndarray | None = None
        self.current_annotated_frame: np.ndarray | None = None
        self.current_metadata: FrameMetadata | None = None
        self.current_result: TrackingResult | None = None
        self.pending_selection: BoundingBox | None = None
        self.processing_fps = 0.0
        self._last_process_monotonic: float | None = None

        self.setWindowTitle(config.application.name)
        self.resize(1280, 780)
        self.setMinimumSize(960, 640)
        self._build_ui()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._consume_next_frame)
        self._update_controls()
        self._update_status()

    def _build_ui(self) -> None:
        central = QWidget()
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(12, 12, 12, 8)
        root_layout.setSpacing(10)

        header = QFrame()
        header.setObjectName("header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 10, 16, 10)
        titles = QVBoxLayout()
        title = QLabel("MilitaryVision")
        title.setObjectName("title")
        subtitle = QLabel("Identity-first single-object tracking")
        subtitle.setObjectName("subtitle")
        titles.addWidget(title)
        titles.addWidget(subtitle)
        header_layout.addLayout(titles)
        header_layout.addStretch()
        self.state_badge = QLabel("NO TARGET")
        self.state_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.state_badge.setMinimumWidth(220)
        self.state_badge.setMinimumHeight(34)
        header_layout.addWidget(self.state_badge)
        root_layout.addWidget(header)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.video_widget = VideoWidget()
        self.video_widget.selection_changed.connect(self._selection_changed)
        splitter.addWidget(self.video_widget)
        splitter.addWidget(self._build_status_panel())
        splitter.setStretchFactor(0, 1)
        splitter.setSizes([940, 280])
        root_layout.addWidget(splitter, 1)

        root_layout.addWidget(self._build_controls())
        self.setCentralWidget(central)
        self.statusBar().showMessage("Open a video or camera to begin")

    def _build_status_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("panel")
        panel.setMinimumWidth(260)
        panel.setMaximumWidth(330)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        section = QLabel("TRACKING STATUS")
        section.setObjectName("section")
        layout.addWidget(section)

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(11)
        self.metrics: dict[str, QLabel] = {}
        rows = [
            ("state", "State"),
            ("confidence", "Confidence"),
            ("identity", "Identity confidence"),
            ("quality", "Tracking quality"),
            ("position", "Position"),
            ("velocity", "Velocity"),
            ("missed", "Missed frames"),
            ("path", "Path length"),
            ("processing_fps", "Processing FPS"),
            ("source_fps", "Source FPS"),
            ("resolution", "Resolution"),
            ("device", "Device"),
            ("identity_id", "Internal identity"),
            ("references", "References"),
            ("model", "Tracker"),
        ]
        for row, (key, name) in enumerate(rows):
            label = QLabel(name)
            label.setObjectName("metricName")
            value = QLabel("--")
            value.setObjectName("metricValue")
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            grid.addWidget(label, row, 0)
            grid.addWidget(value, row, 1)
            self.metrics[key] = value
        layout.addLayout(grid)
        layout.addStretch()

        note = QLabel(
            "Predicted and unverified positions are never displayed as confirmed."
        )
        note.setObjectName("subtitle")
        note.setWordWrap(True)
        layout.addWidget(note)
        return panel

    def _build_controls(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("controls")
        outer = QVBoxLayout(frame)
        outer.setContentsMargins(12, 10, 12, 10)
        outer.setSpacing(8)

        source_row = QHBoxLayout()
        self.open_video_button = self._button("Open video", self._open_video)
        self.open_camera_button = self._button("Open camera", self._open_camera)
        self.open_stream_button = self._button("Open stream", self._open_stream)
        self.mirror_button = self._button("Mirror: Off", self._toggle_mirror)
        self.settings_button = self._button("Settings", self._open_settings)
        self.play_button = self._button("Play", self._toggle_playback, "primary")
        self.step_back_button = self._button("Step backward", self._step_backward)
        self.step_button = self._button("Step forward", self._step_forward)
        for button in [
            self.open_video_button,
            self.open_camera_button,
            self.open_stream_button,
            self.mirror_button,
            self.settings_button,
            self.play_button,
            self.step_back_button,
            self.step_button,
        ]:
            source_row.addWidget(button)
        source_row.addStretch()
        outer.addLayout(source_row)

        tracking_row = QHBoxLayout()
        self.select_button = self._button("Select target", self._begin_selection)
        self.confirm_button = self._button(
            "Confirm selected box",
            self._confirm_selection,
            "primary",
        )
        self.cancel_button = self._button("Cancel selection", self._cancel_selection)
        self.clear_button = self._button("Clear target", self._clear_target, "danger")
        self.csv_button = self._button("Export CSV", self._export_csv)
        self.json_button = self._button("Export JSON", self._export_json)
        self.screenshot_button = self._button("Take screenshot", self._take_screenshot)
        self.record_button = self._button("Start recording", self._toggle_recording)
        for button in [
            self.select_button,
            self.confirm_button,
            self.cancel_button,
            self.clear_button,
            self.csv_button,
            self.json_button,
            self.screenshot_button,
            self.record_button,
        ]:
            tracking_row.addWidget(button)
        tracking_row.addStretch()
        outer.addLayout(tracking_row)
        self.selection_notice = QLabel(
            "Selection inactive. Select a target to draw a box."
        )
        self.selection_notice.setObjectName("subtitle")
        outer.addWidget(self.selection_notice)
        return frame

    @staticmethod
    def _button(
        text: str,
        callback: object,
        object_name: str | None = None,
    ) -> QPushButton:
        button = QPushButton(text)
        if object_name:
            button.setObjectName(object_name)
        button.clicked.connect(callback)
        return button

    def _open_video(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open video",
            str(Path.home()),
            "Video files (*.mp4 *.mkv *.avi *.mov *.m4v);;All files (*)",
        )
        if path:
            self._open_source(path)

    def _open_camera(self) -> None:
        camera_index, accepted = QInputDialog.getInt(
            self,
            "Open camera",
            "Camera index",
            self.config.video.default_camera_index,
            0,
            32,
        )
        if accepted:
            self._open_source(camera_index)

    def _open_stream(self) -> None:
        url, accepted = QInputDialog.getText(
            self,
            "Open stream",
            "RTSP, HTTP, or IP camera URL",
        )
        if accepted and url.strip():
            self._open_source(url.strip())

    def _open_source(self, source: str | int) -> None:
        try:
            self._stop_recording()
            self.source.open(source)
            self.engine = TrackingEngine(self.config)
            self.pending_selection = None
            self.video_widget.set_selection_enabled(False)
            self.selection_notice.setText(
                "Selection inactive. Select a target to draw a box."
            )
            self.selection_notice.setStyleSheet("color: #8e99aa;")
            self.playback_state = PlaybackState.PAUSED
            self._consume_next_frame()
            self._update_mirror_button()
            if self.source.is_local_file:
                self._pause()
                self.statusBar().showMessage(
                    f"Opened {source}; press Play when ready"
                )
            else:
                self._play()
                self.statusBar().showMessage(f"Live source active: {source}")
        except VideoSourceError as error:
            LOGGER.exception("Unable to open source")
            QMessageBox.critical(self, "Source error", str(error))
        self._update_controls()

    def _consume_next_frame(self) -> None:
        started = time.perf_counter()
        packet = self.source.read()
        if packet is None:
            if self.source.is_local_file:
                self.playback_state = PlaybackState.END_OF_STREAM
                self.timer.stop()
                self.statusBar().showMessage("End of video")
            else:
                self.statusBar().showMessage("Frame unavailable")
            self._update_controls()
            return

        frame, metadata = packet
        self.current_frame = frame
        self.current_metadata = metadata
        try:
            result = self.engine.update(frame, metadata)
        except Exception as error:
            LOGGER.exception("Tracking update failed")
            self._pause()
            QMessageBox.critical(self, "Tracking error", str(error))
            return

        elapsed = max(1e-6, time.perf_counter() - started)
        instantaneous_fps = 1.0 / elapsed
        self.processing_fps = (
            instantaneous_fps
            if self.processing_fps == 0
            else self.processing_fps * 0.85 + instantaneous_fps * 0.15
        )
        annotated = render_tracking_overlay(result, self.processing_fps)
        self.current_result = result
        self.current_annotated_frame = annotated
        self.video_widget.set_frame(annotated)
        if self.recorder.active:
            self.recorder.write(annotated)
        self._update_status()
        self._update_controls()

    def _toggle_playback(self) -> None:
        if self.playback_state == PlaybackState.PLAYING:
            self._pause()
        else:
            self._play()

    def _open_settings(self) -> None:
        was_playing = self.playback_state == PlaybackState.PLAYING
        self._pause()
        dialog = SettingsDialog(self.config, self)
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        if accepted and dialog.result_config is not None:
            try:
                save_config(dialog.result_config, default_config_path())
            except Exception as error:
                LOGGER.exception("Unable to save settings")
                QMessageBox.critical(self, "Settings error", str(error))
            else:
                self._stop_recording()
                self.config = dialog.result_config
                self.source.config = self.config.video
                self.engine = TrackingEngine(self.config)
                self.pending_selection = None
                self.video_widget.set_selection_enabled(False)
                self.selection_notice.setText(
                    "Settings applied. Select the target again to create a new identity."
                )
                self.selection_notice.setStyleSheet("color: #f5b046;")
                if self.current_frame is not None and self.current_metadata is not None:
                    result = self.engine.update(
                        self.current_frame,
                        self.current_metadata,
                    )
                    self.current_result = result
                    self.current_annotated_frame = render_tracking_overlay(
                        result,
                        self.processing_fps,
                    )
                    self.video_widget.set_frame(self.current_annotated_frame)
                self.statusBar().showMessage(
                    "Settings saved; active target state was reset"
                )
                self._update_status()
                self._update_controls()
        if was_playing:
            self._play()

    def _toggle_mirror(self) -> None:
        if self.source.capture is None:
            return
        if self.current_metadata is not None and self.engine.state != TrackingState.IDLE:
            self.engine.clear(self.current_metadata)
            self.pending_selection = None
            self.video_widget.set_selection_enabled(False)
            self.selection_notice.setText(
                "Target cleared because mirror mode changed the frame coordinates."
            )
            self.selection_notice.setStyleSheet("color: #f5b046;")
        self.source.mirror_horizontal = not self.source.mirror_horizontal
        self._update_mirror_button()
        self.statusBar().showMessage(
            "Horizontal mirror enabled"
            if self.source.mirror_horizontal
            else "Horizontal mirror disabled"
        )

    def _update_mirror_button(self) -> None:
        self.mirror_button.setText(
            "Mirror: On" if self.source.mirror_horizontal else "Mirror: Off"
        )

    def _play(self) -> None:
        if self.source.capture is None:
            return
        self.playback_state = PlaybackState.PLAYING
        fps = self.source.source_fps or self.config.export.default_fps
        self.timer.start(max(1, int(round(1000.0 / fps))))
        self.play_button.setText("Pause")
        self._update_controls()

    def _pause(self) -> None:
        self.timer.stop()
        if self.source.capture is not None:
            self.playback_state = PlaybackState.PAUSED
        else:
            self.playback_state = PlaybackState.STOPPED
        self.play_button.setText("Play")
        self._update_controls()

    def _step_forward(self) -> None:
        if self.source.capture is None:
            return
        self._pause()
        self._consume_next_frame()

    def _step_backward(self) -> None:
        if not self.source.is_local_file or self.current_metadata is None:
            return
        self._pause()
        if self.engine.state != TrackingState.IDLE:
            self.engine.clear(self.current_metadata)
            self.statusBar().showMessage(
                "Tracking cleared because reverse seeking invalidates temporal state"
            )
        target_frame = max(0, self.source.current_frame_number - 1)
        if self.source.seek_frame(target_frame):
            self._consume_next_frame()

    def _begin_selection(self) -> None:
        if self.current_metadata is None:
            return
        self._pause()
        try:
            self.engine.begin_selection(self.current_metadata)
        except Exception as error:
            QMessageBox.warning(self, "Selection", str(error))
            return
        self.pending_selection = None
        self.video_widget.clear_selection()
        self.video_widget.set_selection_enabled(True)
        self.selection_notice.setText(
            "Selection active: drag a tight box around the target."
        )
        self.selection_notice.setStyleSheet("color: #4fc3db;")
        self.statusBar().showMessage("Drag a tight box around the target")
        self._update_status()
        self._update_controls()

    def _selection_changed(self, box: BoundingBox) -> None:
        self.pending_selection = box
        self.selection_notice.setText(
            f"Selection ready: {box[2]} x {box[3]} pixels. "
            "Select Confirm selected box to save it."
        )
        self.selection_notice.setStyleSheet("color: #6edc7c; font-weight: 600;")
        self.statusBar().showMessage(
            f"Selection {box[2]} x {box[3]} pixels captured; confirm or redraw"
        )
        self._update_controls()

    def _confirm_selection(self) -> None:
        if (
            self.current_frame is None
            or self.current_metadata is None
            or self.pending_selection is None
        ):
            return
        try:
            identity = self.engine.initialize(
                self.current_frame,
                self.pending_selection,
                self.current_metadata,
            )
            result = self.engine.update(self.current_frame, self.current_metadata)
            result.box = identity.last_box
            self.current_result = result
            self.current_annotated_frame = render_tracking_overlay(
                result,
                self.processing_fps,
            )
            self.video_widget.set_frame(self.current_annotated_frame)
            self.video_widget.set_selection_enabled(False)
            self.pending_selection = None
            self.selection_notice.setText(
                "Target confirmed and saved. Press Play to continue tracking."
            )
            self.selection_notice.setStyleSheet("color: #6edc7c;")
            self.statusBar().showMessage("Target identity confirmed and saved")
        except Exception as error:
            LOGGER.exception("Target initialization failed")
            self.pending_selection = None
            self.video_widget.set_selection_enabled(False)
            self.selection_notice.setText(
                "Target initialization failed. Select the target again."
            )
            self.selection_notice.setStyleSheet("color: #eb6060; font-weight: 600;")
            QMessageBox.critical(self, "Initialization error", str(error))
        self._update_status()
        self._update_controls()

    def _cancel_selection(self) -> None:
        if self.current_metadata is None:
            return
        self.engine.cancel_selection(self.current_metadata)
        self.pending_selection = None
        self.video_widget.set_selection_enabled(False)
        self.selection_notice.setText(
            "Selection cancelled. No target identity was saved."
        )
        self.selection_notice.setStyleSheet("color: #8e99aa;")
        self.statusBar().showMessage("Selection cancelled")
        self._update_status()
        self._update_controls()

    def _clear_target(self) -> None:
        if self.current_metadata is None:
            return
        self.engine.clear(self.current_metadata)
        self.pending_selection = None
        self.video_widget.set_selection_enabled(False)
        self.selection_notice.setText(
            "Target cleared. Select a new target when ready."
        )
        self.selection_notice.setStyleSheet("color: #8e99aa;")
        if self.current_frame is not None:
            result = self.engine.update(self.current_frame, self.current_metadata)
            self.current_result = result
            self.current_annotated_frame = render_tracking_overlay(
                result,
                self.processing_fps,
            )
            self.video_widget.set_frame(self.current_annotated_frame)
        self.statusBar().showMessage("Target cleared")
        self._update_status()
        self._update_controls()

    def _export_csv(self) -> None:
        if not self.engine.trajectory.points:
            return
        default = self._default_output_path("sessions", "trajectory", ".csv")
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export trajectory",
            str(default),
            "CSV files (*.csv)",
        )
        if path:
            export_csv(path, self.engine.trajectory.points)
            self.statusBar().showMessage(f"Trajectory exported to {path}")

    def _export_json(self) -> None:
        if self.source.source is None:
            return
        default = self._default_output_path("sessions", "session", ".json")
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export session",
            str(default),
            "JSON files (*.json)",
        )
        if not path:
            return
        resolution = (
            (self.current_metadata.width, self.current_metadata.height)
            if self.current_metadata
            else (0, 0)
        )
        statistics = (
            dict(self.current_result.diagnostics) if self.current_result else {}
        )
        statistics["processing_fps"] = self.processing_fps
        export_json(
            path,
            source=str(self.source.source),
            resolution=resolution,
            source_fps=self.source.source_fps,
            config=self.config,
            identity=self.engine.identity,
            points=self.engine.trajectory.points,
            transitions=self.engine.state_machine.transitions,
            statistics=statistics,
        )
        self.statusBar().showMessage(f"Session exported to {path}")

    def _take_screenshot(self) -> None:
        if self.current_annotated_frame is None:
            return
        default = self._default_output_path("screenshots", "frame", ".png")
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save screenshot",
            str(default),
            "PNG image (*.png)",
        )
        if path:
            if not cv2.imwrite(path, self.current_annotated_frame):
                QMessageBox.critical(self, "Screenshot error", "Unable to write image")
                return
            self.statusBar().showMessage(f"Screenshot saved to {path}")

    def _toggle_recording(self) -> None:
        if self.recorder.active:
            self._stop_recording()
            return
        if self.current_annotated_frame is None:
            return
        default = self._default_output_path("recordings", "annotated", ".mp4")
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Record annotated video",
            str(default),
            "MP4 video (*.mp4)",
        )
        if not path:
            return
        height, width = self.current_annotated_frame.shape[:2]
        try:
            self.recorder.start(
                path,
                width=width,
                height=height,
                fps=self.source.source_fps or self.config.export.default_fps,
                codec=self.config.export.video_codec,
            )
            self.record_button.setText("Stop recording")
            self.statusBar().showMessage(f"Recording to {path}")
        except Exception as error:
            QMessageBox.critical(self, "Recording error", str(error))

    def _stop_recording(self) -> None:
        if self.recorder.active:
            path = self.recorder.path
            self.recorder.stop()
            self.statusBar().showMessage(f"Recording saved to {path}")
        self.record_button.setText("Start recording")

    def _default_output_path(self, folder: str, stem: str, suffix: str) -> Path:
        directory = project_root() / "output" / folder
        directory.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return directory / f"{stem}_{timestamp}{suffix}"

    def _update_controls(self) -> None:
        has_source = self.source.capture is not None
        has_frame = self.current_frame is not None
        selecting = self.engine.state == TrackingState.SELECTING
        has_target = self.engine.identity is not None
        has_points = bool(self.engine.trajectory.points)

        self.play_button.setEnabled(has_source)
        self.mirror_button.setEnabled(has_source)
        self.step_button.setEnabled(has_source)
        self.step_back_button.setEnabled(has_source and self.source.is_local_file)
        self.select_button.setEnabled(has_frame and not selecting)
        self.confirm_button.setEnabled(selecting and self.pending_selection is not None)
        self.cancel_button.setEnabled(selecting)
        self.clear_button.setEnabled(has_target or selecting)
        self.csv_button.setEnabled(has_points)
        self.json_button.setEnabled(has_source)
        self.screenshot_button.setEnabled(self.current_annotated_frame is not None)
        self.record_button.setEnabled(self.current_annotated_frame is not None)

    def _update_status(self) -> None:
        result = self.current_result
        identity = self.engine.identity
        state = self.engine.state
        labels = {
            TrackingState.IDLE: ("NO TARGET", "#8e99aa"),
            TrackingState.SELECTING: ("SELECTING", "#4fc3db"),
            TrackingState.INITIALIZING: ("INITIALIZING", "#4fc3db"),
            TrackingState.LOCKED: ("CONFIRMED", "#6edc7c"),
            TrackingState.OCCLUDED: ("PREDICTED", "#f5b046"),
            TrackingState.REACQUIRING: ("UNVERIFIED", "#cd80d2"),
            TrackingState.LOST: ("NO LOCATION - SEARCHING", "#eb6060"),
        }
        label, colour = labels[state]
        self.state_badge.setText(label)
        self.state_badge.setStyleSheet(
            f"background-color: #171d27; color: {colour}; "
            f"border: 1px solid {colour}; border-radius: 5px; font-weight: 600;"
        )

        box = result.box if result else None
        if box is None and result is not None:
            box = result.predicted_box
        center = (
            (box[0] + box[2] / 2.0, box[1] + box[3] / 2.0)
            if box
            else None
        )
        self.metrics["state"].setText(state.value.upper())
        self.metrics["confidence"].setText(
            f"{(result.confidence if result else 0.0):.0%}"
        )
        self.metrics["identity"].setText(
            f"{(result.identity_confidence if result else 0.0):.0%}"
        )
        self.metrics["quality"].setText(
            f"{(result.tracking_quality if result else 0.0):.0%}"
        )
        self.metrics["position"].setText(
            f"{center[0]:.0f}, {center[1]:.0f}" if center else "--"
        )
        velocity = result.velocity if result else (0.0, 0.0)
        self.metrics["velocity"].setText(f"{velocity[0]:.1f}, {velocity[1]:.1f} px/s")
        self.metrics["missed"].setText(str(result.missed_frames if result else 0))
        path_length = (
            float(result.diagnostics.get("path_length_pixels", 0.0)) if result else 0.0
        )
        self.metrics["path"].setText(f"{path_length:.1f} px")
        self.metrics["processing_fps"].setText(f"{self.processing_fps:.1f}")
        self.metrics["source_fps"].setText(f"{self.source.source_fps:.1f}")
        self.metrics["resolution"].setText(
            f"{self.current_metadata.width} x {self.current_metadata.height}"
            if self.current_metadata
            else "--"
        )
        self.metrics["device"].setText("CPU")
        self.metrics["identity_id"].setText(
            identity.internal_id[:8] if identity else "--"
        )
        self.metrics["references"].setText(
            str(len(identity.references)) if identity else "0"
        )
        tracker_name = self.config.tracking.preferred_tracker
        if tracker_name.upper() == "CSRT":
            tracker_name = f"{tracker_name} {self.config.tracking.csrt_profile.title()}"
        self.metrics["model"].setText(tracker_name)

    def closeEvent(self, event: object) -> None:
        self.timer.stop()
        self._stop_recording()
        self.source.close()
        event.accept()

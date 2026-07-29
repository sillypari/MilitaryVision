from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from persistent_tracker.config import (
    AppConfig,
    config_from_mapping,
    factory_config_path,
    load_config,
    project_root,
    save_config,
    validate_config,
)


@dataclass(frozen=True, slots=True)
class FieldSpec:
    path: str
    label: str
    kind: str
    minimum: float = 0.0
    maximum: float = 1.0
    step: float = 0.01
    decimals: int = 2
    choices: tuple[str, ...] = ()
    tooltip: str = ""


def score(path: str, label: str, tooltip: str = "") -> FieldSpec:
    return FieldSpec(path, label, "float", 0.0, 1.0, 0.01, 2, tooltip=tooltip)


SETTING_DIRECTION_HELP: dict[str, str] = {
    "video.processing_width": (
        "Lower: faster processing with less small-target detail. "
        "Higher: more detail with greater CPU cost."
    ),
    "video.processing_height": (
        "Lower: faster processing with less small-target detail. "
        "Higher: more detail with greater CPU cost."
    ),
    "video.reconnect_attempts": (
        "Reserved for the planned stream-reconnection worker; it does not yet "
        "change MVP behavior."
    ),
    "video.default_camera_index": (
        "Selects which numbered local camera opens by default."
    ),
    "video.mirror_camera_default": (
        "Enabled mirrors local cameras like a selfie view. It does not mirror files "
        "or network streams."
    ),
    "tracking.preferred_tracker": (
        "CSRT is the robust default. KCF is usually faster but weaker on scale "
        "changes. MIL is retained for compatibility testing."
    ),
    "tracking.csrt_profile": (
        "Accurate uses more CPU. Balanced reduces cost while retaining scale and "
        "segmentation signals. Fast trades additional robustness for speed."
    ),
    "tracking.locked_minimum": (
        "Lower: keeps CONFIRMED with weaker combined evidence. "
        "Higher: drops uncertain locks sooner."
    ),
    "tracking.minimum_identity_confidence": (
        "Lower: accepts larger appearance changes but increases identity-switch risk. "
        "Higher: requires a closer identity match."
    ),
    "tracking.minimum_tracking_quality": (
        "Lower: tolerates less consistent motion and visibility. "
        "Higher: requires stronger tracker and motion agreement."
    ),
    "tracking.locked_exit_identity_confidence": (
        "Lower: remains locked through weaker appearance evidence. "
        "Higher: enters identity search sooner."
    ),
    "tracking.locked_exit_tracking_quality": (
        "Lower: tolerates abrupt motion and blur longer. "
        "Higher: rejects unstable tracking sooner."
    ),
    "tracking.weak_observation_grace_frames": (
        "Lower: starts reacquisition sooner. Higher: bridges weak frames longer, "
        "with greater drift risk. Weak frames never update identity memory."
    ),
    "tracking.appearance_override_identity_confidence": (
        "Lower: the fast-jink override accepts weaker identity evidence. "
        "Higher: makes the override more conservative."
    ),
    "tracking.appearance_override_template_similarity": (
        "Lower: tolerates a less similar target crop during a jink. "
        "Higher: demands a closer template match."
    ),
    "tracking.appearance_override_tracking_quality": (
        "Lower: lets appearance override poorer motion quality. "
        "Higher: still requires stable tracking evidence."
    ),
    "tracking.prediction_maximum_outside_ratio": (
        "Lower: hides a predicted box sooner near frame edges. "
        "Higher: allows more of the predicted box outside the image."
    ),
    "tracking.occlusion_threshold": (
        "Lower: tolerates weaker combined evidence before leaving CONFIRMED. "
        "Higher: marks possible occlusion sooner."
    ),
    "tracking.lost_threshold": (
        "Reserved compatibility threshold; the current MVP uses bounded "
        "reacquisition time to enter LOST."
    ),
    "tracking.maximum_prediction_frames": (
        "Lower: stops showing motion prediction sooner. "
        "Higher: predicts for more frames before scene search."
    ),
    "tracking.maximum_prediction_seconds": (
        "Lower: shorter predicted-location window. "
        "Higher: keeps prediction active longer."
    ),
    "tracking.maximum_reacquisition_frames": (
        "Lower: declares LOST after fewer search frames. "
        "Higher: remains REACQUIRING longer."
    ),
    "tracking.maximum_reacquisition_seconds": (
        "Lower: reaches LOST sooner by elapsed time. "
        "Higher: searches longer before LOST."
    ),
    "tracking.maximum_speed_px_per_second": (
        "Reserved for expanded motion gating; the current MVP does not enforce "
        "this limit."
    ),
    "reidentification.appearance_weight": (
        "Lower: appearance contributes less to candidate ranking. "
        "Higher: visual similarity contributes more. All five weights must total 1."
    ),
    "reidentification.motion_weight": (
        "Lower: position and motion contribute less. Higher: nearby plausible motion "
        "matters more. All five weights must total 1."
    ),
    "reidentification.shape_weight": (
        "Lower: aspect-ratio similarity contributes less. Higher: shape contributes "
        "more. All five weights must total 1."
    ),
    "reidentification.colour_weight": (
        "Lower: colour contributes less. Higher: colour contributes more and may be "
        "sensitive to lighting. All five weights must total 1."
    ),
    "reidentification.size_weight": (
        "Lower: size contributes less. Higher: similar scale matters more. "
        "All five weights must total 1."
    ),
    "reidentification.minimum_match_score": (
        "Lower: easier and faster relock with greater false-relock risk. "
        "Higher: stronger total evidence is required."
    ),
    "reidentification.minimum_appearance_score": (
        "Lower: local candidates may look less similar. "
        "Higher: local reacquisition is more conservative."
    ),
    "reidentification.ambiguity_margin": (
        "Lower: accepts candidates with closer competing scores. "
        "Higher: requires a clearer winner."
    ),
    "reidentification.consecutive_confirmations": (
        "Lower: relocks in fewer frames with more one-frame error risk. "
        "Higher: relocks more slowly but verifies consistency longer."
    ),
    "reidentification.local_search_radius": (
        "Lower: faster search near the prediction. "
        "Higher: covers larger jumps with more CPU cost."
    ),
    "reidentification.last_position_search_multiplier": (
        "Lower: keeps the last-position search tighter. "
        "Higher: expands it farther around the last confirmed point."
    ),
    "reidentification.full_frame_search_after_frames": (
        "Lower: begins whole-frame search sooner and uses more CPU. "
        "Higher: stays local longer. Zero searches the full frame immediately."
    ),
    "reidentification.full_frame_motion_floor": (
        "Lower: distant candidates receive less motion credit. "
        "Higher: distance matters less during whole-frame search."
    ),
    "reidentification.full_frame_minimum_appearance_score": (
        "Lower: distant relocks are easier but riskier. "
        "Higher: requires stronger visual identity evidence."
    ),
    "reidentification.full_frame_processing_width": (
        "Lower: faster whole-frame scanning but may miss small targets. "
        "Higher: retains more detail with greater CPU cost."
    ),
    "reidentification.full_frame_max_reference_templates": (
        "Lower: faster search with fewer viewpoints. "
        "Higher: more viewpoint coverage with greater CPU cost."
    ),
    "reidentification.full_frame_ambiguity_margin": (
        "Lower: accepts closer whole-frame competitors. "
        "Higher: requires a clearer distant-candidate winner."
    ),
    "reidentification.lost_search_interval_frames": (
        "Lower: scans more often for quicker relock with higher CPU use. "
        "One searches every processed frame and is recommended for live tracking."
    ),
    "reidentification.confirmation_grace_frames": (
        "Lower: resets verification sooner after an ambiguous frame. Higher: keeps "
        "the same-location hypothesis longer. Ambiguous frames never count as "
        "positive identity confirmations."
    ),
    "reidentification.anchor_consensus_references": (
        "Lower: one strong anchor can dominate. Higher: more immutable views must "
        "agree, reducing false relocks but rejecting larger appearance changes."
    ),
    "reidentification.feature_verification_enabled": (
        "Enabled checks ORB feature layout against immutable anchors when both crops "
        "contain enough texture. Textureless targets continue using other signals."
    ),
    "reidentification.feature_minimum_keypoints": (
        "Lower: enables feature verification on simpler targets. Higher: requires "
        "richer texture before the feature gate is considered reliable."
    ),
    "reidentification.feature_minimum_matches": (
        "Lower: accepts fewer corresponding local details. Higher: reduces false "
        "matches but may reject small, blurred, or rotated targets."
    ),
    "reidentification.feature_minimum_inlier_ratio": (
        "Lower: tolerates less geometric agreement. Higher: requires more matched "
        "details to fit one consistent target transformation."
    ),
    "reidentification.original_anchor_weight": (
        "Lower: adaptive references influence reacquisition more. Higher: immutable "
        "early identity anchors dominate reacquisition. This does not change normal "
        "CSRT continuity scoring."
    ),
    "reidentification.full_frame_minimum_anchor_similarity": (
        "Lower: permits weaker agreement with the immutable original-frame anchors. "
        "Higher: reduces drift risk but may reject large appearance changes."
    ),
    "identity_memory.trusted_reference_weight": (
        "Lower: anchors identity more strongly to the original selection. "
        "Higher: adapts more to verified scale and viewpoint changes, with greater "
        "identity-drift risk."
    ),
    "identity_memory.minimum_update_confidence": (
        "Lower: learns new appearances more easily with greater drift risk. "
        "Higher: stores only stronger observations."
    ),
    "identity_memory.maximum_references": (
        "Lower: less viewpoint history and lower comparison cost. "
        "Higher: more historical views and greater CPU and memory use."
    ),
    "identity_memory.minimum_reference_interval_seconds": (
        "Lower: stores trusted views more frequently. "
        "Higher: spaces normal reference updates farther apart."
    ),
    "identity_memory.bootstrap_reference_count": (
        "Lower: switches to the normal update interval sooner. "
        "Higher: collects more early references at the bootstrap cadence."
    ),
    "identity_memory.bootstrap_reference_interval_seconds": (
        "Lower: collects initial trusted views faster. "
        "Higher: spaces initial views farther apart."
    ),
    "identity_memory.anchor_reference_count": (
        "Lower: keeps fewer immutable early views. Higher: protects more initial "
        "confirmed views from adaptive-memory rotation, using more memory and "
        "comparison work."
    ),
    "identity_memory.minimum_blur_variance": (
        "Lower: allows softer images into memory. "
        "Higher: requires sharper reference crops."
    ),
    "identity_memory.maximum_outside_ratio": (
        "Lower: references must be more fully inside the frame. "
        "Higher: allows more clipped target area into memory."
    ),
    "trajectory.maximum_points": (
        "Lower: retains fewer trajectory samples. "
        "Higher: retains more export history and uses more memory."
    ),
    "trajectory.include_predictions": (
        "Enabled records predicted points during short occlusions. "
        "Predicted segments remain visually distinct and do not count as confirmed path."
    ),
    "trajectory.fade_after_seconds": (
        "Lower: the on-screen trail disappears sooner. Higher: it remains visible "
        "longer. Zero hides the on-screen trail. Export history is unaffected."
    ),
    "export.default_fps": (
        "Lower or higher values change fallback recording playback speed when the "
        "source does not report a usable FPS."
    ),
    "export.video_codec": (
        "Selects the four-character OpenCV recording codec. Availability depends on "
        "the installed video backend."
    ),
}


FIELD_GROUPS: dict[str, tuple[FieldSpec, ...]] = {
    "Video": (
        FieldSpec("video.processing_width", "Processing width", "int", 320, 3840, 16),
        FieldSpec("video.processing_height", "Processing height", "int", 240, 2160, 16),
        FieldSpec("video.reconnect_attempts", "Reconnect attempts", "int", 0, 20, 1),
        FieldSpec("video.default_camera_index", "Default camera index", "int", 0, 32, 1),
        FieldSpec("video.mirror_camera_default", "Mirror laptop camera by default", "bool"),
    ),
    "Tracking": (
        FieldSpec(
            "tracking.preferred_tracker",
            "Short-term tracker",
            "choice",
            choices=("CSRT", "KCF", "MIL"),
        ),
        FieldSpec(
            "tracking.csrt_profile",
            "CSRT performance profile",
            "choice",
            choices=("ACCURATE", "BALANCED", "FAST"),
            tooltip=(
                "Balanced is recommended for laptop use. Accurate restores OpenCV's "
                "heavier defaults; Fast reduces scale and segmentation work."
            ),
        ),
        score("tracking.locked_minimum", "Locked minimum"),
        score("tracking.minimum_identity_confidence", "Identity entry minimum"),
        score("tracking.minimum_tracking_quality", "Tracking quality minimum"),
        score("tracking.locked_exit_identity_confidence", "Identity exit threshold"),
        score("tracking.locked_exit_tracking_quality", "Tracking exit threshold"),
        FieldSpec(
            "tracking.weak_observation_grace_frames",
            "Weak-observation grace frames",
            "int",
            0,
            120,
            1,
        ),
        score(
            "tracking.appearance_override_identity_confidence",
            "Fast-jink identity override",
        ),
        score(
            "tracking.appearance_override_template_similarity",
            "Fast-jink template override",
        ),
        score(
            "tracking.appearance_override_tracking_quality",
            "Fast-jink quality floor",
        ),
        score(
            "tracking.prediction_maximum_outside_ratio",
            "Maximum visible prediction outside ratio",
        ),
        score("tracking.occlusion_threshold", "Occlusion threshold"),
        score("tracking.lost_threshold", "Lost threshold"),
        FieldSpec(
            "tracking.maximum_prediction_frames",
            "Maximum prediction frames",
            "int",
            0,
            600,
            1,
        ),
        FieldSpec(
            "tracking.maximum_prediction_seconds",
            "Maximum prediction seconds",
            "float",
            0.0,
            30.0,
            0.1,
            1,
        ),
        FieldSpec(
            "tracking.maximum_reacquisition_frames",
            "Maximum reacquisition frames",
            "int",
            1,
            3600,
            1,
        ),
        FieldSpec(
            "tracking.maximum_reacquisition_seconds",
            "Maximum reacquisition seconds",
            "float",
            0.1,
            120.0,
            0.5,
            1,
        ),
        FieldSpec(
            "tracking.maximum_speed_px_per_second",
            "Maximum expected speed (px/s)",
            "float",
            10.0,
            10000.0,
            10.0,
            0,
        ),
    ),
    "Reacquisition": (
        score("reidentification.appearance_weight", "Appearance weight"),
        score("reidentification.motion_weight", "Motion weight"),
        score("reidentification.shape_weight", "Shape weight"),
        score("reidentification.colour_weight", "Colour weight"),
        score("reidentification.size_weight", "Size weight"),
        score("reidentification.minimum_match_score", "Minimum match score"),
        score(
            "reidentification.minimum_appearance_score",
            "Local appearance minimum",
        ),
        score("reidentification.ambiguity_margin", "Ambiguity margin"),
        FieldSpec(
            "reidentification.consecutive_confirmations",
            "Consecutive confirmations",
            "int",
            1,
            30,
            1,
        ),
        FieldSpec(
            "reidentification.local_search_radius",
            "Local search radius",
            "int",
            32,
            2000,
            8,
        ),
        FieldSpec(
            "reidentification.last_position_search_multiplier",
            "Last-position search multiplier",
            "float",
            0.5,
            5.0,
            0.05,
            2,
        ),
        FieldSpec(
            "reidentification.full_frame_search_after_frames",
            "Full-frame search after missed frames",
            "int",
            0,
            300,
            1,
        ),
        score(
            "reidentification.full_frame_motion_floor",
            "Full-frame neutral motion prior",
            (
                "Prevents distance from vetoing a whole-frame identity match. "
                "Nearby motion can still provide a small tie-break."
            ),
        ),
        score(
            "reidentification.full_frame_minimum_appearance_score",
            "Full-frame appearance minimum",
        ),
        FieldSpec(
            "reidentification.full_frame_processing_width",
            "Full-frame search processing width",
            "int",
            320,
            3840,
            16,
            tooltip=(
                "CPU proposal-search width. The complete frame is still searched, "
                "then candidates are verified at full processing resolution."
            ),
        ),
        FieldSpec(
            "reidentification.full_frame_max_reference_templates",
            "Full-frame proposal templates",
            "int",
            1,
            8,
            1,
            tooltip=(
                "Always uses the protected original, reserves one slot for the "
                "newest adaptive view when available, then uses early anchors. "
                "Final verification still enforces the anchor floor."
            ),
        ),
        score(
            "reidentification.full_frame_ambiguity_margin",
            "Full-frame ambiguity margin",
            (
                "Minimum score separation during whole-frame search. "
                "Temporal confirmation remains required."
            ),
        ),
        FieldSpec(
            "reidentification.lost_search_interval_frames",
            "Lost-state search interval (frames)",
            "int",
            1,
            120,
            1,
            tooltip=(
                "Whole-frame scan cadence after NO RELIABLE LOCATION. "
                "Lower values relock sooner but use more CPU."
            ),
        ),
        FieldSpec(
            "reidentification.confirmation_grace_frames",
            "Verification ambiguity grace (frames)",
            "int",
            0,
            30,
            1,
            tooltip=(
                "Retains a strong same-location candidate briefly when one frame "
                "is ambiguous. Only fully accepted frames increase verification."
            ),
        ),
        FieldSpec(
            "reidentification.anchor_consensus_references",
            "Anchor consensus references",
            "int",
            1,
            8,
            1,
        ),
        FieldSpec(
            "reidentification.feature_verification_enabled",
            "Feature-geometry verification",
            "bool",
        ),
        FieldSpec(
            "reidentification.feature_minimum_keypoints",
            "Feature minimum keypoints",
            "int",
            4,
            500,
            1,
        ),
        FieldSpec(
            "reidentification.feature_minimum_matches",
            "Feature minimum matches",
            "int",
            4,
            200,
            1,
        ),
        score(
            "reidentification.feature_minimum_inlier_ratio",
            "Feature minimum inlier ratio",
        ),
        score(
            "reidentification.original_anchor_weight",
            "Original-anchor reacquisition weight",
            (
                "Applies only to candidate reacquisition. Normal locked tracking "
                "continues using the trusted recent-reference weight."
            ),
        ),
        score(
            "reidentification.full_frame_minimum_anchor_similarity",
            "Full-frame minimum anchor similarity",
            (
                "A full-frame candidate must pass this immutable-anchor floor even "
                "when a recent adaptive reference matches strongly."
            ),
        ),
    ),
    "Identity memory": (
        score(
            "identity_memory.trusted_reference_weight",
            "Trusted recent-reference weight",
            (
                "Balances the protected original against high-confidence historical "
                "views. Higher values handle large scale and viewpoint changes better."
            ),
        ),
        score(
            "identity_memory.minimum_update_confidence",
            "Reference update confidence",
        ),
        FieldSpec(
            "identity_memory.maximum_references",
            "Maximum references",
            "int",
            1,
            100,
            1,
        ),
        FieldSpec(
            "identity_memory.minimum_reference_interval_seconds",
            "Normal reference interval (s)",
            "float",
            0.0,
            60.0,
            0.05,
            2,
        ),
        FieldSpec(
            "identity_memory.bootstrap_reference_count",
            "Bootstrap reference count",
            "int",
            1,
            20,
            1,
        ),
        FieldSpec(
            "identity_memory.bootstrap_reference_interval_seconds",
            "Bootstrap interval (s)",
            "float",
            0.0,
            5.0,
            0.01,
            2,
        ),
        FieldSpec(
            "identity_memory.anchor_reference_count",
            "Immutable anchor references",
            "int",
            1,
            20,
            1,
        ),
        FieldSpec(
            "identity_memory.minimum_blur_variance",
            "Minimum sharpness variance",
            "float",
            0.0,
            1000.0,
            1.0,
            1,
        ),
        score(
            "identity_memory.maximum_outside_ratio",
            "Maximum reference outside ratio",
        ),
    ),
    "Trajectory and export": (
        FieldSpec(
            "trajectory.maximum_points",
            "Maximum trajectory points",
            "int",
            10,
            100000,
            10,
        ),
        FieldSpec(
            "trajectory.include_predictions",
            "Include predicted trajectory",
            "bool",
        ),
        FieldSpec(
            "trajectory.fade_after_seconds",
            "On-screen trail lifetime (s)",
            "float",
            0.0,
            3600.0,
            1.0,
            1,
        ),
        FieldSpec(
            "export.default_fps",
            "Default recording FPS",
            "float",
            1.0,
            240.0,
            1.0,
            1,
        ),
        FieldSpec(
            "export.video_codec",
            "Video codec",
            "text",
            tooltip="Four-character OpenCV codec such as mp4v.",
        ),
    ),
}


class SettingsDialog(QDialog):
    def __init__(self, config: AppConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("MilitaryVision Settings")
        self.resize(760, 720)
        self.setMinimumSize(680, 560)
        self._base_config = config
        self.result_config: AppConfig | None = None
        self.widgets: dict[str, QWidget] = {}

        root = QVBoxLayout(self)
        title = QLabel("Tracking settings")
        title.setObjectName("title")
        description = QLabel(
            "Changes reset the active target. Hover a setting name or value for "
            "lower-versus-higher guidance."
        )
        description.setObjectName("subtitle")
        root.addWidget(title)
        root.addWidget(description)

        tabs = QTabWidget()
        for group_name, fields in FIELD_GROUPS.items():
            tabs.addTab(self._build_group(fields), group_name)
        root.addWidget(tabs, 1)

        self.status_label = QLabel("Factory defaults remain protected.")
        self.status_label.setObjectName("subtitle")
        root.addWidget(self.status_label)

        actions = QHBoxLayout()
        import_button = QPushButton("Import template")
        import_button.clicked.connect(self._import_template)
        export_button = QPushButton("Export template")
        export_button.clicked.connect(self._export_template)
        restore_button = QPushButton("Restore factory defaults")
        restore_button.setObjectName("danger")
        restore_button.clicked.connect(self._restore_defaults)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        apply_button = QPushButton("Apply settings")
        apply_button.setObjectName("primary")
        apply_button.clicked.connect(self._apply)
        for button in (import_button, export_button, restore_button):
            actions.addWidget(button)
        actions.addStretch()
        actions.addWidget(cancel_button)
        actions.addWidget(apply_button)
        root.addLayout(actions)
        self._set_widgets(config)

    def _build_group(self, fields: tuple[FieldSpec, ...]) -> QWidget:
        content = QFrame()
        form = QFormLayout(content)
        form.setContentsMargins(16, 16, 16, 16)
        form.setHorizontalSpacing(24)
        form.setVerticalSpacing(10)
        for spec in fields:
            widget = self._create_widget(spec)
            guidance = SETTING_DIRECTION_HELP.get(spec.path, "")
            tooltip = " ".join(
                part for part in (spec.tooltip, guidance) if part
            )
            label = QLabel(spec.label)
            if tooltip:
                widget.setToolTip(tooltip)
                label.setToolTip(tooltip)
            self.widgets[spec.path] = widget
            form.addRow(label, widget)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(content)
        return scroll

    @staticmethod
    def _create_widget(spec: FieldSpec) -> QWidget:
        if spec.kind == "bool":
            return QCheckBox()
        if spec.kind == "int":
            widget = QSpinBox()
            widget.setRange(int(spec.minimum), int(spec.maximum))
            widget.setSingleStep(max(1, int(spec.step)))
            return widget
        if spec.kind == "float":
            widget = QDoubleSpinBox()
            widget.setRange(spec.minimum, spec.maximum)
            widget.setSingleStep(spec.step)
            widget.setDecimals(spec.decimals)
            return widget
        if spec.kind == "choice":
            widget = QComboBox()
            widget.addItems(spec.choices)
            return widget
        return QLineEdit()

    def _set_widgets(self, config: AppConfig) -> None:
        raw = asdict(config)
        for group in FIELD_GROUPS.values():
            for spec in group:
                value = self._get_path(raw, spec.path)
                widget = self.widgets[spec.path]
                if isinstance(widget, QCheckBox):
                    widget.setChecked(bool(value))
                elif isinstance(widget, QSpinBox):
                    widget.setValue(int(value))
                elif isinstance(widget, QDoubleSpinBox):
                    widget.setValue(float(value))
                elif isinstance(widget, QComboBox):
                    widget.setCurrentText(str(value))
                elif isinstance(widget, QLineEdit):
                    widget.setText(str(value))

    def _config_from_widgets(self) -> AppConfig:
        raw = asdict(self._base_config)
        for group in FIELD_GROUPS.values():
            for spec in group:
                widget = self.widgets[spec.path]
                if isinstance(widget, QCheckBox):
                    value: Any = widget.isChecked()
                elif isinstance(widget, QSpinBox):
                    value = widget.value()
                elif isinstance(widget, QDoubleSpinBox):
                    value = widget.value()
                elif isinstance(widget, QComboBox):
                    value = widget.currentText()
                elif isinstance(widget, QLineEdit):
                    value = widget.text().strip()
                else:
                    continue
                self._set_path(raw, spec.path, value)
        return config_from_mapping(raw)

    def _apply(self) -> None:
        config = self._validated_widget_config()
        if config is None:
            return
        self.result_config = config
        self.accept()

    def _restore_defaults(self) -> None:
        try:
            factory = load_config(factory_config_path())
        except Exception as error:
            QMessageBox.critical(self, "Factory defaults", str(error))
            return
        self._base_config = factory
        self._set_widgets(factory)
        self.status_label.setText(
            "Factory defaults loaded. Select Apply settings to save them."
        )

    def _import_template(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import settings template",
            str(project_root() / "configs" / "templates"),
            "YAML settings (*.yaml *.yml)",
        )
        if not path:
            return
        try:
            imported = load_config(path)
            errors = validate_config(imported)
            if errors:
                raise ValueError("\n".join(errors))
        except Exception as error:
            QMessageBox.critical(self, "Invalid settings template", str(error))
            return
        self._base_config = imported
        self._set_widgets(imported)
        self.status_label.setText(
            f"Imported {Path(path).name}. Select Apply settings to activate it."
        )

    def _export_template(self) -> None:
        config = self._validated_widget_config()
        if config is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export settings template",
            str(project_root() / "configs" / "templates" / "tracking_profile.yaml"),
            "YAML settings (*.yaml)",
        )
        if not path:
            return
        output_path = Path(path)
        if output_path.suffix.lower() not in {".yaml", ".yml"}:
            output_path = output_path.with_suffix(".yaml")
        try:
            save_config(config, output_path)
        except Exception as error:
            QMessageBox.critical(self, "Template export error", str(error))
            return
        self.status_label.setText(f"Exported template: {output_path.name}")

    def _validated_widget_config(self) -> AppConfig | None:
        try:
            config = self._config_from_widgets()
        except Exception as error:
            QMessageBox.critical(self, "Invalid settings", str(error))
            return None
        errors = validate_config(config)
        if errors:
            QMessageBox.warning(self, "Invalid settings", "\n".join(errors))
            return None
        return config

    @staticmethod
    def _get_path(raw: dict[str, Any], path: str) -> Any:
        section, field = path.split(".", 1)
        return raw[section][field]

    @staticmethod
    def _set_path(raw: dict[str, Any], path: str, value: Any) -> None:
        section, field = path.split(".", 1)
        raw[section][field] = value

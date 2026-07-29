import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QComboBox, QSpinBox

from persistent_tracker.config import load_config
from persistent_tracker.ui.settings_dialog import SettingsDialog


def test_settings_dialog_builds_config_and_restores_factory_defaults() -> None:
    application = QApplication.instance() or QApplication([])
    active_config = load_config()
    dialog = SettingsDialog(active_config)
    width_widget = dialog.widgets["video.processing_width"]
    assert isinstance(width_widget, QSpinBox)
    width_widget.setValue(640)

    changed = dialog._config_from_widgets()
    assert changed.video.processing_width == 640
    reacquisition_width = dialog.widgets[
        "reidentification.full_frame_processing_width"
    ]
    assert isinstance(reacquisition_width, QSpinBox)
    assert reacquisition_width.value() == 640
    csrt_profile = dialog.widgets["tracking.csrt_profile"]
    assert isinstance(csrt_profile, QComboBox)
    assert csrt_profile.currentText() == active_config.tracking.csrt_profile
    trusted_weight = dialog.widgets[
        "identity_memory.trusted_reference_weight"
    ]
    assert "Lower:" in trusted_weight.toolTip()
    anchor_weight = dialog.widgets[
        "reidentification.original_anchor_weight"
    ]
    assert "Normal locked tracking" in anchor_weight.toolTip()
    anchor_floor = dialog.widgets[
        "reidentification.full_frame_minimum_anchor_similarity"
    ]
    assert "immutable-anchor floor" in anchor_floor.toolTip()
    anchor_count = dialog.widgets["identity_memory.anchor_reference_count"]
    assert "immutable early views" in anchor_count.toolTip()
    lost_interval = dialog.widgets[
        "reidentification.lost_search_interval_frames"
    ]
    assert "recommended for live tracking" in lost_interval.toolTip()
    grace = dialog.widgets["reidentification.confirmation_grace_frames"]
    assert "never count" in grace.toolTip()
    feature_gate = dialog.widgets[
        "reidentification.feature_verification_enabled"
    ]
    assert "ORB feature layout" in feature_gate.toolTip()
    trail_lifetime = dialog.widgets["trajectory.fade_after_seconds"]
    assert "Zero hides the on-screen trail" in trail_lifetime.toolTip()
    assert all(widget.toolTip() for widget in dialog.widgets.values())

    dialog._restore_defaults()
    restored = dialog._config_from_widgets()
    assert restored.video.processing_width == 1280
    assert restored.tracking.csrt_profile == "BALANCED"
    assert restored.reidentification.original_anchor_weight == 0.70
    assert restored.reidentification.lost_search_interval_frames == 1
    assert restored.reidentification.confirmation_grace_frames == 2
    assert restored.reidentification.feature_verification_enabled
    assert restored.identity_memory.anchor_reference_count == 3
    dialog.close()
    application.processEvents()

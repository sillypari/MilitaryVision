import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QComboBox, QSpinBox

from persistent_tracker.config import load_config
from persistent_tracker.ui.settings_dialog import SettingsDialog


def test_settings_dialog_builds_config_and_restores_factory_defaults() -> None:
    application = QApplication.instance() or QApplication([])
    dialog = SettingsDialog(load_config())
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
    assert csrt_profile.currentText() == "BALANCED"

    dialog._restore_defaults()
    restored = dialog._config_from_widgets()
    assert restored.video.processing_width == 1280
    dialog.close()
    application.processEvents()

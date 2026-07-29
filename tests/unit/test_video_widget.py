import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from persistent_tracker.ui.video_widget import VideoWidget


def test_selection_stops_resizing_after_mouse_release() -> None:
    application = QApplication.instance() or QApplication([])
    widget = VideoWidget()
    widget.resize(640, 480)
    widget.set_frame(np.zeros((480, 640, 3), dtype=np.uint8))
    widget.set_selection_enabled(True)
    widget.show()
    application.processEvents()

    start = QPoint(100, 100)
    end = QPoint(260, 240)
    QTest.mousePress(widget, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(widget, end)
    QTest.mouseRelease(widget, Qt.MouseButton.LeftButton, pos=end)
    application.processEvents()

    released_end = QPoint(widget._drag_end)
    QTest.mouseMove(widget, QPoint(400, 350))
    application.processEvents()

    assert not widget._dragging
    assert widget._drag_end == released_end
    widget.close()

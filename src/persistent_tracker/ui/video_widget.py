from __future__ import annotations

import cv2
import numpy as np
from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from persistent_tracker.domain.models import BoundingBox


class VideoWidget(QWidget):
    selection_changed = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumSize(640, 360)
        self.setMouseTracking(True)
        self._pixmap: QPixmap | None = None
        self._image_size = (0, 0)
        self._display_rect = QRect()
        self._selection_enabled = False
        self._dragging = False
        self._drag_start: QPoint | None = None
        self._drag_end: QPoint | None = None

    def set_frame(self, frame: np.ndarray) -> None:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width, channels = rgb.shape
        image = QImage(
            rgb.data,
            width,
            height,
            channels * width,
            QImage.Format.Format_RGB888,
        ).copy()
        self._pixmap = QPixmap.fromImage(image)
        self._image_size = (width, height)
        self.update()

    def set_selection_enabled(self, enabled: bool) -> None:
        self._selection_enabled = enabled
        self.setCursor(
            Qt.CursorShape.CrossCursor if enabled else Qt.CursorShape.ArrowCursor
        )
        if not enabled:
            self._dragging = False
            self._drag_start = None
            self._drag_end = None
        self.update()

    def clear_selection(self) -> None:
        self._dragging = False
        self._drag_start = None
        self._drag_end = None
        self.update()

    def paintEvent(self, _event: object) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.GlobalColor.black)
        if self._pixmap is not None:
            scaled = self._pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            self._display_rect = QRect(x, y, scaled.width(), scaled.height())
            painter.drawPixmap(self._display_rect, scaled)

        if self._drag_start is not None and self._drag_end is not None:
            selection = QRect(self._drag_start, self._drag_end).normalized()
            painter.fillRect(selection, QColor(79, 195, 219, 34))
            painter.setPen(QPen(QColor("#4fc3db"), 2, Qt.PenStyle.DashLine))
            painter.drawRect(selection)
            if selection.width() >= 120 and selection.height() >= 30:
                painter.setPen(QColor("#e9fbff"))
                painter.drawText(
                    selection.adjusted(8, 7, -8, -7),
                    Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
                    "PENDING SELECTION",
                )

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if (
            self._selection_enabled
            and event.button() == Qt.MouseButton.LeftButton
            and self._display_rect.contains(event.position().toPoint())
        ):
            self._dragging = True
            self._drag_start = event.position().toPoint()
            self._drag_end = self._drag_start
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if (
            self._selection_enabled
            and self._dragging
            and self._drag_start is not None
        ):
            point = event.position().toPoint()
            point.setX(
                max(self._display_rect.left(), min(point.x(), self._display_rect.right()))
            )
            point.setY(
                max(self._display_rect.top(), min(point.y(), self._display_rect.bottom()))
            )
            self._drag_end = point
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if (
            self._selection_enabled
            and self._dragging
            and self._drag_start is not None
            and event.button() == Qt.MouseButton.LeftButton
        ):
            point = event.position().toPoint()
            point.setX(
                max(self._display_rect.left(), min(point.x(), self._display_rect.right()))
            )
            point.setY(
                max(self._display_rect.top(), min(point.y(), self._display_rect.bottom()))
            )
            self._drag_end = point
            self._dragging = False
            selection = QRect(self._drag_start, self._drag_end).normalized()
            box = self._widget_rect_to_frame_box(selection)
            if box is not None and box[2] >= 8 and box[3] >= 8:
                self.selection_changed.emit(box)
            self.update()

    def _widget_rect_to_frame_box(self, selection: QRect) -> BoundingBox | None:
        image_width, image_height = self._image_size
        if image_width <= 0 or image_height <= 0 or self._display_rect.isEmpty():
            return None
        clipped = selection.intersected(self._display_rect)
        if clipped.isEmpty():
            return None
        scale_x = image_width / self._display_rect.width()
        scale_y = image_height / self._display_rect.height()
        return (
            int(round((clipped.left() - self._display_rect.left()) * scale_x)),
            int(round((clipped.top() - self._display_rect.top()) * scale_y)),
            max(1, int(round(clipped.width() * scale_x))),
            max(1, int(round(clipped.height() * scale_y))),
        )

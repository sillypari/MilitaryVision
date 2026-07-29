from __future__ import annotations

from typing import Protocol

import cv2
import numpy as np

from persistent_tracker.domain.models import BoundingBox


class OpenCVTracker(Protocol):
    def init(self, image: np.ndarray, bounding_box: tuple[int, int, int, int]) -> bool: ...

    def update(self, image: np.ndarray) -> tuple[bool, tuple[float, float, float, float]]: ...


def _tracker_factory(name: str, csrt_profile: str = "BALANCED") -> OpenCVTracker:
    normalized = name.upper()
    constructors = {
        "CSRT": "TrackerCSRT_create",
        "KCF": "TrackerKCF_create",
        "MIL": "TrackerMIL_create",
    }
    constructor_name = constructors.get(normalized, "TrackerCSRT_create")

    constructor = getattr(cv2, constructor_name, None)
    if constructor is None and hasattr(cv2, "legacy"):
        constructor = getattr(cv2.legacy, constructor_name, None)
    if constructor is None:
        raise RuntimeError(
            f"OpenCV tracker {normalized} is unavailable. "
            "Install opencv-contrib-python, not opencv-python."
        )
    if normalized == "CSRT":
        parameters_constructor = getattr(cv2, "TrackerCSRT_Params", None)
        if parameters_constructor is not None:
            parameters = parameters_constructor()
            profile = csrt_profile.upper()
            if profile == "BALANCED":
                parameters.number_of_scales = 25
                parameters.template_size = 150.0
                parameters.admm_iterations = 3
            elif profile == "FAST":
                parameters.number_of_scales = 13
                parameters.template_size = 125.0
                parameters.admm_iterations = 2
                parameters.use_segmentation = False
            try:
                return constructor(parameters)
            except TypeError:
                return constructor()
    return constructor()


class ShortTermTracker:
    def __init__(
        self,
        preferred_tracker: str,
        csrt_profile: str = "BALANCED",
    ) -> None:
        self.preferred_tracker = preferred_tracker
        self.csrt_profile = csrt_profile
        self._tracker: OpenCVTracker | None = None

    def initialize(self, frame: np.ndarray, box: BoundingBox) -> None:
        self._tracker = _tracker_factory(
            self.preferred_tracker,
            self.csrt_profile,
        )
        initialized = self._tracker.init(frame, box)
        if initialized is False:
            self._tracker = None
            raise RuntimeError("OpenCV tracker rejected the target selection")

    def update(self, frame: np.ndarray) -> tuple[bool, BoundingBox | None]:
        if self._tracker is None:
            return False, None
        success, raw_box = self._tracker.update(frame)
        if not success:
            return False, None
        x, y, width, height = raw_box
        if width < 2 or height < 2:
            return False, None
        return True, (
            int(round(x)),
            int(round(y)),
            int(round(width)),
            int(round(height)),
        )

    def clear(self) -> None:
        self._tracker = None

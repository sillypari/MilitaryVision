from __future__ import annotations

import cv2
import numpy as np

from persistent_tracker.domain.models import BoundingBox
from persistent_tracker.utils.geometry import clamp_box


def extract_crop(frame: np.ndarray, box: BoundingBox) -> np.ndarray:
    frame_height, frame_width = frame.shape[:2]
    x, y, width, height = clamp_box(box, frame_width, frame_height)
    return frame[y : y + height, x : x + width].copy()


def colour_histogram(crop: np.ndarray) -> np.ndarray:
    if crop.size == 0:
        return np.zeros((32, 32), dtype=np.float32)
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    histogram = cv2.calcHist([hsv], [0, 1], None, [32, 32], [0, 180, 0, 256])
    cv2.normalize(histogram, histogram, alpha=0.0, beta=1.0, norm_type=cv2.NORM_MINMAX)
    return histogram


def histogram_similarity(left: np.ndarray, right: np.ndarray) -> float:
    distance = cv2.compareHist(
        left.astype(np.float32),
        right.astype(np.float32),
        cv2.HISTCMP_BHATTACHARYYA,
    )
    return float(max(0.0, min(1.0, 1.0 - distance)))


def blur_variance(crop: np.ndarray) -> float:
    if crop.size == 0:
        return 0.0
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def template_similarity(reference: np.ndarray, candidate: np.ndarray) -> float:
    if reference.size == 0 or candidate.size == 0:
        return 0.0
    resized = cv2.resize(
        candidate,
        (reference.shape[1], reference.shape[0]),
        interpolation=cv2.INTER_AREA,
    )
    reference_gray = cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY)
    candidate_gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    score = cv2.matchTemplate(
        candidate_gray,
        reference_gray,
        cv2.TM_CCOEFF_NORMED,
    )[0, 0]
    if not np.isfinite(score):
        return 0.0
    return float(max(0.0, min(1.0, (float(score) + 1.0) / 2.0)))

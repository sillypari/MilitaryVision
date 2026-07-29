from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True, slots=True)
class LocalFeatures:
    points: np.ndarray
    descriptors: np.ndarray | None


@dataclass(frozen=True, slots=True)
class FeatureVerification:
    available: bool
    good_matches: int
    inlier_ratio: float


def extract_orb_features(
    crop: np.ndarray,
    *,
    maximum_features: int = 500,
) -> LocalFeatures:
    if crop.size == 0:
        return LocalFeatures(
            points=np.empty((0, 2), dtype=np.float32),
            descriptors=None,
        )
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    detector = cv2.ORB_create(
        nfeatures=maximum_features,
        scaleFactor=1.2,
        nlevels=8,
        fastThreshold=12,
    )
    keypoints, descriptors = detector.detectAndCompute(gray, None)
    points = np.asarray(
        [keypoint.pt for keypoint in keypoints],
        dtype=np.float32,
    ).reshape(-1, 2)
    return LocalFeatures(points=points, descriptors=descriptors)


def verify_anchor_geometry(
    anchor_features: list[LocalFeatures],
    candidate_features: LocalFeatures,
    *,
    minimum_keypoints: int,
    ratio_threshold: float = 0.75,
) -> FeatureVerification:
    if (
        candidate_features.descriptors is None
        or len(candidate_features.points) < minimum_keypoints
    ):
        return FeatureVerification(False, 0, 0.0)

    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
    available = False
    best_matches = 0
    best_inlier_ratio = 0.0
    for reference in anchor_features:
        if (
            reference.descriptors is None
            or len(reference.points) < minimum_keypoints
        ):
            continue
        available = True
        pairs = matcher.knnMatch(
            reference.descriptors,
            candidate_features.descriptors,
            k=2,
        )
        good = [
            first
            for pair in pairs
            if len(pair) == 2
            for first, second in [pair]
            if first.distance < ratio_threshold * second.distance
        ]
        best_matches = max(best_matches, len(good))
        if len(good) < 4:
            continue
        source_points = np.float32(
            [reference.points[match.queryIdx] for match in good]
        ).reshape(-1, 1, 2)
        candidate_points = np.float32(
            [candidate_features.points[match.trainIdx] for match in good]
        ).reshape(-1, 1, 2)
        try:
            _transform, inlier_mask = cv2.findHomography(
                source_points,
                candidate_points,
                cv2.RANSAC,
                5.0,
            )
        except cv2.error:
            inlier_mask = None
        if inlier_mask is None:
            continue
        inlier_ratio = float(np.count_nonzero(inlier_mask) / len(good))
        best_inlier_ratio = max(best_inlier_ratio, inlier_ratio)

    return FeatureVerification(
        available=available,
        good_matches=best_matches,
        inlier_ratio=best_inlier_ratio,
    )

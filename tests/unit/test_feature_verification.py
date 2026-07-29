import cv2
import numpy as np

from persistent_tracker.tracking.feature_verification import (
    extract_orb_features,
    verify_anchor_geometry,
)


def textured_target(seed: int) -> np.ndarray:
    generator = np.random.default_rng(seed)
    target = generator.integers(20, 235, (120, 160, 3), dtype=np.uint8)
    cv2.rectangle(target, (8, 8), (150, 110), (240, 30, 30), 4)
    cv2.line(target, (10, 100), (145, 15), (20, 240, 80), 5)
    cv2.putText(
        target,
        "BOX",
        (30, 72),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.4,
        (245, 245, 245),
        3,
    )
    return target


def distractor_target(seed: int) -> np.ndarray:
    generator = np.random.default_rng(seed)
    target = generator.integers(20, 235, (120, 160, 3), dtype=np.uint8)
    cv2.circle(target, (80, 60), 48, (30, 80, 240), 5)
    cv2.line(target, (12, 15), (145, 105), (240, 220, 30), 6)
    cv2.putText(
        target,
        "ALT",
        (34, 75),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.3,
        (30, 30, 30),
        3,
    )
    return target


def test_orb_geometry_accepts_same_textured_object() -> None:
    target = textured_target(22)
    reference = extract_orb_features(target)
    candidate = extract_orb_features(target.copy())

    result = verify_anchor_geometry(
        [reference],
        candidate,
        minimum_keypoints=12,
    )

    assert result.available
    assert result.good_matches >= 8
    assert result.inlier_ratio >= 0.35


def test_orb_geometry_rejects_different_textured_object() -> None:
    reference = extract_orb_features(textured_target(22))
    candidate = extract_orb_features(distractor_target(91))

    result = verify_anchor_geometry(
        [reference],
        candidate,
        minimum_keypoints=12,
    )

    assert result.available
    assert result.good_matches < 8 or result.inlier_ratio < 0.35

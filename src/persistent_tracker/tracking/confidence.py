from __future__ import annotations

from dataclasses import dataclass


def clamp_score(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


@dataclass(frozen=True, slots=True)
class ConfidenceAssessment:
    identity_confidence: float
    tracking_quality: float
    combined_confidence: float


def assess_confidence(
    *,
    appearance_similarity: float,
    template_similarity: float,
    motion_similarity: float,
    shape_similarity: float,
    size_similarity: float,
    visibility: float,
    tracker_success: bool,
) -> ConfidenceAssessment:
    identity_confidence = clamp_score(
        0.55 * appearance_similarity
        + 0.25 * template_similarity
        + 0.10 * shape_similarity
        + 0.10 * size_similarity
    )
    tracking_quality = clamp_score(
        0.40 * (1.0 if tracker_success else 0.0)
        + 0.35 * motion_similarity
        + 0.25 * visibility
    )
    combined = clamp_score(0.65 * identity_confidence + 0.35 * tracking_quality)
    return ConfidenceAssessment(
        identity_confidence=identity_confidence,
        tracking_quality=tracking_quality,
        combined_confidence=combined,
    )

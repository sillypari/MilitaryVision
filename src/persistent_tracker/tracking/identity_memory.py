from __future__ import annotations

import uuid

import numpy as np

from persistent_tracker.config import IdentityMemoryConfig
from persistent_tracker.domain.models import (
    BoundingBox,
    FrameMetadata,
    IdentityReference,
    TargetIdentity,
    TrackingState,
)
from persistent_tracker.tracking.appearance import (
    blur_variance,
    colour_histogram,
    extract_crop,
    histogram_similarity,
    template_similarity,
)
from persistent_tracker.utils.geometry import box_center, outside_ratio


class IdentityMemory:
    def __init__(self, config: IdentityMemoryConfig) -> None:
        self.config = config

    def create(
        self,
        frame: np.ndarray,
        box: BoundingBox,
        metadata: FrameMetadata,
    ) -> TargetIdentity:
        crop = extract_crop(frame, box)
        histogram = colour_histogram(crop)
        sharpness = blur_variance(crop)
        original = IdentityReference(
            crop=crop.copy(),
            histogram=histogram.copy(),
            frame_number=metadata.frame_number,
            timestamp=metadata.timestamp,
            confidence=1.0,
            blur_variance=sharpness,
            is_original=True,
            is_anchor=True,
        )
        center = box_center(box)
        return TargetIdentity(
            internal_id=str(uuid.uuid4()),
            state=TrackingState.INITIALIZING,
            original_crop=crop.copy(),
            original_histogram=histogram.copy(),
            references=[original],
            last_box=box,
            last_centroid=center,
            predicted_centroid=center,
        )

    def identity_similarity(self, crop: np.ndarray, identity: TargetIdentity) -> float:
        if identity.original_histogram is None:
            return 0.0
        candidate_histogram = colour_histogram(crop)
        original_score = histogram_similarity(
            identity.original_histogram,
            candidate_histogram,
        )
        historical_scores = [
            histogram_similarity(reference.histogram, candidate_histogram)
            for reference in identity.references[1:]
        ]
        return self._combine_reference_scores(original_score, historical_scores)

    def template_similarity(self, crop: np.ndarray, identity: TargetIdentity) -> float:
        if identity.original_crop is None:
            return 0.0
        original_score = template_similarity(identity.original_crop, crop)
        historical_scores = [
            template_similarity(reference.crop, crop)
            for reference in identity.references[1:]
        ]
        return self._combine_reference_scores(original_score, historical_scores)

    def _combine_reference_scores(
        self,
        original_score: float,
        historical_scores: list[float],
    ) -> float:
        """Fuse the protected original with trusted high-confidence viewpoints."""
        if not historical_scores:
            return original_score
        trusted_score = max(historical_scores)
        trusted_weight = self.config.trusted_reference_weight
        adapted_score = (
            (1.0 - trusted_weight) * original_score
            + trusted_weight * trusted_score
        )
        return max(original_score, adapted_score)

    def maybe_add_reference(
        self,
        identity: TargetIdentity,
        frame: np.ndarray,
        box: BoundingBox,
        metadata: FrameMetadata,
        confidence: float,
    ) -> bool:
        if identity.state != TrackingState.LOCKED:
            return False
        if confidence < self.config.minimum_update_confidence:
            return False
        if outside_ratio(box, metadata.width, metadata.height) > self.config.maximum_outside_ratio:
            return False
        last_reference = identity.references[-1]
        reference_interval = (
            self.config.bootstrap_reference_interval_seconds
            if len(identity.references) < self.config.bootstrap_reference_count
            else self.config.minimum_reference_interval_seconds
        )
        if (
            metadata.timestamp - last_reference.timestamp
            < reference_interval
        ):
            return False

        crop = extract_crop(frame, box)
        sharpness = blur_variance(crop)
        if sharpness < self.config.minimum_blur_variance:
            return False

        reference = IdentityReference(
            crop=crop,
            histogram=colour_histogram(crop),
            frame_number=metadata.frame_number,
            timestamp=metadata.timestamp,
            confidence=confidence,
            blur_variance=sharpness,
            is_anchor=(
                self.anchor_reference_count(identity)
                < self.config.anchor_reference_count
            ),
        )
        identity.references.append(reference)

        while len(identity.references) > self.config.maximum_references:
            removable_index = next(
                (
                    index
                    for index, stored in enumerate(identity.references)
                    if not stored.is_anchor
                ),
                None,
            )
            if removable_index is None:
                break
            del identity.references[removable_index]
        return True

    @staticmethod
    def anchor_references(identity: TargetIdentity) -> list[IdentityReference]:
        return [reference for reference in identity.references if reference.is_anchor]

    @staticmethod
    def adaptive_references(identity: TargetIdentity) -> list[IdentityReference]:
        return [
            reference
            for reference in identity.references
            if not reference.is_anchor
        ]

    @classmethod
    def anchor_reference_count(cls, identity: TargetIdentity) -> int:
        return len(cls.anchor_references(identity))

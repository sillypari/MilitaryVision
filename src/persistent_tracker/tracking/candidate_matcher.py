from __future__ import annotations

import math
from time import perf_counter

import cv2
import numpy as np

from persistent_tracker.config import ReidentificationConfig
from persistent_tracker.domain.models import BoundingBox, CandidateMatch, TargetIdentity
from persistent_tracker.tracking.appearance import (
    colour_histogram,
    extract_crop,
    histogram_similarity,
    template_similarity,
)
from persistent_tracker.utils.geometry import box_center, box_iou


def combined_candidate_score(
    *,
    appearance_similarity: float,
    motion_similarity: float,
    shape_similarity: float,
    colour_similarity: float,
    size_similarity: float,
    config: ReidentificationConfig,
) -> float:
    return float(
        appearance_similarity * config.appearance_weight
        + motion_similarity * config.motion_weight
        + shape_similarity * config.shape_weight
        + colour_similarity * config.colour_weight
        + size_similarity * config.size_weight
    )


def choose_unambiguous_candidate(
    candidates: list[CandidateMatch],
    config: ReidentificationConfig,
    *,
    minimum_appearance_score: float | None = None,
    require_motion_gate: bool = True,
    ambiguity_margin: float | None = None,
) -> CandidateMatch | None:
    if not candidates:
        return None
    ranked = sorted(candidates, key=lambda candidate: candidate.combined_score, reverse=True)
    best = ranked[0]
    second_score = ranked[1].combined_score if len(ranked) > 1 else 0.0
    required_appearance = (
        minimum_appearance_score
        if minimum_appearance_score is not None
        else config.minimum_appearance_score
    )
    if best.appearance_similarity < required_appearance:
        return None
    if require_motion_gate and best.motion_similarity < 0.25:
        return None
    if best.combined_score < config.minimum_match_score:
        return None
    required_margin = (
        config.ambiguity_margin
        if ambiguity_margin is None
        else ambiguity_margin
    )
    if best.combined_score - second_score < required_margin:
        return None
    return best


class LocalCandidateMatcher:
    _scales = (0.85, 1.0, 1.15)

    def __init__(self, config: ReidentificationConfig) -> None:
        self.config = config
        self.last_search_duration_ms = 0.0
        self.last_search_was_full_frame = False

    def find(
        self,
        frame: np.ndarray,
        identity: TargetIdentity,
        predicted_box: BoundingBox,
    ) -> tuple[list[CandidateMatch], CandidateMatch | None]:
        started_at = perf_counter()
        if identity.original_crop is None or identity.original_histogram is None:
            self.last_search_duration_ms = (perf_counter() - started_at) * 1000.0
            self.last_search_was_full_frame = False
            return [], None

        frame_height, frame_width = frame.shape[:2]
        predicted_center = box_center(predicted_box)
        last_center = (
            identity.last_centroid
            if identity.last_centroid is not None
            else box_center(identity.last_box or predicted_box)
        )
        uncertainty = self.config.local_search_radius + identity.missed_frames * 12
        prediction_outside = not (
            0.0 <= predicted_center[0] < frame_width
            and 0.0 <= predicted_center[1] < frame_height
        )
        full_frame_search = prediction_outside or (
            identity.missed_frames >= self.config.full_frame_search_after_frames
        )
        self.last_search_was_full_frame = full_frame_search

        if full_frame_search:
            search_regions = [(0, 0, frame_width, frame_height)]
        else:
            last_radius = int(
                self.config.local_search_radius
                * self.config.last_position_search_multiplier
                + identity.missed_frames * 12
            )
            search_regions = [
                self._search_region(
                    predicted_center,
                    int(uncertainty),
                    frame_width,
                    frame_height,
                ),
                self._search_region(
                    last_center,
                    last_radius,
                    frame_width,
                    frame_height,
                ),
            ]

        proposals: list[tuple[BoundingBox, float]] = []
        reference_crops = [identity.original_crop]
        reference_limit = (
            self.config.full_frame_max_reference_templates
            if full_frame_search
            else 4
        )
        recent_references = [
            reference.crop
            for reference in reversed(identity.references[1:])
            if not reference.is_original
        ]
        reference_crops.extend(recent_references[: max(0, reference_limit - 1)])

        for left, top, right, bottom in search_regions:
            search = frame[top:bottom, left:right]
            if search.size == 0:
                continue
            processing_scale = self._processing_scale(
                search.shape[1],
                reference_crops,
                full_frame_search,
            )
            if processing_scale < 1.0:
                search = cv2.resize(
                    search,
                    (
                        max(1, int(round(search.shape[1] * processing_scale))),
                        max(1, int(round(search.shape[0] * processing_scale))),
                    ),
                    interpolation=cv2.INTER_AREA,
                )
            search_gray = cv2.cvtColor(search, cv2.COLOR_BGR2GRAY)
            for reference_crop in reference_crops:
                reference_height, reference_width = reference_crop.shape[:2]
                for scale in self._scales:
                    box_width = max(8, int(round(reference_width * scale)))
                    box_height = max(8, int(round(reference_height * scale)))
                    template_width = max(
                        8,
                        int(round(box_width * processing_scale)),
                    )
                    template_height = max(
                        8,
                        int(round(box_height * processing_scale)),
                    )
                    if (
                        template_width >= search_gray.shape[1]
                        or template_height >= search_gray.shape[0]
                    ):
                        continue
                    template = cv2.resize(
                        reference_crop,
                        (template_width, template_height),
                        interpolation=cv2.INTER_AREA,
                    )
                    template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
                    response = cv2.matchTemplate(
                        search_gray,
                        template_gray,
                        cv2.TM_CCOEFF_NORMED,
                    )
                    for _ in range(3):
                        _, maximum, _, location = cv2.minMaxLoc(response)
                        if not np.isfinite(maximum):
                            break
                        box = (
                            left + int(round(location[0] / processing_scale)),
                            top + int(round(location[1] / processing_scale)),
                            box_width,
                            box_height,
                        )
                        normalized_score = max(
                            0.0,
                            min(1.0, (maximum + 1.0) / 2.0),
                        )
                        proposals.append((box, normalized_score))
                        suppress_left = max(0, location[0] - template_width // 2)
                        suppress_top = max(0, location[1] - template_height // 2)
                        suppress_right = min(
                            response.shape[1],
                            location[0] + template_width // 2,
                        )
                        suppress_bottom = min(
                            response.shape[0],
                            location[1] + template_height // 2,
                        )
                        response[
                            suppress_top:suppress_bottom,
                            suppress_left:suppress_right,
                        ] = -1.0

        deduplicated: list[tuple[BoundingBox, float]] = []
        for proposal in sorted(proposals, key=lambda item: item[1], reverse=True):
            if all(box_iou(proposal[0], existing[0]) < 0.25 for existing in deduplicated):
                deduplicated.append(proposal)
            if len(deduplicated) >= 6:
                break

        matches: list[CandidateMatch] = []
        predicted_width = max(1, predicted_box[2])
        predicted_height = max(1, predicted_box[3])
        for candidate_id, (box, reference_appearance) in enumerate(
            deduplicated,
            start=1,
        ):
            crop = extract_crop(frame, box)
            original_appearance = template_similarity(identity.original_crop, crop)
            appearance = 0.60 * original_appearance + 0.40 * reference_appearance
            candidate_histogram = colour_histogram(crop)
            original_colour = histogram_similarity(
                identity.original_histogram,
                candidate_histogram,
            )
            historical_colour = max(
                (
                    histogram_similarity(reference.histogram, candidate_histogram)
                    for reference in identity.references[1:]
                ),
                default=original_colour,
            )
            colour = 0.65 * original_colour + 0.35 * historical_colour
            center = box_center(box)
            predicted_distance = math.dist(center, predicted_center)
            last_distance = math.dist(center, last_center)
            predicted_motion = math.exp(
                -predicted_distance / max(1.0, uncertainty * 0.55)
            )
            last_motion = math.exp(
                -last_distance
                / max(
                    1.0,
                    self.config.local_search_radius
                    * self.config.last_position_search_multiplier
                    * 0.55,
                )
            )
            motion = max(predicted_motion, last_motion)
            if full_frame_search:
                motion = max(motion, self.config.full_frame_motion_floor)
            candidate_ratio = box[2] / max(1.0, box[3])
            predicted_ratio = predicted_width / max(1.0, predicted_height)
            shape = math.exp(-abs(math.log(max(1e-3, candidate_ratio / predicted_ratio))))
            area_ratio = (box[2] * box[3]) / max(
                1.0,
                predicted_width * predicted_height,
            )
            size = math.exp(-abs(math.log(max(1e-3, area_ratio))))
            score = combined_candidate_score(
                appearance_similarity=appearance,
                motion_similarity=motion,
                shape_similarity=shape,
                colour_similarity=colour,
                size_similarity=size,
                config=self.config,
            )
            matches.append(
                CandidateMatch(
                    candidate_id=candidate_id,
                    box=box,
                    appearance_similarity=appearance,
                    motion_similarity=motion,
                    colour_similarity=colour,
                    shape_similarity=shape,
                    size_similarity=size,
                    combined_score=score,
                )
            )

        accepted = choose_unambiguous_candidate(
            matches,
            self.config,
            minimum_appearance_score=(
                self.config.full_frame_minimum_appearance_score
                if full_frame_search
                else None
            ),
            require_motion_gate=not full_frame_search,
            ambiguity_margin=(
                self.config.full_frame_ambiguity_margin
                if full_frame_search
                else None
            ),
        )
        self.last_search_duration_ms = (perf_counter() - started_at) * 1000.0
        return matches, accepted

    def _processing_scale(
        self,
        search_width: int,
        reference_crops: list[np.ndarray],
        full_frame_search: bool,
    ) -> float:
        if not full_frame_search:
            return 1.0
        desired_scale = min(
            1.0,
            self.config.full_frame_processing_width / max(1, search_width),
        )
        minimum_reference_side = min(
            min(reference.shape[:2])
            for reference in reference_crops
        )
        minimum_template_scale = min(
            1.0,
            16.0 / max(1, minimum_reference_side),
        )
        return max(desired_scale, minimum_template_scale)

    @staticmethod
    def _search_region(
        center: tuple[float, float],
        radius: int,
        frame_width: int,
        frame_height: int,
    ) -> tuple[int, int, int, int]:
        return (
            max(0, int(center[0] - radius)),
            max(0, int(center[1] - radius)),
            min(frame_width, int(center[0] + radius)),
            min(frame_height, int(center[1] + radius)),
        )

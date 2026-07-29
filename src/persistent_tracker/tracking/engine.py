from __future__ import annotations

import logging
import math

import numpy as np

from persistent_tracker.config import AppConfig
from persistent_tracker.domain.models import (
    BoundingBox,
    FrameMetadata,
    TargetIdentity,
    TrackingResult,
    TrackingState,
    TrajectoryPoint,
)
from persistent_tracker.tracking.appearance import extract_crop
from persistent_tracker.tracking.candidate_matcher import LocalCandidateMatcher
from persistent_tracker.tracking.confidence import assess_confidence
from persistent_tracker.tracking.identity_memory import IdentityMemory
from persistent_tracker.tracking.motion_model import MotionModel
from persistent_tracker.tracking.short_term_tracker import ShortTermTracker
from persistent_tracker.tracking.state_machine import TrackingStateMachine
from persistent_tracker.tracking.trajectory import Trajectory
from persistent_tracker.utils.geometry import (
    box_center,
    clamp_box,
    interpolate_box,
    outside_ratio,
)

LOGGER = logging.getLogger(__name__)


class TrackingEngine:
    """Identity authority for all tracking evidence and state transitions."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.state_machine = TrackingStateMachine()
        self.identity_memory = IdentityMemory(config.identity_memory)
        self.motion = MotionModel()
        self.short_tracker = ShortTermTracker(
            config.tracking.preferred_tracker,
            config.tracking.csrt_profile,
        )
        self.candidate_matcher = LocalCandidateMatcher(config.reidentification)
        self.trajectory = Trajectory(config.trajectory.maximum_points)
        self.identity: TargetIdentity | None = None
        self._unconfirmed_start_frame: int | None = None
        self._unconfirmed_start_timestamp: float | None = None
        self._candidate_streak = 0
        self._last_candidate_box: BoundingBox | None = None
        self._weak_observation_frames = 0

    @property
    def state(self) -> TrackingState:
        return self.state_machine.state

    def begin_selection(self, metadata: FrameMetadata) -> None:
        if self.state == TrackingState.SELECTING:
            return
        if self.state != TrackingState.IDLE:
            self.state_machine.transition(
                TrackingState.SELECTING,
                reason="user requested a new target",
                frame_number=metadata.frame_number,
                timestamp=metadata.timestamp,
            )
        else:
            self.state_machine.transition(
                TrackingState.SELECTING,
                reason="user started target selection",
                frame_number=metadata.frame_number,
                timestamp=metadata.timestamp,
            )
        self.short_tracker.clear()
        self.identity = None
        self.trajectory.clear()
        self._reset_candidate_confirmation()
        self._weak_observation_frames = 0

    def cancel_selection(self, metadata: FrameMetadata) -> None:
        if self.state == TrackingState.SELECTING:
            self.state_machine.transition(
                TrackingState.IDLE,
                reason="selection cancelled",
                frame_number=metadata.frame_number,
                timestamp=metadata.timestamp,
            )

    def initialize(
        self,
        frame: np.ndarray,
        box: BoundingBox,
        metadata: FrameMetadata,
    ) -> TargetIdentity:
        if self.state == TrackingState.IDLE:
            self.begin_selection(metadata)
        if self.state != TrackingState.SELECTING:
            raise RuntimeError("Target can only be initialized from selection state")

        bounded_box = clamp_box(box, metadata.width, metadata.height)
        if bounded_box[2] < 8 or bounded_box[3] < 8:
            raise ValueError("Selection must be at least 8 by 8 pixels")

        self.state_machine.transition(
            TrackingState.INITIALIZING,
            reason="selection confirmed",
            frame_number=metadata.frame_number,
            timestamp=metadata.timestamp,
        )
        try:
            identity = self.identity_memory.create(frame, bounded_box, metadata)
            self.short_tracker.initialize(frame, bounded_box)
            center = box_center(bounded_box)
            self.motion.initialize(center, metadata.timestamp)
        except Exception:
            self.state_machine.transition(
                TrackingState.LOST,
                reason="target initialization failed",
                frame_number=metadata.frame_number,
                timestamp=metadata.timestamp,
            )
            raise

        self.identity = identity
        self.state_machine.transition(
            TrackingState.LOCKED,
            reason="initial identity profile created",
            frame_number=metadata.frame_number,
            timestamp=metadata.timestamp,
        )
        identity.state = TrackingState.LOCKED
        identity.confidence = 1.0
        identity.identity_confidence = 1.0
        identity.tracking_quality = 1.0
        identity.last_confirmed_timestamp = metadata.timestamp
        self._append_trajectory(metadata, bounded_box, 1.0, predicted=False)
        return identity

    def clear(self, metadata: FrameMetadata) -> None:
        self.state_machine.reset(
            frame_number=metadata.frame_number,
            timestamp=metadata.timestamp,
            reason="target cleared",
        )
        self.identity = None
        self.short_tracker.clear()
        self.trajectory.clear()
        self._reset_candidate_confirmation()
        self._weak_observation_frames = 0

    def update(self, frame: np.ndarray, metadata: FrameMetadata) -> TrackingResult:
        if self.identity is None or self.state in {
            TrackingState.IDLE,
            TrackingState.SELECTING,
            TrackingState.INITIALIZING,
            TrackingState.LOST,
        }:
            return self._result(frame, metadata)

        predicted_center = self.motion.predict(metadata.timestamp)
        self.identity.predicted_centroid = predicted_center
        predicted_box = interpolate_box(self.identity.last_box, predicted_center)
        prediction_is_visible = self._prediction_is_visible(predicted_box, metadata)

        if self.state == TrackingState.LOCKED:
            tracker_success, observed_box = self.short_tracker.update(frame)
            if tracker_success and observed_box is not None:
                observed_box = clamp_box(observed_box, metadata.width, metadata.height)
                if self._accept_short_term_observation(
                    frame,
                    observed_box,
                    predicted_center,
                    metadata,
                ):
                    return self._result(frame, metadata, box=observed_box)
            self._enter_occlusion(metadata, "short-term observation failed identity checks")

        candidate_box = self._attempt_reacquisition(frame, predicted_box, metadata)
        if self.state == TrackingState.LOCKED and self.identity.last_box is not None:
            return self._result(frame, metadata, box=self.identity.last_box)

        self.identity.missed_frames += 1
        self.identity.confidence = max(
            0.0,
            self.identity.confidence * 0.92,
        )
        self.identity.identity_confidence = 0.0
        self.identity.tracking_quality = max(
            0.0,
            1.0 - self.identity.missed_frames / max(
                1,
                self.config.tracking.maximum_prediction_frames,
            ),
        )

        predicted_elapsed_frames = self._elapsed_unconfirmed_frames(metadata)
        predicted_elapsed_seconds = self._elapsed_unconfirmed_seconds(metadata)
        if self.state == TrackingState.OCCLUDED:
            if not prediction_is_visible:
                self._transition(
                    TrackingState.REACQUIRING,
                    metadata,
                    "motion prediction left the visible frame; scene search continues",
                )
            elif (
                predicted_elapsed_frames
                >= self.config.tracking.maximum_prediction_frames
                or predicted_elapsed_seconds
                >= self.config.tracking.maximum_prediction_seconds
            ):
                self._transition(
                    TrackingState.REACQUIRING,
                    metadata,
                    "prediction window expired; identity search continues",
                )

        if self.state == TrackingState.REACQUIRING and (
            predicted_elapsed_frames >= self.config.tracking.maximum_reacquisition_frames
            or predicted_elapsed_seconds >= self.config.tracking.maximum_reacquisition_seconds
        ):
            self._transition(
                TrackingState.LOST,
                metadata,
                "reacquisition window expired without verified identity",
            )
            return self._result(frame, metadata)

        show_prediction = (
            self.state == TrackingState.OCCLUDED and prediction_is_visible
        )
        if self.config.trajectory.include_predictions and show_prediction:
            self._append_trajectory(
                metadata,
                predicted_box,
                self.identity.confidence,
                predicted=True,
            )
        return self._result(
            frame,
            metadata,
            predicted_box=predicted_box if show_prediction else None,
            candidate_box=candidate_box,
        )

    def _accept_short_term_observation(
        self,
        frame: np.ndarray,
        box: BoundingBox,
        predicted_center: tuple[float, float],
        metadata: FrameMetadata,
    ) -> bool:
        assert self.identity is not None
        assert self.identity.original_crop is not None
        assert self.identity.last_box is not None

        crop = extract_crop(frame, box)
        appearance = self.identity_memory.identity_similarity(crop, self.identity)
        template = self.identity_memory.template_similarity(crop, self.identity)
        center = box_center(box)
        distance = math.dist(center, predicted_center)
        gate = max(30.0, math.hypot(*self.motion.velocity) * 0.25 + 30.0)
        motion_similarity = math.exp(-distance / gate)
        previous_width = max(1, self.identity.last_box[2])
        previous_height = max(1, self.identity.last_box[3])
        ratio_change = (box[2] / max(1, box[3])) / (
            previous_width / previous_height
        )
        shape_similarity = math.exp(-abs(math.log(max(1e-3, ratio_change))))
        area_change = (box[2] * box[3]) / max(1.0, previous_width * previous_height)
        size_similarity = math.exp(-abs(math.log(max(1e-3, area_change))))
        visibility = 1.0 - outside_ratio(box, metadata.width, metadata.height)
        assessment = assess_confidence(
            appearance_similarity=appearance,
            template_similarity=template,
            motion_similarity=motion_similarity,
            shape_similarity=shape_similarity,
            size_similarity=size_similarity,
            visibility=visibility,
            tracker_success=True,
        )
        strongly_accepted = (
            assessment.combined_confidence >= self.config.tracking.locked_minimum
            and assessment.identity_confidence
            >= self.config.tracking.minimum_identity_confidence
            and assessment.tracking_quality
            >= self.config.tracking.minimum_tracking_quality
        )
        continuity_accepted = (
            (
                (
                    assessment.combined_confidence
                    >= self.config.tracking.occlusion_threshold
                    and assessment.identity_confidence
                    >= self.config.tracking.locked_exit_identity_confidence
                    and assessment.tracking_quality
                    >= self.config.tracking.locked_exit_tracking_quality
                )
                or (
                    assessment.identity_confidence
                    >= self.config.tracking.appearance_override_identity_confidence
                    and template
                    >= self.config.tracking.appearance_override_template_similarity
                    and assessment.tracking_quality
                    >= self.config.tracking.appearance_override_tracking_quality
                    and shape_similarity >= 0.85
                    and size_similarity >= 0.80
                    and visibility >= 0.80
                )
            )
            and self._weak_observation_frames
            < self.config.tracking.weak_observation_grace_frames
        )
        if not strongly_accepted and not continuity_accepted:
            LOGGER.info(
                "Rejected tracker observation frame=%s identity=%.3f quality=%.3f "
                "appearance=%.3f template=%.3f motion=%.3f shape=%.3f size=%.3f "
                "visibility=%.3f weak_frames=%s",
                metadata.frame_number,
                assessment.identity_confidence,
                assessment.tracking_quality,
                appearance,
                template,
                motion_similarity,
                shape_similarity,
                size_similarity,
                visibility,
                self._weak_observation_frames,
            )
            return False
        if strongly_accepted:
            self._weak_observation_frames = 0
        else:
            self._weak_observation_frames += 1
            LOGGER.debug(
                "Accepted weak continuation frame=%s identity=%.3f quality=%.3f "
                "grace=%s/%s",
                metadata.frame_number,
                assessment.identity_confidence,
                assessment.tracking_quality,
                self._weak_observation_frames,
                self.config.tracking.weak_observation_grace_frames,
            )

        corrected_center = self.motion.correct(center, metadata.timestamp)
        self.identity.last_box = box
        self.identity.last_centroid = corrected_center
        self.identity.predicted_centroid = corrected_center
        self.identity.velocity = self.motion.velocity
        self.identity.acceleration = self.motion.acceleration
        self.identity.confidence = assessment.combined_confidence
        self.identity.identity_confidence = assessment.identity_confidence
        self.identity.tracking_quality = assessment.tracking_quality
        self.identity.last_confirmed_timestamp = metadata.timestamp
        self.identity.missed_frames = 0
        self.identity.state = TrackingState.LOCKED
        self._append_trajectory(
            metadata,
            box,
            assessment.combined_confidence,
            predicted=False,
        )
        if strongly_accepted:
            self.identity_memory.maybe_add_reference(
                self.identity,
                frame,
                box,
                metadata,
                assessment.combined_confidence,
            )
        return True

    def _enter_occlusion(self, metadata: FrameMetadata, reason: str) -> None:
        if self.state == TrackingState.LOCKED:
            self._transition(TrackingState.OCCLUDED, metadata, reason)
            self._unconfirmed_start_frame = metadata.frame_number
            self._unconfirmed_start_timestamp = metadata.timestamp
            self._reset_candidate_confirmation()
            self._weak_observation_frames = 0
            if self.config.reidentification.full_frame_search_after_frames == 0:
                self._transition(
                    TrackingState.REACQUIRING,
                    metadata,
                    "short-term lock lost; immediate full-frame identity search",
                )

    def _attempt_reacquisition(
        self,
        frame: np.ndarray,
        predicted_box: BoundingBox,
        metadata: FrameMetadata,
    ) -> BoundingBox | None:
        assert self.identity is not None
        _candidates, accepted = self.candidate_matcher.find(
            frame,
            self.identity,
            predicted_box,
        )
        if accepted is None:
            self._reset_candidate_confirmation()
            return None

        candidate_box = accepted.box
        if self._last_candidate_box is not None:
            previous_center = box_center(self._last_candidate_box)
            candidate_center = box_center(candidate_box)
            consistency_radius = max(candidate_box[2], candidate_box[3]) * 0.75
            if math.dist(previous_center, candidate_center) <= consistency_radius:
                self._candidate_streak += 1
            else:
                self._candidate_streak = 1
        else:
            self._candidate_streak = 1
        self._last_candidate_box = candidate_box

        if self.state == TrackingState.OCCLUDED:
            self._transition(
                TrackingState.REACQUIRING,
                metadata,
                "plausible candidate found; temporal verification required",
            )

        if self._candidate_streak < self.config.reidentification.consecutive_confirmations:
            return candidate_box

        try:
            self.short_tracker.initialize(frame, candidate_box)
        except Exception:
            LOGGER.exception("Candidate passed identity gates but tracker reinit failed")
            self._reset_candidate_confirmation()
            return candidate_box
        center = box_center(candidate_box)
        corrected_center = self.motion.correct(center, metadata.timestamp)
        self.identity.last_box = candidate_box
        self.identity.last_centroid = corrected_center
        self.identity.predicted_centroid = corrected_center
        self.identity.velocity = self.motion.velocity
        self.identity.acceleration = self.motion.acceleration
        self.identity.confidence = accepted.combined_score
        self.identity.identity_confidence = accepted.appearance_similarity
        self.identity.tracking_quality = accepted.motion_similarity
        self.identity.last_confirmed_timestamp = metadata.timestamp
        self.identity.missed_frames = 0
        self._transition(
            TrackingState.LOCKED,
            metadata,
            "candidate identity verified across consecutive frames",
        )
        self._append_trajectory(
            metadata,
            candidate_box,
            accepted.combined_score,
            predicted=False,
        )
        self._unconfirmed_start_frame = None
        self._unconfirmed_start_timestamp = None
        self._reset_candidate_confirmation()
        return candidate_box

    def _transition(
        self,
        state: TrackingState,
        metadata: FrameMetadata,
        reason: str,
    ) -> None:
        self.state_machine.transition(
            state,
            reason=reason,
            frame_number=metadata.frame_number,
            timestamp=metadata.timestamp,
        )
        if self.identity is not None:
            self.identity.state = state

    def _append_trajectory(
        self,
        metadata: FrameMetadata,
        box: BoundingBox,
        confidence: float,
        *,
        predicted: bool,
    ) -> None:
        center = box_center(box)
        self.trajectory.append(
            TrajectoryPoint(
                frame_number=metadata.frame_number,
                timestamp=metadata.timestamp,
                x=center[0],
                y=center[1],
                width=float(box[2]),
                height=float(box[3]),
                confidence=confidence,
                state=self.state,
                predicted=predicted,
            )
        )

    def _elapsed_unconfirmed_frames(self, metadata: FrameMetadata) -> int:
        start = self._unconfirmed_start_frame
        return metadata.frame_number - start if start is not None else 0

    def _elapsed_unconfirmed_seconds(self, metadata: FrameMetadata) -> float:
        start = self._unconfirmed_start_timestamp
        return metadata.timestamp - start if start is not None else 0.0

    def _prediction_is_visible(
        self,
        box: BoundingBox,
        metadata: FrameMetadata,
    ) -> bool:
        center = box_center(box)
        center_inside = (
            0.0 <= center[0] < metadata.width
            and 0.0 <= center[1] < metadata.height
        )
        return (
            center_inside
            and outside_ratio(box, metadata.width, metadata.height)
            <= self.config.tracking.prediction_maximum_outside_ratio
        )

    def _reset_candidate_confirmation(self) -> None:
        self._candidate_streak = 0
        self._last_candidate_box = None

    def _result(
        self,
        frame: np.ndarray,
        metadata: FrameMetadata,
        *,
        box: BoundingBox | None = None,
        predicted_box: BoundingBox | None = None,
        candidate_box: BoundingBox | None = None,
    ) -> TrackingResult:
        identity = self.identity
        return TrackingResult(
            frame=frame,
            metadata=metadata,
            state=self.state,
            box=box,
            predicted_box=predicted_box,
            candidate_box=candidate_box,
            confidence=identity.confidence if identity else 0.0,
            identity_confidence=identity.identity_confidence if identity else 0.0,
            tracking_quality=identity.tracking_quality if identity else 0.0,
            velocity=identity.velocity if identity else (0.0, 0.0),
            missed_frames=identity.missed_frames if identity else 0,
            trajectory=list(self.trajectory.points),
            diagnostics={
                "path_length_pixels": self.trajectory.path_length_pixels,
                "reference_count": len(identity.references) if identity else 0,
                "internal_id": identity.internal_id if identity else None,
                "reidentification_search_ms": (
                    self.candidate_matcher.last_search_duration_ms
                ),
                "reidentification_search_scope": (
                    "full_frame"
                    if self.candidate_matcher.last_search_was_full_frame
                    else "local"
                ),
            },
        )

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np

BoundingBox = tuple[int, int, int, int]


class TrackingState(str, Enum):
    IDLE = "idle"
    SELECTING = "selecting"
    INITIALIZING = "initializing"
    LOCKED = "locked"
    OCCLUDED = "occluded"
    REACQUIRING = "reacquiring"
    LOST = "lost"


class PlaybackState(str, Enum):
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"
    SEEKING = "seeking"
    END_OF_STREAM = "end_of_stream"


class SourceState(str, Enum):
    CLOSED = "closed"
    OPENING = "opening"
    READY = "ready"
    RECONNECTING = "reconnecting"
    ERROR = "error"


@dataclass(slots=True)
class FrameMetadata:
    frame_number: int
    timestamp: float
    width: int
    height: int
    source_fps: float


@dataclass(slots=True)
class IdentityReference:
    crop: np.ndarray
    histogram: np.ndarray
    frame_number: int
    timestamp: float
    confidence: float
    blur_variance: float
    is_original: bool = False
    is_anchor: bool = False


@dataclass(slots=True)
class TargetIdentity:
    internal_id: str
    state: TrackingState = TrackingState.IDLE
    active_tracker_id: int | None = None
    object_class: str | None = None
    original_crop: np.ndarray | None = None
    original_mask: np.ndarray | None = None
    original_histogram: np.ndarray | None = None
    references: list[IdentityReference] = field(default_factory=list)
    last_box: BoundingBox | None = None
    last_centroid: tuple[float, float] | None = None
    predicted_centroid: tuple[float, float] | None = None
    velocity: tuple[float, float] = (0.0, 0.0)
    acceleration: tuple[float, float] = (0.0, 0.0)
    confidence: float = 0.0
    identity_confidence: float = 0.0
    tracking_quality: float = 0.0
    last_confirmed_timestamp: float | None = None
    missed_frames: int = 0


@dataclass(slots=True)
class TrajectoryPoint:
    frame_number: int
    timestamp: float
    x: float
    y: float
    width: float
    height: float
    confidence: float
    state: TrackingState
    predicted: bool
    segment_start: bool = False


@dataclass(slots=True)
class CandidateMatch:
    candidate_id: int
    box: BoundingBox
    appearance_similarity: float
    motion_similarity: float
    colour_similarity: float
    shape_similarity: float
    size_similarity: float
    combined_score: float
    anchor_similarity: float = 0.0
    adaptive_similarity: float = 0.0
    anchor_best_similarity: float = 0.0
    feature_verification_available: bool = False
    feature_matches: int = 0
    feature_inlier_ratio: float = 0.0


@dataclass(slots=True)
class StateTransition:
    frame_number: int
    timestamp: float
    previous_state: TrackingState
    new_state: TrackingState
    reason: str


@dataclass(slots=True)
class TrackingResult:
    frame: np.ndarray
    metadata: FrameMetadata
    state: TrackingState
    box: BoundingBox | None
    predicted_box: BoundingBox | None
    candidate_box: BoundingBox | None
    confidence: float
    identity_confidence: float
    tracking_quality: float
    velocity: tuple[float, float]
    missed_frames: int
    trajectory: list[TrajectoryPoint]
    diagnostics: dict[str, Any] = field(default_factory=dict)

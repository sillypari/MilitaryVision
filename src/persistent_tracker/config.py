from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml


@dataclass(frozen=True, slots=True)
class ApplicationConfig:
    name: str
    debug: bool


@dataclass(frozen=True, slots=True)
class VideoConfig:
    processing_width: int
    processing_height: int
    reconnect_attempts: int
    default_camera_index: int
    mirror_camera_default: bool


@dataclass(frozen=True, slots=True)
class TrackingConfig:
    preferred_tracker: str
    locked_minimum: float
    minimum_identity_confidence: float
    minimum_tracking_quality: float
    locked_exit_identity_confidence: float
    locked_exit_tracking_quality: float
    weak_observation_grace_frames: int
    appearance_override_identity_confidence: float
    appearance_override_template_similarity: float
    appearance_override_tracking_quality: float
    prediction_maximum_outside_ratio: float
    occlusion_threshold: float
    lost_threshold: float
    maximum_prediction_frames: int
    maximum_prediction_seconds: float
    maximum_reacquisition_frames: int
    maximum_reacquisition_seconds: float
    search_area_growth: float
    maximum_speed_px_per_second: float
    csrt_profile: str = "BALANCED"


@dataclass(frozen=True, slots=True)
class ReidentificationConfig:
    appearance_weight: float
    motion_weight: float
    shape_weight: float
    colour_weight: float
    size_weight: float
    minimum_match_score: float
    minimum_appearance_score: float
    ambiguity_margin: float
    consecutive_confirmations: int
    local_search_radius: int
    last_position_search_multiplier: float
    full_frame_search_after_frames: int
    full_frame_motion_floor: float
    full_frame_minimum_appearance_score: float
    full_frame_processing_width: int = 640
    full_frame_max_reference_templates: int = 2
    full_frame_ambiguity_margin: float = 0.06
    lost_search_interval_frames: int = 1
    original_anchor_weight: float = 0.70
    full_frame_minimum_anchor_similarity: float = 0.50
    confirmation_grace_frames: int = 2
    anchor_consensus_references: int = 2
    feature_verification_enabled: bool = True
    feature_minimum_keypoints: int = 12
    feature_minimum_matches: int = 8
    feature_minimum_inlier_ratio: float = 0.35


@dataclass(frozen=True, slots=True)
class IdentityMemoryConfig:
    minimum_update_confidence: float
    maximum_references: int
    minimum_reference_interval_seconds: float
    bootstrap_reference_count: int
    bootstrap_reference_interval_seconds: float
    minimum_blur_variance: float
    maximum_outside_ratio: float
    trusted_reference_weight: float = 0.35
    anchor_reference_count: int = 3


@dataclass(frozen=True, slots=True)
class TrajectoryConfig:
    maximum_points: int
    include_predictions: bool
    fade_after_seconds: float


@dataclass(frozen=True, slots=True)
class ExportConfig:
    default_fps: float
    video_codec: str


@dataclass(frozen=True, slots=True)
class AppConfig:
    application: ApplicationConfig
    video: VideoConfig
    tracking: TrackingConfig
    reidentification: ReidentificationConfig
    identity_memory: IdentityMemoryConfig
    trajectory: TrajectoryConfig
    export: ExportConfig


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_config_path() -> Path:
    return project_root() / "configs" / "default.yaml"


def factory_config_path() -> Path:
    return project_root() / "configs" / "factory_defaults.yaml"


def load_config(path: str | Path | None = None) -> AppConfig:
    config_path = Path(path) if path else default_config_path()
    with config_path.open("r", encoding="utf-8") as stream:
        raw: dict[str, Any] = yaml.safe_load(stream)

    return config_from_mapping(raw)


def config_from_mapping(raw: Mapping[str, Any]) -> AppConfig:
    return AppConfig(
        application=ApplicationConfig(**raw["application"]),
        video=VideoConfig(**raw["video"]),
        tracking=TrackingConfig(**raw["tracking"]),
        reidentification=ReidentificationConfig(**raw["reidentification"]),
        identity_memory=IdentityMemoryConfig(**raw["identity_memory"]),
        trajectory=TrajectoryConfig(**raw["trajectory"]),
        export=ExportConfig(**raw["export"]),
    )


def save_config(config: AppConfig, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as stream:
        yaml.safe_dump(
            asdict(config),
            stream,
            sort_keys=False,
            allow_unicode=False,
        )
    return output_path


def validate_config(config: AppConfig) -> list[str]:
    errors: list[str] = []
    weights = (
        config.reidentification.appearance_weight,
        config.reidentification.motion_weight,
        config.reidentification.shape_weight,
        config.reidentification.colour_weight,
        config.reidentification.size_weight,
    )
    if abs(sum(weights) - 1.0) > 0.001:
        errors.append("Reacquisition weights must add up to 1.0.")
    if config.tracking.lost_threshold > config.tracking.occlusion_threshold:
        errors.append("Lost threshold cannot exceed the occlusion threshold.")
    if config.tracking.occlusion_threshold > config.tracking.locked_minimum:
        errors.append("Occlusion threshold cannot exceed the locked threshold.")
    if config.tracking.csrt_profile.upper() not in {"ACCURATE", "BALANCED", "FAST"}:
        errors.append("CSRT profile must be Accurate, Balanced, or Fast.")
    if (
        config.tracking.locked_exit_identity_confidence
        > config.tracking.minimum_identity_confidence
    ):
        errors.append(
            "Locked exit identity confidence cannot exceed locked entry identity confidence."
        )
    if (
        config.reidentification.full_frame_minimum_appearance_score
        < config.reidentification.minimum_appearance_score
    ):
        errors.append(
            "Full-frame appearance threshold cannot be lower than local appearance threshold."
        )
    if config.reidentification.full_frame_processing_width < 320:
        errors.append("Full-frame search width must be at least 320 pixels.")
    if config.reidentification.full_frame_max_reference_templates < 1:
        errors.append("Full-frame search must use at least one reference template.")
    if not 0.0 <= config.reidentification.full_frame_ambiguity_margin <= 1.0:
        errors.append("Full-frame ambiguity margin must be between 0.0 and 1.0.")
    if config.reidentification.lost_search_interval_frames < 1:
        errors.append("Lost-state search interval must be at least one frame.")
    if config.reidentification.confirmation_grace_frames < 0:
        errors.append("Reacquisition confirmation grace cannot be negative.")
    if config.reidentification.anchor_consensus_references < 1:
        errors.append("Anchor consensus references must be at least one.")
    if config.reidentification.feature_minimum_keypoints < 4:
        errors.append("Feature verification requires at least four keypoints.")
    if config.reidentification.feature_minimum_matches < 4:
        errors.append("Feature verification requires at least four matches.")
    if not 0.0 <= config.reidentification.feature_minimum_inlier_ratio <= 1.0:
        errors.append("Feature minimum inlier ratio must be between 0.0 and 1.0.")
    if not 0.0 <= config.reidentification.original_anchor_weight <= 1.0:
        errors.append("Original anchor weight must be between 0.0 and 1.0.")
    if not (
        0.0
        <= config.reidentification.full_frame_minimum_anchor_similarity
        <= 1.0
    ):
        errors.append(
            "Full-frame minimum anchor similarity must be between 0.0 and 1.0."
        )
    if (
        config.identity_memory.bootstrap_reference_count
        > config.identity_memory.maximum_references
    ):
        errors.append(
            "Bootstrap reference count cannot exceed maximum identity references."
        )
    if not 0.0 <= config.identity_memory.trusted_reference_weight <= 1.0:
        errors.append("Trusted reference weight must be between 0.0 and 1.0.")
    if config.identity_memory.anchor_reference_count < 1:
        errors.append("Anchor reference count must be at least one.")
    if (
        config.identity_memory.anchor_reference_count
        > config.identity_memory.maximum_references
    ):
        errors.append(
            "Anchor reference count cannot exceed maximum identity references."
        )
    if config.video.processing_width < 320 or config.video.processing_height < 240:
        errors.append("Processing resolution must be at least 320 x 240.")
    return errors

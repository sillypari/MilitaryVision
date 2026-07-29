from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from persistent_tracker.config import AppConfig
from persistent_tracker.domain.models import (
    StateTransition,
    TargetIdentity,
    TrajectoryPoint,
)


def export_csv(path: str | Path, points: list[TrajectoryPoint]) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            [
                "timestamp",
                "frame",
                "x",
                "y",
                "width",
                "height",
                "confidence",
                "state",
                "predicted",
            ]
        )
        for point in points:
            writer.writerow(
                [
                    f"{point.timestamp:.6f}",
                    point.frame_number,
                    f"{point.x:.3f}",
                    f"{point.y:.3f}",
                    f"{point.width:.3f}",
                    f"{point.height:.3f}",
                    f"{point.confidence:.6f}",
                    point.state.value,
                    str(point.predicted).lower(),
                ]
            )
    return output_path


def export_json(
    path: str | Path,
    *,
    source: str,
    resolution: tuple[int, int],
    source_fps: float,
    config: AppConfig,
    identity: TargetIdentity | None,
    points: list[TrajectoryPoint],
    transitions: list[StateTransition],
    statistics: dict[str, Any],
) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "input": {
            "source": source,
            "resolution": {"width": resolution[0], "height": resolution[1]},
            "source_fps": source_fps,
        },
        "models": {
            "short_term_tracker": config.tracking.preferred_tracker,
            "short_term_tracker_profile": config.tracking.csrt_profile,
            "detector": None,
            "segmentation": None,
            "reidentification": "histogram_and_template_mvp",
        },
        "configuration": asdict(config),
        "target": _serialize_identity(identity),
        "trajectory": [_serialize_point(point) for point in points],
        "state_transitions": [_serialize_transition(item) for item in transitions],
        "statistics": statistics,
    }
    with output_path.open("w", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2)
    return output_path


def _serialize_identity(identity: TargetIdentity | None) -> dict[str, Any] | None:
    if identity is None:
        return None
    return {
        "internal_id": identity.internal_id,
        "state": identity.state.value,
        "object_class": identity.object_class,
        "last_box": identity.last_box,
        "last_centroid": identity.last_centroid,
        "velocity": identity.velocity,
        "acceleration": identity.acceleration,
        "confidence": identity.confidence,
        "last_confirmed_timestamp": identity.last_confirmed_timestamp,
        "reference_count": len(identity.references),
        "references": [
            {
                "frame": reference.frame_number,
                "timestamp": reference.timestamp,
                "confidence": reference.confidence,
                "blur_variance": reference.blur_variance,
                "is_original": reference.is_original,
                "is_anchor": reference.is_anchor,
                "crop_shape": list(reference.crop.shape),
            }
            for reference in identity.references
        ],
    }


def _serialize_point(point: TrajectoryPoint) -> dict[str, Any]:
    return {
        "timestamp": point.timestamp,
        "frame": point.frame_number,
        "x": point.x,
        "y": point.y,
        "width": point.width,
        "height": point.height,
        "confidence": point.confidence,
        "state": point.state.value,
        "predicted": point.predicted,
        "segment_start": point.segment_start,
    }


def _serialize_transition(transition: StateTransition) -> dict[str, Any]:
    return {
        "frame": transition.frame_number,
        "timestamp": transition.timestamp,
        "previous_state": transition.previous_state.value,
        "new_state": transition.new_state.value,
        "reason": transition.reason,
    }

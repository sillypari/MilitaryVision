import csv
import json

import numpy as np

from persistent_tracker.config import load_config
from persistent_tracker.domain.models import (
    FrameMetadata,
    StateTransition,
    TrackingState,
    TrajectoryPoint,
)
from persistent_tracker.storage.exporters import export_csv, export_json
from persistent_tracker.tracking.identity_memory import IdentityMemory


def test_csv_uses_stable_schema(tmp_path) -> None:
    point = TrajectoryPoint(
        frame_number=3,
        timestamp=0.1,
        x=20.0,
        y=30.0,
        width=10.0,
        height=12.0,
        confidence=0.9,
        state=TrackingState.LOCKED,
        predicted=False,
    )
    path = export_csv(tmp_path / "trajectory.csv", [point])
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.reader(stream))
    assert rows[0] == [
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
    assert rows[1][-2:] == ["locked", "false"]


def test_json_does_not_serialize_raw_numpy_arrays(tmp_path) -> None:
    config = load_config()
    frame = np.full((60, 80, 3), 120, dtype=np.uint8)
    metadata = FrameMetadata(0, 0.0, 80, 60, 30.0)
    identity = IdentityMemory(config.identity_memory).create(
        frame,
        (10, 10, 30, 30),
        metadata,
    )
    transition = StateTransition(
        frame_number=0,
        timestamp=0.0,
        previous_state=TrackingState.INITIALIZING,
        new_state=TrackingState.LOCKED,
        reason="test",
    )
    path = export_json(
        tmp_path / "session.json",
        source="test.mp4",
        resolution=(80, 60),
        source_fps=30.0,
        config=config,
        identity=identity,
        points=[],
        transitions=[transition],
        statistics={"processing_fps": 20.0},
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["target"]["reference_count"] == 1
    assert "crop" not in payload["target"]["references"][0]

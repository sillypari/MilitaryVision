from dataclasses import replace

import numpy as np

from persistent_tracker.config import load_config
from persistent_tracker.domain.models import FrameMetadata, TrackingState
from persistent_tracker.tracking.identity_memory import IdentityMemory


def textured_frame() -> np.ndarray:
    generator = np.random.default_rng(7)
    return generator.integers(0, 256, (120, 160, 3), dtype=np.uint8)


def metadata(frame: int, timestamp: float) -> FrameMetadata:
    return FrameMetadata(
        frame_number=frame,
        timestamp=timestamp,
        width=160,
        height=120,
        source_fps=30.0,
    )


def test_original_reference_is_preserved_when_memory_rotates() -> None:
    config = replace(
        load_config().identity_memory,
        maximum_references=3,
        minimum_reference_interval_seconds=0.0,
        minimum_blur_variance=0.0,
    )
    memory = IdentityMemory(config)
    frame = textured_frame()
    identity = memory.create(frame, (20, 20, 50, 50), metadata(0, 0.0))
    identity.state = TrackingState.LOCKED
    original = identity.references[0].crop.copy()

    for index in range(1, 6):
        assert memory.maybe_add_reference(
            identity,
            frame,
            (20, 20, 50, 50),
            metadata(index, float(index)),
            0.99,
        )

    assert len(identity.references) == 3
    assert identity.references[0].is_original
    assert np.array_equal(identity.references[0].crop, original)


def test_low_confidence_observation_never_updates_memory() -> None:
    memory = IdentityMemory(load_config().identity_memory)
    frame = textured_frame()
    identity = memory.create(frame, (20, 20, 50, 50), metadata(0, 0.0))
    identity.state = TrackingState.LOCKED

    updated = memory.maybe_add_reference(
        identity,
        frame,
        (20, 20, 50, 50),
        metadata(60, 2.0),
        0.2,
    )

    assert not updated
    assert len(identity.references) == 1

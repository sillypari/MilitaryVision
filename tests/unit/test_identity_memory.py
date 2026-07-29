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
    assert all(reference.is_anchor for reference in identity.references)
    assert np.array_equal(identity.references[0].crop, original)


def test_early_anchor_bank_survives_adaptive_memory_rotation() -> None:
    config = replace(
        load_config().identity_memory,
        maximum_references=4,
        anchor_reference_count=3,
        minimum_reference_interval_seconds=0.0,
        bootstrap_reference_interval_seconds=0.0,
        minimum_blur_variance=0.0,
    )
    memory = IdentityMemory(config)
    frame = textured_frame()
    identity = memory.create(frame, (20, 20, 50, 50), metadata(0, 0.0))
    identity.state = TrackingState.LOCKED

    for index in range(1, 8):
        changed = np.roll(frame, index, axis=1)
        assert memory.maybe_add_reference(
            identity,
            changed,
            (20, 20, 50, 50),
            metadata(index, float(index)),
            0.99,
        )

    anchors = memory.anchor_references(identity)
    adaptive = memory.adaptive_references(identity)
    assert [reference.frame_number for reference in anchors] == [0, 1, 2]
    assert len(adaptive) == 1
    assert adaptive[0].frame_number == 7


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


def test_trusted_view_can_outweigh_original_without_replacing_it() -> None:
    base_config = load_config().identity_memory
    adaptive_memory = IdentityMemory(
        replace(
            base_config,
            trusted_reference_weight=0.65,
            minimum_reference_interval_seconds=0.0,
            minimum_blur_variance=0.0,
        )
    )
    legacy_memory = IdentityMemory(
        replace(
            base_config,
            trusted_reference_weight=0.35,
            minimum_reference_interval_seconds=0.0,
            minimum_blur_variance=0.0,
        )
    )
    original_frame = np.zeros((120, 160, 3), dtype=np.uint8)
    original_frame[20:80, 30:100] = (20, 40, 220)
    changed_frame = np.zeros_like(original_frame)
    changed_frame[20:80, 30:100] = (180, 170, 40)
    box = (30, 20, 70, 60)
    identity = adaptive_memory.create(
        original_frame,
        box,
        metadata(0, 0.0),
    )
    identity.state = TrackingState.LOCKED
    assert adaptive_memory.maybe_add_reference(
        identity,
        changed_frame,
        box,
        metadata(1, 1.0),
        0.99,
    )
    candidate = changed_frame[20:80, 30:100].copy()

    adaptive_score = adaptive_memory.identity_similarity(candidate, identity)
    legacy_score = legacy_memory.identity_similarity(candidate, identity)

    assert adaptive_score > legacy_score
    assert identity.references[0].is_original
    assert np.array_equal(
        identity.references[0].crop,
        original_frame[20:80, 30:100],
    )

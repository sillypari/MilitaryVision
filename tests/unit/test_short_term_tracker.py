import numpy as np
import pytest

from persistent_tracker.tracking.short_term_tracker import ShortTermTracker


@pytest.mark.parametrize("profile", ["ACCURATE", "BALANCED", "FAST"])
def test_csrt_profiles_initialize_and_update(profile: str) -> None:
    generator = np.random.default_rng(246)
    frame = generator.integers(0, 35, (240, 320, 3), dtype=np.uint8)
    frame[80:140, 110:180] = generator.integers(
        55,
        240,
        (60, 70, 3),
        dtype=np.uint8,
    )
    tracker = ShortTermTracker("CSRT", profile)

    tracker.initialize(frame, (110, 80, 70, 60))
    success, box = tracker.update(frame)

    assert success
    assert box is not None
    assert box[2] > 2
    assert box[3] > 2

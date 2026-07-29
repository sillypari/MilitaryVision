from dataclasses import replace

import numpy as np

from persistent_tracker.config import load_config
from persistent_tracker.domain.models import (
    CandidateMatch,
    FrameMetadata,
    TrackingState,
)
from persistent_tracker.tracking.engine import TrackingEngine


def metadata(frame_number: int) -> FrameMetadata:
    return FrameMetadata(
        frame_number=frame_number,
        timestamp=frame_number / 30.0,
        width=320,
        height=240,
        source_fps=30.0,
    )


def test_one_ambiguous_frame_does_not_erase_positive_confirmations() -> None:
    base = load_config()
    config = replace(
        base,
        reidentification=replace(
            base.reidentification,
            consecutive_confirmations=3,
            confirmation_grace_frames=1,
        ),
    )
    frame = np.random.default_rng(982).integers(
        0,
        256,
        (240, 320, 3),
        dtype=np.uint8,
    )
    engine = TrackingEngine(config)
    engine.begin_selection(metadata(0))
    engine.initialize(frame, (100, 70, 80, 60), metadata(0))
    engine.short_tracker.update = lambda _frame: (False, None)  # type: ignore[method-assign]
    engine.short_tracker.initialize = lambda _frame, _box: None  # type: ignore[method-assign]

    candidate = CandidateMatch(
        candidate_id=1,
        box=(105, 72, 80, 60),
        appearance_similarity=0.90,
        motion_similarity=0.80,
        colour_similarity=0.90,
        shape_similarity=0.95,
        size_similarity=0.95,
        combined_score=0.88,
        anchor_similarity=0.90,
        adaptive_similarity=0.88,
        anchor_best_similarity=0.92,
    )
    outcomes = [candidate, None, candidate, candidate]

    def find_candidate(
        _frame: np.ndarray,
        _identity: object,
        _predicted_box: object,
    ) -> tuple[list[CandidateMatch], CandidateMatch | None]:
        outcome = outcomes.pop(0)
        engine.candidate_matcher.last_search_was_full_frame = True
        engine.candidate_matcher.last_best_match = candidate
        engine.candidate_matcher.last_rejection_reason = (
            None
            if outcome is not None
            else "leading candidates were too ambiguous"
        )
        return [candidate], outcome

    engine.candidate_matcher.find = find_candidate  # type: ignore[method-assign]

    states = [
        engine.update(frame, metadata(frame_number)).state
        for frame_number in range(1, 5)
    ]

    assert states[:3] == [
        TrackingState.REACQUIRING,
        TrackingState.REACQUIRING,
        TrackingState.REACQUIRING,
    ]
    assert states[3] == TrackingState.LOCKED

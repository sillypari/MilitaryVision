from dataclasses import replace

import pytest

from persistent_tracker.config import load_config
from persistent_tracker.domain.models import CandidateMatch
from persistent_tracker.tracking.candidate_matcher import (
    choose_unambiguous_candidate,
    combined_candidate_score,
)


def candidate(candidate_id: int, score: float, appearance: float = 0.9) -> CandidateMatch:
    return CandidateMatch(
        candidate_id=candidate_id,
        box=(10 * candidate_id, 10, 20, 20),
        appearance_similarity=appearance,
        motion_similarity=0.9,
        colour_similarity=0.9,
        shape_similarity=0.9,
        size_similarity=0.9,
        combined_score=score,
    )


def test_configured_weights_are_applied() -> None:
    config = load_config().reidentification
    score = combined_candidate_score(
        appearance_similarity=0.8,
        motion_similarity=0.6,
        shape_similarity=0.5,
        colour_similarity=0.4,
        size_similarity=0.3,
        config=config,
    )
    assert score == pytest.approx(0.63)


def test_ambiguous_candidates_are_rejected() -> None:
    config = load_config().reidentification
    assert choose_unambiguous_candidate(
        [candidate(1, 0.84), candidate(2, 0.80)],
        config,
    ) is None


def test_clear_candidate_is_accepted() -> None:
    config = replace(
        load_config().reidentification,
        minimum_match_score=0.75,
    )
    selected = choose_unambiguous_candidate(
        [candidate(1, 0.91), candidate(2, 0.72)],
        config,
    )
    assert selected is not None
    assert selected.candidate_id == 1


def test_appearance_gate_cannot_be_overridden_by_combined_score() -> None:
    config = load_config().reidentification
    assert choose_unambiguous_candidate(
        [candidate(1, 0.99, appearance=0.4)],
        config,
    ) is None


def test_full_frame_selection_can_disable_motion_gate() -> None:
    config = replace(
        load_config().reidentification,
        minimum_match_score=0.75,
    )
    distant = candidate(1, 0.90)
    distant.motion_similarity = 0.01

    selected = choose_unambiguous_candidate(
        [distant],
        config,
        minimum_appearance_score=0.82,
        require_motion_gate=False,
    )

    assert selected is distant


def test_full_frame_can_use_temporally_safe_ambiguity_margin() -> None:
    config = replace(
        load_config().reidentification,
        minimum_match_score=0.75,
    )
    best = candidate(1, 0.86)
    second = candidate(2, 0.79)

    assert choose_unambiguous_candidate([best, second], config) is None
    selected = choose_unambiguous_candidate(
        [best, second],
        config,
        ambiguity_margin=config.full_frame_ambiguity_margin,
    )

    assert selected is best

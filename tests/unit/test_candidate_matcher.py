from dataclasses import replace

import pytest

from persistent_tracker.config import load_config
from persistent_tracker.domain.models import CandidateMatch
from persistent_tracker.tracking.candidate_matcher import (
    choose_unambiguous_candidate,
    combined_candidate_score,
    consensus_score,
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


def test_anchor_consensus_requires_multiple_strong_references() -> None:
    assert consensus_score([0.95, 0.45, 0.30], 2) == pytest.approx(0.70)
    assert consensus_score([0.95], 2) == pytest.approx(0.95)


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


def test_adaptive_match_cannot_bypass_full_frame_anchor_floor() -> None:
    config = replace(
        load_config().reidentification,
        minimum_match_score=0.75,
    )
    adaptive_only = candidate(1, 0.92)
    adaptive_only.anchor_similarity = 0.40
    adaptive_only.adaptive_similarity = 0.98

    selected = choose_unambiguous_candidate(
        [adaptive_only],
        config,
        minimum_appearance_score=0.80,
        minimum_anchor_similarity=0.50,
        require_motion_gate=False,
    )

    assert selected is None


def test_full_frame_candidate_passes_when_anchor_and_adaptive_views_agree() -> None:
    config = replace(
        load_config().reidentification,
        minimum_match_score=0.75,
    )
    corroborated = candidate(1, 0.92)
    corroborated.anchor_similarity = 0.82
    corroborated.adaptive_similarity = 0.94

    selected = choose_unambiguous_candidate(
        [corroborated],
        config,
        minimum_appearance_score=0.80,
        minimum_anchor_similarity=0.50,
        require_motion_gate=False,
    )

    assert selected is corroborated


def test_available_feature_geometry_cannot_be_bypassed() -> None:
    config = replace(
        load_config().reidentification,
        minimum_match_score=0.75,
        feature_verification_enabled=True,
        feature_minimum_matches=8,
        feature_minimum_inlier_ratio=0.35,
    )
    visually_similar = candidate(1, 0.92)
    visually_similar.anchor_similarity = 0.90
    visually_similar.feature_verification_available = True
    visually_similar.feature_matches = 5
    visually_similar.feature_inlier_ratio = 0.80

    selected = choose_unambiguous_candidate(
        [visually_similar],
        config,
        minimum_anchor_similarity=0.50,
        require_motion_gate=False,
    )

    assert selected is None

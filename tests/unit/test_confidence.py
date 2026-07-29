from persistent_tracker.tracking.confidence import assess_confidence


def test_confidence_exposes_identity_and_tracking_separately() -> None:
    assessment = assess_confidence(
        appearance_similarity=0.95,
        template_similarity=0.9,
        motion_similarity=0.2,
        shape_similarity=0.9,
        size_similarity=0.9,
        visibility=1.0,
        tracker_success=True,
    )
    assert assessment.identity_confidence > assessment.tracking_quality
    assert 0.0 <= assessment.combined_confidence <= 1.0


def test_failed_tracker_reduces_quality_without_erasing_identity_evidence() -> None:
    assessment = assess_confidence(
        appearance_similarity=0.95,
        template_similarity=0.95,
        motion_similarity=0.4,
        shape_similarity=0.9,
        size_similarity=0.9,
        visibility=0.8,
        tracker_success=False,
    )
    assert assessment.identity_confidence > 0.8
    assert assessment.tracking_quality < 0.5

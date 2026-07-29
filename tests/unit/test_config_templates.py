from dataclasses import asdict, replace

from persistent_tracker.config import (
    load_config,
    save_config,
    validate_config,
)


def test_configuration_template_round_trip(tmp_path) -> None:
    config = load_config()
    path = save_config(config, tmp_path / "profile.yaml")
    restored = load_config(path)
    assert asdict(restored) == asdict(config)


def test_invalid_reacquisition_weights_are_rejected() -> None:
    config = load_config()
    invalid_reidentification = replace(
        config.reidentification,
        appearance_weight=0.90,
    )
    errors = validate_config(
        replace(config, reidentification=invalid_reidentification)
    )
    assert "Reacquisition weights must add up to 1.0." in errors


def test_invalid_full_frame_performance_settings_are_rejected() -> None:
    config = load_config()
    invalid_reidentification = replace(
        config.reidentification,
        full_frame_processing_width=160,
        full_frame_max_reference_templates=0,
    )

    errors = validate_config(
        replace(config, reidentification=invalid_reidentification)
    )

    assert "Full-frame search width must be at least 320 pixels." in errors
    assert "Full-frame search must use at least one reference template." in errors


def test_invalid_csrt_profile_is_rejected() -> None:
    config = load_config()
    invalid_tracking = replace(config.tracking, csrt_profile="TURBO")

    errors = validate_config(replace(config, tracking=invalid_tracking))

    assert "CSRT profile must be Accurate, Balanced, or Fast." in errors


def test_invalid_full_frame_ambiguity_margin_is_rejected() -> None:
    config = load_config()
    invalid_reidentification = replace(
        config.reidentification,
        full_frame_ambiguity_margin=1.5,
    )

    errors = validate_config(
        replace(config, reidentification=invalid_reidentification)
    )

    assert "Full-frame ambiguity margin must be between 0.0 and 1.0." in errors


def test_invalid_lost_search_interval_is_rejected() -> None:
    config = load_config()
    invalid_reidentification = replace(
        config.reidentification,
        lost_search_interval_frames=0,
    )

    errors = validate_config(
        replace(config, reidentification=invalid_reidentification)
    )

    assert "Lost-state search interval must be at least one frame." in errors


def test_invalid_trusted_reference_weight_is_rejected() -> None:
    config = load_config()
    invalid_identity_memory = replace(
        config.identity_memory,
        trusted_reference_weight=1.5,
    )

    errors = validate_config(
        replace(config, identity_memory=invalid_identity_memory)
    )

    assert "Trusted reference weight must be between 0.0 and 1.0." in errors


def test_invalid_anchor_reacquisition_settings_are_rejected() -> None:
    config = load_config()
    invalid_reidentification = replace(
        config.reidentification,
        original_anchor_weight=1.5,
        full_frame_minimum_anchor_similarity=-0.1,
        confirmation_grace_frames=-1,
        anchor_consensus_references=0,
        feature_minimum_keypoints=3,
        feature_minimum_matches=3,
        feature_minimum_inlier_ratio=1.5,
    )
    invalid_identity_memory = replace(
        config.identity_memory,
        anchor_reference_count=config.identity_memory.maximum_references + 1,
    )

    errors = validate_config(
        replace(
            config,
            reidentification=invalid_reidentification,
            identity_memory=invalid_identity_memory,
        )
    )

    assert "Original anchor weight must be between 0.0 and 1.0." in errors
    assert (
        "Full-frame minimum anchor similarity must be between 0.0 and 1.0."
        in errors
    )
    assert (
        "Anchor reference count cannot exceed maximum identity references."
        in errors
    )
    assert "Reacquisition confirmation grace cannot be negative." in errors
    assert "Anchor consensus references must be at least one." in errors
    assert "Feature verification requires at least four keypoints." in errors
    assert "Feature verification requires at least four matches." in errors
    assert "Feature minimum inlier ratio must be between 0.0 and 1.0." in errors

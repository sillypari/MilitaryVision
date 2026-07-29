# Settings and templates

Open **Settings** from the main control bar. Video processing pauses while the
dialog is open.

## Applying changes

Change values in the category tabs and select **Apply settings**. MilitaryVision
validates related thresholds and reacquisition weights before saving.

Hover a setting name or its value control to see the effect of lower and higher
values. Controls that are reserved for a later MVP phase are identified
explicitly instead of implying that they already affect tracking.

Applying settings clears the active target because tracker state created under
one set of thresholds must not continue under another set. Select the target
again after applying.

The active configuration is stored in:

```text
configs/default.yaml
```

## Factory defaults

Select **Restore factory defaults**, inspect the restored values, and then select
**Apply settings**. The protected source is:

```text
configs/factory_defaults.yaml
```

Do not use the factory file as a tuning workspace.

## Exporting a template

1. Adjust the values in the Settings dialog.
2. Select **Export template**.
3. Choose a descriptive YAML filename.

The default profile directory is:

```text
configs/templates/
```

Exporting does not activate the values. Select **Apply settings** when the same
values should also become active.

## Importing a template

1. Select **Import template**.
2. Choose a `.yaml` or `.yml` profile.
3. Review the populated fields.
4. Select **Apply settings**.

Templates must contain the complete configuration schema. Invalid weights,
threshold ordering, processing resolution, or identity-memory limits are
rejected before activation.

## Useful tuning directions

### Identity adaptation across scale changes

The conservative default uses:

```yaml
identity_memory:
  trusted_reference_weight: 0.35
```

The protected original remains available for every comparison. This setting
controls how strongly the best high-confidence historical view can contribute
when it matches better than the original during normal CSRT continuity.

- Increase it cautiously when a target changes scale or viewpoint gradually and
  the tracker box remains stable.
- Reduce it when the scene contains many near-identical objects and stronger
  anchoring to the initial view is preferred.
- A value of `0.35` keeps the original-heavy behavior.

Only sharp, in-frame, strongly confirmed observations enter the trusted history.
Occluded, predicted, weak-continuation, and reacquisition-candidate frames cannot
update it.

The initial identity bank uses:

```yaml
identity_memory:
  anchor_reference_count: 3
```

The exact selection and first strongly confirmed early views are immutable
anchors. Later references rotate within the remaining memory capacity. Increase
the anchor count only when the initial target remains clearly visible long
enough to collect useful viewpoint variation.

The complete tested profile from before this migration is available at:

```text
configs/templates/opencv4_csrt_tested_baseline.yaml
```

The F-16-specific `0.65` experiment remains an optional template:

```text
configs/templates/f16_adaptive_identity.yaml
```

It is benchmark evidence, not a recommended general-purpose default. Test it on
several target types before copying its value into an everyday profile.

### Normal locked tracking

The default short tracker is CSRT with the `BALANCED` laptop profile:

```yaml
tracking:
  preferred_tracker: CSRT
  csrt_profile: BALANCED
```

- `ACCURATE` uses OpenCV's heavier CSRT defaults. Use it when processing FPS
  remains comfortably above the source FPS.
- `BALANCED` retains CSRT appearance, segmentation, and scale signals with a
  smaller search model. This is the recommended laptop setting.
- `FAST` reduces scale work and disables CSRT segmentation. It provides more
  frame-rate headroom but can be less stable through scale or appearance change.

The profile has no effect when KCF or MIL is selected.

The balanced identity-continuation defaults tolerate short camera blur and
lighting changes without allowing those weak frames to update identity memory:

```yaml
tracking:
  locked_minimum: 0.66
  minimum_identity_confidence: 0.54
  locked_exit_identity_confidence: 0.42
  locked_exit_tracking_quality: 0.68
  weak_observation_grace_frames: 12
```

Increase these thresholds when the short tracker follows visually similar
objects incorrectly. Reduce them only in small increments when the correct
target is being dropped despite stable shape, size, and tracking quality.

### Reacquisition

For faster full-frame relock:

```yaml
reidentification:
  full_frame_search_after_frames: 0
```

`0` starts a whole-frame search as soon as the short-term tracker loses its
identity check. The proposal scan uses a reduced copy of the complete frame; it
does not crop the search to the predicted location. Candidate coordinates and
final identity checks remain at the normal processing resolution.

The laptop-friendly defaults are:

```yaml
reidentification:
  full_frame_processing_width: 640
  full_frame_max_reference_templates: 2
  original_anchor_weight: 0.70
  full_frame_minimum_anchor_similarity: 0.50
```

The exact original always supplies a proposal template. When adaptive memory is
available, one proposal slot is reserved for its newest verified view so large
scale or viewpoint changes can still be discovered. Remaining slots use
immutable early anchors. Final candidate verification separately records anchor
and adaptive evidence, so proposal coverage cannot bypass the anchor floor.

`original_anchor_weight` applies only after normal tracker continuity is broken.
It does not change `trusted_reference_weight`, so continuous CSRT tracking can
remain adaptive while full-frame relocking returns to an original-heavy identity
policy.

`full_frame_minimum_anchor_similarity` is a mandatory floor. A candidate that
matches a recent adaptive reference but does not resemble any immutable anchor
remains unverified.

In full-frame mode, distant candidates receive a neutral motion value rather
than a proximity penalty. This allows a verified target to move between opposite
parts of the frame. Nearby motion can contribute a small ranking advantage, but
it cannot prevent a strong distant identity match. The application still rejects
the match when appearance is insufficient, when another candidate has a similar
score, or until the configured number of consecutive confirmations has been
observed.

The balanced relock defaults are:

```yaml
reidentification:
  minimum_match_score: 0.74
  full_frame_minimum_appearance_score: 0.76
  full_frame_minimum_anchor_similarity: 0.50
  anchor_consensus_references: 2
  feature_verification_enabled: true
  feature_minimum_keypoints: 12
  feature_minimum_matches: 8
  feature_minimum_inlier_ratio: 0.35
  full_frame_motion_floor: 0.75
  full_frame_ambiguity_margin: 0.06
  consecutive_confirmations: 3
  confirmation_grace_frames: 2
  lost_search_interval_frames: 1
```

`lost_search_interval_frames` controls the continued whole-frame scan after the
bounded reacquisition window expires. The live-first value `1` searches every
processed frame. The UI remains in `NO LOCATION - SEARCHING` or `UNVERIFIED`
until a candidate passes multi-frame verification. Raise the interval only when
full-frame search consumes unacceptable CPU.

`confirmation_grace_frames` allows the same strong spatial hypothesis to remain
active through brief ambiguity. Those frames do not increase the confirmation
count. A candidate still needs three fully accepted observations.

`anchor_consensus_references` averages the strongest available immutable views
instead of letting one unusually high template score dominate. ORB feature
verification becomes mandatory only when the anchors and candidate contain at
least the configured number of keypoints. This helps matchbox artwork, printed
labels, textured tools, and other detailed targets. Feature-poor targets fall
back to anchor appearance, colour, shape, size, and ambiguity checks.

For fewer false relocks, increase these cautiously:

```yaml
reidentification:
  minimum_match_score: 0.78
  full_frame_minimum_appearance_score: 0.82
  full_frame_ambiguity_margin: 0.10
  consecutive_confirmations: 4
```

For lower CPU use:

```yaml
video:
  processing_width: 960
  processing_height: 540

reidentification:
  full_frame_processing_width: 480
```

Lowering only `full_frame_processing_width` reduces lag while the target is
unverified. It does not reduce normal locked-frame video resolution. Very small
targets may need `640` or a higher value. Increasing
`full_frame_max_reference_templates` improves viewpoint coverage at a substantial
CPU cost, so values above `2` are not recommended for a laptop CPU.

The five reacquisition weights must always add up to `1.0`.

### On-screen trail lifetime

Use **Trajectory and export** > **On-screen trail lifetime (s)**:

```yaml
trajectory:
  fade_after_seconds: 3.0
```

- Lower values remove old trail segments sooner.
- Higher values keep more movement history visible.
- `0` hides the on-screen trail completely.

This setting filters only the rendered overlay. MilitaryVision retains the full
bounded trajectory history for CSV and JSON exports, up to
`trajectory.maximum_points`.

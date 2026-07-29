# Settings and templates

Open **Settings** from the main control bar. Video processing pauses while the
dialog is open.

## Applying changes

Change values in the category tabs and select **Apply settings**. MilitaryVision
validates related thresholds and reacquisition weights before saving.

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
```

The proposal templates are the protected original and the newest high-confidence
reference. Final candidate verification also uses colour and the stored identity
history.

In full-frame mode, the last position does not contribute to the acceptance
score. This allows a verified target to move between opposite parts of the frame.
The application still rejects the match when appearance is insufficient, when
another candidate has a similar identity score, or until the configured number
of consecutive confirmations has been observed.

`full_frame_motion_floor` affects the motion-consistency diagnostic immediately
after a distant relock. It does not limit where the target may be accepted.

For fewer false relocks, increase these cautiously:

```yaml
reidentification:
  full_frame_minimum_appearance_score: 0.86
  ambiguity_margin: 0.15
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

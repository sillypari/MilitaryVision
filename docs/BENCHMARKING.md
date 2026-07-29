# Benchmarking and OpenCV migration

MilitaryVision includes a deterministic local-video benchmark runner. It uses a
fixed starting frame, selection box, and YAML profile so changes can be compared
under the same conditions.

## Running a benchmark

From the project root on Windows:

```powershell
.\.venv\Scripts\python.exe .\scripts\benchmark_tracker.py `
  --video "C:\path\to\video.mp4" `
  --box 360 340 860 275 `
  --config .\configs\default.yaml
```

The four box values are `x`, `y`, `width`, and `height` in the application's
processing resolution. Add `--start-frame N` when selection begins after the
first frame.

Reports are written under `output/benchmarks/` by default. They include:

- OpenCV version and tracker profile
- Processing FPS
- Confirmed-frame percentage
- State counts and final state
- Reacquisition and lost-event counts
- Every state transition with its frame, timestamp, and reason

The runner cannot determine whether a relock is the correct identity without
ground-truth annotations or manual review. A high confirmed percentage alone is
therefore not proof of correct tracking.

## F-16 scale-change benchmark

The initial migration benchmark used a 1280 by 720, 30 FPS, 913-frame clip and a
fixed `(360, 340, 860, 275)` initial box. The aircraft shrinks from a large
near-frame-width target to a very small distant target.

### Identity-memory A/B result

| Profile | Confirmed frames | Confirmed coverage | Lost events | Final state |
|---|---:|---:|---:|---|
| Original-heavy reference weight `0.35` | 498 | 54.55% | 1 | Lost |
| Experimental trusted-view weight `0.65` | 843 | 92.33% | 0 | Reacquiring |

With the original-heavy profile, the tracker observation was rejected at frame
504 and the bounded reacquisition window ended in `LOST` at frame 624.

With the experimental trusted-view adaptation, confirmed tracking continued
until frame 849. The system then reported `REACQUIRING` because the aircraft had
become extremely small. It did not fabricate a confirmed location and did not
enter `LOST` before the clip ended. This one-video result does not establish a
general-purpose default, so the protected factory default remains at `0.35`.
The active profile remains user-managed.

The later anchor-bank change deliberately separates these responsibilities.
`trusted_reference_weight` still controls normal locked-frame continuity, while
`original_anchor_weight` and `full_frame_minimum_anchor_similarity` govern
reacquisition. This preserves scale adaptation without allowing a single
rotating recent reference to independently authorize a lost-target relock. The
earlier benchmark numbers predate that separation and should not be presented as
an anchor-bank comparison.

The comparison reports are generated files and remain outside Git:

```text
output/benchmarks/f16-opencv4-csrt-baseline.json
output/benchmarks/f16-adaptive-identity.json
```

## OpenCV 5 and TrackerViT evaluation

OpenCV 5.0.0 was installed only in `runtime/venv-opencv5`. The production
environment and dependency constraint were left unchanged during evaluation.

The same video and initial box were run directly through the short-term trackers:

| OpenCV | Tracker | Processing FPS | First failure | Invalid box |
|---|---|---:|---:|---:|
| 4.14.0 | CSRT | 15.10 | None | None |
| 5.0.0 | CSRT | 12.77 | None | None |
| 4.14.0 | TrackerViT | 35.95 | 857 | 152 |
| 5.0.0 | TrackerViT | 38.25 | 857 | 152 |

TrackerViT was faster, but its box began expanding outside the frame and reached
an invalid multi-thousand-pixel size. Its success flag remained true during much
of that drift. Promoting it would violate the rule that the system must not
silently present an unreliable location.

OpenCV 5 did not improve CSRT robustness on this clip and reduced raw CSRT
throughput on this laptop. MilitaryVision therefore remains on the tested
OpenCV 4 line for the MVP. A future migration should be reconsidered only when
multiple annotated clips show fewer wrong relocks and acceptable processing
speed.

## Rollback

The pre-migration application code is retained in the local Git branch:

```text
baseline/opencv4-csrt
```

The reusable settings rollback does not require changing branches. Import:

```text
configs/templates/opencv4_csrt_tested_baseline.yaml
```

This restores the tested CSRT Accurate profile and the original-heavy `0.35`
trusted-reference weight.

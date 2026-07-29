# MVP scope

## Goal

Prove the complete interaction and data path on a normal laptop:

```text
video input -> manual selection -> identity profile -> guarded tracking
            -> state transitions -> overlay -> export
```

## Included

- One manually selected target
- Bounding-box tracking
- Local video, webcam, and OpenCV-compatible URL streams
- Protected original appearance reference
- Colour, template, shape, size, position, and motion evidence
- Kalman-based position prediction
- Conservative full-frame reacquisition
- Strong-evidence full-frame reacquisition after tracking failure
- Trajectory and state-transition recording
- Desktop interface and project-local logging
- Settings import, export, validation, and factory restore

## Explicitly deferred

- Point-prompt and mask refinement
- SAM 2 mask propagation
- YOLO detection-assisted selection
- BoT-SORT candidate identities
- Neural appearance embeddings
- Full-frame long-term visual search
- World-coordinate measurements
- Multiple simultaneous selected objects
- Guaranteed frame-accurate reverse playback

## Safety behavior

The MVP may lose a target. It must not silently replace it.

A local candidate can restore confirmed tracking only after:

1. Passing a motion gate.
2. Passing a minimum appearance gate.
3. Passing the combined identity score.
4. Beating the next candidate by the configured ambiguity margin.
5. Remaining spatially consistent for multiple frames.

When these conditions fail, the state remains `REACQUIRING` or becomes `LOST`.
`LOST` has no displayed location but continues a low-frequency full-frame
identity search while video processing remains active.

## Laptop expectation

The baseline targets 720p video on a modern laptop CPU. CSRT is deliberately
chosen for accuracy rather than maximum FPS. Lower the processing resolution in
`configs/default.yaml` when source video is large or CPU performance is limited.

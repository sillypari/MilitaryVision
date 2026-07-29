# Architecture

## Sources of evidence

Trackers and models never own the target identity. They only produce observations.

```text
VideoSource
    |
    v
TrackingEngine
    |-- ShortTermTracker
    |-- MotionModel
    |-- AppearanceModel
    |-- CandidateMatcher
    |
    v
TargetIdentity + TrackingStateMachine
    |
    +--> Trajectory
    +--> OverlayRenderer
    +--> SessionExporter
```

Only `TrackingEngine`, through the state machine, may declare an observation
confirmed.

## State dimensions

Tracking identity and media playback are separate:

```text
TrackingState: IDLE, SELECTING, INITIALIZING, LOCKED,
               OCCLUDED, REACQUIRING, LOST

PlaybackState: STOPPED, PLAYING, PAUSED, SEEKING, END_OF_STREAM

SourceState: CLOSED, OPENING, READY, RECONNECTING, ERROR
```

Pausing therefore does not erase whether the identity was locked or occluded.

## Identity memory

The original crop and histogram are immutable for the lifetime of a target.
Additional references may be captured only from confirmed, sharp, in-frame,
high-confidence observations. The original reference is never replaced.

## Reacquisition

The MVP searches the complete frame as soon as short-term tracking fails. During
local tracking, motion and the last confirmed position remain useful gates.
Full-frame scoring retains the hybrid appearance, motion, colour, shape, and size
model, but distant candidates receive a neutral motion prior. Distance therefore
cannot drive an otherwise valid identity match below the threshold; plausible
nearby motion contributes only a bounded tie-break. Full-frame matches require a
stronger appearance threshold, ambiguity separation, and multiple consecutive
confirmations before the short-term tracker is reinitialized.

For laptop performance, proposal generation searches a scaled copy of the whole
frame and uses the original plus the newest reference crop. The candidate box is
mapped back to processing coordinates, then appearance, colour, size, shape, and
motion are evaluated using the original processing frame. Search scaling changes
proposal cost, not the identity-acceptance rules or the search coverage.

Predicted trajectory points are recorded only while the state remains
`OCCLUDED` and the predicted box is still meaningfully visible. Once prediction
leaves the frame or the prediction window expires, the state changes to
`REACQUIRING` and the trajectory stops extending.

This mechanism intentionally prefers false negatives over false positive identity
switches. A future detector or embedding model can implement the same candidate
interface without changing state ownership.

## Configuration ownership

`configs/default.yaml` is the active profile. `configs/factory_defaults.yaml` is
the protected recovery profile. Imported and exported profiles use the complete
validated schema so no threshold silently falls back to an unrelated value.

CSRT exposes explicit `ACCURATE`, `BALANCED`, and `FAST` profiles. The factory
default is `BALANCED`; changing the profile is a visible configuration decision
and resets the active target.

## Coordinates and time

Boxes use `(x, y, width, height)` pixel coordinates. Trajectory coordinates use
the box center. Video presentation timestamps are used when available; otherwise
a monotonic processing timestamp is recorded. No world distance is calculated.

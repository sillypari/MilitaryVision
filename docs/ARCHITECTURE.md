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

Local-video timeline seeking is different from pausing. A seek introduces a
discontinuity in position and time, so the application clears active target,
motion, candidate-confirmation, and tracker state before displaying the requested
frame. Live cameras and streams do not expose random-access timeline controls.

## Identity memory

Identity memory is divided into two banks:

```text
Immutable anchor bank
    Exact user selection
    First strongly confirmed, sharp, in-frame observations

Rotating adaptive bank
    Later strongly confirmed scale, viewpoint, and lighting variations
```

The exact original crop and histogram are immutable for the lifetime of a
target. The configured number of early anchor observations are also protected
from memory rotation. Additional adaptive references may be captured only from
confirmed, sharp, in-frame, high-confidence observations.

Normal locked tracking uses `trusted_reference_weight` to adapt through gradual
appearance changes. Reacquisition has a separate original-anchor-heavy fusion
weight and mandatory anchor-similarity floor. A recent adaptive reference can
support reacquisition but cannot authorize it by itself.

When at least two immutable views exist, candidate appearance uses the strongest
configured number as a consensus rather than accepting the single best anchor.
Textured targets receive an additional ORB descriptor and RANSAC geometry gate.
When either crop lacks enough keypoints, the feature gate reports unavailable
and the remaining identity signals stay authoritative.

## Reacquisition

The MVP searches the complete frame as soon as short-term tracking fails. During
local tracking, motion and the last confirmed position remain useful gates.
Full-frame scoring retains the hybrid appearance, motion, colour, shape, and size
model, but distant candidates receive a neutral motion prior. Distance therefore
cannot drive an otherwise valid identity match below the threshold; plausible
nearby motion contributes only a bounded tie-break. Full-frame matches require
an immutable-anchor floor, a stronger combined appearance threshold, optional
feature geometry, ambiguity separation, and multiple positive confirmations
before the short-term tracker is reinitialized.

For laptop performance, proposal generation searches a scaled copy of the whole
frame. The exact original is always a proposal template. When adaptive memory is
available, one proposal slot is reserved for the newest verified view so large
scale or viewpoint changes can still be found; remaining slots use immutable
early anchors. The candidate box is mapped back to processing coordinates, then
appearance, colour, size, shape, and motion are evaluated using the original
processing frame. Adaptive proposal generation does not bypass anchor-heavy
identity acceptance. Search scaling changes proposal cost, not the
identity-acceptance rules or the search coverage.

Candidate diagnostics retain the strongest anchor similarity, adaptive
similarity, anchor-consensus score, feature matches and inlier ratio, combined
appearance, total score, and rejection reason. Logs are throttled during
prolonged searches while verified relocks are always recorded.

The live-first default scans every processed frame while `LOST`. Live capture
also requests a one-frame backend buffer to reduce stale-camera latency when the
installed backend supports it. A strong same-location candidate can survive a
short ambiguity grace window, but ambiguous frames do not increment identity
confirmation.

Predicted trajectory points are recorded only while the state remains
`OCCLUDED` and the predicted box is still meaningfully visible. Once prediction
leaves the frame or the prediction window expires, the state changes to
`REACQUIRING` and the trajectory stops extending.

After the bounded reacquisition window expires, `LOST` means there is no reliable
location, not that processing has stopped. The engine performs a configurable
low-frequency whole-frame search while remaining in `LOST`. A plausible match
transitions to `REACQUIRING`, restarts the verification window, and must earn the
same configured number of positive confirmations before `LOCKED`.

The first confirmed trajectory point after a lost interval starts a new segment.
Rendering and path-length calculation do not connect the last known position to
the reacquired position across unknown motion.

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

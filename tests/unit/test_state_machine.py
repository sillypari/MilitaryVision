import pytest

from persistent_tracker.domain.models import TrackingState
from persistent_tracker.tracking.state_machine import (
    InvalidStateTransition,
    TrackingStateMachine,
)


def transition(
    machine: TrackingStateMachine,
    state: TrackingState,
    frame: int,
) -> None:
    machine.transition(
        state,
        reason="test",
        frame_number=frame,
        timestamp=frame / 30.0,
    )


def test_identity_safe_occlusion_flow() -> None:
    machine = TrackingStateMachine()
    transition(machine, TrackingState.SELECTING, 0)
    transition(machine, TrackingState.INITIALIZING, 0)
    transition(machine, TrackingState.LOCKED, 0)
    transition(machine, TrackingState.OCCLUDED, 10)
    transition(machine, TrackingState.REACQUIRING, 20)
    transition(machine, TrackingState.LOCKED, 23)

    assert machine.state == TrackingState.LOCKED
    assert [item.new_state for item in machine.transitions] == [
        TrackingState.SELECTING,
        TrackingState.INITIALIZING,
        TrackingState.LOCKED,
        TrackingState.OCCLUDED,
        TrackingState.REACQUIRING,
        TrackingState.LOCKED,
    ]


def test_idle_cannot_silently_become_locked() -> None:
    machine = TrackingStateMachine()
    with pytest.raises(InvalidStateTransition):
        transition(machine, TrackingState.LOCKED, 0)


def test_lost_requires_reacquisition_or_manual_selection() -> None:
    machine = TrackingStateMachine()
    transition(machine, TrackingState.SELECTING, 0)
    transition(machine, TrackingState.INITIALIZING, 0)
    transition(machine, TrackingState.LOST, 1)
    with pytest.raises(InvalidStateTransition):
        transition(machine, TrackingState.LOCKED, 2)

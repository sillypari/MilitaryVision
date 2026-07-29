from __future__ import annotations

import logging

from persistent_tracker.domain.models import StateTransition, TrackingState

LOGGER = logging.getLogger(__name__)


class InvalidStateTransition(ValueError):
    """Raised when code attempts a transition that violates identity policy."""


class TrackingStateMachine:
    _allowed: dict[TrackingState, set[TrackingState]] = {
        TrackingState.IDLE: {TrackingState.SELECTING},
        TrackingState.SELECTING: {
            TrackingState.IDLE,
            TrackingState.INITIALIZING,
        },
        TrackingState.INITIALIZING: {
            TrackingState.IDLE,
            TrackingState.LOCKED,
            TrackingState.LOST,
        },
        TrackingState.LOCKED: {
            TrackingState.IDLE,
            TrackingState.SELECTING,
            TrackingState.OCCLUDED,
            TrackingState.REACQUIRING,
            TrackingState.LOST,
        },
        TrackingState.OCCLUDED: {
            TrackingState.IDLE,
            TrackingState.SELECTING,
            TrackingState.REACQUIRING,
            TrackingState.LOCKED,
            TrackingState.LOST,
        },
        TrackingState.REACQUIRING: {
            TrackingState.IDLE,
            TrackingState.SELECTING,
            TrackingState.LOCKED,
            TrackingState.LOST,
        },
        TrackingState.LOST: {
            TrackingState.IDLE,
            TrackingState.SELECTING,
            TrackingState.REACQUIRING,
            TrackingState.INITIALIZING,
        },
    }

    def __init__(self) -> None:
        self.state = TrackingState.IDLE
        self.transitions: list[StateTransition] = []

    def transition(
        self,
        new_state: TrackingState,
        *,
        reason: str,
        frame_number: int,
        timestamp: float,
    ) -> StateTransition | None:
        if new_state == self.state:
            return None
        if new_state not in self._allowed[self.state]:
            raise InvalidStateTransition(
                f"Cannot transition from {self.state.value} to {new_state.value}"
            )

        transition = StateTransition(
            frame_number=frame_number,
            timestamp=timestamp,
            previous_state=self.state,
            new_state=new_state,
            reason=reason,
        )
        self.state = new_state
        self.transitions.append(transition)
        LOGGER.info(
            "Tracking state transition frame=%s previous=%s new=%s reason=%s",
            frame_number,
            transition.previous_state.value,
            transition.new_state.value,
            reason,
        )
        return transition

    def reset(self, *, frame_number: int, timestamp: float, reason: str) -> None:
        if self.state != TrackingState.IDLE:
            self.transition(
                TrackingState.IDLE,
                reason=reason,
                frame_number=frame_number,
                timestamp=timestamp,
            )

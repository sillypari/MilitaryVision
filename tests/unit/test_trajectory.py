from persistent_tracker.domain.models import TrackingState, TrajectoryPoint
from persistent_tracker.tracking.trajectory import Trajectory


def point(x: float, predicted: bool) -> TrajectoryPoint:
    return TrajectoryPoint(
        frame_number=int(x),
        timestamp=x,
        x=x,
        y=0.0,
        width=10.0,
        height=10.0,
        confidence=1.0,
        state=TrackingState.OCCLUDED if predicted else TrackingState.LOCKED,
        predicted=predicted,
    )


def test_path_length_excludes_predicted_segments() -> None:
    trajectory = Trajectory(maximum_points=10)
    trajectory.append(point(0, False))
    trajectory.append(point(3, False))
    trajectory.append(point(6, True))
    trajectory.append(point(9, False))
    assert trajectory.path_length_pixels == 3.0


def test_trajectory_is_bounded() -> None:
    trajectory = Trajectory(maximum_points=2)
    trajectory.append(point(0, False))
    trajectory.append(point(1, False))
    trajectory.append(point(2, False))
    assert [item.x for item in trajectory.points] == [1, 2]

from __future__ import annotations

from persistent_tracker.domain.models import TrajectoryPoint


class Trajectory:
    def __init__(self, maximum_points: int) -> None:
        self.maximum_points = maximum_points
        self.points: list[TrajectoryPoint] = []

    def append(self, point: TrajectoryPoint) -> None:
        self.points.append(point)
        if len(self.points) > self.maximum_points:
            del self.points[: len(self.points) - self.maximum_points]

    def clear(self) -> None:
        self.points.clear()

    @property
    def path_length_pixels(self) -> float:
        total = 0.0
        previous: TrajectoryPoint | None = None
        for point in self.points:
            if previous is not None and not point.predicted and not previous.predicted:
                total += ((point.x - previous.x) ** 2 + (point.y - previous.y) ** 2) ** 0.5
            previous = point
        return total

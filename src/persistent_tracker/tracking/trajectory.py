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

    def visible_points(
        self,
        current_timestamp: float,
        lifetime_seconds: float,
    ) -> list[TrajectoryPoint]:
        """Return the recent display window without deleting export history."""
        if lifetime_seconds <= 0.0:
            return []
        cutoff = current_timestamp - lifetime_seconds
        return [point for point in self.points if point.timestamp >= cutoff]

    @property
    def path_length_pixels(self) -> float:
        total = 0.0
        previous: TrajectoryPoint | None = None
        for point in self.points:
            if (
                previous is not None
                and not point.segment_start
                and not point.predicted
                and not previous.predicted
            ):
                total += ((point.x - previous.x) ** 2 + (point.y - previous.y) ** 2) ** 0.5
            previous = point
        return total

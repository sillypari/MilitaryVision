from __future__ import annotations

import cv2
import numpy as np


class MotionModel:
    def __init__(self) -> None:
        self._filter = cv2.KalmanFilter(4, 2)
        self._filter.measurementMatrix = np.array(
            [[1, 0, 0, 0], [0, 1, 0, 0]],
            dtype=np.float32,
        )
        self._filter.processNoiseCov = np.diag([1.0, 1.0, 25.0, 25.0]).astype(
            np.float32
        )
        self._filter.measurementNoiseCov = np.eye(2, dtype=np.float32) * 4.0
        self._filter.errorCovPost = np.eye(4, dtype=np.float32)
        self._initialized = False
        self._last_step_timestamp: float | None = None
        self._last_measurement_timestamp: float | None = None
        self._last_velocity = (0.0, 0.0)
        self.velocity = (0.0, 0.0)
        self.acceleration = (0.0, 0.0)

    def initialize(self, center: tuple[float, float], timestamp: float) -> None:
        state = np.array(
            [[center[0]], [center[1]], [0.0], [0.0]],
            dtype=np.float32,
        )
        self._filter.statePost = state.copy()
        self._filter.statePre = state.copy()
        self._last_step_timestamp = timestamp
        self._last_measurement_timestamp = timestamp
        self._last_velocity = (0.0, 0.0)
        self.velocity = (0.0, 0.0)
        self.acceleration = (0.0, 0.0)
        self._initialized = True

    def predict(self, timestamp: float) -> tuple[float, float]:
        if not self._initialized:
            raise RuntimeError("Motion model must be initialized before prediction")
        previous = (
            self._last_step_timestamp
            if self._last_step_timestamp is not None
            else timestamp
        )
        delta = max(1e-3, min(1.0, timestamp - previous))
        self._filter.transitionMatrix = np.array(
            [[1, 0, delta, 0], [0, 1, 0, delta], [0, 0, 1, 0], [0, 0, 0, 1]],
            dtype=np.float32,
        )
        predicted = self._filter.predict()
        self._last_step_timestamp = timestamp
        self.velocity = (float(predicted[2, 0]), float(predicted[3, 0]))
        return float(predicted[0, 0]), float(predicted[1, 0])

    def correct(
        self,
        center: tuple[float, float],
        timestamp: float,
    ) -> tuple[float, float]:
        if not self._initialized:
            self.initialize(center, timestamp)
            return center

        measurement = np.array([[center[0]], [center[1]]], dtype=np.float32)
        corrected = self._filter.correct(measurement)
        previous_measurement = (
            self._last_measurement_timestamp
            if self._last_measurement_timestamp is not None
            else timestamp
        )
        measurement_delta = max(1e-3, timestamp - previous_measurement)
        new_velocity = (float(corrected[2, 0]), float(corrected[3, 0]))
        self.acceleration = (
            (new_velocity[0] - self._last_velocity[0]) / measurement_delta,
            (new_velocity[1] - self._last_velocity[1]) / measurement_delta,
        )
        self._last_velocity = new_velocity
        self.velocity = new_velocity
        self._last_measurement_timestamp = timestamp
        return float(corrected[0, 0]), float(corrected[1, 0])

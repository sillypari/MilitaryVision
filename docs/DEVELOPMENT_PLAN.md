# Development plan

## Phase 0: Contracts and identity rules

- Domain models and coordinate conventions
- Separate source, playback, and tracking states
- State-transition tests
- Confidence and candidate scoring tests
- Identity-memory update policy

## Phase 1: Laptop MVP

- Video, webcam, and stream input
- Confirmed box selection
- CSRT short-term tracker
- Kalman prediction
- Conservative full-frame reacquisition
- Full-frame reacquisition with multi-frame identity verification
- Professional PySide6 interface
- Trajectory, screenshot, JSON, CSV, and annotated-video export
- Validated settings page and reusable configuration templates
- Laptop-tuned CSRT profiles and scaled whole-frame proposal search

## Phase 2: Detector and learned appearance adapters

- YOLO candidate generator
- Detector-assisted selection
- General visual embedding adapter
- Local feature matching
- Camera motion estimation
- Evaluation against similar-object crossings

## Phase 3: Segmentation adapter

- SAM 2 point and box prompts
- Positive and negative refinement
- Mask propagation and mask-quality checks
- Mask centroid trajectory
- Drift-triggered re-prompting

## Phase 4: Production pipeline

- Dedicated capture and inference workers
- Bounded queues and latency metrics
- Robust RTSP reconnection
- Video timestamp synchronization
- ONNX, OpenVINO, or TensorRT adapters
- Packaging and hardware diagnostics

## Release gate

A feature does not improve the release if it increases wrong-object
reacquisitions. Identity-switch and false-reacquisition counts are release-blocking
metrics.

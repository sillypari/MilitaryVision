# SAM 2 requirements and integration plan

This document describes the requirements for adding Meta SAM 2 to
MilitaryVision. SAM 2 is not installed or required by the current MVP.

Requirements were checked against the official Meta SAM 2 repository on
2026-07-30.

## Official software requirements

Meta currently recommends:

- Linux
- Python 3.10 or newer
- PyTorch 2.5.1 or newer
- TorchVision 0.20.1 or newer, matched to the PyTorch build
- A CUDA toolkit matching the CUDA version used by PyTorch
- WSL with Ubuntu when the host operating system is Windows

The official installation guide is:

```text
https://github.com/facebookresearch/sam2/blob/main/INSTALL.md
```

The optional SAM 2 CUDA extension can be skipped with
`SAM2_BUILD_CUDA=0`. Image and video prediction can still run, but the
CUDA-based mask post-processing step that removes small holes and sprinkles is
disabled.

## Available SAM 2.1 models

| Model | Parameters | Intended trade-off |
|---|---:|---|
| `sam2.1_hiera_tiny` | 38.9 million | Best starting point for limited hardware |
| `sam2.1_hiera_small` | 46 million | Slightly stronger, moderately heavier |
| `sam2.1_hiera_base_plus` | 80.8 million | Higher quality and compute cost |
| `sam2.1_hiera_large` | 224.4 million | Highest quality and largest compute cost |

Meta's published video speeds were measured on an NVIDIA A100 with PyTorch
2.5.1 and CUDA 12.4 using model compilation. Those figures should not be used as
an estimate for laptop CPU or integrated-graphics performance.

The official model table and checkpoints are available at:

```text
https://github.com/facebookresearch/sam2#model-description
```

## Current laptop assessment

The current development laptop has:

```text
CPU: 12th Gen Intel Core i3-1215U
RAM: 15.7 GB
GPU: Intel UHD integrated graphics
CUDA: unavailable
```

This laptop is suitable for the current OpenCV tracker. It is not a practical
target for real-time SAM 2 video propagation because the official accelerated
path requires an NVIDIA CUDA GPU.

CPU-only experimentation may be possible with the CUDA extension disabled and
the Tiny checkpoint, but it should be treated as offline or low-frame-rate
testing. It should not replace the current real-time tracking path on this
machine.

## Practical development recommendation

For useful local SAM 2 video development, use:

- Windows 11 with WSL 2 and Ubuntu, or native Linux
- An NVIDIA RTX GPU supported by the installed PyTorch CUDA build
- At least 8 GB of VRAM as a practical starting target
- At least 16 GB of system RAM
- SSD storage with several gigabytes free for PyTorch, CUDA libraries,
  checkpoints, and caches
- `sam2.1_hiera_tiny` for the first integration

The VRAM and storage guidance above is a MilitaryVision engineering
recommendation, not an official minimum published by Meta. Actual memory use
depends on model size, frame resolution, video length, object count, memory
offloading, and compilation settings.

## Recommended MilitaryVision architecture

SAM 2 should be an optional segmentation adapter, not the owner of target
identity.

```text
User point or box prompt
    |
    v
SAM 2 initial mask
    |
    v
SAM 2 video mask propagation
    |
    +--> mask confidence and centroid
    |
    v
TrackingEngine identity checks
    |
    +--> appearance memory
    +--> motion consistency
    +--> ambiguity rejection
    +--> state machine
```

Integration rules:

- Run SAM 2 in a separate inference worker so UI capture and rendering do not
  block.
- Keep inference queues bounded and drop stale live frames.
- Preserve the original target crop and mask.
- Do not let a propagated mask silently replace the internal target identity.
- Do not update identity memory from low-confidence or occluded masks.
- Fall back to the current box tracker when the SAM 2 worker is unavailable.
- Make the SAM 2 dependency optional so the CPU MVP remains easy to install.
- Start with box prompts, then add positive and negative point refinement.

## Suggested development sequence

1. Build and benchmark a separate SAM 2.1 Tiny proof of concept on CUDA.
2. Add a typed `Segmenter` interface without changing `TrackingEngine`
   ownership.
3. Generate an initial mask from the confirmed selection box.
4. Propagate masks asynchronously through video frames.
5. Add mask quality, fragmentation, shrinkage, and boundary checks.
6. Use the mask centroid as an additional trajectory signal.
7. Add point-based positive and negative refinement to the UI.
8. Benchmark latency and identity switches before enabling it by default.

Do not install SAM 2 into the current MVP environment until a compatible CUDA
machine or a deliberately accepted CPU-only experiment is available.

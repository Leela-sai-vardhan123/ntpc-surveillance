"""
GPU Configuration & Optimization
Handles device selection, half-precision, and inference optimization.
"""

import torch
import logging

logger = logging.getLogger(__name__)


def get_device() -> str:
    """Auto-select best available device."""
    if torch.cuda.is_available():
        device = "cuda"
        gpu_name = torch.cuda.get_device_name(0)
        vram = torch.cuda.get_device_properties(0).total_memory / 1e9
        logger.info(f"[GPU] Using CUDA — {gpu_name} ({vram:.1f} GB VRAM)")
    else:
        device = "cpu"
        logger.info("[GPU] CUDA not available — using CPU")
    return device


def optimize_model(model, device: str, half_precision: bool = False):
    """
    Apply GPU optimizations to a YOLO model.
    half_precision: FP16 — doubles throughput on NVIDIA GPUs.
    """
    model.to(device)
    if half_precision and device == "cuda":
        model.half()
        logger.info("[GPU] FP16 half-precision enabled")
    # Fuse Conv+BN layers for faster inference
    try:
        model.fuse()
        logger.info("[GPU] Layer fusion applied")
    except Exception:
        pass
    return model


def warmup(model, device: str, imgsz: int = 640, n: int = 3):
    """
    Run dummy inference to warm up GPU kernels.
    Avoids slow first-frame inference.
    """
    import numpy as np
    dummy = np.zeros((imgsz, imgsz, 3), dtype=np.uint8)
    for _ in range(n):
        model(dummy, verbose=False, device=device)
    logger.info(f"[GPU] Warmup complete ({n} iterations)")


def log_gpu_stats():
    """Log current GPU memory usage."""
    if torch.cuda.is_available():
        allocated = torch.cuda.memory_allocated(0) / 1e9
        reserved  = torch.cuda.memory_reserved(0) / 1e9
        logger.info(f"[GPU] Memory — Allocated: {allocated:.2f}GB | Reserved: {reserved:.2f}GB")

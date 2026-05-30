"""
DeepSORT Tracker
Replaces basic SORT with appearance-feature-based tracking.
Gives stable IDs even through occlusions — critical for speed estimation.

Install: pip install deep-sort-realtime
"""

import logging
import numpy as np

logger = logging.getLogger(__name__)


class DeepSORTTracker:
    """
    Wrapper around deep_sort_realtime for clean integration
    with our YOLOv8 detection pipeline.
    """

    def __init__(self, max_age: int = 30, n_init: int = 3,
                 max_cosine_distance: float = 0.4, device: str = "cpu"):
        """
        max_age             : frames to keep a lost track alive
        n_init              : frames before a track is confirmed
        max_cosine_distance : appearance similarity threshold (lower = stricter)
        device              : 'cuda' or 'cpu' for appearance extractor
        """
        try:
            from deep_sort_realtime.deepsort_tracker import DeepSort
            self._tracker = DeepSort(
                max_age=max_age,
                n_init=n_init,
                max_cosine_distance=max_cosine_distance,
                nn_budget=100,
                embedder_gpu=(device == "cuda"),
            )
            self.available = True
            logger.info("[DeepSORT] Tracker initialized successfully")
        except ImportError:
            logger.warning(
                "[DeepSORT] deep-sort-realtime not installed — "
                "falling back to YOLO built-in tracker. "
                "Run: pip install deep-sort-realtime"
            )
            self._tracker = None
            self.available = False

    def update(self, detections: list, frame: np.ndarray) -> list:
        """
        detections: list of (bbox_ltwh, confidence, class_name)
            bbox_ltwh = [left, top, width, height]
        frame:      current BGR frame (for appearance embedding)

        Returns: list of Track objects with .track_id and .to_ltrb()
        """
        if not self.available or self._tracker is None:
            return []

        if not detections:
            self._tracker.update_tracks([], frame=frame)
            return []

        tracks = self._tracker.update_tracks(detections, frame=frame)
        confirmed = [t for t in tracks if t.is_confirmed()]
        return confirmed

    @staticmethod
    def yolo_to_deepsort(boxes) -> list:
        """
        Convert YOLO result boxes to DeepSORT input format.
        Returns list of ([l, t, w, h], confidence, class_name)
        """
        detections = []
        for box in boxes:
            x1, y1, x2, y2 = map(float, box.xyxy[0])
            conf  = float(box.conf.item())
            cls   = int(box.cls.item())
            w, h  = x2 - x1, y2 - y1
            detections.append(([x1, y1, w, h], conf, str(cls)))
        return detections

    @staticmethod
    def ltrb(track) -> tuple:
        """Extract (x1, y1, x2, y2) from a confirmed DeepSORT track."""
        coords = track.to_ltrb()
        return tuple(map(int, coords))

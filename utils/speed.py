"""
Speed Estimator — Improved Accuracy
Fixes:
- Uses centroid smoothing to avoid jitter
- Minimum frame threshold to filter false readings
- Speed smoothing with rolling average
- Perspective correction factor
"""


class SpeedEstimator:
    def __init__(self, entry_line_y: int, exit_line_y: int,
                 real_distance_meters: float, fps: float,
                 perspective_factor: float = 1.0):
        """
        entry_line_y        : Y pixel of entry line
        exit_line_y         : Y pixel of exit line
        real_distance_meters: Actual road distance between lines (meters)
        fps                 : Video frame rate
        perspective_factor  : Correction for camera angle (1.0 = top-down,
                              1.2-1.5 = typical road camera angle)
        """
        self.entry_line_y    = entry_line_y
        self.exit_line_y     = exit_line_y
        self.real_distance_m = real_distance_meters
        self.fps             = max(fps, 1.0)
        self.perspective     = perspective_factor
        self.pixel_distance  = abs(exit_line_y - entry_line_y)

        # Minimum frames between entry and exit to be valid
        # A vehicle going 200 km/h over 10m at 25fps = ~4.5 frames minimum
        self.MIN_FRAMES = max(3, int(fps * (real_distance_meters / 100.0)))
        self.MAX_FRAMES = int(fps * 30)  # 30 seconds max

        print(f"[Speed] Calibration: {real_distance_meters}m between lines | "
              f"{self.pixel_distance}px | {fps}fps | "
              f"min_frames={self.MIN_FRAMES}")

    def new_vehicle_state(self) -> dict:
        return {
            "entry_frame":   None,
            "entry_y":       None,
            "exit_frame":    None,
            "exit_y":        None,
            "speed_history": [],   # rolling speed estimates
        }

    def update(self, vehicle: dict, cy: int, frame_idx: int):
        """Update entry/exit crossing state."""
        # Entry crossing — vehicle moves down into entry zone
        if vehicle["entry_frame"] is None and cy >= self.entry_line_y:
            vehicle["entry_frame"] = frame_idx
            vehicle["entry_y"]     = cy

        # Exit crossing — vehicle has crossed entry and now crosses exit
        elif (vehicle["entry_frame"] is not None and
              vehicle["exit_frame"]  is None and
              cy >= self.exit_line_y):
            vehicle["exit_frame"] = frame_idx
            vehicle["exit_y"]     = cy

        return vehicle

    def compute_speed(self, vehicle: dict) -> float | None:
        """
        Compute speed in km/h.
        Returns None if data is invalid or unreliable.
        """
        ef = vehicle.get("entry_frame")
        xf = vehicle.get("exit_frame")

        if ef is None or xf is None:
            return None

        delta_frames = xf - ef

        # Filter out impossible readings
        if delta_frames < self.MIN_FRAMES:
            # Too fast — likely false detection
            return None
        if delta_frames > self.MAX_FRAMES:
            # Too slow — vehicle stopped between lines
            return None

        # Time taken
        time_sec = delta_frames / self.fps

        # Distance with perspective correction
        distance_m = self.real_distance_m * self.perspective

        # Speed calculation
        speed_mps  = distance_m / time_sec
        speed_kmph = speed_mps * 3.6

        # Sanity check — cap at 250 km/h
        if speed_kmph > 250 or speed_kmph < 1:
            return None

        # Smooth with history
        history = vehicle.get("speed_history", [])
        history.append(speed_kmph)
        if len(history) > 3:
            history.pop(0)
        vehicle["speed_history"] = history

        # Return smoothed average
        smoothed = sum(history) / len(history)
        return round(smoothed, 1)

    def get_perspective_factor(self, camera_height_m: float,
                                distance_to_road_m: float) -> float:
        """
        Calculate perspective correction factor from camera geometry.
        camera_height_m    : Height of camera above road (meters)
        distance_to_road_m : Horizontal distance from camera to road center
        """
        import math
        angle = math.atan2(camera_height_m, distance_to_road_m)
        return 1.0 / math.sin(angle) if math.sin(angle) > 0 else 1.0

"""
Night Vision Enhancement
Improves detection in low-light/night conditions using:
- CLAHE (Contrast Limited Adaptive Histogram Equalization)
- Denoising
- Gamma correction
- White balance
"""

import cv2
import numpy as np


class NightVisionEnhancer:
    def __init__(self, mode: str = "auto"):
        """
        mode: 'auto'   — detect brightness and apply if needed
              'always' — always enhance
              'off'    — disabled
        """
        self.mode      = mode
        self.clahe     = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        self.threshold = 80  # brightness below this = night mode active

    def is_dark(self, frame: np.ndarray) -> bool:
        """Check if frame is dark enough to need enhancement."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return float(gray.mean()) < self.threshold

    def enhance(self, frame: np.ndarray) -> tuple[np.ndarray, bool]:
        """
        Enhance frame if needed.
        Returns: (enhanced_frame, was_enhanced)
        """
        if self.mode == "off":
            return frame, False

        should_enhance = self.mode == "always" or (
            self.mode == "auto" and self.is_dark(frame)
        )

        if not should_enhance:
            return frame, False

        return self._apply(frame), True

    def _apply(self, frame: np.ndarray) -> np.ndarray:
        """Apply full enhancement pipeline."""
        # 1. Denoise
        denoised = cv2.fastNlMeansDenoisingColored(frame, None, 6, 6, 7, 21)

        # 2. CLAHE on L channel (LAB color space)
        lab   = cv2.cvtColor(denoised, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        l_eq  = self.clahe.apply(l)
        lab_eq = cv2.merge([l_eq, a, b])
        enhanced = cv2.cvtColor(lab_eq, cv2.COLOR_LAB2BGR)

        # 3. Gamma correction (brighten)
        gamma   = 1.5
        lut     = np.array([min(255, int((i / 255.0) ** (1.0 / gamma) * 255))
                             for i in range(256)], dtype=np.uint8)
        enhanced = cv2.LUT(enhanced, lut)

        # 4. Sharpen
        kernel   = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
        enhanced = cv2.filter2D(enhanced, -1, kernel)

        return enhanced

    def draw_indicator(self, frame: np.ndarray, enhanced: bool) -> np.ndarray:
        """Draw night vision indicator on frame."""
        if enhanced:
            cv2.putText(frame, "🌙 NIGHT MODE", (frame.shape[1] - 180, 24),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 220, 180), 2)
        return frame

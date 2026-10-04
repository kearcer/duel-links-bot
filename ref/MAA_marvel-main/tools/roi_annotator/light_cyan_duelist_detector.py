from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

import cv2
import numpy as np


@dataclass(frozen=True)
class LightCyanDetection:
    """One light-cyan region in image coordinates."""

    x: int
    y: int
    width: int
    height: int
    area: int
    score: float

    @property
    def center(self) -> tuple[int, int]:
        return (self.x + self.width // 2, self.y + self.height // 2)

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["center"] = list(self.center)
        return value


class LightCyanDuelistDetector:
    """Detect light-cyan duelist markers without writing debug images.

    The detector intentionally returns candidate regions, rather than claiming a
    character identity.  A caller can use the candidate center as the click
    point or apply a separate world/duelist policy.
    """

    def __init__(
        self,
        *,
        hue: tuple[int, int] = (75, 105),
        saturation: tuple[int, int] = (35, 255),
        value: tuple[int, int] = (120, 255),
        min_area: int = 6,
        max_area: int | None = None,
        min_score: float = 0.35,
    ) -> None:
        if not 0 <= hue[0] <= hue[1] <= 179:
            raise ValueError("hue must be within 0..179")
        if not 0 <= saturation[0] <= saturation[1] <= 255:
            raise ValueError("saturation must be within 0..255")
        if not 0 <= value[0] <= value[1] <= 255:
            raise ValueError("value must be within 0..255")
        if min_area < 1 or (max_area is not None and max_area < min_area):
            raise ValueError("invalid component area limits")
        if not 0 <= min_score <= 1:
            raise ValueError("min_score must be within 0..1")
        self.hue = hue
        self.saturation = saturation
        self.value = value
        self.min_area = min_area
        self.max_area = max_area
        self.min_score = min_score

    @staticmethod
    def _array(image: Any) -> np.ndarray:
        if isinstance(image, (str, Path)):
            image = cv2.imdecode(np.fromfile(str(image), dtype=np.uint8), cv2.IMREAD_COLOR)
            if image is None:
                raise ValueError("image could not be loaded")
            return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        if hasattr(image, "convert"):
            image = np.asarray(image.convert("RGB"))
        else:
            image = np.asarray(image)
        if image.ndim != 3 or image.shape[2] < 3 or image.shape[0] == 0 or image.shape[1] == 0:
            raise ValueError("image must be a non-empty RGB image")
        return image[:, :, :3].astype(np.uint8, copy=False)

    @staticmethod
    def _clip_roi(roi: dict[str, int] | tuple[int, int, int, int] | None, width: int, height: int) -> tuple[int, int, int, int]:
        if roi is None:
            return 0, 0, width, height
        if isinstance(roi, dict):
            x, y, rw, rh = (int(roi[key]) for key in ("x", "y", "width", "height"))
        else:
            x, y, rw, rh = map(int, roi)
        if rw <= 0 or rh <= 0:
            raise ValueError("ROI dimensions must be positive")
        left, top = max(0, x), max(0, y)
        right, bottom = min(width, x + rw), min(height, y + rh)
        if right <= left or bottom <= top:
            raise ValueError("ROI is outside the image")
        return left, top, right, bottom

    def detect(self, image: Any, roi: dict[str, int] | tuple[int, int, int, int] | None = None) -> list[LightCyanDetection]:
        rgb = self._array(image)
        height, width = rgb.shape[:2]
        left, top, right, bottom = self._clip_roi(roi, width, height)
        hsv = cv2.cvtColor(rgb[top:bottom, left:right], cv2.COLOR_RGB2HSV)
        mask = cv2.inRange(
            hsv,
            np.array((self.hue[0], self.saturation[0], self.value[0]), dtype=np.uint8),
            np.array((self.hue[1], self.saturation[1], self.value[1]), dtype=np.uint8),
        )
        count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
        detections: list[LightCyanDetection] = []
        for label in range(1, count):
            area = int(stats[label, cv2.CC_STAT_AREA])
            if area < self.min_area or (self.max_area is not None and area > self.max_area):
                continue
            component = labels == label
            mean_saturation = float(hsv[:, :, 1][component].mean()) / 255
            mean_value = float(hsv[:, :, 2][component].mean()) / 255
            score = mean_saturation * mean_value
            if score < self.min_score:
                continue
            x = left + int(stats[label, cv2.CC_STAT_LEFT])
            y = top + int(stats[label, cv2.CC_STAT_TOP])
            detections.append(LightCyanDetection(x, y, int(stats[label, cv2.CC_STAT_WIDTH]), int(stats[label, cv2.CC_STAT_HEIGHT]), area, round(score, 4)))
        return sorted(detections, key=lambda item: (-item.area, item.y, item.x))

    def detect_roi(self, image: Any, manager: Any, name: str) -> list[LightCyanDetection]:
        array = self._array(image)
        return self.detect(array, manager.get_scaled_rect(name, array.shape[1], array.shape[0]))


def detect_light_cyan_duelists(image: Any, roi: dict[str, int] | tuple[int, int, int, int] | None = None, **kwargs: Any) -> list[LightCyanDetection]:
    return LightCyanDuelistDetector(**kwargs).detect(image, roi)


__all__ = ["LightCyanDetection", "LightCyanDuelistDetector", "detect_light_cyan_duelists"]

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

import cv2
import numpy as np


@dataclass(frozen=True)
class LightCyanDetection:
    x: int
    y: int
    width: int
    height: int
    area: int
    radius: float = 0.0
    circularity: float = 0.0
    score: float = 0.0
    light_cyan_ratio: float = 0.0
    dark_blue_ratio: float = 0.0
    yellow_ratio: float = 0.0
    center_cyan_ratio: float = 0.0
    cyan_sector_count: int = 0
    shape: str = "circle"
    reason: str = "accepted"

    @property
    def center(self) -> tuple[int, int]:
        return (self.x + self.width // 2, self.y + self.height // 2)

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["center"] = list(self.center)
        return value


class LightCyanDuelistDetector:
    """Detect circular light-cyan duelist avatar rings using shared in-memory CV logic."""

    def __init__(
        self,
        *,
        hue: tuple[int, int] = (88, 100),
        saturation: tuple[int, int] = (100, 255),
        value: tuple[int, int] = (150, 255),
        min_radius: int = 18,
        max_radius: int = 48,
        min_score: float = 0.78,
        min_ring_cyan_ratio: float = 0.30,
        max_center_cyan_ratio: float = 0.12,
        dark_blue_hue: tuple[int, int] = (103, 125),
        dark_blue_saturation_min: int = 100,
        dark_blue_value_min: int = 110,
        dark_blue_limit: float = 0.25,
        yellow_hue: tuple[int, int] = (15, 32),
        yellow_saturation_min: int = 90,
        yellow_value_min: int = 120,
        yellow_limit: float = 0.20,
        sector_count: int = 24,
        min_cyan_sectors: int = 16,
        circle_threshold: float = 0.70,
        min_circle_score: float | None = None,
        min_area: int | None = None,
    ) -> None:
        self.hue, self.saturation, self.value = tuple(hue), tuple(saturation), tuple(value)
        self.min_radius, self.max_radius = int(min_radius), int(max_radius)
        self.min_score = float(min_score)
        self.min_ring_cyan_ratio = float(min_ring_cyan_ratio)
        self.max_center_cyan_ratio = float(max_center_cyan_ratio)
        self.dark_blue_hue = tuple(dark_blue_hue)
        self.dark_blue_saturation_min = int(dark_blue_saturation_min)
        self.dark_blue_value_min = int(dark_blue_value_min)
        self.dark_blue_limit = float(dark_blue_limit)
        self.yellow_hue = tuple(yellow_hue)
        self.yellow_saturation_min = int(yellow_saturation_min)
        self.yellow_value_min = int(yellow_value_min)
        self.yellow_limit = float(yellow_limit)
        self.sector_count = int(sector_count)
        self.min_cyan_sectors = int(min_cyan_sectors)
        self.circle_threshold = float(circle_threshold if min_circle_score is None else min_circle_score)
        self._legacy_min_area = min_area
        for low, high, limit, name in (
            (*self.hue, 179, "hue"),
            (*self.saturation, 255, "saturation"),
            (*self.value, 255, "value"),
            (*self.dark_blue_hue, 179, "dark_blue_hue"),
            (*self.yellow_hue, 179, "yellow_hue"),
        ):
            if not 0 <= low <= high <= limit:
                raise ValueError(f"invalid {name} limits")
        if self.min_radius < 2 or self.max_radius < self.min_radius:
            raise ValueError("invalid radius limits")
        if self.sector_count <= 0 or self.min_cyan_sectors < 0:
            raise ValueError("invalid sector limits")

    @staticmethod
    def _array(image: Any) -> np.ndarray:
        if isinstance(image, (str, Path)):
            image = cv2.imdecode(np.fromfile(str(image), dtype=np.uint8), cv2.IMREAD_COLOR)
            if image is None:
                raise ValueError("image could not be loaded")
            return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        if hasattr(image, "convert"):
            image = np.asarray(image.convert("RGB"))
        image = np.asarray(image)
        if image.ndim != 3 or image.shape[2] < 3 or not image.shape[0] or not image.shape[1]:
            raise ValueError("image must be a non-empty RGB image")
        return image[:, :, :3].astype(np.uint8, copy=False)

    @staticmethod
    def _clip_roi(roi: dict[str, int] | tuple[int, int, int, int] | None, width: int, height: int) -> tuple[int, int, int, int]:
        if roi is None:
            return 0, 0, width, height
        if isinstance(roi, dict):
            x, y, rw, rh = (int(roi[k]) for k in ("x", "y", "width", "height"))
        else:
            x, y, rw, rh = map(int, roi)
        left, top, right, bottom = max(0, x), max(0, y), min(width, x + rw), min(height, y + rh)
        if right <= left or bottom <= top:
            raise ValueError("ROI is outside the image")
        return left, top, right, bottom

    def _masks(self, hsv: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
        light = (h >= self.hue[0]) & (h <= self.hue[1]) & (s >= self.saturation[0]) & (v >= self.value[0])
        dark = (h >= self.dark_blue_hue[0]) & (h <= self.dark_blue_hue[1]) & (s >= self.dark_blue_saturation_min) & (v >= self.dark_blue_value_min)
        yellow = (h >= self.yellow_hue[0]) & (h <= self.yellow_hue[1]) & (s >= self.yellow_saturation_min) & (v >= self.yellow_value_min)
        return light, dark, yellow

    def _ring_stats(self, hsv: np.ndarray, cx: int, cy: int, radius: float) -> tuple[float, float, float, float, int]:
        height, width = hsv.shape[:2]
        yy, xx = np.ogrid[:height, :width]
        dx, dy = xx - cx, yy - cy
        distance = np.sqrt(dx * dx + dy * dy)
        ring = (distance >= radius * 0.60) & (distance <= radius * 1.08)
        center = distance <= radius * 0.45
        light, dark, yellow = self._masks(hsv)
        ring_total = max(int(ring.sum()), 1)
        center_total = max(int(center.sum()), 1)
        angles = (np.arctan2(dy, dx) + np.pi) * self.sector_count / (2 * np.pi)
        sectors = angles.astype(np.int16).clip(0, self.sector_count - 1)
        covered = 0
        for sector in range(self.sector_count):
            sector_mask = ring & (sectors == sector)
            sector_total = int(sector_mask.sum())
            if sector_total and float((sector_mask & light).sum() / sector_total) >= 0.12:
                covered += 1
        return (
            float((ring & light).sum() / ring_total),
            float((ring & dark).sum() / ring_total),
            float((ring & yellow).sum() / ring_total),
            float((center & light).sum() / center_total),
            covered,
        )

    def _candidates(self, hsv: np.ndarray, gray: np.ndarray) -> list[tuple[int, int, float, float, str]]:
        blurred = cv2.medianBlur(gray, 5)
        circles = cv2.HoughCircles(
            blurred,
            cv2.HOUGH_GRADIENT,
            dp=1.1,
            minDist=max(12, self.min_radius * 1.4),
            param1=80,
            param2=18,
            minRadius=self.min_radius,
            maxRadius=self.max_radius,
        )
        result: list[tuple[int, int, float, float, str]] = []
        if circles is not None:
            result.extend((int(c[0]), int(c[1]), float(c[2]), 1.0, "hough") for c in np.round(circles[0]).astype(int))
        light, _, _ = self._masks(hsv)
        mask = (light.astype(np.uint8) * 255)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            area = cv2.contourArea(contour)
            if area <= 0:
                continue
            (x, y), radius = cv2.minEnclosingCircle(contour)
            if not self.min_radius <= radius <= self.max_radius:
                continue
            perimeter = cv2.arcLength(contour, True)
            if perimeter <= 0:
                continue
            circularity = float(min(1.0, 4 * np.pi * area / (perimeter * perimeter)))
            bx, by, bw, bh = cv2.boundingRect(contour)
            aspect_score = min(bw, bh) / max(bw, bh) if max(bw, bh) else 0.0
            approx = cv2.approxPolyDP(contour, 0.04 * perimeter, True)
            polygon_penalty = 0.25 if len(approx) == 6 else 0.0
            circle_score = max(0.0, circularity * 0.65 + aspect_score * 0.35 - polygon_penalty)
            result.append((round(x), round(y), float(radius), circle_score, "contour"))
        return result

    def _legacy_detect_detailed(self, rgb: np.ndarray, left: int, top: int, right: int, bottom: int) -> dict[str, Any]:
        hsv = cv2.cvtColor(rgb[top:bottom, left:right], cv2.COLOR_RGB2HSV)
        light, _, _ = self._masks(hsv)
        count, labels, stats, _ = cv2.connectedComponentsWithStats(light.astype(np.uint8) * 255, 8)
        detections = []
        for label in range(1, count):
            area = int(stats[label, cv2.CC_STAT_AREA])
            if self._legacy_min_area is not None and area < self._legacy_min_area:
                continue
            component = labels == label
            score = float(hsv[:, :, 1][component].mean() / 255 * hsv[:, :, 2][component].mean() / 255)
            x = left + int(stats[label, cv2.CC_STAT_LEFT])
            y = top + int(stats[label, cv2.CC_STAT_TOP])
            detections.append(LightCyanDetection(x, y, int(stats[label, cv2.CC_STAT_WIDTH]), int(stats[label, cv2.CC_STAT_HEIGHT]), area, 0.0, 0.0, round(score, 4)))
        return {"detections": sorted(detections, key=lambda item: (-item.area, item.y, item.x)), "candidates": detections, "rejected": [], "debug_preview": rgb.copy()}

    def detect_detailed(self, image: Any, roi: dict[str, int] | tuple[int, int, int, int] | None = None) -> dict[str, Any]:
        rgb = self._array(image)
        height, width = rgb.shape[:2]
        left, top, right, bottom = self._clip_roi(roi, width, height)
        if self._legacy_min_area is not None:
            return self._legacy_detect_detailed(rgb, left, top, right, bottom)

        crop = rgb[top:bottom, left:right]
        hsv = cv2.cvtColor(crop, cv2.COLOR_RGB2HSV)
        gray = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
        candidates: list[LightCyanDetection] = []
        rejected: list[LightCyanDetection] = []
        for cx, cy, radius, circle_score, shape in self._candidates(hsv, gray):
            if cx < radius or cy < radius or cx + radius >= crop.shape[1] or cy + radius >= crop.shape[0]:
                continue
            ring_cyan, dark_blue, yellow, center_cyan, sectors = self._ring_stats(hsv, cx, cy, radius)
            sector_score = min(1.0, sectors / max(self.min_cyan_sectors, 1))
            score = (
                min(1.0, ring_cyan / 0.45) * 0.42
                + max(0.0, 1.0 - center_cyan / max(self.max_center_cyan_ratio, 0.001)) * 0.24
                + max(0.0, 1.0 - dark_blue / max(self.dark_blue_limit, 0.001)) * 0.10
                + max(0.0, 1.0 - yellow / max(self.yellow_limit, 0.001)) * 0.08
                + circle_score * 0.11
                + sector_score * 0.05
            )
            x, y, box = round(cx - radius), round(cy - radius), round(radius * 2)
            reason = "accepted"
            if ring_cyan < self.min_ring_cyan_ratio:
                reason = "REJECT: LOW_RING_CYAN"
            elif center_cyan > self.max_center_cyan_ratio:
                reason = "REJECT: HIGH_CENTER_CYAN"
            elif dark_blue > ring_cyan or dark_blue > self.dark_blue_limit:
                reason = "REJECT: DARK_BLUE"
            elif yellow > ring_cyan or yellow > self.yellow_limit:
                reason = "REJECT: YELLOW"
            elif circle_score < self.circle_threshold:
                reason = "REJECT: LOW_CIRCLE_SCORE"
            elif score < self.min_score:
                reason = "REJECT: LOW_SCORE"
            item = LightCyanDetection(
                left + x,
                top + y,
                box,
                box,
                int(round(np.pi * radius * radius)),
                round(radius, 2),
                round(circle_score, 4),
                round(score, 4),
                round(ring_cyan, 4),
                round(dark_blue, 4),
                round(yellow, 4),
                round(center_cyan, 4),
                sectors,
                shape,
                reason,
            )
            (candidates if reason == "accepted" else rejected).append(item)

        candidates.sort(key=lambda item: item.score, reverse=True)
        selected: list[LightCyanDetection] = []
        for item in candidates:
            if any((item.center[0] - other.center[0]) ** 2 + (item.center[1] - other.center[1]) ** 2 < (min(item.radius, other.radius) * 0.8) ** 2 for other in selected):
                rejected.append(LightCyanDetection(**{**asdict(item), "reason": "REJECT: DUPLICATE"}))
            else:
                selected.append(item)

        debug = rgb.copy()
        for item, color in [(item, (40, 220, 60)) for item in selected] + [(item, (240, 100, 30)) for item in rejected]:
            cx, cy = item.center
            cv2.circle(debug, (cx, cy), max(2, round(item.radius)), color, 2)
            label = "TARGET" if item.reason == "accepted" else item.reason
            cv2.putText(debug, f"{label} {item.score:.2f}", (max(0, item.x), max(12, item.y)), cv2.FONT_HERSHEY_SIMPLEX, 0.38, color, 1, cv2.LINE_AA)
        all_candidates = candidates + rejected
        rejected_reasons = [item.reason for item in rejected]
        stats = {
            "all_candidates": len(all_candidates),
            "size_pass": len(all_candidates),
            "color_pass": len(all_candidates) - sum(reason in {"REJECT: LOW_RING_CYAN", "REJECT: HIGH_CENTER_CYAN", "REJECT: DARK_BLUE", "REJECT: YELLOW"} for reason in rejected_reasons),
            "circle_pass": len(all_candidates) - sum(reason in {"REJECT: LOW_RING_CYAN", "REJECT: HIGH_CENTER_CYAN", "REJECT: DARK_BLUE", "REJECT: YELLOW", "REJECT: LOW_CIRCLE_SCORE"} for reason in rejected_reasons),
            "final_targets": len(selected),
        }
        return {"detections": selected, "candidates": all_candidates, "rejected": rejected, "stats": stats, "debug_preview": debug}

    def detect(self, image: Any, roi: dict[str, int] | tuple[int, int, int, int] | None = None) -> list[LightCyanDetection]:
        return self.detect_detailed(image, roi)["detections"]

    def detect_roi(self, image: Any, manager: Any, name: str) -> list[LightCyanDetection]:
        array = self._array(image)
        return self.detect(array, manager.get_scaled_rect(name, array.shape[1], array.shape[0]))


def detect_light_cyan_duelists(image: Any, roi: dict[str, int] | tuple[int, int, int, int] | None = None, **kwargs: Any) -> list[LightCyanDetection]:
    return LightCyanDuelistDetector(**kwargs).detect(image, roi)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", nargs="+", type=Path, required=True)
    args = parser.parse_args()
    detector = LightCyanDuelistDetector()
    for sample in args.samples:
        result = detector.detect_detailed(sample)
        print(f"{sample.name}: {len(result['detections'])} detections; {len(result['rejected'])} rejected")

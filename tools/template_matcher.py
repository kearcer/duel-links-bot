from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np


class TemplateMatcher:
    """Match an ROI template against its scaled fixed ROI in a screenshot."""

    def __init__(self, grayscale: bool = True) -> None:
        self.grayscale = grayscale

    @staticmethod
    def _image(value: Any) -> np.ndarray:
        if isinstance(value, np.ndarray):
            image = value.copy()
        elif isinstance(value, (str, Path)):
            image = cv2.imdecode(np.fromfile(str(value), dtype=np.uint8), cv2.IMREAD_COLOR)
        else:
            image = cv2.cvtColor(np.asarray(value.convert("RGB")), cv2.COLOR_RGB2BGR)
        if image is None or image.size == 0:
            raise ValueError("image could not be loaded")
        return image

    @staticmethod
    def _matcher_config(config: dict[str, Any]) -> dict[str, Any]:
        matcher = dict(config.get("matcher", {}))
        matcher.setdefault("method", "TM_CCOEFF_NORMED")
        matcher.setdefault("grayscale", config.get("grayscale", True))
        matcher.setdefault("threshold", config.get("threshold", 0.85))
        matcher.setdefault("search_mode", config.get("search_mode", "fixed_roi"))
        return matcher

    def match(
        self,
        screenshot: Any,
        template: Any,
        config: dict[str, Any],
        threshold: float | None = None,
    ) -> dict[str, Any]:
        matcher = self._matcher_config(config)
        if matcher["method"] != "TM_CCOEFF_NORMED":
            raise ValueError("only TM_CCOEFF_NORMED is supported in the first template matcher")
        if matcher["search_mode"] != "fixed_roi":
            raise ValueError("only fixed_roi search mode is supported in the first template matcher")

        screen = self._image(screenshot)
        needle = self._image(template)
        original_template_size = {"width": int(needle.shape[1]), "height": int(needle.shape[0])}
        base = config.get("base_resolution", {})
        base_width = int(base.get("width", screen.shape[1]))
        base_height = int(base.get("height", screen.shape[0]))
        if base_width <= 0 or base_height <= 0:
            raise ValueError("base resolution must be positive")

        scale_x = screen.shape[1] / base_width
        scale_y = screen.shape[0] / base_height
        roi = config["roi"]
        x = round(int(roi["x"]) * scale_x)
        y = round(int(roi["y"]) * scale_y)
        width = max(1, round(int(roi["width"]) * scale_x))
        height = max(1, round(int(roi["height"]) * scale_y))
        x, y = max(0, x), max(0, y)
        right, bottom = min(screen.shape[1], x + width), min(screen.shape[0], y + height)
        search = screen[y:bottom, x:right]
        if search.size == 0:
            raise ValueError("scaled ROI is outside the screenshot")

        search_size = {"width": int(search.shape[1]), "height": int(search.shape[0])}
        target_size = (max(1, round(needle.shape[1] * scale_x)), max(1, round(needle.shape[0] * scale_y)))
        resized = target_size != (needle.shape[1], needle.shape[0])
        if resized:
            interpolation = cv2.INTER_AREA if target_size[0] < needle.shape[1] else cv2.INTER_LINEAR
            needle = cv2.resize(needle, target_size, interpolation=interpolation)
        if needle.shape[1] > search.shape[1] or needle.shape[0] > search.shape[0]:
            raise ValueError("scaled template is larger than the fixed ROI")

        grayscale = bool(matcher.get("grayscale", self.grayscale))
        haystack = cv2.cvtColor(search, cv2.COLOR_BGR2GRAY) if grayscale and search.ndim == 3 else search
        match_needle = cv2.cvtColor(needle, cv2.COLOR_BGR2GRAY) if grayscale and needle.ndim == 3 else needle
        result = cv2.matchTemplate(haystack, match_needle, cv2.TM_CCOEFF_NORMED)
        _, score, _, location = cv2.minMaxLoc(result)
        score = float(score)
        threshold = float(matcher.get("threshold", 0.85) if threshold is None else threshold)
        matched = score >= threshold
        match_location = {"x": x + location[0], "y": y + location[1]}
        click = config.get("click", {})
        if click.get("mode") == "none":
            click_point = None
        elif click.get("mode") == "custom" and "x" in click and "y" in click:
            click_point = {"x": round(int(click["x"]) * scale_x), "y": round(int(click["y"]) * scale_y)}
        else:
            click_point = {"x": match_location["x"] + needle.shape[1] // 2, "y": match_location["y"] + needle.shape[0] // 2}

        preview = screen.copy()
        color = (0, 200, 0) if matched else (0, 0, 255)
        cv2.rectangle(preview, (match_location["x"], match_location["y"]),
                      (match_location["x"] + needle.shape[1] - 1, match_location["y"] + needle.shape[0] - 1), color, 2)
        if click_point:
            cv2.drawMarker(preview, (click_point["x"], click_point["y"]), color, cv2.MARKER_CROSS, 14, 2)
        cv2.putText(preview, f"score={score:.4f} threshold={threshold:.4f} {'MATCH' if matched else 'NO MATCH'}", (8, 24),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2, cv2.LINE_AA)
        return {
            "matched": matched,
            "should_click": matched and click_point is not None,
            "score": score,
            "threshold": threshold,
            "match_location": match_location if matched else None,
            "best_location": match_location,
            "click_point": click_point if matched else None,
            "resized": resized,
            "original_template_size": original_template_size,
            "template_size": {"width": int(needle.shape[1]), "height": int(needle.shape[0])},
            "search_size": search_size,
            "grayscale": grayscale,
            "method": "TM_CCOEFF_NORMED",
            "mode": "fixed_roi",
            "debug_preview": preview,
        }

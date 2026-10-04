from __future__ import annotations

import json
import math
import re
import shutil
from pathlib import Path
from typing import Any


ROI_TYPES = {"ocr", "template", "color", "click"}
MATCH_MODES = {"contains", "equals", "regex", "number"}


LIGHT_CYAN_DEFAULTS = {
    "hue": [75, 105],
    "saturation": [35, 255],
    "value": [120, 255],
    "min_area": 6,
    "min_score": 0.35,
}


def scale_rect(rect: dict[str, int], base_width: int, base_height: int, current_width: int, current_height: int) -> dict[str, int]:
    """Scale a saved rectangle from its base resolution to the current resolution."""
    if base_width <= 0 or base_height <= 0:
        raise ValueError("base resolution must be positive")
    return {
        "x": round(rect["x"] * current_width / base_width),
        "y": round(rect["y"] * current_height / base_height),
        "width": round(rect["width"] * current_width / base_width),
        "height": round(rect["height"] * current_height / base_height),
    }


def _safe_name(name: str) -> str:
    name = name.strip()
    if not name:
        raise ValueError("ROI name cannot be empty")
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    if name in {".", ".."}:
        raise ValueError("invalid ROI name")
    return name


def _int(value: Any, field: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field} must be an integer") from error


class ROIManager:
    """Read and write named ROI records stored as one directory per ROI."""

    def __init__(self, root: str | Path = "ROI_DB") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, name: str) -> Path:
        return self.root / _safe_name(name)

    def names(self) -> list[str]:
        return sorted(
            directory.name
            for directory in self.root.iterdir()
            if directory.is_dir() and (directory / "config.json").is_file()
        )

    def load(self, name: str) -> dict[str, Any]:
        with (self.path(name) / "config.json").open("r", encoding="utf-8") as stream:
            return json.load(stream)

    def get_config(self, name: str) -> dict[str, Any]:
        return self.load(name)

    def get_rect(self, name: str) -> dict[str, int]:
        return dict(self.load(name)["roi"])

    def get_click_point(self, name: str) -> dict[str, int] | None:
        click = self.load(name).get("click", {})
        if click.get("mode") == "none":
            return None
        return {"x": int(click["x"]), "y": int(click["y"])}

    def get_scaled_rect(self, name: str, current_width: int, current_height: int) -> dict[str, int]:
        config = self.load(name)
        base = config["base_resolution"]
        return scale_rect(config["roi"], base["width"], base["height"], current_width, current_height)

    def get_scaled_click_point(self, name: str, current_width: int, current_height: int) -> dict[str, int] | None:
        config = self.load(name)
        click = self.get_click_point(name)
        if click is None:
            return None
        base = config["base_resolution"]
        return scaled_point(click, base["width"], base["height"], current_width, current_height)

    def get_color_detector(self, name: str) -> Any:
        config = self.load(name)
        if config.get("type") != "color":
            raise ValueError(f"ROI {name!r} is not a color ROI")
        settings = dict(config.get("color", {}))
        detector_name = settings.pop("detector", "light_cyan_duelist")
        if detector_name != "light_cyan_duelist":
            raise ValueError(f"unsupported color detector: {detector_name}")
        try:
            from tools.light_cyan_duelist_detector import LightCyanDuelistDetector
        except ImportError:
            from light_cyan_duelist_detector import LightCyanDuelistDetector
        return LightCyanDuelistDetector(**settings)

    def save(
        self,
        name: str,
        screenshot: Any,
        rect: dict[str, int],
        roi_type: str,
        threshold: float = 0.85,
        click_mode: str = "center",
        click_point: tuple[int, int] | None = None,
        expected_text: str = "",
        match_mode: str = "contains",
        scene: str = "",
        tags: list[str] | None = None,
        overwrite: bool = False,
    ) -> Path:
        from PIL import Image, ImageDraw, ImageFont

        name = _safe_name(name)
        roi_type = roi_type.lower().strip()
        if roi_type not in ROI_TYPES:
            raise ValueError(f"unsupported ROI type: {roi_type}")
        match_mode = match_mode.lower().strip()
        if match_mode not in MATCH_MODES:
            raise ValueError(f"unsupported OCR match mode: {match_mode}")
        image = screenshot.convert("RGB")
        width, height = image.size
        x, y = _int(rect.get("x"), "x"), _int(rect.get("y"), "y")
        roi_width, roi_height = _int(rect.get("width"), "width"), _int(rect.get("height"), "height")
        if roi_width <= 0 or roi_height <= 0 or x < 0 or y < 0 or x + roi_width > width or y + roi_height > height:
            raise ValueError("ROI must be a positive rectangle inside the screenshot")
        if click_mode not in {"center", "custom", "none"}:
            raise ValueError("click mode must be center, custom, or none")
        if click_mode == "center":
            click_x, click_y = x + roi_width // 2, y + roi_height // 2
        elif click_mode == "custom":
            if click_point is None:
                raise ValueError("custom click mode requires a click point")
            click_x, click_y = map(int, click_point)
            if not (0 <= click_x < width and 0 <= click_y < height):
                raise ValueError("custom click point must be inside the screenshot")
        else:
            click_x = click_y = None

        directory = self.path(name)
        if directory.exists() and not overwrite:
            raise FileExistsError(name)
        directory.mkdir(parents=True, exist_ok=True)
        image.save(directory / "screenshot.png")
        image.crop((x, y, x + roi_width, y + roi_height)).save(directory / "roi.png")
        preview = image.copy()
        draw = ImageDraw.Draw(preview)
        draw.rectangle((x, y, x + roi_width - 1, y + roi_height - 1), outline="red", width=max(2, round(width / 360)))
        label = f"{name} [{roi_type}]"
        try:
            draw.text((x + 4, max(0, y - 20)), label, fill="red", stroke_width=2, stroke_fill="white")
        except (OSError, ValueError):
            draw.text((x + 4, max(0, y - 20)), label, fill="red")
        if click_x is not None:
            radius = max(4, round(width / 180))
            draw.ellipse((click_x - radius, click_y - radius, click_x + radius, click_y + radius), fill="blue", outline="white")
        preview.save(directory / "preview.png")

        config: dict[str, Any] = {
            "name": name,
            "base_resolution": {"width": width, "height": height},
            "roi": {"x": x, "y": y, "width": roi_width, "height": roi_height},
            "type": roi_type,
            "threshold": float(threshold),
            "click": {"mode": click_mode},
            "scene": scene.strip(),
            "tags": tags or [],
        }
        if click_x is not None:
            config["click"].update({"x": click_x, "y": click_y})
        if roi_type == "ocr":
            config["ocr"] = {"expected_text": expected_text, "match_mode": match_mode}
        if roi_type == "color":
            config["color"] = {"detector": "light_cyan_duelist", **LIGHT_CYAN_DEFAULTS}
        (directory / "config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return directory


def scaled_point(point: dict[str, int], base_width: int, base_height: int, current_width: int, current_height: int) -> dict[str, int]:
    return scale_rect({"x": point["x"], "y": point["y"], "width": 0, "height": 0}, base_width, base_height, current_width, current_height) | {"x": round(point["x"] * current_width / base_width), "y": round(point["y"] * current_height / base_height)}

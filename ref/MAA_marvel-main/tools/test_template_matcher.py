from __future__ import annotations

import cv2
import numpy as np

from template_matcher import TemplateMatcher


def main() -> None:
    screen = np.zeros((80, 120, 3), dtype=np.uint8)
    pattern = np.zeros((15, 25, 3), dtype=np.uint8)
    pattern[:, :12] = (40, 180, 240)
    cv2.circle(pattern, (18, 7), 5, (220, 40, 80), -1)
    screen[30:45, 50:75] = pattern
    template = pattern.copy()
    config = {"roi": {"x": 45, "y": 25, "width": 35, "height": 25}, "base_resolution": {"width": 120, "height": 80}, "threshold": 0.99, "click": {"mode": "center"}}
    matcher = TemplateMatcher()
    assert matcher.match(screen, template, config)["matched"]
    assert not matcher.match(np.zeros_like(screen), template, config)["matched"]
    assert matcher.match(cv2.resize(screen, (240, 160)), template, config)["resized"]
    print("template matcher self-check passed")


if __name__ == "__main__":
    main()

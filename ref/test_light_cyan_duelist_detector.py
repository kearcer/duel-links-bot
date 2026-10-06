from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from light_cyan_duelist_detector import LightCyanDuelistDetector, detect_light_cyan_duelists


class LightCyanDuelistDetectorTests(unittest.TestCase):
    def test_detects_light_cyan_components_in_roi(self) -> None:
        image = np.zeros((100, 140, 3), dtype=np.uint8)
        image[20:30, 30:45] = (120, 220, 235)
        image[60:66, 100:108] = (110, 200, 230)
        detections = detect_light_cyan_duelists(image, roi=(10, 10, 120, 70), min_area=10)
        self.assertEqual([(d.x, d.y, d.width, d.height) for d in detections], [(30, 20, 15, 10), (100, 60, 8, 6)])
        self.assertEqual(detections[0].center, (37, 25))

    def test_rejects_gray_and_outside_roi(self) -> None:
        image = np.zeros((40, 40, 3), dtype=np.uint8)
        image[5:15, 5:15] = (180, 180, 180)
        image[25:35, 25:35] = (120, 220, 235)
        self.assertEqual(LightCyanDuelistDetector(min_area=5).detect(image, (0, 0, 20, 20)), [])

    def test_roi_manager_scaling(self) -> None:
        image = np.zeros((200, 200, 3), dtype=np.uint8)
        image[40:60, 40:60] = (120, 220, 235)
        class Manager:
            def get_scaled_rect(self, name, width, height):
                self.name = name
                return {"x": 20, "y": 20, "width": 40, "height": 40}
        manager = Manager()
        result = LightCyanDuelistDetector(min_area=10).detect_roi(image, manager, "duelist")
        self.assertEqual(len(result), 1)
        self.assertEqual(manager.name, "duelist")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from pathlib import Path
import json
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from agent.maa_compat import AgentServer, Context, CustomAction, JRecognitionType, JOCR
from agent.runtime.commands import parse_json_object
from agent.runtime.diagnostics import DIAGNOSTICS
from agent.runtime.store import STORE


DEFAULT_PACKAGE_NAME = "jp.konami.duellinks"
AREAS = ("Gate", "Duel", "Shop", "Studio")
AREA_LABELS = {
    0: ("gate", "决斗", "gate"),
    1: ("duel", "决斗", "duel"),
    2: ("shop", "商店", "shop"),
    3: ("studio", "工作室", "studio"),
}
BOTTOM_NAV_ROI = (0, 1035, 720, 245)
AREA_TAB_ROIS = (
    (0, 1035, 180, 245),
    (180, 1035, 180, 245),
    (360, 1035, 180, 245),
    (540, 1035, 180, 245),
)
NAV_REFERENCE_PATH = Path(__file__).resolve().parents[2] / "assets" / "resource" / "template" / "duel_links" / "bottom_nav.png"
LOOT_ID = 99

DUELISTS_BY_WORLD: dict[int, tuple[int, ...]] = {
    0: (1, 2, 3, 6, 7, 8, 13, 14, 15, 16, 17, 18, 19),
    1: (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13),
    4: (1, 2, 6, 7, 8, 13, 14, 15, 16, 17, 18, 19, 23, 24, 25, 26, 27, 28),
    5: (2, 6, 7, 14, 15, 18, 19, 29),
    7: (2, 3, 6, 7, 8, 13, 14, 15, 16, 17, 18, 22),
}
DEFAULT_DUELISTS = (1, 2, 3, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19)

OBJECT_COLORS: dict[int, tuple[str, tuple[int, ...]]] = {
    1: ("Alyssa", (0xF9E7D5, 0xF5D1B5, 0xFFE4C7, 0xFFE2C8, 0xFFE3CA)),
    2: ("Nick", (0xEBC29E, 0xEBC29E, 0xEDC8A1)),
    3: ("Emma", (0xC79574, 0xEDBE9B, 0xF6E2D5, 0x765752)),
    4: ("Zachary", (0xDBB59C, 0xDBB8A0, 0xDCBAA4, 0xFFEBD2)),
    5: ("Alexis", (0x675A34, 0xECCC7A, 0xBDA862, 0xB5A164)),
    6: ("Ashley", (0xEECCBB,)),
    7: ("Vagabond", (0xE5C399, 0xDFC599, 0xE6C399, 0xE8C699, 0xE5C499, 0xE5BEA1)),
    8: ("Jay", (0xEECA9B, 0xEEC3A4, 0xEEC3A1, 0xEBC6A0, 0xEECB9D, 0xEEBE9E, 0x664744)),
    9: ("Logan", (0xFCD8B1, 0xFCDBAF, 0xFFDCAB, 0xFDD4B0, 0xFFDAAA, 0xFBDAB0, 0xFCD9AB, 0xFBDAAB)),
    10: ("Madison", (0xFFE8D2, 0xFFE6D3, 0xFDEEDC, 0xFFE6D5, 0xFFE5D8, 0xFFE2D9, 0xFFEDD4, 0xFFE8DC)),
    11: ("Evan", (0xFEDBAD, 0xF6DCAA, 0xFDDDAA, 0xFEDCAE, 0xFCD9AE, 0xF8D6B2, 0xFADAAD, 0xFFDDAB)),
    12: ("Aster", (0xFFE9CC, 0xFFE5D0, 0xFFE9CC)),
    13: ("Jesse", (0xF7D6AC, 0xFBDEB0, 0xFEDCAA, 0xF7D5AA, 0xF8D4AA, 0xF0CBA0, 0xFCD1A9, 0xF4D1AA, 0xF9D6AA)),
    14: ("Mai", (0xFFDDBB,)),
    15: ("David", (0xEEC09E, 0xEBBEA7, 0xEEC79E, 0xEEC3A1)),
    16: ("Bakura", (0xD3A08F, 0xCCA988, 0xCCA688, 0xCCA088, 0xCCA588, 0xCCA188, 0xCC9F88, 0xCCA788, 0xCCA787)),
    17: ("Josh", (0xEEC89D, 0xE8CBA3, 0xEEBFA6, 0xE7C59A, 0xEDCAA1, 0xF6CCA3, 0xEEC5A0, 0xECC098, 0xEEC6A6)),
    18: ("Odin", (0xA37053, 0xA97051, 0xA27050, 0xA26D4D)),
    19: ("Anzu", (0xBD9A67, 0xC19977, 0xBD9977, 0xC49970, 0xBB906C, 0xBB996B, 0xBB966B)),
    20: ("Roa", (0xBBE089, 0xF7FFE3, 0xBFDD8C, 0xEFDDBC, 0xF2E3CF, 0xFEFEFA, 0x81A153, 0xD4AF9A)),
    21: ("Celestia", (0xF0EEA8, 0xFBFBE1, 0x1EAC9D, 0xFFFF8D, 0xF1EEDC, 0xBBAB54, 0xF2F2AA, 0xF4F1AA, 0x121313)),
    22: ("Nail", (0x6EB1DA, 0x73CDD7, 0x73CCCD, 0x142429, 0x74CDCC, 0x77CCD6)),
    23: ("Yuya", (0x336944, 0x48BF72, 0xEECCAA, 0xB56533, 0x74B6CE)),
    24: ("Dennis Event", (0xC66A59, 0xD55151, 0xE5DDBB, 0xBB4444, 0xC4B3AA)),
    25: ("Emmeline", (0xEED0BB, 0x2A0B0B, 0x4D6FA8, 0x2C4466)),
    26: ("Gong Strong", (0x873533, 0xE3BB99, 0x3B4647, 0x8F979A, 0xCF8B7A)),
    27: ("Margareth", (0x55472D, 0xD7C3B5, 0x34476E, 0x8D8585, 0x574C34, 0x89794E)),
    # The old AutoIt database had duplicate Case 28; keep the later Shay entry because AutoIt would make it unreachable.
    28: ("Shay", (0xDDB596, 0x558894, 0x2B4752, 0x222C3C, 0x812B33, 0x725E4B, 0xCEBBAA, 0x33445D)),
    29: ("Bravo", (0x7FC25E, 0xC7C7C8, 0xDEBD57, 0xE5426B, 0x453E3D, 0xEECCB4, 0x23889F)),
    LOOT_ID: ("Loot", (0xFF6600, 0xFF7700, 0xFF8700, 0xFF5700)),
}


@dataclass
class DuelLinksRuntimeState:
    package_name: str = DEFAULT_PACKAGE_NAME
    world: int = 0
    start_area: int = 0
    current_area: int = 0
    loop_areas: bool = True
    enable_clicks: bool = True
    color_tolerance: int = 24
    scan_step: int = 2
    last_event: str = "not_started"
    last_node: str = ""
    duelist_index: int = 0
    events: list[dict[str, Any]] = field(default_factory=list)


STATE = DuelLinksRuntimeState()


def _bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on", "enable", "enabled"}:
        return True
    if normalized in {"0", "false", "no", "off", "disable", "disabled"}:
        return False
    return default


def _custom_param(argv: CustomAction.RunArg) -> dict[str, Any]:
    raw = getattr(argv, "custom_action_param", None)
    if raw in (None, ""):
        return {}
    return parse_json_object(raw)


def _image_shape(image: Any) -> tuple[int, int] | None:
    shape = getattr(image, "shape", None)
    if not shape or len(shape) < 2:
        return None
    height = int(shape[0])
    width = int(shape[1])
    if height <= 0 or width <= 0:
        return None
    return width, height


def _matches_expected_shape(
    shape: tuple[int, int],
    expected_width: int,
    expected_height: int,
) -> bool:
    width, height = shape
    if width == expected_width and height == expected_height:
        return True
    actual_ratio = width / height
    expected_ratio = expected_width / expected_height
    return abs(actual_ratio - expected_ratio) <= 0.02 and height >= width


def _ocr_results(detail: Any | None) -> list[Any]:
    if detail is None:
        return []
    filtered = list(getattr(detail, "filtered_results", []))
    return filtered or list(getattr(detail, "all_results", []))


def _ocr_texts(context: Context, image: Any, roi: tuple[int, int, int, int]) -> list[str]:
    try:
        detail = context.run_recognition_direct(
            JRecognitionType.OCR,
            JOCR(roi=roi, threshold=0.08, only_rec=True),
            image,
        )
    except Exception as error:
        _record("area_ocr_failed", roi=roi, error=str(error))
        return []
    return [
        str(getattr(result, "text", "")).strip().lower()
        for result in _ocr_results(detail)
        if str(getattr(result, "text", "")).strip()
    ]


def _area_from_texts(texts: list[str]) -> int | None:
    joined = " ".join(texts)
    for area, (_, chinese, english) in AREA_LABELS.items():
        if english in joined or chinese in joined:
            return area
    return None


def _area_template_score(image: Any, area: int) -> float:
    """Compare a live bottom-tab crop with the supplied 720x1280 reference crop."""
    try:
        from PIL import Image
        import io

        reference = Image.open(NAV_REFERENCE_PATH).convert("RGB")
        pixels = np.asarray(image)
        if pixels.ndim != 3 or pixels.shape[0] < 1280 or pixels.shape[1] < 720:
            return 0.0
        live = Image.fromarray(pixels[:1280, :720, :3]).convert("RGB")
        left, top, width, height = AREA_TAB_ROIS[area]
        live_crop = np.asarray(live.crop((left, top, left + width, top + height)), dtype=np.float32)
        ref_crop = np.asarray(reference.crop((left, top, left + width, top + height)), dtype=np.float32)
        return float(np.mean(np.abs(live_crop - ref_crop)))
    except Exception:
        return 0.0


def _detect_area(context: Context, image: Any) -> int | None:
    texts = _ocr_texts(context, image, BOTTOM_NAV_ROI)
    area = _area_from_texts(texts)
    if area is not None:
        _record("area_detected", method="ocr", area=AREAS[area], texts=texts)
        return area
    scores = [_area_template_score(image, index) for index in range(4)]
    if scores and min(scores) < 55:
        area = min(range(4), key=lambda index: scores[index])
        _record("area_detected", method="template", area=AREAS[area], scores=[round(score, 1) for score in scores])
        return area
    _record("area_unknown", texts=texts, template_scores=[round(score, 1) for score in scores])
    return None


def _switch_area(context: Context, target: int) -> bool:
    try:
        controller = context.tasker.controller
        left, top, width, height = AREA_TAB_ROIS[target]
        job = controller.post_click(left + width // 2, top + height // 2).wait()
        if not getattr(job, "succeeded", True):
            return False
        time.sleep(0.8)
        _record("area_switched", area=AREAS[target], x=left + width // 2, y=top + height // 2)
        return True
    except Exception as error:
        _record("area_switch_failed", area=AREAS[target], error=str(error))
        return False
def _positive_int(value: Any, default: int, *, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


def _rgb(color: int) -> tuple[int, int, int]:
    return (color >> 16) & 0xFF, (color >> 8) & 0xFF, color & 0xFF


def _duelist_ids(world: int) -> tuple[int, ...]:
    return DUELISTS_BY_WORLD.get(world, DEFAULT_DUELISTS)


def _search_roi(width: int, height: int) -> tuple[int, int, int, int]:
    # Old AutoIt excluded side bars and UI chrome.  In portrait Android the only
    # generally safe invariant before real template resources is: avoid the top
    # status/header area and bottom navigation/action bar.
    return 0, int(height * 0.12), width, int(height * 0.86)


def _color_score(pixels: np.ndarray, x: int, y: int, target: tuple[int, int, int], tolerance: int) -> int:
    radius = 5
    left = max(0, x - radius)
    right = min(pixels.shape[1], x + radius + 1)
    top = max(0, y - radius)
    bottom = min(pixels.shape[0], y + radius + 1)
    region = pixels[top:bottom, left:right, :3].astype(np.int16)
    delta = np.abs(region - np.array(target, dtype=np.int16))
    return int(np.count_nonzero(np.all(delta <= tolerance, axis=2)))


def _best_color_spot(
    image: Any,
    colors: tuple[int, ...],
    *,
    tolerance: int,
    step: int,
) -> tuple[int, int, int] | None:
    try:
        pixels = np.asarray(image)
    except Exception:
        return None
    if pixels.ndim != 3 or pixels.shape[2] < 3:
        return None
    height, width = pixels.shape[:2]
    left, top, right, bottom = _search_roi(width, height)
    targets = tuple(_rgb(color) for color in colors)
    best: tuple[int, int, int] | None = None
    for target in targets:
        target_array = np.array(target, dtype=np.int16)
        sample = pixels[top:bottom:step, left:right:step, :3].astype(np.int16)
        delta = np.abs(sample - target_array)
        hits = np.argwhere(np.all(delta <= tolerance, axis=2))
        for row, col in hits[:200]:
            x = left + int(col) * step
            y = top + int(row) * step
            score = _color_score(pixels, x, y, target, tolerance)
            if best is None or score > best[2]:
                best = (x, y, score)
    if best is None or best[2] < 2:
        return None
    return best


def _record(event: str, **detail: Any) -> None:
    STATE.last_event = event
    payload = {"event": event, "time": time.time(), **detail}
    STATE.events.append(payload)
    print(
        "[DuelLinksDecision] "
        + " ".join(f"{key}={value}" for key, value in payload.items() if key != "time"),
        flush=True,
    )


def _click(context: Context, x: int, y: int) -> bool:
    if not STATE.enable_clicks:
        return True
    try:
        context.tasker.controller.post_click(int(x), int(y)).wait()
        return True
    except Exception as error:
        _record("click_failed", x=x, y=y, error=str(error))
        return False


@AgentServer.custom_action("DuelLinksRecordState")
class DuelLinksRecordState(CustomAction):
    """Record Duel Links configuration and high-level state."""

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        del context
        values = _custom_param(argv)
        package_name = str(values.get("package_name", STATE.package_name)).strip()
        if package_name:
            STATE.package_name = package_name
        STATE.world = _positive_int(values.get("world"), STATE.world, minimum=0, maximum=9)
        STATE.start_area = _positive_int(values.get("start_area"), STATE.start_area, minimum=0, maximum=3)
        STATE.current_area = _positive_int(values.get("current_area"), STATE.current_area, minimum=0, maximum=3)
        STATE.loop_areas = _bool(values.get("loop_areas"), STATE.loop_areas)
        STATE.enable_clicks = _bool(values.get("enable_clicks"), STATE.enable_clicks)
        STATE.color_tolerance = _positive_int(values.get("color_tolerance"), STATE.color_tolerance, minimum=0, maximum=80)
        STATE.scan_step = _positive_int(values.get("scan_step"), STATE.scan_step, minimum=1, maximum=8)
        event = str(values.get("event", "state"))
        STATE.last_node = str(getattr(argv, "node_name", ""))
        _record(
            event,
            package=STATE.package_name,
            world=STATE.world,
            start_area=STATE.start_area,
            current_area=STATE.current_area,
            loop=STATE.loop_areas,
            clicks=STATE.enable_clicks,
            node=STATE.last_node,
        )
        return True


@AgentServer.custom_action("DuelLinksStreetDuelStep")
class DuelLinksStreetDuelStep(CustomAction):
    """Run one migrated Street_duel decision step on the current visible area."""

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        values = _custom_param(argv)
        if values:
            DuelLinksRecordState().run(context, argv)
        try:
            image = context.tasker.controller.post_screencap().get(wait=True)
        except Exception as error:
            _record("screencap_failed", error=str(error))
            return False

        shape = _image_shape(image)
        if shape is None:
            _record("screencap_empty")
            return False

        detected_area = _detect_area(context, image)
        if detected_area is None:
            _record("area_navigation_blocked", target_area=AREAS[STATE.current_area])
            return False
        if detected_area != STATE.current_area:
            _record(
                "area_navigation_needed",
                detected_area=AREAS[detected_area],
                target_area=AREAS[STATE.current_area],
            )
            return _switch_area(context, STATE.current_area)

        loot_name, loot_colors = OBJECT_COLORS[LOOT_ID]
        loot = _best_color_spot(
            image,
            loot_colors,
            tolerance=STATE.color_tolerance,
            step=STATE.scan_step,
        )
        if loot is not None:
            x, y, score = loot
            _record("loot_detected", name=loot_name, x=x, y=y, score=score, size=f"{shape[0]}x{shape[1]}")
            _click(context, x, y)
            time.sleep(0.8)
            return True

        duelist_ids = _duelist_ids(STATE.world)
        for offset in range(len(duelist_ids)):
            index = (STATE.duelist_index + offset) % len(duelist_ids)
            duelist_id = duelist_ids[index]
            name, colors = OBJECT_COLORS[duelist_id]
            spot = _best_color_spot(
                image,
                colors,
                tolerance=STATE.color_tolerance,
                step=STATE.scan_step,
            )
            if spot is None:
                continue
            x, y, score = spot
            STATE.duelist_index = index
            _record(
                "duelist_detected",
                id=duelist_id,
                name=name,
                x=x,
                y=y,
                score=score,
                area=AREAS[STATE.current_area],
                size=f"{shape[0]}x{shape[1]}",
            )
            _click(context, x, y)
            time.sleep(1.0)
            STATE.duelist_index = (STATE.duelist_index + 1) % len(duelist_ids)
            return True

        area_name = AREAS[STATE.current_area]
        if STATE.current_area < 3:
            next_area = STATE.current_area + 1
        elif STATE.loop_areas:
            next_area = STATE.start_area
        else:
            next_area = STATE.current_area
        _record("area_clear", area=area_name, next_area=AREAS[next_area])
        if next_area != STATE.current_area:
            STATE.current_area = next_area
            _switch_area(context, next_area)
        return False


def _area_index(value: Any, default: int = 0) -> int:
    if isinstance(value, str):
        normalized = value.strip().lower()
        for index, name in enumerate(AREAS):
            if normalized in {name.lower(), str(index)}:
                return index
    return _positive_int(value, default, minimum=0, maximum=3)


def _image_rgb(image: Any) -> np.ndarray | None:
    try:
        pixels = np.asarray(image)
    except Exception:
        return None
    if pixels.ndim != 3 or pixels.shape[2] < 3:
        return None
    return pixels[:, :, :3].astype(np.uint8, copy=False)


def _detection_dir() -> Path:
    directory = Path.cwd() / "debug" / "duel_links_detections" / time.strftime("%Y%m%d-%H%M%S")
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _save_detection_image(pixels: np.ndarray, path: Path, x: int, y: int, size: int = 160) -> None:
    from PIL import Image

    height, width = pixels.shape[:2]
    half = size // 2
    left = max(0, x - half)
    top = max(0, y - half)
    right = min(width, x + half)
    bottom = min(height, y + half)
    Image.fromarray(pixels[top:bottom, left:right, :3], mode="RGB").save(path)


@AgentServer.custom_action("DuelLinksSwitchArea")
class DuelLinksSwitchArea(CustomAction):
    """Switch to one of the four fixed bottom navigation areas."""

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        values = _custom_param(argv)
        target = _area_index(values.get("area", values.get("target_area")), STATE.current_area)
        STATE.current_area = target
        STATE.last_node = str(getattr(argv, "node_name", ""))
        return _switch_area(context, target)


@AgentServer.custom_action("DuelLinksExportDuelistDetections")
class DuelLinksExportDuelistDetections(CustomAction):
    """Save the current screen and one crop for every color-matched duelist."""

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        values = _custom_param(argv)
        try:
            image = context.tasker.controller.post_screencap().get(wait=True)
        except Exception as error:
            _record("duelist_export_screencap_failed", error=str(error))
            return False
        pixels = _image_rgb(image)
        if pixels is None:
            _record("duelist_export_empty")
            return False

        detected_area = _detect_area(context, image)
        if detected_area is not None:
            STATE.current_area = detected_area
        output = _detection_dir()
        from PIL import Image

        Image.fromarray(pixels, mode="RGB").save(output / "full.png")
        tolerance = _positive_int(values.get("color_tolerance"), STATE.color_tolerance, minimum=0, maximum=80)
        step = _positive_int(values.get("scan_step"), STATE.scan_step, minimum=1, maximum=8)
        detections: list[dict[str, Any]] = []
        for duelist_id in _duelist_ids(STATE.world):
            name, colors = OBJECT_COLORS[duelist_id]
            spot = _best_color_spot(image, colors, tolerance=tolerance, step=step)
            if spot is None or spot[2] < 5:
                continue
            x, y, score = spot
            safe_name = "".join(char if char.isalnum() else "_" for char in name).strip("_") or str(duelist_id)
            crop_name = f"{AREAS[STATE.current_area]}_{duelist_id:02d}_{safe_name}_x{x}_y{y}_score{score}.png"
            _save_detection_image(pixels, output / crop_name, x, y)
            detections.append({"id": duelist_id, "name": name, "x": x, "y": y, "score": score, "crop": crop_name})

        metadata = {
            "area": AREAS[STATE.current_area],
            "area_index": STATE.current_area,
            "world": STATE.world,
            "size": {"width": int(pixels.shape[1]), "height": int(pixels.shape[0])},
            "detections": detections,
            "directory": str(output),
        }
        (output / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        _record("duelist_exported", area=AREAS[STATE.current_area], count=len(detections), directory=str(output))
        print(f"[DuelLinksDetections] directory={output} count={len(detections)}", flush=True)
        return True


@AgentServer.custom_action("DuelLinksOpenDetectionFolder")
class DuelLinksOpenDetectionFolder(CustomAction):
    """Open the newest exported detection directory on Windows."""

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        del context, argv
        root = Path.cwd() / "debug" / "duel_links_detections"
        if not root.exists():
            _record("duelist_folder_missing", directory=str(root))
            return False
        folders = sorted((path for path in root.iterdir() if path.is_dir()), key=lambda path: path.stat().st_mtime)
        target = folders[-1] if folders else root
        try:
            import os
            os.startfile(str(target))
        except Exception as error:
            _record("duelist_folder_open_failed", directory=str(target), error=str(error))
            return False
        _record("duelist_folder_opened", directory=str(target))
        return True
@AgentServer.custom_action("DuelLinksWarmupScreencap")
class DuelLinksWarmupScreencap(CustomAction):
    """Wait until the controller returns a portrait Duel Links frame."""

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        values = _custom_param(argv)
        timeout_ms = _positive_int(
            values.get("timeout_ms"),
            60000,
            minimum=1000,
            maximum=180000,
        )
        interval_ms = _positive_int(
            values.get("interval_ms"),
            1000,
            minimum=100,
            maximum=5000,
        )
        expected_width = _positive_int(
            values.get("expected_width"),
            720,
            minimum=1,
            maximum=4096,
        )
        expected_height = _positive_int(
            values.get("expected_height"),
            1280,
            minimum=1,
            maximum=4096,
        )
        started = time.monotonic()
        deadline = started + timeout_ms / 1000.0
        attempts = 0
        last_error = "not attempted"

        while True:
            attempts += 1
            try:
                image = context.tasker.controller.post_screencap().get(wait=True)
                shape = _image_shape(image)
                if shape is not None and _matches_expected_shape(
                    shape,
                    expected_width,
                    expected_height,
                ):
                    elapsed_ms = int((time.monotonic() - started) * 1000)
                    print(
                        "[DuelLinksWarmupScreencap] success "
                        f"attempts={attempts} elapsed_ms={elapsed_ms} "
                        f"size={shape[0]}x{shape[1]}",
                        flush=True,
                    )
                    return True
                last_error = (
                    "empty image" if shape is None else f"unexpected size {shape[0]}x{shape[1]}"
                )
            except Exception as error:
                last_error = str(error)

            now = time.monotonic()
            if now >= deadline:
                break
            time.sleep(min(interval_ms / 1000.0, max(0.0, deadline - now)))

        elapsed_ms = int((time.monotonic() - started) * 1000)
        detail = {
            "attempts": attempts,
            "elapsed_ms": elapsed_ms,
            "expected_size": f"{expected_width}x{expected_height}",
            "last_error": last_error,
        }
        print(
            "[DuelLinksWarmupScreencap] failed "
            f"attempts={attempts} elapsed_ms={elapsed_ms} error={last_error}",
            flush=True,
        )
        DIAGNOSTICS.emit(
            STORE.state_or_none(),
            event="incident",
            source="duel_links_warmup",
            reason="screencap_warmup_failed",
            node=str(getattr(argv, "node_name", "DuelLinksWarmupScreencap")),
            detail=detail,
        )
        return False

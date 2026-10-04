from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tkinter as tk
import numpy as np
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageDraw, ImageTk

try:
    from .roi_manager import ROIManager
    from .template_matcher import TemplateMatcher
except ImportError:
    from roi_manager import ROIManager
    from template_matcher import TemplateMatcher


TYPE_LABELS = {
    "ocr": "OCR",
    "template": "图片模板匹配",
    "color": "颜色/状态检测（兼容）",
    "light_cyan_duelist_detector": "浅青蓝色圆形决斗者",
    "click": "仅点击坐标",
}


class ROIApp:
    def __init__(self, root: tk.Tk, db: Path, image_path: Path | None = None, adb: str | None = None, device: str | None = None) -> None:
        self.root = root
        self.manager = ROIManager(db)
        self.adb = adb
        self.device = device
        self.image: Image.Image | None = None
        self.photo: ImageTk.PhotoImage | None = None
        self.canvas_scale = 1.0
        self.drag_start: tuple[int, int] | None = None
        self.rect_id: int | None = None
        self.selected_rect: dict[str, int] | None = None
        self.custom_click: tuple[int, int] | None = None
        self._build_ui()
        if image_path:
            self.load_image(image_path)
        elif adb:
            self.capture()
        self.refresh_list()

    def _build_ui(self) -> None:
        self.root.title("ROI 标注与管理工具")
        self.root.geometry("1200x820")
        self.root.minsize(900, 600)
        self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)
        toolbar = ttk.Frame(self.root, padding=6)
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="重新截图", command=self.capture).pack(side="left")
        ttk.Button(toolbar, text="加载截图", command=self.choose_image).pack(side="left", padx=5)
        ttk.Label(toolbar, text="拖动鼠标框选 ROI；右键可记录自定义点击点").pack(side="left", padx=12)

        main = ttk.PanedWindow(self.root, orient="horizontal")
        main.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        left = ttk.Frame(main)
        right = ttk.Frame(main, padding=8)
        main.add(left, weight=4)
        main.add(right, weight=1)

        self.canvas = tk.Canvas(left, background="#202124", cursor="crosshair", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _event: self._redraw())
        self.canvas.bind("<ButtonPress-1>", self.begin_roi)
        self.canvas.bind("<B1-Motion>", self.drag_roi)
        self.canvas.bind("<ButtonRelease-1>", self.end_roi)
        self.canvas.bind("<Button-3>", self.record_click)

        form = ttk.Frame(right)
        form.pack(fill="x")
        self.name_var = tk.StringVar()
        self.type_var = tk.StringVar(value="template")
        self.threshold_var = tk.StringVar(value="0.85")
        self.click_var = tk.StringVar(value="center")
        self.scene_var = tk.StringVar()
        self.tags_var = tk.StringVar()
        self.expected_var = tk.StringVar()
        self.match_var = tk.StringVar(value="contains")
        self.rect_var = tk.StringVar(value="未选择")
        self._field(form, "名称", self.name_var)
        ttk.Label(form, text="识别类型").pack(anchor="w", pady=(8, 2))
        type_box = ttk.Combobox(form, textvariable=self.type_var, state="readonly", values=list(TYPE_LABELS))
        type_box.pack(fill="x")
        type_box.bind("<<ComboboxSelected>>", lambda _event: self._toggle_ocr())
        self._field(form, "阈值", self.threshold_var)
        ttk.Label(form, text="点击方式").pack(anchor="w", pady=(8, 2))
        ttk.Combobox(form, textvariable=self.click_var, state="readonly", values=("center", "custom", "none")).pack(fill="x")
        self._field(form, "场景（可选）", self.scene_var)
        self._field(form, "标签（逗号分隔）", self.tags_var)
        self._field(form, "OCR 预期文本", self.expected_var)
        ttk.Label(form, text="OCR 匹配模式").pack(anchor="w", pady=(8, 2))
        ttk.Combobox(form, textvariable=self.match_var, state="readonly", values=("contains", "equals", "regex", "number")).pack(fill="x")
        ttk.Label(form, textvariable=self.rect_var, foreground="#555").pack(anchor="w", pady=(8, 2))
        ttk.Button(form, text="保存 ROI", command=self.save).pack(fill="x", pady=(10, 3))
        ttk.Button(form, text="删除当前 ROI", command=self.delete_current).pack(fill="x")
        self.validate_button = ttk.Button(form, text="验证当前模板/检测器", command=self.validate_current)
        self.validate_button.pack(fill="x", pady=(3, 0))

        ttk.Separator(right).pack(fill="x", pady=12)
        ttk.Label(right, text="已有 ROI").pack(anchor="w")
        self.listbox = tk.Listbox(right, exportselection=False)
        self.listbox.pack(fill="both", expand=True, pady=5)
        self.listbox.bind("<<ListboxSelect>>", self.load_selected)
        self.status = ttk.Label(right, text="等待截图", wraplength=240)
        self.status.pack(fill="x", pady=5)
        self._toggle_ocr()

    @staticmethod
    def _field(parent: ttk.Frame, label: str, variable: tk.StringVar) -> None:
        ttk.Label(parent, text=label).pack(anchor="w", pady=(8, 2))
        ttk.Entry(parent, textvariable=variable).pack(fill="x")

    def _toggle_ocr(self) -> None:
        if hasattr(self, "validate_button"):
            valid = self.type_var.get() in {"template", "color", "light_cyan_duelist_detector"} and self.name_var.get() in self.manager.names()
            self.validate_button.configure(state="normal" if valid else "disabled")

    def capture(self) -> None:
        if not self.adb:
            self.status.configure(text="未配置 ADB，请使用“加载截图”选择图片")
            self.choose_image()
            return
        try:
            self.set_image(self._capture_image())
            self.status.configure(text="截图成功")
        except (OSError, subprocess.SubprocessError, ValueError) as error:
            messagebox.showerror("截图失败", str(error))

    def _capture_image(self) -> Image.Image:
        if not self.adb:
            raise ValueError("未配置 ADB")
        command = [self.adb]
        if self.device:
            command += ["-s", self.device]
        command += ["exec-out", "screencap", "-p"]
        from io import BytesIO
        return Image.open(BytesIO(subprocess.check_output(command, timeout=15))).convert("RGB")

    def choose_image(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("图片", "*.png *.jpg *.jpeg"), ("所有文件", "*.*")])
        if path:
            self.load_image(Path(path))

    def load_image(self, path: Path) -> None:
        try:
            self.set_image(Image.open(path).convert("RGB"))
            self.status.configure(text=f"已加载 {path.name}")
        except OSError as error:
            messagebox.showerror("加载失败", str(error))

    def _load_latest_debug_image(self) -> None:
        candidates = sorted(
            Path.cwd().glob("debug/**/*.png"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        if candidates:
            self.load_image(candidates[0])

    def set_image(self, image: Image.Image) -> None:
        self.image = image
        self.selected_rect = None
        self.rect_var.set(f"原图：{image.width}×{image.height}，未选择 ROI")
        self._redraw()

    def _redraw(self) -> None:
        if self.image is None or not self.canvas.winfo_width() or not self.canvas.winfo_height():
            return
        scale = min((self.canvas.winfo_width() - 10) / self.image.width, (self.canvas.winfo_height() - 10) / self.image.height, 1.0)
        self.canvas_scale = max(scale, 0.01)
        shown = self.image.resize((round(self.image.width * self.canvas_scale), round(self.image.height * self.canvas_scale)))
        self.photo = ImageTk.PhotoImage(shown)
        self.canvas.delete("all")
        self.canvas.create_image(5, 5, image=self.photo, anchor="nw")
        if self.selected_rect:
            r = self.selected_rect
            self.canvas.create_rectangle(5 + r["x"] * self.canvas_scale, 5 + r["y"] * self.canvas_scale, 5 + (r["x"] + r["width"]) * self.canvas_scale, 5 + (r["y"] + r["height"]) * self.canvas_scale, outline="red", width=2)

    def _image_point(self, event: tk.Event) -> tuple[int, int]:
        if self.image is None:
            return 0, 0
        x = round((event.x - 5) / self.canvas_scale)
        y = round((event.y - 5) / self.canvas_scale)
        return max(0, min(self.image.width - 1, x)), max(0, min(self.image.height - 1, y))

    def begin_roi(self, event: tk.Event) -> None:
        if self.image is None:
            return
        self.drag_start = self._image_point(event)
        self.selected_rect = None
        self.rect_var.set(f"原图：{self.image.width}×{self.image.height}，绘制中")

    def drag_roi(self, event: tk.Event) -> None:
        if self.drag_start is None:
            return
        x, y = self._image_point(event)
        sx, sy = self.drag_start
        self.selected_rect = {"x": min(sx, x), "y": min(sy, y), "width": abs(x - sx), "height": abs(y - sy)}
        self.rect_var.set(f"x={self.selected_rect['x']} y={self.selected_rect['y']} w={self.selected_rect['width']} h={self.selected_rect['height']}")
        self._redraw()

    def end_roi(self, _event: tk.Event) -> None:
        self.drag_start = None

    def record_click(self, event: tk.Event) -> None:
        self.custom_click = self._image_point(event)
        self.click_var.set("custom")
        self.status.configure(text=f"自定义点击点：{self.custom_click[0]}, {self.custom_click[1]}")

    def save(self) -> None:
        if self.image is None or not self.selected_rect:
            messagebox.showwarning("无法保存", "请先加载截图并框选 ROI")
            return
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("无法保存", "请输入 ROI 名称")
            return
        exists = name in self.manager.names()
        overwrite = False
        if exists:
            answer = messagebox.askyesnocancel("ROI 已存在", "是：覆盖\n否：取消\n取消：取消保存")
            if answer is None or not answer:
                return
            overwrite = True
        try:
            threshold = float(self.threshold_var.get())
            tags = [tag.strip() for tag in self.tags_var.get().split(",") if tag.strip()]
            directory = self.manager.save(name, self.image, self.selected_rect, self.type_var.get(), threshold, self.click_var.get(), self.custom_click, self.expected_var.get(), self.match_var.get(), self.scene_var.get(), tags, overwrite)
        except (ValueError, FileExistsError, OSError) as error:
            messagebox.showerror("保存失败", str(error))
            return
        self.status.configure(text=f"已保存：{directory}")
        self.refresh_list()

    def refresh_list(self) -> None:
        self.listbox.delete(0, tk.END)
        for name in self.manager.names():
            self.listbox.insert(tk.END, name)

    def load_selected(self, _event: tk.Event) -> None:
        selection = self.listbox.curselection()
        if not selection:
            return
        name = self.listbox.get(selection[0])
        config = self.manager.load(name)
        self.name_var.set(name)
        self.type_var.set(config.get("type", "template"))
        self.threshold_var.set(str(config.get("threshold", 0.85)))
        self.click_var.set(config.get("click", {}).get("mode", "center"))
        self.scene_var.set(config.get("scene", ""))
        self.tags_var.set(",".join(config.get("tags", [])))
        self.expected_var.set(config.get("ocr", {}).get("expected_text", ""))
        self.match_var.set(config.get("ocr", {}).get("match_mode", "contains"))
        self.selected_rect = config["roi"]
        screenshot = self.manager.path(name) / "screenshot.png"
        if screenshot.is_file():
            self.load_image(screenshot)
            self.selected_rect = config["roi"]
            self._redraw()
        self.rect_var.set(str(config["roi"]))
        self._toggle_ocr()

    def validate_current(self) -> None:
        name = self.name_var.get().strip()
        directory = self.manager.path(name)
        try:
            config = self.manager.load(name)
        except (OSError, ValueError) as error:
            messagebox.showerror("Validate failed", str(error))
            return
        roi_type = config.get("type", "template")
        if roi_type not in {"template", "color", "light_cyan_duelist_detector"}:
            messagebox.showerror("Validate failed", f"Unsupported ROI type: {roi_type}")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title(f"ROI validate: {name}")
        dialog.resizable(True, True)
        result_text = tk.StringVar(value="Validating...")
        threshold = tk.StringVar(value=str(config.get("matcher", {}).get("threshold", config.get("threshold", 0.85))))
        debug_images: list[object] = []
        debounce_id: str | None = None

        if roi_type == "template":
            threshold_frame = ttk.Frame(dialog)
            threshold_frame.pack(fill="x", padx=10, pady=(10, 2))
            ttk.Label(threshold_frame, text="Threshold").pack(side="left")
            ttk.Entry(threshold_frame, textvariable=threshold, width=10).pack(side="left", padx=6)

        light_param_vars: dict[str, tk.StringVar] = {}
        light_param_specs = {
            "min_radius": (18, 12, 35, True, "????"),
            "max_radius": (48, 35, 70, True, "????"),
            "min_ring_cyan_ratio": (0.30, 0.20, 0.55, False, "????????"),
            "max_center_cyan_ratio": (0.12, 0.05, 0.25, False, "????????"),
            "min_circle_score": (0.70, 0.40, 0.95, False, "??????"),
            "min_score": (0.78, 0.50, 0.95, False, "?????"),
        }

        def collect_light_settings() -> dict[str, float | int]:
            settings: dict[str, float | int] = {}
            for key, (_default, low, high, is_int, label) in light_param_specs.items():
                raw = light_param_vars[key].get().strip()
                value = float(raw)
                if not low <= value <= high:
                    raise ValueError(f"{label} must be between {low} and {high}")
                settings[key] = int(round(value)) if is_int else float(value)
            return settings

        def schedule_validation() -> None:
            nonlocal debounce_id
            if debounce_id is not None:
                dialog.after_cancel(debounce_id)
            debounce_id = dialog.after(400, lambda: run_validation(False))

        def save_light_settings() -> None:
            try:
                settings = collect_light_settings()
                updated = self.manager.load(name)
                color = dict(updated.get("color", {}))
                color.update(settings)
                color["detector"] = "light_cyan_duelist_detector"
                updated["color"] = color
                (directory / "config.json").write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8")
                config.clear()
                config.update(updated)
                messagebox.showinfo("Saved", "?????????? config.json", parent=dialog)
            except (OSError, ValueError, TypeError) as error:
                messagebox.showerror("Save failed", str(error), parent=dialog)

        if roi_type != "template":
            param_frame = ttk.LabelFrame(dialog, text="??????????????????", padding=8)
            param_frame.pack(fill="x", padx=10, pady=(10, 2))
            saved_color = dict(config.get("color", {}))
            for row, (key, (default, low, high, is_int, label)) in enumerate(light_param_specs.items()):
                value = saved_color.get(key, saved_color.get("circle_threshold", default) if key == "min_circle_score" else default)
                variable = tk.StringVar(value=str(int(value)) if is_int else f"{float(value):.2f}")
                light_param_vars[key] = variable
                ttk.Label(param_frame, text=label).grid(row=row, column=0, sticky="w", padx=(0, 6), pady=2)
                scale = ttk.Scale(param_frame, from_=low, to=high, orient="horizontal")
                scale.set(float(value))
                scale.grid(row=row, column=1, sticky="ew", padx=4, pady=2)
                entry = ttk.Entry(param_frame, textvariable=variable, width=8)
                entry.grid(row=row, column=2, sticky="e", padx=(6, 0), pady=2)
                def on_slide(slider_value: str, var: tk.StringVar = variable, integer: bool = is_int) -> None:
                    number = float(slider_value)
                    var.set(str(int(round(number))) if integer else f"{number:.2f}")
                    schedule_validation()
                scale.configure(command=on_slide)
                entry.bind("<KeyRelease>", lambda _event, slider=scale, var=variable, integer=is_int: (slider.set(float(var.get())), schedule_validation()))
            param_frame.columnconfigure(1, weight=1)
            ttk.Button(param_frame, text="??????", command=save_light_settings).grid(row=len(light_param_specs), column=0, columnspan=3, sticky="ew", pady=(8, 0))

        result_label = ttk.Label(dialog, textvariable=result_text, justify="left")
        result_label.pack(fill="x", padx=10, pady=8)
        preview_label = ttk.Label(dialog)
        preview_label.pack(padx=10, pady=4)

        def run_validation(refresh: bool = False) -> None:
            nonlocal debounce_id
            debounce_id = None
            try:
                screen = self._capture_image() if (refresh and self.adb) else self.image
                if screen is None:
                    screen = self._capture_image()
                self.image = screen
                if roi_type == "template":
                    value = float(threshold.get())
                    if not 0 <= value <= 1:
                        raise ValueError("threshold must be between 0 and 1")
                    result = TemplateMatcher().match(screen, directory / "roi.png", config, value)
                    location = result["match_location"] or result["best_location"]
                    point = result["click_point"]
                    point_text = f"({point['x']}, {point['y']})" if point else "none"
                    result_text.set(
                        f"Type: template\nMatched: {'YES' if result['matched'] else 'NO'}\n"
                        f"Should click: {'YES' if result['should_click'] else 'NO'}\n"
                        f"Score: {result['score']:.4f}\nThreshold: {result['threshold']:.4f}\n"
                        f"Match location: ({location['x']}, {location['y']})\nGlobal click: {point_text}\n"
                        f"Resized: {'YES' if result['resized'] else 'NO'}"
                    )
                    result_label.configure(foreground="green" if result["matched"] else "red")
                    debug = result["debug_preview"][:, :, ::-1]
                else:
                    try:
                        from .light_cyan_duelist_detector import LightCyanDuelistDetector
                    except ImportError:
                        from light_cyan_duelist_detector import LightCyanDuelistDetector
                    settings = dict(config.get("color", {}))
                    settings.pop("detector", None)
                    settings.update(collect_light_settings())
                    detector = LightCyanDuelistDetector(**settings)
                    base = config["base_resolution"]
                    rect = config["roi"]
                    scaled = {"x": round(rect["x"] * screen.width / base["width"]), "y": round(rect["y"] * screen.height / base["height"]), "width": round(rect["width"] * screen.width / base["width"]), "height": round(rect["height"] * screen.height / base["height"])}
                    result = detector.detect_detailed(screen, scaled)
                    stats = result.get("stats", {})
                    result_text.set(
                        "Type: light_cyan_duelist_detector\n"
                        f"????: {stats.get('all_candidates', len(result['candidates']))}\n"
                        f"??????: {stats.get('size_pass', len(result['candidates']))}\n"
                        f"??????: {stats.get('color_pass', 0)}\n"
                        f"??????: {stats.get('circle_pass', 0)}\n"
                        f"????: {len(result['detections'])}\n"
                        f"Rejected: {len(result['rejected'])}\n"
                        f"ROI: x={scaled['x']} y={scaled['y']} w={scaled['width']} h={scaled['height']}"
                    )
                    result_label.configure(foreground="green" if result["detections"] else "red")
                    debug = self._build_candidate_preview(result["debug_preview"], screen, result["candidates"])
                debug_images.clear()
                debug_images.append(debug)
                shown = Image.fromarray(debug).convert("RGB")
                shown.thumbnail((640, 720))
                dialog.preview_photo = ImageTk.PhotoImage(shown)
                preview_label.configure(image=dialog.preview_photo)
            except (OSError, ValueError, TypeError, subprocess.SubprocessError) as error:
                messagebox.showerror("Validate failed", str(error), parent=dialog)

        buttons = ttk.Frame(dialog)
        buttons.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(buttons, text="Validate", command=lambda: run_validation(False)).pack(side="left")
        ttk.Button(buttons, text="Screenshot and validate", command=lambda: run_validation(True)).pack(side="left", padx=5)
        dialog.protocol("WM_DELETE_WINDOW", lambda: (debug_images.clear(), dialog.destroy()))
        run_validation(True)

    def _build_candidate_preview(self, debug: object, screen: Image.Image, candidates: list[object]) -> object:
        base = Image.fromarray(debug).convert("RGB")
        items = list(candidates)[:24]
        if not items:
            return debug
        thumb_size = 86
        label_height = 28
        gap = 8
        columns = max(1, base.width // (thumb_size + gap))
        rows = (len(items) + columns - 1) // columns
        sheet_height = rows * (thumb_size + label_height + gap) + gap
        sheet = Image.new("RGB", (base.width, sheet_height), "#202020")
        for index, item in enumerate(items):
            row, column = divmod(index, columns)
            x = column * (thumb_size + gap) + gap
            y = row * (thumb_size + label_height + gap) + gap
            pad = max(6, round(getattr(item, "radius", 0) * 0.25))
            left = max(0, int(item.x) - pad)
            top = max(0, int(item.y) - pad)
            right = min(screen.width, int(item.x + item.width) + pad)
            bottom = min(screen.height, int(item.y + item.height) + pad)
            crop = screen.crop((left, top, right, bottom)).convert("RGB")
            crop.thumbnail((thumb_size, thumb_size))
            tx = x + (thumb_size - crop.width) // 2
            sheet.paste(crop, (tx, y))
            border = "#32d74b" if getattr(item, "reason", "") == "accepted" else "#ff9f0a"
            drawer = ImageDraw.Draw(sheet)
            drawer.rectangle((x, y, x + thumb_size - 1, y + thumb_size - 1), outline=border, width=2)
            drawer.text((x, y + thumb_size + 2), f"{index + 1}: {getattr(item, 'score', 0):.2f}", fill=border)
            reason = getattr(item, "reason", "")
            if reason and reason != "accepted":
                drawer.text((x, y + thumb_size + 14), reason.replace("REJECT: ", ""), fill="#dddddd")
        combined = Image.new("RGB", (base.width, base.height + sheet_height), "black")
        combined.paste(base, (0, 0))
        combined.paste(sheet, (0, base.height))
        return np.asarray(combined)

    def delete_current(self) -> None:
        name = self.name_var.get().strip()
        if name and messagebox.askyesno("确认删除", f"删除 ROI：{name}？"):
            import shutil
            shutil.rmtree(self.manager.path(name), ignore_errors=True)
            self.refresh_list()
            self.status.configure(text=f"已删除：{name}")


def main() -> None:
    parser = argparse.ArgumentParser(description="ROI 标注与管理工具")
    parser.add_argument("--db", default="ROI_DB", help="ROI 数据库目录")
    parser.add_argument("--image", type=Path, help="启动时加载的截图")
    parser.add_argument("--adb", help="ADB 可执行文件路径，用于重新截图")
    parser.add_argument("--device", help="ADB 设备序列号")
    args = parser.parse_args()
    root = tk.Tk()
    ROIApp(root, Path(args.db), args.image, args.adb, args.device)
    root.mainloop()


if __name__ == "__main__":
    main()

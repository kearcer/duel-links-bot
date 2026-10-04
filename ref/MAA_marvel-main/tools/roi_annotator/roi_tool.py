from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

try:
    from .roi_manager import ROIManager
except ImportError:
    from roi_manager import ROIManager


TYPE_LABELS = {"ocr": "OCR", "template": "图片模板匹配", "color": "颜色/状态检测", "click": "仅点击坐标"}


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
        pass

    def capture(self) -> None:
        if not self.adb:
            self.status.configure(text="未配置 ADB，请使用“加载截图”选择图片")
            self.choose_image()
            return
        command = [self.adb]
        if self.device:
            command += ["-s", self.device]
        command += ["exec-out", "screencap", "-p"]
        try:
            data = subprocess.check_output(command, timeout=15)
            from io import BytesIO
            self.set_image(Image.open(BytesIO(data)).convert("RGB"))
            self.status.configure(text="截图成功")
        except (OSError, subprocess.SubprocessError, ValueError) as error:
            messagebox.showerror("截图失败", str(error))

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

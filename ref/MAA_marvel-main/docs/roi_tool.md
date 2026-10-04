# ROI 标注与管理工具

这是一个独立的 Python/Tkinter 工具，用于在游戏截图上人工标注 ROI，并将截图、裁剪图、预览图和 JSON 配置保存到 ROI 数据库。第一版不包含自动战斗、OCR 引擎或状态机。

## 目录

- `tools/roi_tool.py`：GUI 标注工具
- `tools/roi_manager.py`：可被主程序复用的 `ROIManager` 和坐标换算函数
- `tools/light_cyan_duelist_detector.py`：无副作用的浅青色候选区域检测器
- `tools/test_light_cyan_duelist_detector.py`：无需设备的检测器自检

```powershell
python tools/test_light_cyan_duelist_detector.py
```

For a saved color ROI, `ROIManager.get_color_detector(name)` returns the configured detector. The detector uses HSV connected components, accepts a scaled ROI, returns image-coordinate candidate boxes and centers, and never writes debug images. It is intentionally a color candidate detector; identity selection remains a separate policy.


在 `ref/MAA_marvel-main` 目录执行：

```powershell
python -m pip install -r tools/roi_requirements.txt
python tools/roi_tool.py --db ROI_DB
```

也可以直接加载已有截图：

```powershell
python tools/roi_tool.py --db ROI_DB --image temp/mumu-165608.png
```

使用已有 MuMu/ADB 设备截图时，指定 ADB：

```powershell
python tools/roi_tool.py --db ROI_DB --adb "D:\executer\MuMu\MuMuPlayer-12.0\nx_main\adb.exe" --device "192.168.50.111:16384"
```

如果未指定 ADB，点击“重新截图”会打开图片选择器；这样工具也可以独立使用，不依赖模拟器。

## 颜色 ROI 与浅青色决斗者检测

将 ROI 类型设为 `color` 会在 `config.json` 写入 `color.detector=light_cyan_duelist` 及 HSV/面积默认值。主程序可通过 `ROIManager.get_color_detector(name)` 加载它，再调用 `detect(image)` 或 `detect_roi(image, manager, name)`。返回的是按面积排序的候选框和中心点；检测器不保存调试图，也不把颜色候选误当作决斗者身份。


1. 点击“重新截图”获取当前画面，或点击“加载截图”。
2. 在左侧截图上按住鼠标左键拖动，松开后生成 ROI。
3. 坐标始终从显示画面换算回原始截图尺寸，保存的不是界面缩放坐标。
4. 输入名称，选择 `ocr`、`template`、`color` 或 `click`。
5. 默认点击方式为 ROI 中心；右键点击截图可记录自定义点击点，再选择 `custom`。
6. 点击“保存 ROI”。同名 ROI 会提示覆盖或取消，保存后可在右侧列表重新加载和修改。

6. `template` 类型 ROI 可点击“验证当前模板”：工具获取 ADB 当前截图（无 ADB 时验证当前已加载截图），读取 `config.json` 与 `roi.png`，在 fixed ROI 内匹配。可临时调整阈值并重新验证，确认后点击“保存阈值”；验证只显示结果，不会执行点击。结果包含分数、阈值、匹配位置、建议点击坐标和是否自动缩放。


```text
ROI_DB/
└── 开始按钮/
    ├── screenshot.png
    ├── roi.png
    ├── preview.png
    └── config.json
```

## JSON 字段

```json
{
  "name": "开始按钮",
  "base_resolution": {"width": 720, "height": 1280},
  "roi": {"x": 100, "y": 200, "width": 120, "height": 50},
  "type": "template",
  "threshold": 0.85,
  "click": {"mode": "center", "x": 160, "y": 225},
  "scene": "home",
  "tags": ["button", "start"]
}
```

当类型为 `ocr` 时还会生成：

```json
"ocr": {"expected_text": "", "match_mode": "contains"}
```

`match_mode` 预留 `contains`、`equals`、`regex`、`number`。

## 主程序读取

```python
from tools.roi_manager import ROIManager, scale_rect

manager = ROIManager("ROI_DB")
rect = manager.get_rect("开始按钮")
click = manager.get_click_point("开始按钮")
kind = manager.get_type("开始按钮")
config = manager.get_config("开始按钮")

runtime_rect = scale_rect(
    rect,
    config["base_resolution"]["width"],
    config["base_resolution"]["height"],
    current_width=1080,
    current_height=1920,
)
```

比例换算公式为：

```text
real_x = saved_x * current_width / base_width
real_y = saved_y * current_height / base_height
real_width = saved_width * current_width / base_width
real_height = saved_height * current_height / base_height
```

`roi.png` 可以直接作为 OpenCV 模板匹配模板；`screenshot.png` 和 `preview.png` 用于追溯和人工检查。中文目录名和 JSON 均使用 UTF-8。

## 测试读取

```powershell
python tools/test_roi.py "开始按钮" --db ROI_DB
```

如果后续主程序已经生成 ROI，可打印名称、坐标、点击坐标和识别类型。

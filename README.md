# Duel Link Bot

这是一个面向 Windows + MuMu 12/ADB 的《Yu-Gi-Oh! Duel Links》自动阶段脚本包。仓库根目录放阶段执行入口，`tools` 目录放 ROI 获取/标注工具和识别辅助代码。

## 快速使用

推荐从 GitHub Releases 下载最新的 `duel-stage-bot-*.zip`，解压后进入目录运行：

```powershell
.\run_duel_stage.bat
```

也可以直接指定阶段：

```powershell
.\run_duel_stage.bat 1
.\run_duel_stage.bat 2
.\run_duel_stage.bat 3
```

阶段含义由脚本内逻辑定义：

- `0`：组合阶段入口。
- `1`：路人决斗流程。
- `2`：传奇决斗者世界巡检流程。
- `3`：传送门循环决斗流程。

## ADB 配置

脚本通过 ADB 截图和点击模拟器。默认按以下顺序查找 ADB：

1. 程序目录下的 `adb.exe`
2. 程序目录下的 `platform-tools\adb.exe`
3. 系统 `PATH` 中的 `adb`

如果 ADB 在其他位置，可以设置环境变量：

```powershell
$env:DUEL_STAGE_ADB="D:\path\to\adb.exe"
.\run_duel_stage.bat 1
```

也可以直接运行 Python 入口并传参：

```powershell
python .\duel_stages.py 1 --adb "D:\path\to\adb.exe" --device "127.0.0.1:16384"
```

未指定 `--device` 时脚本会自动选择在线 ADB 设备；如果没有在线设备，会尝试调用 ADB 同目录的 `MuMuManager.exe` 连接 MuMu 实例。

## 源码运行

如果不使用 Release 里的 exe，也可以直接运行源码：

```powershell
python -m pip install -r requirements.txt
.\run_duel_stage.bat 1
```

依赖主要是 `Pillow`、`numpy`、`opencv-python`。

## ROI 标注工具

ROI 工具用于查看、维护和新增 `ROI_DB` 中的识别模板。它随仓库上传，但不会进入 CI 的 exe 打包流程。

源码方式运行：

```powershell
python -m pip install -r requirements.txt
.\tools\run_roi_tool.bat
```

工具默认加载根目录下的 `ROI_DB`。如果没有配置 ADB，工具仍会启动，可以通过“加载截图”查看和维护已有 ROI。

ROI 工具可用这些环境变量覆盖默认值：

```powershell
$env:ADB_PATH="D:\path\to\adb.exe"
$env:DEVICE="127.0.0.1:16384"
.\tools\run_roi_tool.bat
```

## 目录结构

```text
run_duel_stage.bat        # 阶段执行入口，Release 包中优先调用 duel_stages.exe
duel_stages.py            # 阶段自动化主逻辑
requirements.txt          # 源码运行依赖
duel_stages.spec          # PyInstaller 打包配置
build.ps1                 # 本地打包脚本
ROI_DB/                   # 已有 ROI 模板和配置
tools/
  run_roi_tool.bat        # ROI 标注工具入口，不参与 CI exe 打包
  roi_tool.py             # ROI GUI 标注工具
  roi_manager.py          # ROI 配置读写和坐标缩放
  template_matcher.py     # OpenCV 模板匹配
  light_cyan_duelist_detector.py
```

## 本地打包

在仓库根目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

构建产物会生成在 `package`，其中包含：

- `duel_stages.exe`
- `run_duel_stage.bat`
- `requirements.txt`
- `tools/`
- `ROI_DB/`
- `README.md`

## GitHub Actions 打包

[.github/workflows/build-duel-stage.yml](.github/workflows/build-duel-stage.yml) 会在 Windows runner 上构建 `duel_stages.exe`。

- push 到 `master`、pull request、手动触发 workflow：上传 Actions artifact。
- 推送 `v*` tag：上传 artifact，并创建 GitHub Release。

当前 workflow 会强制 Python 使用 UTF-8 输出，避免 Windows runner 在打印中文帮助文本时使用 `cp1252` 导致编码失败。

## 注意事项

- 请先启动 MuMu 12，并开启 ADB/调试功能。
- 建议只保持一个模拟器实例在线；多个设备在线时脚本默认选择第一个，可用 `--device` 指定。
- `ROI_DB` 中的模板和坐标与截图分辨率相关，实际使用前建议先用 ROI 工具验证关键模板。
- 脚本会执行 ADB 点击操作，运行前请确认游戏停留在预期页面。

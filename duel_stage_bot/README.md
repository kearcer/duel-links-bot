# Duel Stage Bot

这是从 `run_duel_stage.bat` 相关代码整理出的独立运行目录。下载仓库后进入本目录即可运行，不需要原 `ref/MAA_marvel-main` 工程。

## 目录内容

- `run_duel_stage.bat`：Python 入口脚本，支持 `0/1/2/3` 阶段选择。
- `tools/duel_stages.py`：阶段自动化主逻辑。
- `run_roi_tool.bat`、`tools/roi_tool.py`：ROI 标注/管理工具，可加载并维护同一份 `ROI_DB`。
- `tools/roi_manager.py`、`tools/template_matcher.py`、`tools/light_cyan_duelist_detector.py`：ROI 与图像识别依赖代码。
- `ROI_DB/`：运行所需识别模板与配置。
- `requirements.txt`：Python 运行依赖。

## 直接运行源码

先安装 Python 3.12 或更新版本，然后在本目录执行：

```powershell
python -m pip install -r requirements.txt
.\run_duel_stage.bat 1
```

也可以运行交互菜单：

```powershell
.\run_duel_stage.bat
```

默认会从这些位置查找 ADB：

1. 本目录下的 `adb.exe`
2. 本目录下的 `platform-tools\adb.exe`
3. 系统 `PATH` 中的 `adb`

如果 ADB 不在这些位置，可以传参数或设置环境变量：

```powershell
python .\tools\duel_stages.py 1 --adb "D:\path\to\adb.exe"
$env:DUEL_STAGE_ADB="D:\path\to\adb.exe"
.\run_duel_stage.bat 1
```

## ROI 标注工具

ROI 工具不会进入 GitHub CI 打包，但源码随目录一起提交。安装依赖后运行：

```powershell
.\run_roi_tool.bat
```

工具默认加载本目录下的 `ROI_DB`，右侧列表会显示已有 ROI。若未找到 ADB，工具仍会启动，可以通过“加载截图”查看和维护已有 ROI。

ADB 查找顺序与阶段脚本一致：本目录 `adb.exe`、`platform-tools\adb.exe`、系统 `PATH`。也可以设置环境变量：

```powershell
$env:ADB_PATH="D:\path\to\adb.exe"
$env:DEVICE="127.0.0.1:16384"
.\run_roi_tool.bat
```

## 使用 GitHub Actions 打包

仓库中的 `.github/workflows/build-duel-stage.yml` 会在 Windows 上使用 PyInstaller 生成 `duel_stages.exe`，并打包这些文件：

- `duel_stages.exe`
- `run_duel_stage.bat`
- `ROI_DB/`
- `README.md`

推送到 `master` 或创建 pull request 时会产出 Actions artifact。推送 `v*` tag 时会同时发布到 GitHub Release。
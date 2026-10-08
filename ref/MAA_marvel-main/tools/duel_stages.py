from __future__ import annotations

import argparse
import logging
import subprocess
import time
from pathlib import Path

try:
    from .roi_manager import ROIManager
    from .template_matcher import TemplateMatcher
except ImportError:
    from roi_manager import ROIManager
    from template_matcher import TemplateMatcher


DB = Path(__file__).resolve().parents[1] / "ROI_DB"
LOG_FILE = Path(__file__).with_name("duel_stages.log")
ADB = r"D:\executer\MuMu\MuMuPlayer-12.0\nx_main\adb.exe"
DEVICE = None

POLL_INTERVAL = 1.0
ENTRY_IDLE_TIMEOUT = 12.0
POST_DUEL_UNKNOWN_CLICK_INTERVAL = 1.0

MAIN_ROIS = ("传送门", "竞技场", "商店", "决斗工作室")
NETWORK_ROI = "没有发现网络链接_重启"

# 进入自动决斗阶段的统一返回值
ENTRY_AUTO_STARTED = "AUTO_DUEL_STARTED"
ENTRY_NO_RESOURCE = "NO_RESOURCE"
ENTRY_NO_DUEL = "NO_DUEL"

# 决斗结束统一处理器的返回值
POST_MAIN_PAGE = "MAIN_PAGE"
POST_PORTAL_PAGE = "PORTAL_PAGE"

manager = ROIManager(DB)
matcher = TemplateMatcher()
logger = logging.getLogger(__name__)
network_recoveries = 0
device_is_explicit = False


# ============================================================
# ADB / 截图 / ROI 基础能力
# ============================================================


def list_adb_devices():
    output = subprocess.check_output([ADB, "devices"], text=True, timeout=15)
    return [
        parts[0]
        for line in output.splitlines()[1:]
        if len(parts := line.split()) >= 2 and parts[1] == "device"
    ]


def connect_mumu_devices():
    mumu_manager = Path(ADB).with_name("MuMuManager.exe")
    if not mumu_manager.is_file():
        return

    result = subprocess.run(
        [str(mumu_manager), "adb", "-v", "all", "-c", "connect"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=15,
    )
    logger.info("MuMu ADB：%s", (result.stdout or result.stderr or "").strip())


def resolve_device():
    global DEVICE

    devices = list_adb_devices()
    if not devices:
        connect_mumu_devices()
        devices = list_adb_devices()

    if not devices:
        raise RuntimeError("未找到在线 ADB 设备，请确认 MuMu 已启动 Android 且已开启 ADB 调试")

    DEVICE = devices[0]
    if len(devices) > 1:
        logger.warning("发现多个 ADB 设备，自动使用第一个：%s；可用 --device 指定", DEVICE)
    else:
        logger.info("自动发现 ADB 设备：%s", DEVICE)

    return DEVICE


def run_adb(*args, capture_output=False):
    global DEVICE

    if not DEVICE:
        resolve_device()

    command = [ADB, "-s", DEVICE, *args]

    try:
        if capture_output:
            return subprocess.check_output(command, timeout=15)
        subprocess.run(command, check=True, timeout=15)
    except subprocess.CalledProcessError:
        if device_is_explicit:
            raise

        previous_device = DEVICE
        DEVICE = None
        resolve_device()

        if DEVICE == previous_device:
            raise

        logger.warning("ADB 设备已变更：%s -> %s，正在重试", previous_device, DEVICE)
        command = [ADB, "-s", DEVICE, *args]

        if capture_output:
            return subprocess.check_output(command, timeout=15)
        subprocess.run(command, check=True, timeout=15)


def capture_screen():
    from io import BytesIO
    from PIL import Image

    return Image.open(
        BytesIO(run_adb("exec-out", "screencap", "-p", capture_output=True))
    ).convert("RGB")


def match_roi(name, screen=None):
    logger.info("[Match] 正在匹配：%s", name, stacklevel=2)

    config = manager.load(name)
    threshold = float(
        config.get("matcher", {}).get("threshold", config.get("threshold", 0.85))
    )

    if not 0 <= threshold <= 1:
        raise ValueError(f"{name}: threshold must be between 0 and 1")

    if screen is None:
        screen = capture_screen()

    matched = matcher.match(
        screen,
        manager.path(name) / "roi.png",
        config,
        threshold,
    )["matched"]

    logger.info(
        "[Match] 匹配结果：%s — %s",
        name,
        "成功" if matched else "失败",
        stacklevel=2,
    )
    return matched


def click_roi_center(name):
    logger.info("[Click] 正在点击：%s", name, stacklevel=2)

    screen = capture_screen()
    roi = manager.get_scaled_rect(name, *screen.size)
    x = round(roi["x"] + roi["width"] / 2)
    y = round(roi["y"] + roi["height"] / 2)

    if not (0 <= x < screen.width and 0 <= y < screen.height):
        raise ValueError(f"{name}: ROI center is outside the screenshot")

    run_adb("shell", "input", "tap", str(x), str(y))
    time.sleep(POLL_INTERVAL)


def click_screen_top_quarter():
    """点击图像上四分之一处的正中间。仅在结算阶段作为通用推进点击使用。"""
    logger.info("[Click] 正在点击：屏幕顶部四分之一处", stacklevel=2)

    screen = capture_screen()
    run_adb(
        "shell",
        "input",
        "tap",
        str(screen.width // 2),
        str(screen.height // 4),
    )
    time.sleep(POLL_INTERVAL)


# ============================================================
# 页面状态 / 网络恢复
# ============================================================


def is_main_page(screen=None):
    if screen is None:
        screen = capture_screen()
    return all(match_roi(name, screen) for name in MAIN_ROIS)


def is_legend_world_page(screen=None):
    if screen is None:
        screen = capture_screen()

    return (
        match_roi("传送门", screen)
        and match_roi("决斗工作室", screen)
        and not match_roi("商店", screen)
        and not match_roi("竞技场", screen)
    )


def check_and_recover_network():
    global network_recoveries

    recovered = False

    while match_roi(NETWORK_ROI):
        if network_recoveries >= 10:
            raise SystemExit("[Network] 累计恢复10次后仍存在网络异常，终止执行")

        network_recoveries += 1
        logger.info("[Network] 检测到网络异常，恢复 %s/10", network_recoveries)

        click_roi_center(NETWORK_ROI)
        time.sleep(10)
        click_roi_center(NETWORK_ROI)
        time.sleep(POLL_INTERVAL)
        recovered = True

    return recovered


def wait_until_match(name):
    while not match_roi(name):
        check_and_recover_network()
        time.sleep(POLL_INTERVAL)


def wait_until_main_page():
    while not is_main_page():
        check_and_recover_network()
        time.sleep(POLL_INTERVAL)


# ============================================================
# 统一阶段 A：点击目标以后，一直处理到“自动决斗”真正启动
# ============================================================

# 每个元素：
#   (用于识别的 ROI, 匹配成功后要点击的 ROI, 点击后返回结果)
#
# click_name 为 None：
#   只把它当成已知页面状态，不点击。
#
# return_result 为 None：
#   处理完成后继续 ENTRY 循环。
#
# 以后自动决斗前出现新的简单页面，只需要在这里增加一项。
ENTRY_ACTIONS = (
    # 自动决斗：出现即点击，并结束 Entry 阶段。
    ("自动决斗", "自动决斗", ENTRY_AUTO_STARTED),

    # 传送门次数/物品不足：点击退出并结束当前进入流程。
    ("人物对话界面_物品数量不足", "退出", ENTRY_NO_RESOURCE),

    # 决斗宝珠不足/补充提示：
    # 前半段也检测，出现后关闭补充页面，并按“资源不足”结束本次进入流程。
    ("决斗宝珠补充标识", "决斗宝珠补充页面关闭按钮", ENTRY_NO_RESOURCE),

    # 特殊活动：选择自己的卡组。
    ("角色和卡组的选择", "活动选择自己的卡组_点击", None),

    # 剧情/人物对话。
    ("人物对话界面识别", "剧情_下一步", None),

    # Stage3 第一次进入或每场结束后返回传送门人物页时，点击决斗入口。
    ("传送门人物界面_决斗", "传送门人物界面_决斗", None),

    # “决斗”只作为已知状态标识，不点击，继续等待“自动决斗”。
    ("决斗", None, None),
)


def enter_auto_duel(idle_timeout=None):
    """
    三个 Stage 共用的“进入自动决斗”处理器。

    统一扫描 ENTRY_ACTIONS：
      - 一轮截图最多处理一个命中的状态；
      - 有点击 ROI 就点击；
      - 有 return_result 就立即返回；
      - 没有 return_result 就重新截图继续匹配；
      - “决斗”这种 click_name=None 的状态只确认页面，不点击。

    idle_timeout：
      - None：持续等待，直到自动决斗启动或命中资源不足。
      - 数字：连续这么多秒完全没有命中任何 ENTRY_ACTIONS 状态时，
        返回 ENTRY_NO_DUEL。
    """
    last_activity = time.monotonic()

    while True:
        screen = capture_screen()
        handled = False
        handled_click_name = None

        for detect_name, click_name, return_result in ENTRY_ACTIONS:
            if not match_roi(detect_name, screen):
                continue

            logger.info("[Entry] 命中：%s", detect_name)
            last_activity = time.monotonic()
            handled = True
            handled_click_name = click_name

            if click_name is not None:
                logger.info("[Entry] %s -> %s", detect_name, click_name)
                click_roi_center(click_name)

            if return_result is not None:
                return return_result

            # 一轮只处理一个状态；处理后重新截图再判断。
            break

        if handled:
            # click_roi_center 本身已经等待 POLL_INTERVAL；
            # 只有“只识别不点击”的状态需要在这里额外等待。
            if handled_click_name is None:
                check_and_recover_network()
                time.sleep(POLL_INTERVAL)
            continue

        if check_and_recover_network():
            last_activity = time.monotonic()
            continue

        if idle_timeout is not None:
            if time.monotonic() - last_activity >= idle_timeout:
                logger.info("[Entry] 指定时间内未发现进入决斗状态")
                return ENTRY_NO_DUEL

        time.sleep(POLL_INTERVAL)


# ============================================================
# 统一阶段 B：决斗胜利后，一直处理到主页面或传送门决斗页面
# ============================================================


# 所有 Stage 的结算特殊界面统一放在这里。
# 每个元素：(用于识别的 ROI, 匹配后要点击的 ROI)
# 以后新增结算弹窗，只需要往这里增加一项，不需要分别修改 Stage1/2/3。
POST_DUEL_ACTIONS = (
    ("决斗胜利_好", "决斗胜利_好"),
    ("决斗胜利_下一步", "决斗胜利_下一步"),
    ("决斗宝珠补充标识", "决斗宝珠补充页面关闭按钮"),
    ("战斗结束_好友列表", "战斗结束_好友列表_取消"),
    ("查看无名决斗者卡组_标识", "查看无名决斗者卡组_取消"),
    ("决斗结束下一步", "决斗结束下一步"),
    ("决斗胜利_活动好_3倍", "决斗胜利_活动好_3倍"),
    ("决斗胜利_活动好", "决斗胜利_活动好"),
    ("活动得分_好", "活动得分_好"),
    ("活动得分_多倍_好", "活动得分_多倍_好"),
    ("活动得分_多倍_奖励倍率3_好", "活动得分_多倍_奖励倍率3_好"),
    ("活动奖励翻倍_确认", "活动奖励翻倍_确认"),
    ("人物对话界面识别", "剧情_下一步"),
)


def detect_post_duel_terminal(screen=None):
    """
    统一判断结算阶段是否已经结束。

    Stage1/Stage2：通常回到标准主页面。
    Stage3：通常回到传送门人物的“决斗”界面，可以直接开始下一场。
    """
    if screen is None:
        screen = capture_screen()

    # 先检查传送门决斗页，避免已经回到 Stage3 入口后继续乱点。
    if match_roi("传送门人物界面_决斗", screen):
        return POST_PORTAL_PAGE

    # 某些画面中“决斗”本身也可作为传送门决斗界面的状态标识。
    if match_roi("决斗", screen):
        return POST_PORTAL_PAGE

    if is_main_page(screen):
        return POST_MAIN_PAGE

    return None


def post_duel_click(click_name):
    """
    结算阶段专用点击：
      1. 点击匹配到的 ROI 对应按钮；
      2. 等页面变化；
      3. 若此时还没有到主页面/传送门决斗页，再点击一次屏幕上四分之一正中间。

    第二次通用点击用于：
      - 加速结算动画；
      - 跳过升级界面；
      - 跳过获得物品等没有单独 ROI 的中间页。
    """
    click_roi_center(click_name)

    screen = capture_screen()
    terminal = detect_post_duel_terminal(screen)
    if terminal:
        return terminal

    click_screen_top_quarter()
    return None


def wait_and_finish_duel():
    """
    三个 Stage 共用的完整决斗结算处理器。

    1. 自动决斗已经点击以后，每 15 秒检测一次“决斗胜利_好”。
    2. 检测到以后进入统一结算循环。
    3. 每一轮只处理一个匹配界面，然后重新截图。
    4. 所有已知结算点击后，再补点一次屏幕上四分之一正中间。
    5. 如果完全没有识别到已知界面，也补点一次上四分之一正中间，
       用于升级/物品/动画等无 ROI 页面。
    6. 直到回到标准主页面，或者回到传送门“决斗”界面。
    """

    logger.info("[Duel] 等待战斗结束")

    while True:
        time.sleep(15)

        screen = capture_screen()
        if match_roi("决斗胜利_好", screen):
            break

        check_and_recover_network()

    logger.info("[Duel] 胜利，进入统一结算处理")

    # 先处理第一次明确的“决斗胜利_好”。
    terminal = post_duel_click("决斗胜利_好")
    if terminal:
        logger.info("[Duel] 结算结束：%s", terminal)
        return terminal

    while True:
        screen = capture_screen()

        # 必须先判断终点，再进行任何额外点击。
        terminal = detect_post_duel_terminal(screen)
        if terminal:
            logger.info("[Duel] 结算结束：%s", terminal)
            return terminal

        handled = False

        # 一轮截图最多执行一个明确动作；点击后重新截图。
        for detect_name, click_name in POST_DUEL_ACTIONS:
            if match_roi(detect_name, screen):
                logger.info("[PostDuel] %s -> %s", detect_name, click_name)
                terminal = post_duel_click(click_name)
                if terminal:
                    logger.info("[Duel] 结算结束：%s", terminal)
                    return terminal

                handled = True
                break

        if handled:
            continue

        # 未识别到任何已知结算界面：
        # 用通用点击推进升级、掉落物品、经验动画等没有专门 ROI 的页面。
        if check_and_recover_network():
            continue

        logger.info("[PostDuel] 未命中已知结算模板，执行通用推进点击")
        click_screen_top_quarter()
        time.sleep(POST_DUEL_UNKNOWN_CLICK_INTERVAL)


# ============================================================
# Stage 公共入口
# ============================================================


def start_stage(number):
    global network_recoveries

    network_recoveries = 0
    logger.info("[Stage%s] 开始", number)

    if is_main_page():
        return True

    check_and_recover_network()
    logger.warning("请回到主界面")
    return False


# ============================================================
# Stage 1：路人
# ============================================================


def run_stage_1():
    if not start_stage(1):
        return

    while True:
        wait_until_main_page()

        if match_roi("路人负样本"):
            logger.info("[Stage1] 路人负样本匹配，完成")
            return

        logger.info("[Stage1] 路人负样本未匹配，点击并尝试进入决斗")
        click_roi_center("路人负样本")

        entry_result = enter_auto_duel(idle_timeout=ENTRY_IDLE_TIMEOUT)

        if entry_result == ENTRY_NO_RESOURCE:
            logger.info("[Stage1] 检测到资源不足/决斗宝珠不足，阶段一结束")
            return

        if entry_result == ENTRY_NO_DUEL:
            logger.info("[Stage1] 本次点击未进入决斗，重新检查主页面/路人")
            continue

        finish_result = wait_and_finish_duel()

        if finish_result == POST_MAIN_PAGE:
            logger.info("[Stage1] 已回到主页面，继续检查路人")
            continue

        # Stage1 正常不应回到传送门决斗页，但统一处理器允许返回该状态。
        logger.warning("[Stage1] 结算后进入传送门决斗页，结束阶段一避免误操作")
        return


# ============================================================
# Stage 2：传奇决斗者世界 1~9，当前保留 9 轮逻辑
# ============================================================


def finish_stage_2():
    screen = capture_screen()

    if is_main_page(screen):
        logger.info("[Stage2] 已确认回到主界面")
        return

    if (
        match_roi("传送门", screen)
        and match_roi("决斗工作室", screen)
        and not match_roi("商店", screen)
        and not match_roi("竞技场", screen)
        and match_roi("切换世界", screen)
    ):
        logger.info("[Stage2] 检测到仍在世界流程中，点击切换世界返回主界面")
        click_roi_center("切换世界")
        wait_until_main_page()


def run_stage_2():
    if not start_stage(2):
        return

    click_roi_center("切换世界")

    # 按当前需求保留：Round 1~9，每轮 World 1~9，共 81 次世界检查。
    for round_number in range(1, 10):
        for world in range(1, 10):
            time.sleep(POLL_INTERVAL)
            logger.info("[Stage2] Round %s / World %s", round_number, world)

            target = f"传奇决斗者世界{world}负样本"

            # 保留当前实际运行逻辑：直接点击该世界目标 ROI。
            click_roi_center(target)

            # 原代码这里等待约10秒判断是否进入人物对话/自动决斗。
            # 现在由统一 enter_auto_duel 完成；若持续没有任何已知进入状态，则返回 NO_DUEL。
            entry_result = enter_auto_duel(idle_timeout=10.0)

            if entry_result == ENTRY_AUTO_STARTED:
                logger.info("[Stage2] 已进入自动决斗")
                finish_result = wait_and_finish_duel()

                if finish_result == POST_PORTAL_PAGE:
                    logger.warning("[Stage2] 结算后进入传送门决斗页，结束阶段二避免误操作")
                    return

            elif entry_result == ENTRY_NO_RESOURCE:
                logger.info("[Stage2] 检测到资源不足/决斗宝珠不足，尝试返回主界面")
                finish_stage_2()
                return

            else:
                # 保留原来的 Stage2 业务分支：点击后没有进入决斗时，
                # 先执行 finish_stage_2，再判断是否已经回到主页面。
                finish_stage_2()

                if is_main_page():
                    logger.info("[Stage2] 检测到已回到主界面，阶段二完成")
                    return

                logger.info("[Stage2] 未进入决斗，进入下一世界")
                continue

            # 9轮 × 9世界：只有 Round9 / World9 是最后一次。
            is_last_world = round_number == 9 and world == 9

            if not is_last_world:
                while not match_roi("切换世界"):
                    check_and_recover_network()
                    time.sleep(POLL_INTERVAL)

                click_roi_center("切换世界")
            else:
                logger.info("[Stage2] 已完成9轮世界1~9巡检，阶段二完成")
                finish_stage_2()
                return

    logger.info("[Stage2] 完成")


# ============================================================
# Stage 3：传送门循环决斗
# ============================================================


def run_stage_3():
    if not start_stage(3):
        return

    logger.info("[Stage3] 开始传送门")
    click_roi_center("传送门")

    while True:
        # enter_auto_duel 会统一处理：
        # 传送门人物界面_决斗 / 人物对话 / 卡组选择 / 自动决斗 / 物品不足。
        entry_result = enter_auto_duel(idle_timeout=None)

        if entry_result == ENTRY_NO_RESOURCE:
            logger.info("[Stage3] 检测到资源不足/决斗宝珠不足，等待返回主页面")
            wait_until_main_page()
            logger.info("[Stage3] 已回到主界面，阶段三完成")
            return

        if entry_result != ENTRY_AUTO_STARTED:
            logger.info("[Stage3] 未进入自动决斗，阶段三结束")
            return

        finish_result = wait_and_finish_duel()

        if finish_result == POST_PORTAL_PAGE:
            # 这是 Stage3 的正常连续挑战状态。
            # 不需要再返回主页面，也不需要重新点击“传送门”。
            # 下一轮 enter_auto_duel 会识别“传送门人物界面_决斗”并继续挑战。
            logger.info("[Stage3] 已回到传送门决斗界面，继续下一场")
            continue

        if finish_result == POST_MAIN_PAGE:
            logger.info("[Stage3] 已回到主界面，阶段三完成")
            return


# ============================================================
# Stage 0：保留原有组合执行入口
# ============================================================


def shutdown_windows():
    logger.info("[Stage0] 两轮完成，30秒后关闭 Windows；按 Ctrl+C 取消，请保存工作")
    time.sleep(30)
    subprocess.run(["shutdown", "/s", "/t", "0"], check=True, timeout=15)


def run_stage_0():
    for round_number in range(1, 3):
        logger.info("[Stage0] 开始第%s轮：阶段1 → 阶段2 → 阶段3", round_number)

        run_stage_1()
        run_stage_2()
        run_stage_3()

        if round_number < 2:
            logger.info("[Stage0] 第1轮完成，等待5分钟后开始第2轮")
            time.sleep(5 * 60)

    # shutdown_windows()


# ============================================================
# CLI
# ============================================================
# ============================================================
# CLI / 交互菜单
# ============================================================


def wait_for_any_key(message="请按任意键返回阶段选择菜单..."):
    """Windows 下真正等待任意键；其他环境回退到按回车。"""
    print()
    print(message, end="", flush=True)

    try:
        import msvcrt

        msvcrt.getwch()
        print()
    except ImportError:
        input()


def select_stage():
    """循环读取 0/1/2/3；输入 q/quit/exit 可退出程序。"""
    while True:
        try:
            value = input("Select stage [0/1/2/3] (q=退出): ").strip().lower()
        except EOFError:
            return None

        if value in {"q", "quit", "exit"}:
            return None

        if value in {"0", "1", "2", "3"}:
            return int(value)

        print("请输入 0、1、2、3，或 q 退出。")


def run_selected_stage(stage):
    """
    执行一次所选阶段。

    无论正常结束、业务提前结束、手动 Ctrl+C，还是运行异常，
    都不会直接退出 Python 进程；调用方可以返回阶段选择菜单。
    """
    stage_map = {
        0: run_stage_0,
        1: run_stage_1,
        2: run_stage_2,
        3: run_stage_3,
    }

    try:
        stage_map[stage]()
        logger.info("[Menu] Stage%s 本次执行结束", stage)
        return True

    except KeyboardInterrupt:
        logger.info("[Menu] Stage%s 已手动停止", stage)
        return False

    except SystemExit as error:
        # 网络恢复10次仍失败等旧逻辑会抛 SystemExit。
        # 这里拦截，避免整个程序退出，让用户回到阶段菜单重新选择。
        message = str(error) or "脚本请求终止当前阶段"
        logger.error("[Menu] Stage%s 执行失败：%s", stage, message)
        print(f"执行失败：{message}")
        return False

    except Exception as error:
        # 包括 ADB、ROI、模板、文件、子进程等运行错误。
        logger.exception("[Menu] Stage%s 执行失败：%s", stage, error)
        print(f"执行失败：{error}")
        return False


def main():
    global ADB, DEVICE, device_is_explicit, manager

    parser = argparse.ArgumentParser(
        description="独立运行决斗链接挂机阶段；运行结束/失败后自动返回阶段选择菜单"
    )
    # stage 改为可选：
    # - 直接运行 duel_stages.py -> 进入菜单
    # - duel_stages.py 1 -> 先运行 Stage1，结束后仍返回菜单
    parser.add_argument("stage", nargs="?", type=int, choices=(0, 1, 2, 3))
    parser.add_argument("--adb", default=ADB)
    parser.add_argument("--device", help="ADB 设备序列号；默认自动发现在线设备")
    parser.add_argument("--db", type=Path, default=DB)
    args = parser.parse_args()

    ADB = args.adb
    DEVICE = args.device
    device_is_explicit = args.device is not None
    manager = ROIManager(args.db)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(filename)s:%(lineno)d] %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(LOG_FILE, mode="w", encoding="utf-8"),
        ],
        force=True,
    )

    pending_stage = args.stage

    while True:
        if pending_stage is None:
            stage = select_stage()
            if stage is None:
                logger.info("已退出")
                return
        else:
            stage = pending_stage
            pending_stage = None

        run_selected_stage(stage)

        # 正常结束和失败都停在这里，按任意键后重新显示 0/1/2/3 菜单。
        wait_for_any_key()


if __name__ == "__main__":
    main()

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
MAIN_ROIS = ("传送门", "竞技场", "商店", "决斗工作室")
NETWORK_ROI = "没有发现网络链接_重启"
manager = ROIManager(DB)
matcher = TemplateMatcher()
logger = logging.getLogger(__name__)
network_recoveries = 0
device_is_explicit = False


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

    return Image.open(BytesIO(run_adb("exec-out", "screencap", "-p", capture_output=True))).convert("RGB")


def match_roi(name, screen=None):
    logger.info("[Match] 正在匹配：%s", name, stacklevel=2)
    config = manager.load(name)
    threshold = float(config.get("matcher", {}).get("threshold", config.get("threshold", 0.85)))
    if not 0 <= threshold <= 1:
        raise ValueError(f"{name}: threshold must be between 0 and 1")
    if screen is None:
        screen = capture_screen()
    matched = matcher.match(screen, manager.path(name) / "roi.png", config, threshold)["matched"]
    logger.info("[Match] 匹配结果：%s — %s", name, "成功" if matched else "失败", stacklevel=2)
    return matched


def click_roi_center(name):
    logger.info("[Click] 正在点击：%s", name, stacklevel=2)
    screen = capture_screen()
    roi = manager.get_scaled_rect(name, *screen.size)
    x, y = round(roi["x"] + roi["width"] / 2), round(roi["y"] + roi["height"] / 2)
    if not (0 <= x < screen.width and 0 <= y < screen.height):
        raise ValueError(f"{name}: ROI center is outside the screenshot")
    run_adb("shell", "input", "tap", str(x), str(y))
    time.sleep(POLL_INTERVAL)


def click_screen_top_quarter():
    logger.info("[Click] 正在点击：屏幕顶部四分之一处", stacklevel=2)
    screen = capture_screen()
    run_adb("shell", "input", "tap", str(screen.width // 2), str(screen.height // 4))
    time.sleep(POLL_INTERVAL)


def is_main_page(screen=None):
    if screen is None:
        screen = capture_screen()
    return all(match_roi(name, screen) for name in MAIN_ROIS)


def is_legend_world_page():
    screen = capture_screen()
    return (match_roi("传送门", screen) and match_roi("决斗工作室", screen)
            and not match_roi("商店", screen) and not match_roi("竞技场", screen))


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


def wait_until_portal_duel():
    while True:
        screen = capture_screen()
        if match_roi("人物对话界面_物品数量不足", screen):
            click_roi_center("退出")
            return False
        if match_roi("传送门人物界面_决斗", screen):
            return True
        if match_roi("人物对话界面识别", screen):
            click_roi_center("剧情_下一步")
        check_and_recover_network()
        time.sleep(POLL_INTERVAL)


def handle_dialog_until_auto_duel(stage):
    while True:
        if stage == 3:
            if match_roi("决斗"):
                time.sleep(POLL_INTERVAL)
                if match_roi("自动决斗"):
                    return True
                logger.info("[Stage3] 未出现自动决斗，退出当前决斗")
                click_roi_center("退出")
                time.sleep(POLL_INTERVAL)
                if match_roi("退出"):
                    click_roi_center("退出")
                wait_until_main_page()
                logger.info("[Stage3] 已回到主界面，阶段三完成")
                return False
        elif match_roi("自动决斗"):
            return True
        if match_roi("人物对话界面识别"):
            click_roi_center("剧情_下一步")
        check_and_recover_network()
        time.sleep(POLL_INTERVAL)


def handle_post_duel_reward(stage, screen):
    if stage == 1:
        if match_roi("决斗宝珠补充标识", screen):
            click_roi_center("决斗宝珠补充页面关闭按钮")
            time.sleep(POLL_INTERVAL)
            screen = capture_screen()
        if match_roi("战斗结束_好友列表", screen):
            click_roi_center("战斗结束_好友列表_取消")
            screen = capture_screen()
            if match_roi("查看无名决斗者卡组_标识", screen):
                click_roi_center("查看无名决斗者卡组_取消")
            time.sleep(POLL_INTERVAL)
            screen = capture_screen()
        if match_roi("决斗结束下一步", screen):
            click_roi_center("决斗结束下一步")
            time.sleep(POLL_INTERVAL)
        click_roi_center("决斗胜利_活动好")
        click_roi_center("决斗胜利_活动好_3倍")
    elif stage == 2:
        if match_roi("决斗胜利_下一步", screen):
            click_roi_center("决斗胜利_下一步")
        elif match_roi("决斗胜利_活动好", screen):
            click_roi_center("决斗胜利_活动好")
        else:
            click_roi_center("活动得分_好")
    elif stage == 3:
        click_roi_center("活动得分_好")
        # click_roi_center("决斗胜利_活动好")


def wait_and_finish_duel(stage):
    while True:
        logger.info("[Duel] 等待战斗结束")
        while True:
            time.sleep(15)
            if match_roi("决斗胜利_好"):
                break
            check_and_recover_network()
        logger.info("[Duel] 胜利")
        click_roi_center("决斗胜利_好")
        next_clicks = 0
        while next_clicks < 2:
            click_screen_top_quarter()
            time.sleep(2)
            if match_roi("决斗胜利_下一步"):
                click_roi_center("决斗胜利_下一步")
                next_clicks += 1
            else:
                check_and_recover_network()
        time.sleep(POLL_INTERVAL)
        while True:
            screen = capture_screen()
            handle_post_duel_reward(stage, screen)
            time.sleep(POLL_INTERVAL)
            screen = capture_screen()
            if stage == 1 and match_roi("决斗宝珠补充标识", screen):
                logger.info("[Stage1] 奖励结束后检测到决斗宝珠补充页面")
                click_roi_center("决斗宝珠补充页面关闭按钮")
                time.sleep(POLL_INTERVAL)
                screen = capture_screen()
            if stage == 3 and match_roi("传送门人物界面_决斗", screen):
                logger.info("[Stage3] 发现下一个传送门决斗，继续挑战")
                click_roi_center("传送门人物界面_决斗")
                time.sleep(POLL_INTERVAL)
                if not handle_dialog_until_auto_duel(3):
                    return
                logger.info("[Duel] 自动决斗")
                click_roi_center("自动决斗")
                break
            if match_roi("人物对话界面识别", screen):
                click_roi_center("剧情_下一步")
            elif is_main_page(screen):
                logger.info("[Duel] 返回主页面")
                return
            elif stage == 3 and match_roi("退出", screen):
                logger.info("[Stage3] 未发现下一个传送门决斗，退出")
                click_roi_center("退出")
                wait_until_main_page()
                logger.info("[Stage3] 已回到主界面，阶段三完成")
                return
            check_and_recover_network()
            time.sleep(POLL_INTERVAL)
        # Stage 3 found another duel; restart the victory-wait cycle.


def run_normal_duel(stage):
    if not handle_dialog_until_auto_duel(stage):
        return
    logger.info("[Duel] 自动决斗")
    click_roi_center("自动决斗")
    wait_and_finish_duel(stage)


def start_stage(number):
    global network_recoveries
    network_recoveries = 0
    logger.info("[Stage%s] 开始", number)
    if is_main_page():
        return True
    check_and_recover_network()
    logger.warning("请回到主界面")
    return False


def run_stage_1():
    if not start_stage(1):
        return
    while True:
        wait_until_main_page()
        if match_roi("路人负样本"):
            logger.info("[Stage1] 路人负样本匹配，完成")
            return
        logger.info("[Stage1] 路人负样本未匹配，开始决斗")
        click_roi_center("路人负样本")
        run_normal_duel(1)


def run_stage_2():
    if not start_stage(2):
        return
    click_roi_center("切换世界")
    for round_number in range(1, 10):
        for world in range(1, 10):
            time.sleep(POLL_INTERVAL)
            logger.info("[Stage2] Round %s / World %s", round_number, world)
            target = f"传奇决斗者世界{world}负样本"
            click_roi_center(target)
            time.sleep(10)
            if match_roi("人物对话界面识别") or match_roi("自动决斗"):
                if match_roi("人物对话界面识别"):
                    click_roi_center("剧情_下一步")
                time.sleep(POLL_INTERVAL)
                logger.info("[Stage2] 人物对话或自动决斗出现，开始决斗")
                time.sleep(5)
                if match_roi("角色和卡组的选择"):
                    click_roi_center("活动选择自己的卡组_点击")
                time.sleep(POLL_INTERVAL)
                run_normal_duel(2)
            else:
                finish_stage_2()
                if is_main_page():
                    logger.info("[Stage2] 检测到已回到主界面，阶段二完成")
                    return
                logger.info("[Stage2] 未出现人物对话或自动决斗，进入下一世界")
                continue
            if round_number != 9 or world != 9:
                while not match_roi("切换世界"):
                    check_and_recover_network()
                    time.sleep(POLL_INTERVAL)
                click_roi_center("切换世界")
            else:
                logger.info("[Stage2] 已完成所有世界，阶段二完成")
                finish_stage_2()
                return

    logger.info("[Stage2] 完成")


def finish_stage_2():
    screen = capture_screen()
    if is_main_page(screen):
        logger.info("[Stage2] 已确认回到主界面")
        return
    if (match_roi("传送门", screen) and match_roi("决斗工作室", screen)
            and not match_roi("商店", screen) and not match_roi("竞技场", screen)
            and match_roi("切换世界", screen)):
        logger.info("[Stage2] 检测到仍在世界流程中，点击切换世界返回主界面")
        click_roi_center("切换世界")
        wait_until_main_page()


def run_stage_3():
    if not start_stage(3):
        return
    while True:
        logger.info("[Stage3] 开始传送门")
        click_roi_center("传送门")
        time.sleep(POLL_INTERVAL)
        if not wait_until_portal_duel():
            logger.info("[Stage3] 道具数量不足，阶段三完成")
            return
        click_roi_center("传送门人物界面_决斗")
        time.sleep(POLL_INTERVAL)
        if not handle_dialog_until_auto_duel(3):
            return
        logger.info("[Duel] 自动决斗")
        click_roi_center("自动决斗")
        wait_and_finish_duel(3)
        return


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


def main():
    global ADB, DEVICE, device_is_explicit, manager
    parser = argparse.ArgumentParser(description="独立运行决斗链接挂机阶段；Ctrl+C 停止")
    parser.add_argument("stage", type=int, choices=(0, 1, 2, 3))
    parser.add_argument("--adb", default=ADB)
    parser.add_argument("--device", help="ADB 设备序列号；默认自动发现在线设备")
    parser.add_argument("--db", type=Path, default=DB)
    args = parser.parse_args()
    ADB, DEVICE = args.adb, args.device
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
    try:
        {0: run_stage_0, 1: run_stage_1, 2: run_stage_2, 3: run_stage_3}[args.stage]()
    except KeyboardInterrupt:
        logger.info("已手动停止")
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as error:
        raise SystemExit(f"执行失败：{error}") from error


if __name__ == "__main__":
    main()

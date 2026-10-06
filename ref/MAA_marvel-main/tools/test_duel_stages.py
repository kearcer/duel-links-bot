import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tools import duel_stages as stages


class DeviceDiscoveryTests(unittest.TestCase):
    def test_match_logs_success_and_failure(self):
        for matched in (True, False):
            with (
                self.subTest(matched=matched),
                patch.object(stages.manager, "load", return_value={}),
                patch.object(stages.matcher, "match", return_value={"matched": matched}),
                self.assertLogs(stages.logger, level="INFO") as logs,
            ):
                self.assertIs(stages.match_roi("目标", screen="screen"), matched)
            self.assertIn("正在匹配：目标", logs.output[0])
            self.assertIn("匹配结果：目标 — " + ("成功" if matched else "失败"), logs.output[1])

    def test_click_waits_before_next_match_captures_screen(self):
        screen = SimpleNamespace(size=(100, 200), width=100, height=200)
        for click in (lambda: stages.click_roi_center("目标"), stages.click_screen_top_quarter):
            events = []

            def capture():
                events.append("capture")
                return screen

            with (
                self.subTest(click=click),
                patch.object(stages, "capture_screen", side_effect=capture),
                patch.object(stages, "run_adb", side_effect=lambda *args: events.append("tap")),
                patch.object(stages.time, "sleep", side_effect=lambda seconds: events.append(("sleep", seconds))),
                patch.object(stages.manager, "get_scaled_rect", return_value={"x": 0, "y": 0, "width": 20, "height": 20}),
                patch.object(stages.manager, "load", return_value={}),
                patch.object(stages.matcher, "match", side_effect=lambda *args: events.append("match") or {"matched": True}),
            ):
                click()
                self.assertTrue(stages.match_roi("目标"))
            self.assertEqual(events, ["capture", "tap", ("sleep", 1.0), "capture", "match"])

    def test_reward_matches_use_fresh_screens_after_clicks(self):
        for card_dialog in (False, True):
            with (
                self.subTest(card_dialog=card_dialog),
                patch.object(stages, "capture_screen", side_effect=["after_friend", "after_card"]) as capture,
                patch.object(stages, "match_roi", side_effect=[False, True, card_dialog, False]) as match,
                patch.object(stages, "click_roi_center"),
                patch.object(stages.time, "sleep"),
            ):
                stages.handle_post_duel_reward(1, "before_click")
                self.assertEqual(capture.call_count, 2)
                self.assertEqual(
                    [call.args for call in match.call_args_list],
                    [
                        ("决斗宝珠补充标识", "before_click"),
                        ("战斗结束_好友列表", "before_click"),
                        ("查看无名决斗者卡组_标识", "after_friend"),
                        ("决斗结束下一步", "after_card"),
                    ],
                )

    def test_unconnected_mumu_is_connected_using_current_address(self):
        address = "192.168.50.111:5555"
        with (
            patch.object(stages, "DEVICE", None),
            patch.object(stages.Path, "is_file", return_value=True),
            patch.object(stages, "list_adb_devices", side_effect=[[], [address]]),
            patch.object(stages.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "connected", "")) as connect,
        ):
            self.assertEqual(stages.resolve_device(), address)
            connect.assert_called_once_with(
                [str(stages.Path(stages.ADB).with_name("MuMuManager.exe")), "adb", "-v", "all", "-c", "connect"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
            )

    def test_portal_wait_advances_dialogue_until_duel_appears(self):
        with (
            patch.object(stages, "capture_screen", return_value="screen"),
            patch.object(stages, "match_roi", side_effect=[False, False, True, False, False, True, False, True]) as match,
            patch.object(stages, "click_roi_center") as click,
            patch.object(stages, "check_and_recover_network"),
            patch.object(stages.time, "sleep"),
        ):
            stages.wait_until_portal_duel()
            self.assertEqual(click.call_count, 2)
            self.assertTrue(all(call.args == ("剧情_下一步",) for call in click.call_args_list))
            self.assertEqual(
                [call.args[0] for call in match.call_args_list],
                [
                    "人物对话界面_物品数量不足", "传送门人物界面_决斗", "人物对话界面识别",
                    "人物对话界面_物品数量不足", "传送门人物界面_决斗", "人物对话界面识别",
                    "人物对话界面_物品数量不足", "传送门人物界面_决斗",
                ],
            )

    def test_stage_three_checks_duel_before_auto_duel(self):
        for auto_duel in (False, True):
            events = []

            def match(name):
                events.append(name)
                return auto_duel if name == "自动决斗" else name == "决斗"

            with (
                self.subTest(auto_duel=auto_duel),
                patch.object(stages, "match_roi", side_effect=match),
                patch.object(stages.time, "sleep", side_effect=lambda seconds: events.append(("sleep", seconds))),
                patch.object(stages, "click_roi_center") as click,
                patch.object(stages, "wait_until_main_page") as wait,
            ):
                self.assertEqual(stages.handle_dialog_until_auto_duel(3), auto_duel)
                self.assertEqual(events[:3], ["决斗", ("sleep", 1.0), "自动决斗"])
                if auto_duel:
                    click.assert_not_called()
                    wait.assert_not_called()
                else:
                    click.assert_called_once_with("退出")
                    wait.assert_called_once_with()

    def test_stage_three_without_duel_continues_dialogue(self):
        with (
            patch.object(stages, "match_roi", side_effect=[False, True, True, True]) as match,
            patch.object(stages, "click_roi_center") as click,
            patch.object(stages, "check_and_recover_network") as recover,
            patch.object(stages.time, "sleep"),
            patch.object(stages, "wait_until_main_page") as wait,
        ):
            self.assertTrue(stages.handle_dialog_until_auto_duel(3))
            self.assertEqual(
                [call.args[0] for call in match.call_args_list],
                ["决斗", "人物对话界面识别", "决斗", "自动决斗"],
            )
            click.assert_called_once_with("剧情_下一步")
            recover.assert_called_once_with()
            wait.assert_not_called()

    def test_other_stages_do_not_require_duel_match(self):
        for stage in (1, 2):
            with (
                self.subTest(stage=stage),
                patch.object(stages, "match_roi", return_value=True) as match,
                patch.object(stages.time, "sleep") as sleep,
            ):
                self.assertTrue(stages.handle_dialog_until_auto_duel(stage))
                match.assert_called_once_with("自动决斗")
                sleep.assert_not_called()

    def test_stage_zero_runs_two_rounds_then_shutdowns(self):
        events = []
        with (
            patch.object(stages, "run_stage_1", side_effect=lambda: events.append(1)),
            patch.object(stages, "run_stage_2", side_effect=lambda: events.append(2)),
            patch.object(stages, "run_stage_3", side_effect=lambda: events.append(3)),
            patch.object(stages.time, "sleep", side_effect=lambda seconds: events.append(seconds)),
            patch.object(stages, "shutdown_windows") as shutdown,
        ):
            stages.run_stage_0()
        self.assertEqual(events, [1, 2, 3, 300, 1, 2, 3])
        shutdown.assert_called_once_with()

    def test_existing_device_does_not_require_mumu(self):
        with (
            patch.object(stages, "DEVICE", None),
            patch.object(stages, "list_adb_devices", return_value=["emulator-5554"]),
            patch.object(stages, "connect_mumu_devices") as connect,
        ):
            self.assertEqual(stages.resolve_device(), "emulator-5554")
            connect.assert_not_called()

    def test_failed_connection_is_not_treated_as_online(self):
        with (
            patch.object(stages, "list_adb_devices", return_value=[]),
            patch.object(stages, "connect_mumu_devices"),
        ):
            with self.assertRaisesRegex(RuntimeError, "ADB"):
                stages.resolve_device()


if __name__ == "__main__":
    unittest.main()

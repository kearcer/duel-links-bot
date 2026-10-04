from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

from agent.actions.play_turn import MAX_RANDOM_SWIPES, PlayTurn
from agent.recognitions.card_selection import BattleHand, DetectedCard
from agent.recognitions.lane_state import LaneState
from agent.runtime.store import STORE


class FakeJob:
    succeeded = True

    def wait(self):
        return self


class FakeController:
    def __init__(self) -> None:
        self.swipes: list[tuple[int, int, int, int, int]] = []

    def post_swipe(self, x1, y1, x2, y2, duration):
        self.swipes.append((x1, y1, x2, y2, duration))
        return FakeJob()


class FakeContext:
    def __init__(self) -> None:
        self.controller = FakeController()
        self.tasker = SimpleNamespace(controller=self.controller)
        self.next_overrides: list[tuple[str, list[str]]] = []

    def run_recognition(self, entry, image):
        del entry, image
        return SimpleNamespace(hit=True, box=(1580, 900, 340, 180))

    def override_next(self, node_name, next_list):
        self.next_overrides.append((node_name, list(next_list)))
        return True


def active_frame() -> np.ndarray:
    image = np.zeros((1080, 1920, 3), dtype=np.uint8)
    image[960:1030, 1670:1850] = (200, 20, 150)
    return image


def card(slot: int, cost: int, x: int) -> DetectedCard:
    return DetectedCard(slot, cost, 0.95, (x - 45, 885, 90, 90))


def empty_lanes() -> tuple[LaneState, LaneState, LaneState]:
    return tuple(
        LaneState(center, (False, False, False, False), (0.0, 0.0, 0.0, 0.0))
        for center in (710, 960, 1210)
    )


class PlayStrategyTests(unittest.TestCase):
    def test_agatha_strategy_only_allows_end_turn(self) -> None:
        state = STORE.configure({"play_strategy": "agatha"}, now=0.0)
        context = FakeContext()

        with patch(
            "agent.actions.play_turn._scan_with_retry",
            return_value=BattleHand(1, (), "no_blue_badges"),
        ):
            self.assertTrue(PlayTurn().run(context, SimpleNamespace()))

        self.assertEqual(context.controller.swipes, [])
        self.assertTrue(state.end_turn_allowed)
        self.assertEqual(state.end_turn_reason, "agatha_strategy")

    def test_agatha_strategy_takes_over_when_playable_card_is_visible(self) -> None:
        state = STORE.configure({"play_strategy": "agatha"}, now=0.0)
        context = FakeContext()
        playable = BattleHand(2, (card(0, 2, 300),), "blue_badge_path")
        zero_energy = BattleHand(0, (), "energy_zero")

        with (
            patch(
                "agent.actions.play_turn._scan_with_retry",
                side_effect=[playable, playable, zero_energy],
            ),
            patch("agent.actions.play_turn.scan_lane_states", return_value=empty_lanes()),
            patch(
                "agent.actions.play_turn._wait_for_play_resolution",
                return_value="ready",
            ),
            patch(
                "agent.actions.play_turn._confirm_play_from_fresh_frames",
                return_value=True,
            ),
        ):
            self.assertTrue(PlayTurn().run(context, SimpleNamespace()))

        self.assertEqual(len(context.controller.swipes), 1)
        self.assertEqual(context.controller.swipes[0][:2], (300, 930))
        self.assertTrue(state.end_turn_allowed)
        self.assertEqual(state.end_turn_reason, "energy_zero")

    def test_random_strategy_uses_limited_swipes(self) -> None:
        state = STORE.configure({"play_strategy": "random"}, now=0.0)
        context = FakeContext()

        with (
            patch("agent.actions.play_turn._capture_frame", return_value=active_frame()),
            patch("agent.actions.play_turn._zero_energy_visible", return_value=False),
            patch(
                "agent.actions.play_turn._wait_for_play_resolution",
                return_value="ready",
            ),
        ):
            self.assertTrue(PlayTurn().run(context, SimpleNamespace()))

        self.assertEqual(len(context.controller.swipes), MAX_RANDOM_SWIPES)
        self.assertTrue(state.end_turn_allowed)
        self.assertEqual(state.end_turn_reason, "random_strategy_exhausted")


if __name__ == "__main__":
    unittest.main()

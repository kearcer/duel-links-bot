import importlib
import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np

from agent.maa_compat import AgentServer, NotificationType
from agent.runtime.diagnostics import RuntimeDiagnostics
from agent.runtime.event_listener import MarvelContextEventSink, _capture_async
from agent.session.config import SessionConfig
from agent.session.state import SessionState


class AgentImportTests(unittest.TestCase):
    def test_async_incident_capture_detaches_cached_frame_from_controller(self) -> None:
        frame = np.zeros((8, 12, 3), dtype=np.uint8)
        controller = MagicMock()
        controller.cached_image = frame

        class ImmediateThread:
            def __init__(self, *, target, args, kwargs, **_options) -> None:
                self.target = target
                self.args = args
                self.kwargs = kwargs

            def start(self) -> None:
                self.target(*self.args, **self.kwargs)

        with (
            patch("agent.runtime.event_listener.Thread", ImmediateThread),
            patch("agent.runtime.event_listener.DIAGNOSTICS.capture") as capture,
        ):
            _capture_async(
                controller,
                None,
                source="pipeline",
                reason="pipeline_next_list_timeout",
            )

        capture.assert_called_once()
        args, kwargs = capture.call_args
        self.assertIsNone(args[0])
        self.assertIsNone(args[1])
        self.assertIsNot(kwargs["image"], frame)
        np.testing.assert_array_equal(kwargs["image"], frame)

    def test_async_incident_capture_reports_cached_frame_failure_once(self) -> None:
        controller = MagicMock()
        controller.cached_image.copy.side_effect = RuntimeError(
            "Failed to get cached image."
        )

        class ImmediateThread:
            def __init__(self, *, target, args, kwargs, **_options) -> None:
                self.target = target
                self.args = args
                self.kwargs = kwargs

            def start(self) -> None:
                self.target(*self.args, **self.kwargs)

        with (
            patch("agent.runtime.event_listener.Thread", ImmediateThread),
            patch("agent.runtime.event_listener.DIAGNOSTICS.capture") as capture,
            patch("sys.stdout", new_callable=io.StringIO) as stdout,
        ):
            _capture_async(
                controller,
                None,
                source="pipeline",
                reason="pipeline_node_failed",
                detail={"task_id": 7},
            )

        self.assertNotIn("cached_image_failed", stdout.getvalue())
        capture.assert_called_once()
        self.assertIsNone(capture.call_args.kwargs["image"])
        self.assertEqual(
            capture.call_args.kwargs["detail"]["capture_image_error"],
            "Failed to get cached image.",
        )

    def test_context_sink_captures_only_final_pipeline_failure(self) -> None:
        sink = MarvelContextEventSink()
        context = MagicMock()
        detail = SimpleNamespace(task_id=7, name="测试节点")

        with (
            patch("agent.runtime.event_listener.DIAGNOSTICS.record_node") as record,
            patch("agent.runtime.event_listener._capture_async") as capture,
            patch("agent.runtime.event_listener._state", return_value=None),
        ):
            sink.on_node_pipeline_node(
                context,
                NotificationType.Starting,
                detail,
            )
            capture.assert_not_called()

            sink.on_node_pipeline_node(
                context,
                NotificationType.Failed,
                detail,
            )

        self.assertEqual(record.call_count, 2)
        capture.assert_called_once_with(
            context.tasker.controller,
            None,
            source="pipeline",
            reason="pipeline_node_failed",
            node="测试节点",
            detail={"task_id": 7},
            throttle_seconds=30.0,
        )

    def test_main_registers_expected_adapters_without_starting_socket(self) -> None:
        importlib.import_module("agent.main")

        self.assertTrue(
            {
                "MarvelConfigureSession",
                "MarvelPlayTurn",
                "MarvelRecordEvent",
                "MarvelRouteConquestTier",
                "MarvelRecoveryAction",
                "MarvelTraceRuntime",
                "MarvelWarmupScreencap",
            }.issubset(AgentServer._custom_action_holder)
        )
        self.assertTrue(
            {
                "MarvelSessionGate",
                "MarvelCardSelection",
                "MarvelDailyTaskReward",
                "MarvelSafeEntry",
            }.issubset(AgentServer._custom_recognition_holder)
        )

    def test_main_starts_agent_server_with_socket_id(self) -> None:
        main_module = importlib.import_module("agent.main")
        with (
            patch("agent.main.Toolkit.init_option") as init_option,
            patch("agent.main.migrate_runtime_task_cache") as migrate,
            patch("agent.main.AgentServer.start_up") as start_up,
            patch("agent.main.AgentServer.join") as join,
            patch("agent.main.AgentServer.shut_down") as shut_down,
            patch("sys.argv", ["python", "-m", "agent.main", "socket-1"]),
        ):
            main_module.main()

        init_option.assert_called_once_with("./")
        migrate.assert_called_once()
        start_up.assert_called_once_with("socket-1")
        join.assert_called_once()
        shut_down.assert_called_once()

    def test_diagnostics_reuses_root_task_run_id_for_session(self) -> None:
        diagnostics = RuntimeDiagnostics()
        diagnostics.begin_task(7, "征服-任务入口", "uuid", "hash")
        started = diagnostics._payload(
            None,
            event="task_started",
            source="framework",
            reason="task_starting",
        )
        state = SessionState(SessionConfig(), started_at=0.0)

        diagnostics.begin_run(state)

        self.assertIsNotNone(started["run_id"])
        self.assertEqual(state.run_id, started["run_id"])

    def test_diagnostics_stdout_is_compact_but_file_keeps_full_event(self) -> None:
        diagnostics = RuntimeDiagnostics()
        diagnostics.begin_task(7, "寰佹湇-浠诲姟鍏ュ彛", "uuid", "hash")

        with tempfile.TemporaryDirectory() as temp_dir:
            event_log = Path(temp_dir) / "runtime-events.jsonl"
            with (
                patch("agent.runtime.diagnostics.EVENT_LOG", new=event_log),
                patch("sys.stdout", new_callable=io.StringIO) as stdout,
            ):
                diagnostics.emit(
                    None,
                    event="incident",
                    source="warmup",
                    reason="screencap_warmup_failed",
                    node="寰佹湇-浠诲姟鍏ュ彛",
                    detail={
                        "attempts": 20,
                        "elapsed_ms": 20000,
                        "last_error": "empty image",
                    },
                )

            output = stdout.getvalue()
            self.assertIn("[MarvelRuntimeIssue]", output)
            self.assertIn("reason=screencap_warmup_failed", output)
            self.assertIn("last_error=empty image", output)
            self.assertNotIn('"recent_nodes"', output)
            self.assertIn('"recent_nodes"', event_log.read_text("utf-8"))

    def test_diagnostics_keeps_normal_events_off_stdout(self) -> None:
        diagnostics = RuntimeDiagnostics()

        with tempfile.TemporaryDirectory() as temp_dir:
            event_log = Path(temp_dir) / "runtime-events.jsonl"
            with (
                patch("agent.runtime.diagnostics.EVENT_LOG", new=event_log),
                patch("sys.stdout", new_callable=io.StringIO) as stdout,
            ):
                diagnostics.emit(
                    None,
                    event="task_started",
                    source="framework",
                    reason="task_starting",
                    detail={"entry": "寰佹湇-浠诲姟鍏ュ彛"},
                )

            self.assertEqual(stdout.getvalue(), "")
            self.assertIn('"task_started"', event_log.read_text("utf-8"))


if __name__ == "__main__":
    unittest.main()

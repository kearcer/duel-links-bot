import sys

from agent.maa_compat import AgentServer, Toolkit

# Import Duel Links registrations before AgentServer starts.
from agent.actions.duel_links import (
    DuelLinksExportDuelistDetections,
    DuelLinksOpenDetectionFolder,
    DuelLinksRecordState,
    DuelLinksStreetDuelStep,
    DuelLinksSwitchArea,
    DuelLinksWarmupScreencap,
)
from agent.runtime import event_listener
from agent.runtime.task_cache import migrate_runtime_task_cache


def _short_error(error: BaseException) -> str:
    return str(error).replace("\n", " ").replace("\r", " ").strip()[:160]


def main() -> None:
    """Start the Duel Links AgentServer with the socket id passed by MaaFramework."""
    started = False
    try:
        Toolkit.init_option("./")
        if len(sys.argv) < 2:
            raise SystemExit("Usage: python -m agent.main <socket_id>")
        AgentServer.start_up(sys.argv[-1])
        started = True
        AgentServer.join()
    except BaseException as error:
        print(
            "[DuelLinksRuntimeIssue] event=agent_failed source=agent "
            f"reason={type(error).__name__} error={_short_error(error)}",
            flush=True,
        )
        raise
    finally:
        if started:
            AgentServer.shut_down()


if __name__ == "__main__":
    main()

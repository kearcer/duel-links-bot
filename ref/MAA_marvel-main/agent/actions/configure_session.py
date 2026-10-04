import time

from agent.maa_compat import AgentServer, Context, CustomAction

from agent.runtime.commands import parse_json_object
from agent.runtime.diagnostics import DIAGNOSTICS
from agent.runtime.store import STORE


CONFIG_NODE_NAMES = (
    "Config_DailyBattleMode",
    "Config_PlayStrategy",
    "Config_LaneOrder",
    "Config_MaxTier",
    "Config_ReserveTickets",
    "Config_StopDailyPass",
    "Config_Retreat",
    "Config_ClaimTaskRewardsHours",
    "Config_MatchmakingTimeout",
    "Config_AutoRestart",
    "Config_DeckName",
)


def _node_custom_values(context: Context, name: str) -> dict:
    try:
        node = context.get_node_data(name) or {}
    except Exception:
        return {}
    values = (
        node.get("action", {})
        .get("param", {})
        .get("custom_action_param", {})
    )
    return dict(values) if isinstance(values, dict) else {}


@AgentServer.custom_action("MarvelConfigureSession")
class ConfigureSession(CustomAction):
    """接收 Pipeline/UI 参数，初始化本次任务共用的运行状态。"""

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        node_name = getattr(argv, "node_name", "")
        values = {}
        for name in CONFIG_NODE_NAMES:
            values.update(_node_custom_values(context, name))
        # custom_action_param 由入口节点传入，优先级高于通用配置节点。
        values.update(parse_json_object(argv.custom_action_param))
        # STORE 保存本次征服任务的配置和计数状态，供出牌、撤退、SNAP、恢复读取。
        checkpoint_enabled = node_name not in {
            "邮箱-初始化会话",
            "公共-领奖-初始化会话",
        }
        restore_checkpoint = None
        if values.get("daily_routine") is True:
            restore_checkpoint = False
        state = STORE.configure(
            values,
            time.monotonic(),
            checkpoint_enabled=checkpoint_enabled,
            restore_checkpoint=restore_checkpoint,
        )
        if values.get("daily_routine") is True:
            state.reset_daily_routine()
            STORE.persist_checkpoint()
        return True

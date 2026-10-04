from enum import Enum

try:
    from maa.agent.agent_server import AgentServer
    from maa.context import Context, ContextEventSink, JRecognitionType
    from maa.custom_action import CustomAction
    from maa.custom_recognition import CustomRecognition
    from maa.event_sink import NotificationType
    from maa.pipeline import JOCR
    from maa.tasker import Tasker, TaskerEventSink
    from maa.toolkit import Toolkit
except ModuleNotFoundError:
    class AgentServer:
        _custom_action_holder = {}
        _custom_recognition_holder = {}
        _context_sink_holder = []
        _tasker_sink_holder = []

        @classmethod
        def custom_action(cls, name: str):
            def register(action_cls):
                cls._custom_action_holder[name] = action_cls
                return action_cls

            return register

        @classmethod
        def custom_recognition(cls, name: str):
            def register(recognition_cls):
                cls._custom_recognition_holder[name] = recognition_cls
                return recognition_cls

            return register

        @classmethod
        def context_sink(cls):
            def register(sink_cls):
                cls._context_sink_holder.append(sink_cls)
                return sink_cls

            return register

        @classmethod
        def tasker_sink(cls):
            def register(sink_cls):
                cls._tasker_sink_holder.append(sink_cls)
                return sink_cls

            return register

        @classmethod
        def start_up(cls, socket_id: str) -> None:
            del socket_id

        @classmethod
        def join(cls) -> None:
            pass

        @classmethod
        def shut_down(cls) -> None:
            pass

    class Context:
        pass

    class ContextEventSink:
        pass

    class JRecognitionType:
        OCR = "OCR"

    class NotificationType(Enum):
        Starting = "Starting"
        Succeeded = "Succeeded"
        Failed = "Failed"

    class Tasker:
        pass

    class TaskerEventSink:
        pass

    class CustomAction:
        class RunArg:
            pass

    class CustomRecognition:
        class AnalyzeArg:
            pass

        class AnalyzeResult:
            def __init__(self, *, box=None, detail=None):
                self.box = box
                self.detail = detail

    class JOCR:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class Toolkit:
        @staticmethod
        def init_option(path: str) -> None:
            del path

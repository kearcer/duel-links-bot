import sys
from dataclasses import dataclass as _dataclass
from typing import Any


def dataclass(*args: Any, **kwargs: Any) -> Any:
    if sys.version_info < (3, 10):
        kwargs.pop("slots", None)
    return _dataclass(*args, **kwargs)

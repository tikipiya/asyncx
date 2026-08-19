from importlib.metadata import PackageNotFoundError, version

from .exceptions import TaskError, TaskTimeoutError
from .sync_to_async import async_to_sync, sync_to_async
from .task_manager import Task, TaskManager

try:
    __version__ = version("asyncx-tools")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"

__all__ = [
    "Task",
    "TaskError",
    "TaskManager",
    "TaskTimeoutError",
    "async_to_sync",
    "sync_to_async",
]

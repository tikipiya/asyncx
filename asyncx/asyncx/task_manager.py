import asyncio
import heapq
from typing import List, Optional, Callable, Dict, Tuple, TypeVar, Generic, Awaitable, ParamSpec, cast
from dataclasses import dataclass
from .exceptions import TaskError, TaskTimeoutError

T = TypeVar('T')
P = ParamSpec('P')

@dataclass
class Task(Generic[T]):
    """非同期タスクを表すクラス"""
    name: str
    func: Callable[P, Awaitable[T]]
    priority: int = 0
    timeout: Optional[float] = None
    args: P.args = ()
    kwargs: P.kwargs = None

    def __post_init__(self) -> None:
        if self.kwargs is None:
            self.kwargs = {}

    def __lt__(self, other: 'Task[T]') -> bool:
        # 優先度が高いタスクが先に実行されるようにする
        return self.priority > other.priority

class TaskManager(Generic[T]):
    """非同期タスクを管理するクラス"""
    
    def __init__(self, max_concurrent_tasks: int = 10) -> None:
        self.max_concurrent_tasks = max_concurrent_tasks
        self.semaphore = asyncio.Semaphore(max_concurrent_tasks)
        self._task_queue: List[Task[T]] = []  # 優先度付きキューとして使用
        self._results: Dict[str, T] = {}
        self._errors: Dict[str, Exception] = {}

    async def add_task(self, task: Task[T]) -> None:
        """タスクを優先度付きキューに追加する"""
        heapq.heappush(self._task_queue, task)

    async def run_task(self, task: Task[T]) -> T:
        """単一のタスクを実行する"""
        try:
            async with self.semaphore:
                if task.timeout:
                    result = await asyncio.wait_for(
                        task.func(*task.args, **task.kwargs),
                        timeout=task.timeout
                    )
                else:
                    result = await task.func(*task.args, **task.kwargs)
                self._results[task.name] = result
                return result
        except asyncio.TimeoutError:
            error = TaskTimeoutError(f"Task {task.name} timed out after {task.timeout} seconds")
            self._errors[task.name] = error
            raise error
        except Exception as e:
            self._errors[task.name] = e
            raise TaskError(f"Error in task {task.name}: {str(e)}") from e

    async def run_tasks(self, tasks: Optional[List[Task[T]]] = None) -> Dict[str, T]:
        """複数のタスクを優先度順に実行する"""
        if tasks:
            self._task_queue = []
            for task in tasks:
                heapq.heappush(self._task_queue, task)

        if not self._task_queue:
            return {}

        # 優先度順にタスクを実行
        running_tasks: List[Awaitable[T]] = []
        while self._task_queue:
            task = heapq.heappop(self._task_queue)
            running_tasks.append(self.run_task(task))

        # すべてのタスクを並行して実行
        await asyncio.gather(*running_tasks, return_exceptions=True)

        return self._results

    def get_results(self) -> Dict[str, T]:
        """タスクの実行結果を取得する"""
        return self._results

    def get_errors(self) -> Dict[str, Exception]:
        """タスクの実行エラーを取得する"""
        return self._errors

    def clear(self) -> None:
        """タスク管理の状態をクリアする"""
        self._task_queue.clear()
        self._results.clear()
        self._errors.clear() 
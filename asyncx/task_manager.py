import asyncio
import heapq
import itertools
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

from .exceptions import TaskError, TaskTimeoutError

T = TypeVar("T")


@dataclass
class Task(Generic[T]):
    """非同期タスクと実行条件を表す。"""

    name: str
    func: Callable[..., Awaitable[T]]
    priority: int = 0
    timeout: float | None = None
    args: tuple[Any, ...] = ()
    kwargs: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.timeout is not None and self.timeout < 0:
            raise ValueError("timeout must be greater than or equal to 0")


class TaskManager(Generic[T]):
    """優先度と同時実行数を制御して非同期タスクを管理する。"""

    def __init__(self, max_concurrent_tasks: int = 10) -> None:
        if isinstance(max_concurrent_tasks, bool) or not isinstance(
            max_concurrent_tasks, int
        ):
            raise TypeError("max_concurrent_tasks must be an integer")
        if max_concurrent_tasks < 1:
            raise ValueError("max_concurrent_tasks must be greater than 0")

        self.max_concurrent_tasks = max_concurrent_tasks
        self.semaphore = asyncio.Semaphore(max_concurrent_tasks)
        self._task_queue: list[tuple[int, int, Task[T]]] = []
        self._queued_names: set[str] = set()
        self._sequence = itertools.count()
        self._results: dict[str, T] = {}
        self._errors: dict[str, Exception] = {}
        self._run_lock = asyncio.Lock()
        self._is_running = False

    def _enqueue(self, task: Task[T]) -> None:
        if task.name in self._queued_names:
            raise ValueError(f"Duplicate task name: {task.name}")

        entry = (-task.priority, next(self._sequence), task)
        heapq.heappush(self._task_queue, entry)
        self._queued_names.add(task.name)

    async def add_task(self, task: Task[T]) -> None:
        """タスクを安定した優先度付きキューに追加する。"""
        if self._is_running:
            raise RuntimeError("Cannot add tasks while run_tasks() is active")
        self._enqueue(task)

    async def run_task(self, task: Task[T]) -> T:
        """単一のタスクを実行し、結果または正規化したエラーを記録する。"""
        try:
            async with self.semaphore:
                awaitable = task.func(*task.args, **task.kwargs)
                if task.timeout is None:
                    result = await awaitable
                else:
                    scheduled = asyncio.ensure_future(awaitable)
                    try:
                        result = await asyncio.wait_for(
                            scheduled,
                            timeout=task.timeout,
                        )
                    except TimeoutError as exc:
                        # タスク自身が送出したTimeoutErrorは通常エラーとして扱う。
                        if not scheduled.cancelled():
                            raise
                        raise TaskTimeoutError(
                            f"Task {task.name} timed out after {task.timeout} seconds"
                        ) from exc

                self._results[task.name] = result
                return result
        except TaskTimeoutError as timeout_error:
            self._errors[task.name] = timeout_error
            raise
        except Exception as exc:
            task_error = TaskError(f"Error in task {task.name}: {exc}")
            self._errors[task.name] = task_error
            raise task_error from exc

    async def _run_worker(self) -> None:
        """キューから優先度順にタスクを取得して実行する。"""
        while self._task_queue:
            _, _, task = heapq.heappop(self._task_queue)
            try:
                await self.run_task(task)
            except TaskError:
                # バッチ全体を完走させ、終了時にまとめて通知する。
                continue

    async def run_tasks(
        self,
        tasks: Iterable[Task[T]] | None = None,
        *,
        raise_on_error: bool = True,
    ) -> dict[str, T]:
        """複数タスクを優先度順に実行する。

        デフォルトでは全タスクの完了後、1件以上失敗していればTaskErrorを
        送出する。raise_on_error=Falseでは成功結果を返し、失敗の詳細は
        get_errors()から取得できる。
        """
        async with self._run_lock:
            self._is_running = True
            try:
                if tasks is not None:
                    task_list = list(tasks)
                    names = [task.name for task in task_list]
                    if len(names) != len(set(names)):
                        raise ValueError("Task names must be unique within a batch")

                    self._task_queue.clear()
                    self._queued_names.clear()
                    for task in task_list:
                        self._enqueue(task)

                self._results.clear()
                self._errors.clear()

                if not self._task_queue:
                    return {}

                worker_count = min(
                    self.max_concurrent_tasks,
                    len(self._task_queue),
                )
                await asyncio.gather(*(self._run_worker() for _ in range(worker_count)))

                if self._errors and raise_on_error:
                    failed_names = ", ".join(self._errors)
                    error = TaskError(
                        f"{len(self._errors)} task(s) failed: {failed_names}"
                    )
                    raise error from next(iter(self._errors.values()))

                return dict(self._results)
            finally:
                self._queued_names.clear()
                self._task_queue.clear()
                self._is_running = False

    def get_results(self) -> dict[str, T]:
        """現在の成功結果をスナップショットとして取得する。"""
        return dict(self._results)

    def get_errors(self) -> dict[str, Exception]:
        """現在のエラーをスナップショットとして取得する。"""
        return dict(self._errors)

    def clear(self) -> None:
        """キューと実行状態をクリアする。"""
        if self._is_running:
            raise RuntimeError("Cannot clear TaskManager while run_tasks() is active")
        self._task_queue.clear()
        self._queued_names.clear()
        self._results.clear()
        self._errors.clear()

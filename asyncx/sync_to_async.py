import asyncio
import contextvars
import functools
from concurrent.futures import ThreadPoolExecutor
from typing import TypeVar, Callable, Awaitable, ParamSpec, Optional, cast

T = TypeVar('T')
P = ParamSpec('P')

# 呼び出しごとのスレッド生成を避け、実行中イベントループからの変換時に
# 利用するワーカープールをプロセス内で再利用する。
_ASYNC_TO_SYNC_EXECUTOR = ThreadPoolExecutor(
    thread_name_prefix="asyncx-async-to-sync"
)

# thread-sensitiveな同期関数は、すべて同じ専用スレッドで逐次実行する。
_THREAD_SENSITIVE_EXECUTOR = ThreadPoolExecutor(
    max_workers=1,
    thread_name_prefix="asyncx-thread-sensitive",
)

def sync_to_async(
    func: Callable[P, T],
    thread_sensitive: bool = True,
    executor: Optional[ThreadPoolExecutor] = None,
) -> Callable[P, Awaitable[T]]:
    """
    同期関数を非同期関数に変換するデコレータ

    Args:
        func: 変換対象の同期関数
        thread_sensitive: 同期関数を専用の同一スレッドで逐次実行するか
        executor: thread_sensitive=Falseで使用するカスタムExecutor

    Returns:
        非同期関数
    """
    if asyncio.iscoroutinefunction(func):
        return cast(Callable[P, Awaitable[T]], func)

    if thread_sensitive and executor is not None:
        raise TypeError(
            "executor cannot be used with thread_sensitive=True"
        )

    @functools.wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        if not thread_sensitive and executor is None:
            # asyncio.to_threadは呼び出し元のContextを自動的にコピーする。
            return await asyncio.to_thread(func, *args, **kwargs)

        loop = asyncio.get_running_loop()
        context = contextvars.copy_context()
        call = functools.partial(func, *args, **kwargs)
        call_with_context = functools.partial(context.run, call)
        selected_executor = (
            _THREAD_SENSITIVE_EXECUTOR if thread_sensitive else executor
        )
        return await loop.run_in_executor(
            selected_executor,
            call_with_context,
        )

    return cast(Callable[P, Awaitable[T]], wrapper)

async def _await_with_timeout(
    awaitable: Awaitable[T],
    timeout: Optional[float]
) -> T:
    """awaitableを実行し、指定時だけタイムアウトを適用する。"""
    if timeout is None:
        return await awaitable

    task = asyncio.ensure_future(awaitable)
    try:
        return await asyncio.wait_for(task, timeout=timeout)
    except TimeoutError as exc:
        # awaitable自身が送出したTimeoutErrorは変換しない。
        if not task.cancelled():
            raise
        raise RuntimeError(
            f"Operation timed out after {timeout} seconds"
        ) from exc


def _run_awaitable(awaitable: Awaitable[T], timeout: Optional[float]) -> T:
    """新しいイベントループでawaitableを最後まで実行する。"""
    return asyncio.run(_await_with_timeout(awaitable, timeout))


def async_to_sync(
    func: Callable[P, Awaitable[T]],
    *,
    timeout: Optional[float] = None
) -> Callable[P, T]:
    """
    非同期関数を同期関数に変換するデコレータ

    Args:
        func: 変換対象の非同期関数
        timeout: タイムアウト秒数（指定しない場合は無制限）

    Returns:
        同期関数
    """
    if not asyncio.iscoroutinefunction(func):
        return cast(Callable[P, T], func)

    if timeout is not None and timeout < 0:
        raise ValueError("timeout must be greater than or equal to 0")

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        awaitable = func(*args, **kwargs)

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            # 同期コンテキストでは余分なスレッド切り替えを行わない。
            return _run_awaitable(awaitable, timeout)

        # 現在のイベントループ上で同期的に待つとデッドロックするため、
        # 再利用可能なワーカー上の別イベントループで実行する。
        context = contextvars.copy_context()
        future = _ASYNC_TO_SYNC_EXECUTOR.submit(
            context.run,
            _run_awaitable,
            awaitable,
            timeout
        )
        return future.result()

    return cast(Callable[P, T], wrapper)

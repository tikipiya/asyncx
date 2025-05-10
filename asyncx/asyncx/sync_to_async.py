import asyncio
import functools
from concurrent.futures import ThreadPoolExecutor
from typing import TypeVar, Callable, Awaitable, ParamSpec, Optional, cast

T = TypeVar('T')
P = ParamSpec('P')

def sync_to_async(
    func: Callable[P, T],
    thread_sensitive: bool = True,
    executor: Optional[ThreadPoolExecutor] = None
) -> Callable[P, Awaitable[T]]:
    """
    同期関数を非同期関数に変換するデコレータ

    Args:
        func: 変換対象の同期関数
        thread_sensitive: スレッドセーフティを考慮するかどうか
        executor: 使用するThreadPoolExecutor（指定しない場合は新規作成）

    Returns:
        非同期関数
    """
    if asyncio.iscoroutinefunction(func):
        return cast(Callable[P, Awaitable[T]], func)

    @functools.wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        if thread_sensitive:
            # スレッドセーフティを考慮する場合
            loop = asyncio.get_running_loop()
            current_executor = executor or ThreadPoolExecutor()
            try:
                return await loop.run_in_executor(
                    current_executor,
                    functools.partial(func, *args, **kwargs)
                )
            finally:
                if executor is None:
                    current_executor.shutdown(wait=False)
        else:
            # スレッドセーフティを考慮しない場合
            return await asyncio.to_thread(func, *args, **kwargs)

    return cast(Callable[P, Awaitable[T]], wrapper)

def async_to_sync(func: Callable[P, Awaitable[T]]) -> Callable[P, T]:
    """
    非同期関数を同期関数に変換するデコレータ

    Args:
        func: 変換対象の非同期関数

    Returns:
        同期関数
    """
    if not asyncio.iscoroutinefunction(func):
        return cast(Callable[P, T], func)

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # 既存のイベントループが動作中の場合
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = asyncio.run_coroutine_threadsafe(func(*args, **kwargs), loop)
                try:
                    return future.result(timeout=30)  # タイムアウトを設定
                except concurrent.futures.TimeoutError:
                    raise RuntimeError("Operation timed out while waiting for event loop")
        else:
            # 新しいイベントループを作成
            try:
                return asyncio.run(func(*args, **kwargs))
            except RuntimeError as e:
                if "already running" in str(e):
                    # 既存のイベントループが存在する場合
                    loop = asyncio.get_event_loop()
                    return loop.run_until_complete(func(*args, **kwargs))
                raise

    return cast(Callable[P, T], wrapper) 
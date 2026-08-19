import asyncio
import contextvars
import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from asyncx import async_to_sync, sync_to_async


def sync_function(x: int, y: int) -> int:
    return x + y


async def async_function(x: int, y: int) -> int:
    await asyncio.sleep(0.01)
    return x + y


class AsyncCallable:
    async def __call__(self, value: str) -> str:
        await asyncio.sleep(0)
        return value


@pytest.mark.asyncio
async def test_sync_to_async():
    async_func = sync_to_async(sync_function)

    result = await async_func(1, 2)

    assert result == 3


def test_sync_to_async_returns_coroutine_function_unchanged():
    assert sync_to_async(async_function) is async_function


@pytest.mark.asyncio
async def test_sync_to_async_returns_async_callable_unchanged():
    callable_object = AsyncCallable()

    assert sync_to_async(callable_object) is callable_object
    assert await sync_to_async(callable_object)("value") == "value"


def test_async_to_sync():
    sync_func = async_to_sync(async_function)

    result = sync_func(1, 2)

    assert result == 3


def test_async_to_sync_supports_async_callable_object():
    sync_func = async_to_sync(AsyncCallable())

    assert sync_func("value") == "value"


@pytest.mark.asyncio
async def test_thread_sensitive_calls_use_one_shared_thread():
    def identify_thread(value: int) -> tuple[int, int]:
        time.sleep(0.01)
        return value, threading.get_ident()

    async_func = sync_to_async(identify_thread, thread_sensitive=True)

    results = await asyncio.gather(*(async_func(value) for value in range(5)))

    assert [value for value, _ in results] == list(range(5))
    assert len({thread_id for _, thread_id in results}) == 1


@pytest.mark.asyncio
async def test_non_thread_sensitive_calls_can_run_in_parallel():
    barrier = threading.Barrier(2)

    def meet_in_parallel() -> int:
        barrier.wait(timeout=1)
        return threading.get_ident()

    async_func = sync_to_async(meet_in_parallel, thread_sensitive=False)

    thread_ids = await asyncio.gather(async_func(), async_func())

    assert len(set(thread_ids)) == 2


@pytest.mark.asyncio
async def test_sync_to_async_runs_in_parallel_by_default():
    barrier = threading.Barrier(2)

    def meet_in_parallel() -> int:
        barrier.wait(timeout=1)
        return threading.get_ident()

    async_func = sync_to_async(meet_in_parallel)
    thread_ids = await asyncio.gather(async_func(), async_func())

    assert len(set(thread_ids)) == 2


@pytest.mark.asyncio
async def test_non_thread_sensitive_call_uses_custom_executor():
    def current_thread_name() -> str:
        return threading.current_thread().name

    with ThreadPoolExecutor(
        max_workers=2,
        thread_name_prefix="asyncx-custom",
    ) as executor:
        async_func = sync_to_async(
            current_thread_name,
            thread_sensitive=False,
            executor=executor,
        )

        thread_name = await async_func()

    assert thread_name.startswith("asyncx-custom")


def test_thread_sensitive_rejects_custom_executor():
    with (
        ThreadPoolExecutor(max_workers=1) as executor,
        pytest.raises(TypeError, match="thread_sensitive=True"),
    ):
        sync_to_async(sync_function, thread_sensitive=True, executor=executor)


@pytest.mark.asyncio
async def test_sync_to_async_propagates_contextvars():
    request_id = contextvars.ContextVar("request_id", default="missing")

    def read_request_id() -> str:
        return request_id.get()

    request_id.set("request-123")
    sensitive_func = sync_to_async(read_request_id, thread_sensitive=True)
    regular_func = sync_to_async(read_request_id, thread_sensitive=False)

    assert await sensitive_func() == "request-123"
    assert await regular_func() == "request-123"


@pytest.mark.asyncio
async def test_custom_executor_propagates_contextvars():
    request_id = contextvars.ContextVar("request_id", default="missing")

    def read_request_id() -> str:
        return request_id.get()

    request_id.set("custom-request")
    with ThreadPoolExecutor(max_workers=1) as executor:
        async_func = sync_to_async(
            read_request_id,
            thread_sensitive=False,
            executor=executor,
        )

        result = await async_func()

    assert result == "custom-request"


@pytest.mark.asyncio
async def test_sync_to_async_cancellation_is_immediate_and_worker_recovers():
    started = threading.Event()
    release = threading.Event()
    finished = threading.Event()

    def blocking_function(value: str) -> str:
        if value == "blocking":
            started.set()
            release.wait(timeout=2)
            finished.set()
        return value

    async_func = sync_to_async(blocking_function, thread_sensitive=True)
    pending = asyncio.create_task(async_func("blocking"))
    assert await asyncio.to_thread(started.wait, 1)

    pending.cancel()
    with pytest.raises(asyncio.CancelledError):
        await pending

    assert not finished.is_set()
    release.set()
    assert await asyncio.to_thread(finished.wait, 1)
    assert await async_func("next") == "next"


@pytest.mark.asyncio
async def test_async_to_sync_with_running_loop():
    sync_func = async_to_sync(async_function)

    result = sync_func(1, 2)

    assert result == 3


def test_async_to_sync_timeout():
    async def long_running_task():
        await asyncio.sleep(2)
        return "done"

    sync_func = async_to_sync(long_running_task, timeout=0.05)

    with pytest.raises(RuntimeError, match="Operation timed out"):
        sync_func()


def test_async_to_sync_timeout_cancels_coroutine():
    cancelled = threading.Event()

    async def cancellable_task() -> None:
        try:
            await asyncio.sleep(2)
        finally:
            cancelled.set()

    sync_func = async_to_sync(cancellable_task, timeout=0.01)

    with pytest.raises(RuntimeError, match="Operation timed out"):
        sync_func()

    assert cancelled.is_set()


def test_async_to_sync_rejects_negative_timeout():
    with pytest.raises(ValueError, match="timeout"):
        async_to_sync(async_function, timeout=-1)


@pytest.mark.parametrize("timeout", [math.nan, math.inf, -math.inf])
def test_async_to_sync_rejects_non_finite_timeout(timeout: float):
    with pytest.raises(ValueError, match="finite"):
        async_to_sync(async_function, timeout=timeout)


@pytest.mark.parametrize("timeout", [True, "1"])
def test_async_to_sync_rejects_non_numeric_timeout(timeout):
    with pytest.raises(TypeError, match="finite number"):
        async_to_sync(async_function, timeout=timeout)


def test_async_to_sync_preserves_inner_timeout_error():
    async def raises_timeout() -> None:
        raise TimeoutError("from coroutine")

    sync_func = async_to_sync(raises_timeout, timeout=1)

    with pytest.raises(TimeoutError, match="from coroutine"):
        sync_func()


def test_async_to_sync_returns_sync_function_unchanged():
    assert async_to_sync(sync_function) is sync_function


@pytest.mark.asyncio
async def test_async_to_sync_in_nested_loop():
    async def outer_task():
        async def inner_task():
            sync_func = async_to_sync(async_function)
            return sync_func(1, 2)

        return await inner_task()

    result = await outer_task()

    assert result == 3


@pytest.mark.asyncio
async def test_async_to_sync_propagates_contextvars_from_running_loop():
    request_id = contextvars.ContextVar("request_id", default="missing")

    async def read_request_id() -> str:
        await asyncio.sleep(0)
        return request_id.get()

    request_id.set("async-request")
    sync_func = async_to_sync(read_request_id)

    assert sync_func() == "async-request"

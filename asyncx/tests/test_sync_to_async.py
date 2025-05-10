import pytest
import asyncio
import time
from asyncx import sync_to_async, async_to_sync
from concurrent.futures import ThreadPoolExecutor

def sync_function(x: int, y: int) -> int:
    time.sleep(0.1)  # 重い処理をシミュレート
    return x + y

async def async_function(x: int, y: int) -> int:
    await asyncio.sleep(0.1)  # 重い処理をシミュレート
    return x + y

@pytest.mark.asyncio
async def test_sync_to_async():
    async_func = sync_to_async(sync_function)
    result = await async_func(1, 2)
    assert result == 3

def test_async_to_sync():
    sync_func = async_to_sync(async_function)
    result = sync_func(1, 2)
    assert result == 3

@pytest.mark.asyncio
async def test_sync_to_async_thread_safety():
    async_func = sync_to_async(sync_function, thread_sensitive=True)
    results = await asyncio.gather(
        async_func(1, 2),
        async_func(3, 4),
        async_func(5, 6)
    )
    assert results == [3, 7, 11]

@pytest.mark.asyncio
async def test_sync_to_async_with_executor():
    with ThreadPoolExecutor(max_workers=2) as executor:
        async_func = sync_to_async(sync_function, executor=executor)
        results = await asyncio.gather(
            async_func(1, 2),
            async_func(3, 4)
        )
        assert results == [3, 7]

@pytest.mark.asyncio
async def test_async_to_sync_with_running_loop():
    async def nested_async():
        sync_func = async_to_sync(async_function)
        return sync_func(1, 2)

    result = await nested_async()
    assert result == 3

@pytest.mark.asyncio
async def test_async_to_sync_timeout():
    async def long_running_task():
        await asyncio.sleep(2)
        return "done"

    sync_func = async_to_sync(long_running_task)
    with pytest.raises(RuntimeError, match="Operation timed out"):
        sync_func()

@pytest.mark.asyncio
async def test_async_to_sync_in_nested_loop():
    async def outer_task():
        async def inner_task():
            sync_func = async_to_sync(async_function)
            return sync_func(1, 2)
        return await inner_task()

    result = await outer_task()
    assert result == 3 
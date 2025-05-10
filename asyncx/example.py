import asyncio
import time
from asyncx import sync_to_async, async_to_sync, Task, TaskManager
from typing import List

# 同期関数を非同期化
@sync_to_async
def heavy_sync_task(x: int) -> int:
    print(f"同期処理開始: {x}")
    time.sleep(1)
    print(f"同期処理完了: {x}")
    return x * 2

# 非同期関数
async def heavy_async_task(x: int) -> int:
    print(f"非同期処理開始: {x}")
    await asyncio.sleep(1)
    print(f"非同期処理完了: {x}")
    return x * 3

async def main():
    print("=== sync_to_async のテスト ===")
    start = time.time()
    results = await asyncio.gather(
        heavy_sync_task(1),
        heavy_sync_task(2),
        heavy_sync_task(3)
    )
    print(f"結果: {results}")
    print(f"実行時間: {time.time() - start:.2f}秒\n")

    print("=== TaskManager（優先度付きキュー）のテスト ===")
    manager = TaskManager[int]()
    tasks: List[Task[int]] = [
        Task("low", heavy_async_task, args=(1,), priority=1),
        Task("high", heavy_async_task, args=(2,), priority=3),
        Task("medium", heavy_async_task, args=(3,), priority=2),
    ]
    results = await manager.run_tasks(tasks)
    print(f"TaskManager結果: {results}\n")

if __name__ == "__main__":
    asyncio.run(main())

    print("=== async_to_sync のテスト ===")
    sync_heavy_async_task = async_to_sync(heavy_async_task)
    start = time.time()
    result1 = sync_heavy_async_task(4)
    result2 = sync_heavy_async_task(5)
    result3 = sync_heavy_async_task(6)
    print(f"結果: {[result1, result2, result3]}")
    print(f"実行時間: {time.time() - start:.2f}秒") 
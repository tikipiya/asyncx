import pytest
import asyncio
from typing import List, Dict
from asyncx import TaskManager, Task, TaskError, TaskTimeoutError
import heapq

async def sample_task(delay: float, result: str = "success") -> str:
    await asyncio.sleep(delay)
    return result

async def failing_task() -> None:
    await asyncio.sleep(0.1)
    raise ValueError("Task failed")

@pytest.mark.asyncio
async def test_basic_task_execution():
    manager = TaskManager[str]()
    task = Task("test_task", sample_task, args=(0.1,))
    result = await manager.run_task(task)
    assert result == "success"

@pytest.mark.asyncio
async def test_multiple_tasks():
    manager = TaskManager[str]()
    tasks = [
        Task("task1", sample_task, args=(0.1,), priority=1),
        Task("task2", sample_task, args=(0.2,), priority=2),
    ]
    results = await manager.run_tasks(tasks)
    assert len(results) == 2
    assert results["task1"] == "success"
    assert results["task2"] == "success"

@pytest.mark.asyncio
async def test_task_timeout():
    manager = TaskManager[str]()
    task = Task("timeout_task", sample_task, args=(2.0,), timeout=0.1)
    with pytest.raises(TaskTimeoutError):
        await manager.run_task(task)

@pytest.mark.asyncio
async def test_task_error_handling():
    manager = TaskManager[None]()
    task = Task("error_task", failing_task)
    with pytest.raises(TaskError):
        await manager.run_task(task)
    assert "error_task" in manager.get_errors()

@pytest.mark.asyncio
async def test_priority_queue():
    manager = TaskManager[str]()
    tasks = [
        Task("low_priority", sample_task, args=(0.1,), priority=1),
        Task("high_priority", sample_task, args=(0.1,), priority=3),
        Task("medium_priority", sample_task, args=(0.1,), priority=2),
    ]
    
    # タスクを追加
    for task in tasks:
        await manager.add_task(task)
    
    # 実行順序を確認
    execution_order: List[str] = []
    while manager._task_queue:
        task = heapq.heappop(manager._task_queue)
        execution_order.append(task.name)
    
    assert execution_order == ["high_priority", "medium_priority", "low_priority"]

@pytest.mark.asyncio
async def test_concurrent_task_execution():
    manager = TaskManager[str](max_concurrent_tasks=2)
    tasks = [
        Task(f"task_{i}", sample_task, args=(0.1,), priority=i)
        for i in range(5)
    ]
    
    results = await manager.run_tasks(tasks)
    assert len(results) == 5
    assert all(result == "success" for result in results.values()) 
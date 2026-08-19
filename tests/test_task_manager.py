import asyncio
import math
from dataclasses import FrozenInstanceError

import pytest

from asyncx import Task, TaskError, TaskManager, TaskTimeoutError


async def sample_task(delay: float, result: str = "success") -> str:
    await asyncio.sleep(delay)
    return result


async def failing_task() -> None:
    await asyncio.sleep(0)
    raise ValueError("Task failed")


@pytest.mark.asyncio
async def test_basic_task_execution():
    manager = TaskManager[str]()
    task = Task("test_task", sample_task, args=(0.01,))

    result = await manager.run_task(task)

    assert result == "success"


@pytest.mark.asyncio
async def test_multiple_tasks():
    manager = TaskManager[str]()
    tasks = [
        Task("task1", sample_task, args=(0.01,), priority=1),
        Task("task2", sample_task, args=(0.02,), priority=2),
    ]

    results = await manager.run_tasks(tasks)

    assert results == {"task1": "success", "task2": "success"}


@pytest.mark.asyncio
async def test_task_timeout():
    manager = TaskManager[str]()
    task = Task("timeout_task", sample_task, args=(1.0,), timeout=0.01)

    with pytest.raises(TaskTimeoutError):
        await manager.run_task(task)


@pytest.mark.asyncio
async def test_zero_timeout_is_enforced():
    manager = TaskManager[str]()
    task = Task("timeout_task", sample_task, args=(0.01,), timeout=0)

    with pytest.raises(TaskTimeoutError):
        await manager.run_task(task)


@pytest.mark.asyncio
async def test_task_raised_timeout_error_is_not_misclassified():
    async def raises_timeout() -> None:
        raise TimeoutError("from task body")

    manager = TaskManager[None]()
    task = Task("inner_timeout", raises_timeout, timeout=1)

    with pytest.raises(TaskError) as captured:
        await manager.run_task(task)

    assert type(captured.value) is TaskError
    assert manager.get_errors()["inner_timeout"] is captured.value


@pytest.mark.asyncio
async def test_task_error_handling():
    manager = TaskManager[None]()
    task = Task("error_task", failing_task)

    with pytest.raises(TaskError) as captured:
        await manager.run_task(task)

    assert manager.get_errors()["error_task"] is captured.value


@pytest.mark.asyncio
async def test_batch_raises_after_all_tasks_finish():
    manager = TaskManager[str](max_concurrent_tasks=2)
    tasks = [
        Task("success", sample_task, args=(0.01, "done")),
        Task("failure", failing_task),
    ]

    with pytest.raises(TaskError, match=r"1 task\(s\) failed: failure"):
        await manager.run_tasks(tasks)

    assert manager.get_results() == {"success": "done"}
    assert list(manager.get_errors()) == ["failure"]


@pytest.mark.asyncio
async def test_batch_can_collect_errors_without_raising():
    manager = TaskManager[str]()
    tasks = [
        Task("success", sample_task, args=(0, "done")),
        Task("failure", failing_task),
    ]

    results = await manager.run_tasks(tasks, raise_on_error=False)

    assert results == {"success": "done"}
    assert list(manager.get_errors()) == ["failure"]


@pytest.mark.asyncio
async def test_each_batch_resets_results_and_errors():
    manager = TaskManager[str]()
    await manager.run_tasks([Task("first", sample_task, args=(0, "first"))])
    await manager.run_tasks(
        [Task("failure", failing_task)],
        raise_on_error=False,
    )

    assert manager.get_results() == {}
    assert list(manager.get_errors()) == ["failure"]

    results = await manager.run_tasks([Task("second", sample_task, args=(0, "second"))])

    assert results == {"second": "second"}
    assert manager.get_errors() == {}


@pytest.mark.asyncio
async def test_explicit_empty_batch_discards_queued_tasks():
    executed = False

    async def mark_executed() -> None:
        nonlocal executed
        executed = True

    manager = TaskManager[None]()
    await manager.add_task(Task("queued", mark_executed))

    results = await manager.run_tasks([])

    assert results == {}
    assert executed is False


@pytest.mark.asyncio
async def test_previously_added_tasks_run_without_batch_argument():
    manager = TaskManager[str]()
    await manager.add_task(Task("queued", sample_task, args=(0, "queued-result")))

    results = await manager.run_tasks()

    assert results == {"queued": "queued-result"}


@pytest.mark.asyncio
async def test_priority_is_stable_and_observable_through_public_api():
    execution_order: list[str] = []

    async def record(name: str) -> str:
        execution_order.append(name)
        await asyncio.sleep(0)
        return name

    manager = TaskManager[str](max_concurrent_tasks=1)
    tasks = [
        Task("low", record, args=("low",), priority=1),
        Task("high_a", record, args=("high_a",), priority=3),
        Task("high_b", record, args=("high_b",), priority=3),
        Task("medium", record, args=("medium",), priority=2),
    ]

    await manager.run_tasks(tasks)

    assert execution_order == ["high_a", "high_b", "medium", "low"]


@pytest.mark.asyncio
async def test_concurrent_task_limit_is_enforced():
    active = 0
    max_active = 0

    async def tracked_task() -> str:
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.02)
        active -= 1
        return "success"

    manager = TaskManager[str](max_concurrent_tasks=2)
    tasks = [Task(f"task_{index}", tracked_task) for index in range(5)]

    results = await manager.run_tasks(tasks)

    assert len(results) == 5
    assert max_active == 2


@pytest.mark.parametrize("value", [0, -1])
def test_max_concurrent_tasks_must_be_positive(value: int):
    with pytest.raises(ValueError, match="greater than 0"):
        TaskManager(max_concurrent_tasks=value)


@pytest.mark.parametrize("value", [True, 1.5, "2"])
def test_max_concurrent_tasks_must_be_an_integer(value):
    with pytest.raises(TypeError, match="integer"):
        TaskManager(max_concurrent_tasks=value)


@pytest.mark.asyncio
async def test_add_task_rejects_duplicate_names():
    manager = TaskManager[str]()
    await manager.add_task(Task("duplicate", sample_task, args=(0,)))

    with pytest.raises(ValueError, match="Duplicate task name"):
        await manager.add_task(Task("duplicate", sample_task, args=(0,)))


@pytest.mark.asyncio
async def test_batch_rejects_duplicate_names():
    manager = TaskManager[str]()
    tasks = [
        Task("duplicate", sample_task, args=(0,)),
        Task("duplicate", sample_task, args=(0,)),
    ]

    with pytest.raises(ValueError, match="unique"):
        await manager.run_tasks(tasks)


@pytest.mark.asyncio
async def test_task_name_can_be_reused_in_a_later_batch():
    manager = TaskManager[str]()

    first = await manager.run_tasks([Task("reusable", sample_task, args=(0, "first"))])
    second = await manager.run_tasks(
        [Task("reusable", sample_task, args=(0, "second"))]
    )

    assert first == {"reusable": "first"}
    assert second == {"reusable": "second"}


@pytest.mark.asyncio
async def test_result_and_error_accessors_return_snapshots():
    manager = TaskManager[str]()
    await manager.run_tasks([Task("success", sample_task, args=(0, "value"))])

    results = manager.get_results()
    results["injected"] = "changed"

    assert manager.get_results() == {"success": "value"}

    await manager.run_tasks(
        [Task("failure", failing_task)],
        raise_on_error=False,
    )
    errors = manager.get_errors()
    errors.clear()

    assert list(manager.get_errors()) == ["failure"]


def test_task_configuration_is_immutable():
    first = Task("first", sample_task)
    second = Task("second", sample_task)

    with pytest.raises(FrozenInstanceError):
        first.name = "changed"
    with pytest.raises(TypeError):
        first.kwargs["result"] = "changed"

    assert second.kwargs == {}


def test_task_rejects_negative_timeout():
    with pytest.raises(ValueError, match="timeout"):
        Task("invalid", sample_task, timeout=-1)


@pytest.mark.parametrize("timeout", [math.nan, math.inf, -math.inf])
def test_task_rejects_non_finite_timeout(timeout: float):
    with pytest.raises(ValueError, match="finite"):
        Task("invalid", sample_task, timeout=timeout)


@pytest.mark.parametrize("timeout", [True, "1"])
def test_task_rejects_non_numeric_timeout(timeout):
    with pytest.raises(TypeError, match="finite number"):
        Task("invalid", sample_task, timeout=timeout)


@pytest.mark.parametrize("priority", [True, 1.5, "1"])
def test_task_rejects_non_integer_priority(priority):
    with pytest.raises(TypeError, match="priority"):
        Task("invalid", sample_task, priority=priority)


def test_task_rejects_empty_name():
    with pytest.raises(ValueError, match="name"):
        Task("", sample_task)


def test_task_rejects_non_string_name():
    with pytest.raises(TypeError, match="name"):
        Task(1, sample_task)


def test_task_rejects_non_callable_func():
    with pytest.raises(TypeError, match="func"):
        Task("invalid", None)


@pytest.mark.asyncio
async def test_cancelling_batch_cancels_running_tasks_and_recovers():
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def wait_forever() -> None:
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    manager = TaskManager[None]()
    running = asyncio.create_task(manager.run_tasks([Task("blocking", wait_forever)]))
    await started.wait()

    running.cancel()
    with pytest.raises(asyncio.CancelledError):
        await running

    await asyncio.wait_for(cancelled.wait(), timeout=1)
    assert await manager.run_tasks([]) == {}


@pytest.mark.asyncio
async def test_self_cancelled_task_does_not_leave_sibling_running():
    sibling_started = asyncio.Event()
    sibling_cancelled = asyncio.Event()
    sibling_finished = False

    async def sibling() -> None:
        nonlocal sibling_finished
        sibling_started.set()
        try:
            await asyncio.Event().wait()
            sibling_finished = True
        finally:
            sibling_cancelled.set()

    async def self_cancel() -> None:
        await sibling_started.wait()
        raise asyncio.CancelledError

    manager = TaskManager[None](max_concurrent_tasks=2)
    tasks = [
        Task("sibling", sibling, priority=1),
        Task("self-cancel", self_cancel),
    ]

    with pytest.raises(asyncio.CancelledError):
        await manager.run_tasks(tasks)

    await asyncio.wait_for(sibling_cancelled.wait(), timeout=1)
    await asyncio.sleep(0)
    assert sibling_finished is False
    assert manager.get_results() == {}
    assert await manager.run_tasks([]) == {}


@pytest.mark.asyncio
async def test_concurrent_batches_are_serialized():
    first_started = asyncio.Event()
    release_first = asyncio.Event()

    async def first_task() -> str:
        first_started.set()
        await release_first.wait()
        return "first"

    manager = TaskManager[str]()
    first_batch = asyncio.create_task(manager.run_tasks([Task("first", first_task)]))
    await first_started.wait()
    second_batch = asyncio.create_task(
        manager.run_tasks([Task("second", sample_task, args=(0, "second"))])
    )
    await asyncio.sleep(0)

    assert not second_batch.done()
    release_first.set()
    first_result, second_result = await asyncio.gather(
        first_batch,
        second_batch,
    )

    assert first_result == {"first": "first"}
    assert second_result == {"second": "second"}


@pytest.mark.asyncio
async def test_add_task_is_rejected_during_batch_execution():
    started = asyncio.Event()
    release = asyncio.Event()

    async def blocking_task() -> None:
        started.set()
        await release.wait()

    manager = TaskManager[None]()
    running = asyncio.create_task(manager.run_tasks([Task("blocking", blocking_task)]))
    await started.wait()

    with pytest.raises(RuntimeError, match="Cannot add tasks"):
        await manager.add_task(Task("late", blocking_task))

    release.set()
    await running


@pytest.mark.asyncio
async def test_clear_is_rejected_during_batch_execution():
    started = asyncio.Event()
    release = asyncio.Event()

    async def blocking_task() -> None:
        started.set()
        await release.wait()

    manager = TaskManager[None]()
    running = asyncio.create_task(manager.run_tasks([Task("blocking", blocking_task)]))
    await started.wait()

    with pytest.raises(RuntimeError, match="Cannot clear TaskManager"):
        manager.clear()

    release.set()
    await running


@pytest.mark.asyncio
async def test_clear_resets_queue_results_and_errors_when_idle():
    manager = TaskManager[str]()
    await manager.run_task(Task("done", sample_task, args=(0, "value")))
    await manager.add_task(Task("queued", sample_task, args=(0,)))

    manager.clear()

    assert manager.get_results() == {}
    assert manager.get_errors() == {}
    assert await manager.run_tasks() == {}

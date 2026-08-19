class TaskError(Exception):
    """タスク実行中の一般的なエラー"""

    pass


class TaskTimeoutError(TaskError):
    """タスクのタイムアウトエラー"""

    pass

class TaskError(Exception):
    """タスク実行中の一般的なエラー"""
    pass

class TaskTimeoutError(TaskError):
    """タスクのタイムアウトエラー"""
    pass

class TaskPriorityError(TaskError):
    """タスクの優先順位に関するエラー"""
    pass

class TaskResourceError(TaskError):
    """タスクのリソース制限に関するエラー"""
    pass 
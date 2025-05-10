# AsyncX Tools

非同期タスク管理のためのPythonライブラリです。

## 機能

- 複数の非同期タスクの並行実行
- タスクの優先順位付け
- エラーハンドリング
- タスクの進捗監視
- リソース制限のサポート
- 同期処理から非同期処理への変換
- 非同期処理から同期処理への変換

## インストール

```bash
pip install asyncx-tools
```

## 使用例

### タスク管理

```python
from asyncx import TaskManager, Task

async def main():
    manager = TaskManager()
    
    # タスクの作成
    task1 = Task("task1", priority=1)
    task2 = Task("task2", priority=2)
    
    # タスクの実行
    await manager.run_tasks([task1, task2])
```

### 同期処理から非同期処理への変換

```python
from asyncx import sync_to_async

# 同期関数
def heavy_calculation(x: int, y: int) -> int:
    # 重い処理
    return x + y

# 非同期関数に変換
async_heavy_calculation = sync_to_async(heavy_calculation)

# 使用例
async def main():
    result = await async_heavy_calculation(1, 2)
    print(result)  # 3
```

### 非同期処理から同期処理への変換

```python
from asyncx import async_to_sync

# 非同期関数
async def async_operation(x: int, y: int) -> int:
    await asyncio.sleep(0.1)
    return x + y

# 同期関数に変換
sync_operation = async_to_sync(async_operation)

# 使用例
result = sync_operation(1, 2)
print(result)  # 3
```

## ライセンス

MIT License 
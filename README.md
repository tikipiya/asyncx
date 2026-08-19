# AsyncX Tools

非同期タスク管理のためのPythonライブラリです。

## 機能

- 複数の非同期タスクの並行実行
- 安定した優先順位付け
- エラーハンドリング
- 同時実行数とタイムアウトの制御
- 同期処理から非同期処理への変換
- 非同期処理から同期処理への変換

## インストール

```bash
pip install asyncx-tools
```

## 使用例

### タスク管理

```python
import asyncio

from asyncx import TaskManager, Task


async def fetch_value(value: str) -> str:
    await asyncio.sleep(0.1)
    return value


async def main():
    manager = TaskManager()

    # タスクの作成
    task1 = Task("task1", fetch_value, args=("first",), priority=1)
    task2 = Task("task2", fetch_value, args=("second",), priority=2)

    # タスクの実行
    results = await manager.run_tasks([task1, task2])
    print(results)


asyncio.run(main())
```

`TaskManager`の動作:

- 優先度が高いタスクから開始し、同じ優先度では追加順を維持します。
- `max_concurrent_tasks`で同時実行数を制限できます。
- `Task(..., timeout=秒数)`でタスクごとのタイムアウトを設定できます。
- 同じバッチ内でタスク名が重複すると`ValueError`になります。
- バッチ終了時に失敗があると、既定では`TaskError`を送出します。
- `raise_on_error=False`を指定すると成功結果を返し、失敗は
  `manager.get_errors()`から取得できます。
- 結果とエラーは実行ごとに初期化されます。
- 複数の`run_tasks()`は順番に実行され、実行中の`add_task()`と`clear()`は
  競合を避けるため拒否されます。

### 同期処理から非同期処理への変換

```python
import asyncio

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


asyncio.run(main())
```

`thread_sensitive=True`（既定値）では、同期関数を共通の専用スレッドで
逐次実行します。スレッドセーフな処理を並列化する場合は
`thread_sensitive=False`を指定してください。カスタム`ThreadPoolExecutor`は
`thread_sensitive=False`の場合だけ指定できます。

### 非同期処理から同期処理への変換

```python
import asyncio

from asyncx import async_to_sync


# 非同期関数
async def async_operation(x: int, y: int) -> int:
    await asyncio.sleep(0.1)
    return x + y


# 同期関数に変換（必要ならタイムアウト秒数を指定可能）
sync_operation = async_to_sync(async_operation, timeout=1.0)

# 使用例
result = sync_operation(1, 2)
print(result)  # 3
```

## ライセンス

MIT Licenseです。詳細は[LICENSE](LICENSE)を参照してください。

利用報告や、このライブラリへのリンクは必須ではありませんが歓迎します。

## 開発環境

Windows PowerShellでは、リポジトリのルートで次のコマンドを実行します。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m pytest
python -m mypy asyncx
python -m ruff check .
python -m ruff format --check .
```

ソースコード、テスト、サンプルはそれぞれ次の場所にあります。

- ライブラリ: `asyncx/`
- テスト: `tests/`
- サンプル: `examples/`

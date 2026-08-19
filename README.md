# AsyncX Tools

AsyncX Toolsは、非同期タスクの優先度付き実行と、同期関数・非同期関数の相互変換を
小さなAPIで扱うPythonライブラリです。

## 主な機能

- 優先度と追加順を考慮した非同期タスクの実行
- 同時実行数の制限
- タスク単位のタイムアウト
- バッチ全体のエラー収集
- 同期関数をブロッキングせずに呼び出す`sync_to_async`
- 非同期関数を同期コードから呼び出す`async_to_sync`
- `ContextVar`の引き継ぎ
- Python 3.10〜3.13と型情報（`py.typed`）のサポート

## 動作環境

- Python 3.10以上
- 実行時の外部依存なし

## インストール

```bash
python -m pip install asyncx-tools
```

インストール後は`asyncx`パッケージから公開APIをインポートします。

```python
import asyncx

print(asyncx.__version__)
```

## クイックスタート

```python
import asyncio

from asyncx import Task, TaskManager


async def fetch_value(value: str, delay: float) -> str:
    await asyncio.sleep(delay)
    return value


async def main() -> None:
    manager = TaskManager[str](max_concurrent_tasks=2)
    tasks = [
        Task("low", fetch_value, args=("low", 0.1), priority=1),
        Task("high", fetch_value, args=("high", 0.1), priority=10),
        Task("medium", fetch_value, args=("medium", 0.1), priority=5),
    ]

    results = await manager.run_tasks(tasks)
    print(results)


asyncio.run(main())
```

優先度は開始順を決めます。並行実行時の完了順は各タスクの処理時間によって変わります。

## Task

`Task`は実行対象と実行条件を保持する不変データクラスです。

```python
Task(
    name,
    func,
    priority=0,
    timeout=None,
    args=(),
    kwargs={},
)
```

| 引数 | 説明 |
| --- | --- |
| `name` | 結果とエラーのキーになる空でない文字列 |
| `func` | `Awaitable`を返す呼び出し可能オブジェクト |
| `priority` | 整数。値が大きいタスクから開始 |
| `timeout` | 0以上の有限な秒数。`None`は無制限 |
| `args` | `func`へ渡す位置引数 |
| `kwargs` | `func`へ渡すキーワード引数 |

同じ優先度では追加順が維持されます。`name`、`priority`、`timeout`などのフィールドは
作成後に再代入できず、`kwargs`もコピーされた読み取り専用マッピングになります。

## TaskManager

### 作成

```python
from asyncx import TaskManager

manager = TaskManager[str](max_concurrent_tasks=10)
```

`max_concurrent_tasks`は1以上の整数です。同時に実行されるタスク数の上限になります。

| メソッド | 説明 |
| --- | --- |
| `await add_task(task)` | 優先度付きキューへ1件追加 |
| `await run_task(task)` | 1件を直ちに実行 |
| `await run_tasks(tasks=None, *, raise_on_error=True)` | キューまたは指定バッチを実行 |
| `get_results()` | 成功結果のコピーを取得 |
| `get_errors()` | エラーのコピーを取得 |
| `clear()` | 待機キュー、結果、エラーを消去 |

### タスクを直接渡して実行

```python
results = await manager.run_tasks(
    [
        Task("first", fetch_value, args=("A", 0.1)),
        Task("second", fetch_value, args=("B", 0.1)),
    ]
)
```

### 先にキューへ追加して実行

```python
await manager.add_task(Task("first", fetch_value, args=("A", 0.1)))
await manager.add_task(Task("second", fetch_value, args=("B", 0.1)))

results = await manager.run_tasks()
```

`run_tasks(tasks)`へ明示的にタスクを渡すと、追加済みキューはそのバッチで置き換わります。
空リストを渡した場合も追加済みキューは破棄されます。

### 単一タスクの実行

```python
result = await manager.run_task(Task("single", fetch_value, args=("value", 0.1)))
```

`run_task()`も同時実行数の制限を使用し、結果またはエラーをManagerへ記録します。

### 結果とエラー

```python
results = manager.get_results()
errors = manager.get_errors()
```

両メソッドは内部状態のコピーを返します。返された辞書を変更してもManager内部には
影響しません。結果とエラーは、`run_tasks()`を開始するたびに初期化されます。

### エラーを収集して処理を継続

既定ではすべてのタスクを完走した後、1件以上失敗していれば`TaskError`を送出します。

```python
import asyncio

from asyncx import Task, TaskManager


async def succeeds() -> str:
    return "ok"


async def fails() -> str:
    raise ValueError("failed")


async def main() -> None:
    manager = TaskManager[str]()
    results = await manager.run_tasks(
        [Task("success", succeeds), Task("failure", fails)],
        raise_on_error=False,
    )

    print(results)  # {"success": "ok"}
    print(manager.get_errors())  # {"failure": TaskError(...)}


asyncio.run(main())
```

個別タスクの例外は`TaskError`へ変換され、元の例外は`__cause__`に保持されます。
Managerが適用したタイムアウトは`TaskTimeoutError`になります。タスク本体が自ら送出した
`TimeoutError`は、Managerのタイムアウトとは区別して通常の`TaskError`として扱われます。

### キャンセルと同時操作

- `run_tasks()`をキャンセルすると、実行中のワーカーと兄弟タスクもキャンセルされます。
- タスク自身が`CancelledError`を送出した場合も、兄弟タスクを残留させません。
- 複数の`run_tasks()`呼び出しは、同じManager内で順番に実行されます。
- 実行中の`add_task()`と`clear()`は競合防止のため`RuntimeError`になります。
- `clear()`は待機中のキュー、結果、エラーを消去します。

キャンセルは協調的です。タスク内に`await`がなくイベントループを占有する処理は、即座に
停止できません。

## sync_to_async

同期関数をイベントループの外に移し、非同期関数として呼び出せるようにします。

```python
sync_to_async(func, thread_sensitive=False, executor=None)
```

```python
import asyncio
import time

from asyncx import sync_to_async


@sync_to_async
def blocking_io(value: int) -> int:
    time.sleep(0.2)
    return value * 2


async def main() -> None:
    results = await asyncio.gather(
        blocking_io(1),
        blocking_io(2),
        blocking_io(3),
    )
    print(results)  # [2, 4, 6]


asyncio.run(main())
```

通常の関数呼び出し形式でも利用できます。

```python
def blocking_io_plain(value: int) -> int:
    time.sleep(0.2)
    return value * 2


async_blocking_io = sync_to_async(blocking_io_plain)
```

### スレッド動作

| 設定 | 動作 | 主な用途 |
| --- | --- | --- |
| 既定値 | 複数スレッドで並行実行 | ファイル、ネットワークなどスレッドセーフなI/O |
| `thread_sensitive=True` | 共通の専用スレッドで逐次実行 | 同一スレッドを要求する既存コード |
| `executor=pool` | 指定した`ThreadPoolExecutor`で実行 | ワーカー数やライフサイクルを制御したい場合 |

カスタムExecutorは`thread_sensitive=False`の場合だけ指定できます。

```python
import time
from concurrent.futures import ThreadPoolExecutor


def blocking_io_plain(value: int) -> int:
    time.sleep(0.2)
    return value * 2


async def use_custom_pool() -> int:
    with ThreadPoolExecutor(max_workers=4) as pool:
        async_func = sync_to_async(
            blocking_io_plain,
            thread_sensitive=False,
            executor=pool,
        )
        return await async_func(10)
```

呼び出し元の`ContextVar`はワーカースレッドへ引き継がれます。呼び出し側のasyncioタスクを
キャンセルしても、スレッド上ですでに開始した同期関数自体は停止できません。同期関数の
終了後、ワーカーは再利用されます。

スレッド化は、Pythonコード主体のCPU負荷を必ず高速化するものではありません。
主な対象はブロッキングI/Oです。

非同期関数や`async __call__`を持つオブジェクトを渡した場合は二重変換せず、そのまま返します。

## async_to_sync

非同期関数を同期コードから呼び出せる関数に変換します。

```python
async_to_sync(func, *, timeout=None)
```

```python
import asyncio

from asyncx import async_to_sync


async def fetch_number(value: int) -> int:
    await asyncio.sleep(0.1)
    return value


fetch_number_sync = async_to_sync(fetch_number, timeout=1.0)
result = fetch_number_sync(10)
```

`timeout`には0以上の有限な秒数、または`None`を指定できます。Managerとは独立した変換API
なので、タイムアウト時は`RuntimeError`を送出します。非同期関数自身が送出した
`TimeoutError`は変換せず、そのまま伝播します。

同期コンテキストでは、呼び出しスレッド上に新しいイベントループを作成します。実行中の
イベントループがあるスレッドから呼ばれた場合は、デッドロックを避けるため別スレッドの
イベントループを使用します。ただし呼び出し元スレッドは完了まで同期的に待機します。

非同期コード内では`async_to_sync`を使わず、対象関数を直接`await`する方が効率的です。
特定のイベントループに結び付いた`Future`などを別スレッドへ持ち込まないでください。

非同期関数だけでなく、`async __call__`を持つオブジェクトにも対応します。

## 例外

```python
from asyncx import TaskError, TaskTimeoutError
```

| 例外 | 意味 |
| --- | --- |
| `TaskError` | タスク失敗、またはバッチ内に1件以上の失敗があった |
| `TaskTimeoutError` | `Task.timeout`で指定した時間を超過した |

`TaskTimeoutError`は`TaskError`のサブクラスです。

## 性能のヒント

- `TaskManager`の`max_concurrent_tasks`は接続先やリソースの上限に合わせて調整してください。
- 優先度は開始順を制御しますが、完了順までは保証しません。
- スレッドセーフなI/O関数では、既定の`sync_to_async`が並行性を活用します。
- スレッド固定が不要な処理に`thread_sensitive=True`を指定すると、全呼び出しが直列になります。
- 非同期関数内では`time.sleep()`などを避け、`asyncio.sleep()`または`sync_to_async`を使います。
- CPU負荷の高いPython処理には、スレッドではなくプロセス分離も検討してください。

## 1.0.0へ移行する場合の注意

- `sync_to_async`の既定値は並行実行です。スレッド固定が必要なら
  `thread_sensitive=True`を明示してください。
- `Task`の設定は作成後に変更できません。変更が必要な場合は新しい`Task`を作成してください。
- タイムアウトには有限値だけを指定できます。`NaN`と無限大は拒否されます。

その他の変更点は[CHANGELOG.md](CHANGELOG.md)を参照してください。

## 開発

Windows PowerShellでは、リポジトリのルートで次を実行します。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m pytest
python -m mypy asyncx
python -m ruff check .
python -m ruff format --check .
python -m build --sdist --wheel
python -m twine check dist/*
```

CIではPython 3.10〜3.13のテスト、Ruff、mypy、カバレッジ、配布物のビルド、
Twine検査、wheelからのimportを確認します。

```text
asyncx/    ライブラリ本体
tests/     テスト
examples/  実行例
```

## ライセンス

MIT Licenseです。詳細は[LICENSE](LICENSE)を参照してください。

利用報告や、このライブラリへのリンクは必須ではありませんが歓迎します。

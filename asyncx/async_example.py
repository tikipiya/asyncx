import asyncio
import time

async def task1():
    print("タスク1を開始します")
    await asyncio.sleep(2)  # 2秒待機
    print("タスク1が完了しました")

async def task2():
    print("タスク2を開始します")
    await asyncio.sleep(1)  # 1秒待機
    print("タスク2が完了しました")

async def task3():
    print("タスク3を開始します")
    await asyncio.sleep(3)  # 3秒待機
    print("タスク3が完了しました")

async def main():
    # タスクを並行して実行
    start_time = time.time()
    
    # すべてのタスクを同時に実行
    await asyncio.gather(task1(), task2(), task3())
    
    end_time = time.time()
    print(f"すべてのタスクが完了しました。実行時間: {end_time - start_time:.2f}秒")

if __name__ == "__main__":
    # 非同期イベントループを実行
    asyncio.run(main()) 
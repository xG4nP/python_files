import asyncio
import heapq
import uuid
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict
from enum import Enum, auto

class TaskStatus(Enum):
    PENDING = auto()
    EXECUTING = auto()
    COMPLETED = auto()
    FAILED = auto()

@dataclass(order=True)
class Task:
    """A prioritized unit of work with unique identity and state tracking."""
    priority: int
    id: str = field(default_factory=lambda: str(uuid.uuid4()), compare=False)
    func: Callable = field(repr=False, compare=False, default=None)
    args: tuple = field(default_factory=tuple, compare=False)
    status: TaskStatus = field(default=TaskStatus.PENDING, compare=False)
    result: Any = field(default=None, compare=False)

class Orchestrator:
    """
    An asynchronous kernel that manages task execution using a priority-based 
    event loop and non-blocking I/O.
    """
    def __init__(self, workers: int = 3):
        self._queue = []  # Priority Heap
        self._results: Dict[str, Task] = {}
        self._lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(workers)
        self._stop_event = asyncio.Event()

    async def schedule(self, priority: int, func: Callable, *args):
        """Injects a task into the priority heap using atomic locking."""
        async with self._lock:
            task = Task(priority=priority, func=func, args=args)
            heapq.heappush(self._queue, task)
            self._results[task.id] = task
            print(f"[SCHEDULED] Task {task.id} (Priority: {priority})")
            return task.id

    async def _worker(self):
        """Worker loop that pulls from the heap based on priority."""
        while not self._stop_event.is_set() or self._queue:
            async with self._semaphore:
                target_task = None
                async with self._lock:
                    if self._queue:
                        target_task = heapq.heappop(self._queue)

                if target_task:
                    await self._execute(target_task)
                else:
                    await asyncio.sleep(0.1)

    async def _execute(self, task: Task):
        """Executes the task and handles potential runtime failures."""
        task.status = TaskStatus.EXECUTING
        try:
            # Check if function is a coroutine or standard function
            if asyncio.iscoroutinefunction(task.func):
                task.result = await task.func(*task.args)
            else:
                task.result = task.func(*task.args)
            task.status = TaskStatus.COMPLETED
            print(f"[SUCCESS] Task {task.id} finished.")
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.result = e
            print(f"[ERROR] Task {task.id} failed: {e}")

    async def run(self):
        """Bootstraps the orchestration engine."""
        print("--- Aether Orchestrator Online ---")
        workers = [asyncio.create_task(self._worker()) for _ in range(3)]
        await asyncio.gather(*workers)

# --- Implementation Example ---

async def simulate_io_heavy_work(name: str, duration: float):
    await asyncio.sleep(duration)
    return f"Result for {name}"

async def main():
    kernel = Orchestrator(workers=2)

    # Adding tasks with varying priorities
    await kernel.schedule(10, simulate_io_heavy_work, "Low Priority Alpha", 2)
    await kernel.schedule(1, simulate_io_heavy_work, "High Priority Gamma", 1)
    await kernel.schedule(5, simulate_io_heavy_work, "Mid Priority Beta", 0.5)

    # Graceful shutdown simulation after 4 seconds
    loop = asyncio.get_running_loop()
    loop.call_later(4, kernel._stop_event.set)
    
    await kernel.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

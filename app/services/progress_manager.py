"""Progress Tracking Manager for monitoring and streaming real-time status of long-running operations."""

import asyncio
import time
import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, Optional, Callable, Any, AsyncGenerator, List
from app.core.models import TaskProgress, TaskStatus

logger = logging.getLogger("dokimi_app.progress")


class ProgressManager:
    """In-memory progress registry with async event notification for SSE/WebSocket subscribers."""

    def __init__(self):
        self._tasks: Dict[str, TaskProgress] = {}
        self._subscribers: Dict[str, List[asyncio.Queue]] = {}
        self._cancel_flags: Dict[str, bool] = {}

    def create_task(self, task_type: str, total_steps: int = 1, initial_step: str = "Starting...") -> TaskProgress:
        """Create and register a new tracked task."""
        task_id = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc)
        progress = TaskProgress(
            task_id=task_id,
            task_type=task_type,
            status=TaskStatus.RUNNING,
            percent=0.0,
            current_step=initial_step,
            total_steps=max(total_steps, 1),
            completed_steps=0,
            elapsed_seconds=0.0,
            estimated_remaining_seconds=None,
            started_at=now,
            updated_at=now,
        )
        self._tasks[task_id] = progress
        self._cancel_flags[task_id] = False
        self._subscribers[task_id] = []
        logger.info(f"Task created: [{task_id}] {task_type} (total_steps={total_steps})")
        return progress

    def get_task(self, task_id: str) -> Optional[TaskProgress]:
        """Retrieve current task state."""
        return self._tasks.get(task_id)

    def is_cancelled(self, task_id: str) -> bool:
        """Check if cancellation has been requested for this task."""
        return self._cancel_flags.get(task_id, False)

    def cancel_task(self, task_id: str) -> bool:
        """Request cancellation of an active task."""
        if task_id in self._tasks:
            self._cancel_flags[task_id] = True
            task = self._tasks[task_id]
            if task.status == TaskStatus.RUNNING:
                task.status = TaskStatus.CANCELLED
                task.current_step = "Operation cancelled by user."
                task.updated_at = datetime.now(timezone.utc)
                self._notify_subscribers(task_id, task)
            logger.info(f"Task cancellation requested for [{task_id}]")
            return True
        return False

    def update_step(
        self,
        task_id: str,
        step_text: str,
        completed_steps: Optional[int] = None,
        total_steps: Optional[int] = None,
        force_percent: Optional[float] = None
    ) -> Optional[TaskProgress]:
        """Update progress metrics, calculate elapsed and estimated remaining time, and broadcast to listeners."""
        task = self._tasks.get(task_id)
        if not task or task.status in (TaskStatus.CANCELLED, TaskStatus.COMPLETED, TaskStatus.FAILED):
            return task

        now = datetime.now(timezone.utc)
        start_ts = task.started_at.timestamp()
        current_ts = now.timestamp()
        elapsed = max(0.0, current_ts - start_ts)
        task.elapsed_seconds = round(elapsed, 2)
        task.current_step = step_text
        task.updated_at = now

        if total_steps is not None:
            task.total_steps = max(total_steps, 1)

        if completed_steps is not None:
            task.completed_steps = completed_steps

        if force_percent is not None:
            task.percent = round(min(max(force_percent, 0.0), 100.0), 1)
        elif task.total_steps > 0:
            task.percent = round(min((task.completed_steps / task.total_steps) * 100.0, 100.0), 1)

        # Estimate remaining time based on step rate
        if task.percent > 0 and task.percent < 100:
            total_est_seconds = (elapsed / (task.percent / 100.0))
            task.estimated_remaining_seconds = round(max(0.0, total_est_seconds - elapsed), 1)
        elif task.percent >= 100:
            task.estimated_remaining_seconds = 0.0

        self._notify_subscribers(task_id, task)
        return task

    def complete_task(self, task_id: str, result_data: Optional[Dict[str, Any]] = None, message: str = "Completed successfully.") -> Optional[TaskProgress]:
        """Mark task as completed."""
        task = self._tasks.get(task_id)
        if not task:
            return None

        now = datetime.now(timezone.utc)
        task.status = TaskStatus.COMPLETED
        task.percent = 100.0
        task.completed_steps = task.total_steps
        task.current_step = message
        task.estimated_remaining_seconds = 0.0
        task.elapsed_seconds = round(now.timestamp() - task.started_at.timestamp(), 2)
        task.updated_at = now
        task.result_data = result_data

        self._notify_subscribers(task_id, task)
        logger.info(f"Task [{task_id}] COMPLETED in {task.elapsed_seconds}s")
        return task

    def fail_task(self, task_id: str, error_message: str) -> Optional[TaskProgress]:
        """Mark task as failed with an error message."""
        task = self._tasks.get(task_id)
        if not task:
            return None

        now = datetime.now(timezone.utc)
        task.status = TaskStatus.FAILED
        task.error_message = error_message
        task.current_step = f"Failed: {error_message}"
        task.elapsed_seconds = round(now.timestamp() - task.started_at.timestamp(), 2)
        task.updated_at = now

        self._notify_subscribers(task_id, task)
        logger.error(f"Task [{task_id}] FAILED: {error_message}")
        return task

    def subscribe(self, task_id: str) -> asyncio.Queue:
        """Subscribe to real-time events for a specific task."""
        q = asyncio.Queue()
        if task_id not in self._subscribers:
            self._subscribers[task_id] = []
        self._subscribers[task_id].append(q)
        # Send current state immediately if task exists
        if task_id in self._tasks:
            q.put_nowait(self._tasks[task_id])
        return q

    def unsubscribe(self, task_id: str, q: asyncio.Queue) -> None:
        """Unsubscribe queue listener."""
        if task_id in self._subscribers and q in self._subscribers[task_id]:
            self._subscribers[task_id].remove(q)

    def _notify_subscribers(self, task_id: str, task: TaskProgress) -> None:
        """Push update to all active subscribers."""
        if task_id in self._subscribers:
            for q in list(self._subscribers[task_id]):
                try:
                    q.put_nowait(task)
                except Exception:
                    pass

    async def stream_task_sse(self, task_id: str) -> AsyncGenerator[str, None]:
        """Stream Server-Sent Events (SSE) for a task until completion, cancellation, or failure."""
        q = self.subscribe(task_id)
        try:
            while True:
                try:
                    task: TaskProgress = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield f"data: {task.model_dump_json()}\n\n"
                    if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                        break
                except asyncio.TimeoutError:
                    # Keep-alive heartbeat comment
                    yield ": heartbeat\n\n"
                    if task_id in self._tasks:
                        current = self._tasks[task_id]
                        if current.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                            break
        finally:
            self.unsubscribe(task_id, q)


progress_manager = ProgressManager()

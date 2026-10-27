"""Unit tests for Progress Tracking Manager and Task Streaming API."""

import pytest
import asyncio
import httpx
from fastapi.testclient import TestClient

from app.main import app
from app.services.progress_manager import progress_manager
from app.core.models import TaskProgress, TaskStatus


client = TestClient(app)


def test_create_and_get_tracked_task():
    """Verify task registration and state retrieval."""
    task = progress_manager.create_task(
        task_type="experiment",
        total_steps=10,
        initial_step="Starting evaluation"
    )
    assert task.task_id is not None
    assert task.status == TaskStatus.RUNNING
    assert task.percent == 0.0

    retrieved = progress_manager.get_task(task.task_id)
    assert retrieved is not None
    assert retrieved.task_id == task.task_id


def test_update_step_and_time_estimation():
    """Verify progress step increment and time estimation calculations."""
    task = progress_manager.create_task(task_type="batch_eval", total_steps=4)
    
    # Update step 2 of 4 (50%)
    updated = progress_manager.update_step(
        task_id=task.task_id,
        step_text="Evaluating scenario 2...",
        completed_steps=2
    )
    assert updated.percent == 50.0
    assert updated.current_step == "Evaluating scenario 2..."
    assert updated.elapsed_seconds >= 0.0


def test_task_completion_and_failure():
    """Verify completing and failing tasks."""
    task = progress_manager.create_task(task_type="test", total_steps=2)
    
    comp = progress_manager.complete_task(
        task_id=task.task_id,
        result_data={"score": 0.95},
        message="Finished successfully"
    )
    assert comp.status == TaskStatus.COMPLETED
    assert comp.percent == 100.0
    assert comp.result_data == {"score": 0.95}

    # Test failure
    task2 = progress_manager.create_task(task_type="test2", total_steps=2)
    failed = progress_manager.fail_task(task_id=task2.task_id, error_message="Network unreachable")
    assert failed.status == TaskStatus.FAILED
    assert "Network unreachable" in failed.error_message


def test_task_cancellation():
    """Verify task cancellation flow."""
    task = progress_manager.create_task(task_type="cancellable_eval", total_steps=5)
    assert progress_manager.is_cancelled(task.task_id) is False

    cancelled = progress_manager.cancel_task(task.task_id)
    assert cancelled is True
    assert progress_manager.is_cancelled(task.task_id) is True
    
    current = progress_manager.get_task(task.task_id)
    assert current.status == TaskStatus.CANCELLED


def test_task_api_endpoints():
    """Verify HTTP API endpoints for /api/tasks."""
    # 1. Create task via API
    res = client.post("/api/tasks", json={
        "task_type": "experiment",
        "total_steps": 8,
        "initial_step": "Bootstrapping..."
    })
    assert res.status_code == 200
    data = res.json()
    task_id = data["task_id"]
    assert data["status"] == "running"
    assert data["total_steps"] == 8

    # 2. Query task via API
    res = client.get(f"/api/tasks/{task_id}")
    assert res.status_code == 200
    assert res.json()["task_id"] == task_id

    # 3. Cancel task via API
    res = client.post(f"/api/tasks/{task_id}/cancel")
    assert res.status_code == 200
    assert res.json()["status"] == "cancelled"


def test_nonexistent_task_api():
    """Verify 404 behavior for invalid task IDs."""
    res = client.get("/api/tasks/invalid_id_9999")
    assert res.status_code == 404

    res = client.post("/api/tasks/invalid_id_9999/cancel")
    assert res.status_code == 404

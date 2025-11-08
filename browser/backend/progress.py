import uuid
import threading
from typing import Dict, Optional
from datetime import datetime, timedelta


class ProgressManager:
    def __init__(self, ttl_minutes: int = 10):
        self._storage: Dict[str, Dict] = {}
        self._lock = threading.Lock()
        self._ttl = timedelta(minutes=ttl_minutes)

    def _cleanup(self) -> None:
        now = datetime.now()
        expired_keys = [
            task_id for task_id, data in self._storage.items()
            if now - data["created_at"] > self._ttl
        ]
        for key in expired_keys:
            del self._storage[key]

    def create_task(self) -> str:
        task_id = str(uuid.uuid4())
        with self._lock:
            self._storage[task_id] = {
                "total": 0,
                "processed": 0,
                "status": "starting",
                "message": "Инициализация…",
                "created_at": datetime.now(),
                "error": None
            }
        return task_id

    def update(self, task_id: str, processed: int, total: int, message: Optional[str] = None) -> None:
        with self._lock:
            if task_id not in self._storage:
                return

            self._storage[task_id].update({
                "processed": processed,
                "total": total,
                "status": "processing",
                "created_at": datetime.now()
            })
            if message:
                self._storage[task_id]["message"] = message

    def complete(self, task_id: str, message: str = "Завершено") -> None:
        with self._lock:
            if task_id not in self._storage:
                return

            task = self._storage[task_id]
            task.update({
                "status": "completed",
                "message": message,
                "processed": task["total"]
            })

    def error(self, task_id: str, error_message: str) -> None:
        with self._lock:
            if task_id not in self._storage:
                return

            self._storage[task_id].update({
                "status": "error",
                "message": "Ошибка",
                "error": error_message
            })

    def get(self, task_id: str) -> Optional[Dict]:
        with self._lock:
            if task_id not in self._storage:
                return None

            self._cleanup()
            return self._storage[task_id].copy()


progress_manager = ProgressManager()

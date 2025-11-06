"""
Модуль для отслеживания прогресса обработки изображений.
"""
import uuid
import threading
from typing import Dict, Optional
from datetime import datetime, timedelta

# Глобальное хранилище прогресса
progress_storage: Dict[str, Dict] = {}
storage_lock = threading.Lock()

# Время жизни записи прогресса (10 минут)
PROGRESS_TTL = timedelta(minutes=10)


def create_progress_task() -> str:
    """Создает новую задачу обработки и возвращает её ID."""
    task_id = str(uuid.uuid4())
    with storage_lock:
        progress_storage[task_id] = {
            "total": 0,
            "processed": 0,
            "status": "starting",  # starting, processing, completed, error
            "message": "Инициализация…",
            "created_at": datetime.now(),
            "error": None
        }
    return task_id


def update_progress(task_id: str, processed: int, total: int, message: str = None):
    """Обновляет прогресс задачи."""
    with storage_lock:
        if task_id in progress_storage:
            progress_storage[task_id]["processed"] = processed
            progress_storage[task_id]["total"] = total
            progress_storage[task_id]["status"] = "processing"
            if message:
                progress_storage[task_id]["message"] = message
            progress_storage[task_id]["created_at"] = datetime.now()


def complete_progress(task_id: str, message: str = "Завершено"):
    """Отмечает задачу как завершенную."""
    with storage_lock:
        if task_id in progress_storage:
            progress_storage[task_id]["status"] = "completed"
            progress_storage[task_id]["message"] = message
            progress_storage[task_id]["processed"] = progress_storage[task_id]["total"]


def error_progress(task_id: str, error_message: str):
    """Отмечает задачу как завершенную с ошибкой."""
    with storage_lock:
        if task_id in progress_storage:
            progress_storage[task_id]["status"] = "error"
            progress_storage[task_id]["message"] = "Ошибка"
            progress_storage[task_id]["error"] = error_message


def get_progress(task_id: str) -> Optional[Dict]:
    """Получает текущий прогресс задачи."""
    with storage_lock:
        if task_id not in progress_storage:
            return None
        
        progress = progress_storage[task_id].copy()
        
        # Очистка старых задач
        cleanup_old_progress()
        
        return progress


def cleanup_old_progress():
    """Удаляет старые записи прогресса."""
    now = datetime.now()
    expired_keys = [
        task_id for task_id, data in progress_storage.items()
        if now - data["created_at"] > PROGRESS_TTL
    ]
    for key in expired_keys:
        del progress_storage[key]


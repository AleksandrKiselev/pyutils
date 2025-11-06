"""
Тесты для модуля progress.py
"""
import time
import pytest
from datetime import datetime, timedelta

from progress import (
    create_progress_task,
    update_progress,
    complete_progress,
    error_progress,
    get_progress,
    cleanup_old_progress,
    progress_storage,
    PROGRESS_TTL
)


class TestProgress:
    """Тесты для функций отслеживания прогресса."""
    
    def test_create_progress_task(self):
        """Тест создания задачи прогресса."""
        task_id = create_progress_task()
        assert task_id is not None
        assert isinstance(task_id, str)
        assert len(task_id) > 0
        
        progress = get_progress(task_id)
        assert progress is not None
        assert progress["total"] == 0
        assert progress["processed"] == 0
        assert progress["status"] == "starting"
        assert "created_at" in progress
    
    def test_update_progress(self):
        """Тест обновления прогресса."""
        task_id = create_progress_task()
        update_progress(task_id, 10, 100, "Обработка...")
        
        progress = get_progress(task_id)
        assert progress["processed"] == 10
        assert progress["total"] == 100
        assert progress["status"] == "processing"
        assert progress["message"] == "Обработка..."
    
    def test_complete_progress(self):
        """Тест завершения задачи."""
        task_id = create_progress_task()
        update_progress(task_id, 50, 100)
        complete_progress(task_id, "Завершено")
        
        progress = get_progress(task_id)
        assert progress["status"] == "completed"
        assert progress["message"] == "Завершено"
        assert progress["processed"] == progress["total"]
    
    def test_error_progress(self):
        """Тест ошибки в задаче."""
        task_id = create_progress_task()
        error_progress(task_id, "Ошибка обработки")
        
        progress = get_progress(task_id)
        assert progress["status"] == "error"
        assert progress["message"] == "Ошибка"
        assert progress["error"] == "Ошибка обработки"
    
    def test_get_progress_nonexistent(self):
        """Тест получения прогресса несуществующей задачи."""
        progress = get_progress("nonexistent_task_id")
        assert progress is None
    
    def test_multiple_tasks(self):
        """Тест работы с несколькими задачами."""
        task1 = create_progress_task()
        task2 = create_progress_task()
        
        update_progress(task1, 10, 50)
        update_progress(task2, 20, 100)
        
        progress1 = get_progress(task1)
        progress2 = get_progress(task2)
        
        assert progress1["processed"] == 10
        assert progress2["processed"] == 20
        assert progress1["total"] == 50
        assert progress2["total"] == 100
    
    def test_progress_thread_safety(self):
        """Тест потокобезопасности (базовый)."""
        import threading
        
        task_id = create_progress_task()
        results = []
        
        def update_task(value):
            update_progress(task_id, value, 100)
            results.append(get_progress(task_id)["processed"])
        
        threads = [threading.Thread(target=update_task, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Проверяем, что последнее обновление сохранилось
        final_progress = get_progress(task_id)
        assert final_progress["processed"] in results
    
    def test_cleanup_old_progress(self, monkeypatch):
        """Тест очистки старых задач."""
        task_id = create_progress_task()
        
        # Мокаем время создания задачи на прошлое
        old_time = datetime.now() - PROGRESS_TTL - timedelta(minutes=1)
        progress_storage[task_id]["created_at"] = old_time
        
        # Вызываем cleanup через get_progress
        get_progress(task_id)
        
        # Задача должна быть удалена
        assert task_id not in progress_storage
    
    def test_progress_percentage_calculation(self):
        """Тест расчета процента прогресса."""
        task_id = create_progress_task()
        update_progress(task_id, 25, 100)
        
        progress = get_progress(task_id)
        percentage = (progress["processed"] / progress["total"] * 100) if progress["total"] > 0 else 0
        assert percentage == 25.0
    
    def test_progress_zero_total(self):
        """Тест прогресса с нулевым общим количеством."""
        task_id = create_progress_task()
        update_progress(task_id, 0, 0, "Инициализация")
        
        progress = get_progress(task_id)
        assert progress["total"] == 0
        assert progress["processed"] == 0


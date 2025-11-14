import os
from functools import lru_cache


@lru_cache(maxsize=1024)
def _get_thumbnail_data(file_path: str, mtime: float) -> bytes:
    """Читает миниатюру с диска. Кэшируется по пути и времени модификации."""
    with open(file_path, "rb") as f:
        return f.read()


def get_thumbnail_data(file_path: str) -> bytes:
    """Получает данные миниатюры с кэшированием. Проверяет актуальность по mtime."""
    mtime = os.path.getmtime(file_path)
    return _get_thumbnail_data(file_path, mtime)


def invalidate_thumbnail_cache(file_path: str) -> None:
    """Инвалидирует кэш миниатюры для указанного файла"""
    try:
        _get_thumbnail_data.cache_clear()
    except OSError:
        pass


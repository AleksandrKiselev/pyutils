"""
Утилиты для операций с файлами и папками.
"""
import os
import hashlib
import logging
from functools import lru_cache
from typing import Dict, Any, Iterator, Optional
from config import config
from exceptions import FileOperationError

logger = logging.getLogger(__name__)

_created_dirs_cache = set()


def _sanitize_filename(filename: str) -> str:
    """
    Очищает имя файла от небезопасных символов для использования в именах файлов метаданных.
    Заменяет недопустимые символы на подчеркивания.
    """
    # Удаляем или заменяем небезопасные символы
    unsafe_chars = '<>:"/\\|?*'
    safe_name = filename
    for char in unsafe_chars:
        safe_name = safe_name.replace(char, '_')
    
    # Ограничиваем длину имени для избежания проблем с длинными путями
    # Оставляем достаточно места для хеша (8 символов) и расширения
    max_length = 200
    if len(safe_name) > max_length:
        # Берем начало и конец имени файла
        name_part = safe_name[:max_length // 2] + safe_name[-(max_length // 2):]
        safe_name = name_part
    
    return safe_name


@lru_cache(maxsize=10000)
def _get_path_hash(rel_path_normalized: str) -> str:
    """
    Вычисляет MD5 хеш от нормализованного относительного пути.
    Кешируется для ускорения повторных вычислений.
    """
    return hashlib.md5(rel_path_normalized.encode('utf-8')).hexdigest()


def get_metadata_file_path(image_path: str, ext: str) -> str:
    try:
        if not os.path.isabs(image_path):
            image_path = get_absolute_path(image_path)
        
        rel_path = get_relative_path(image_path)
        
        if rel_path.startswith(".."):
            rel_dir = ""
            logger.warning(f"Файл {image_path} находится вне IMAGE_FOLDER, метаданные будут в корне .metadata")
        else:
            rel_dir = os.path.dirname(rel_path) or ""
        
        filename = os.path.basename(image_path)
        
        meta_base = os.path.join(config.IMAGE_FOLDER, ".metadata")
        if rel_dir:
            meta_dir = os.path.join(meta_base, rel_dir)
        else:
            meta_dir = meta_base
        
        if meta_dir not in _created_dirs_cache:
            os.makedirs(meta_dir, exist_ok=True)
            _created_dirs_cache.add(meta_dir)
        
        # Используем хеш относительного пути для гарантированной уникальности
        # Это решает проблему конфликтов для файлов с одинаковым именем, но разными расширениями,
        # а также для файлов со сложными именами (точки, специальные символы и т.д.)
        # Хеш вычисляется от нормализованного относительного пути (с использованием '/' как разделителя)
        # Используется кешированная функция для ускорения повторных вычислений
        rel_path_normalized = rel_path.replace("\\", "/")
        path_hash = _get_path_hash(rel_path_normalized)
        
        # Сохраняем читаемость: используем короткое имя файла + хеш для уникальности
        # Это позволяет легко найти файл по имени, но гарантирует отсутствие конфликтов
        # Формат: имя_расширение_хеш.расширение_метаданных (например: image_png_e5f6g7h8.webp)
        base_name, original_ext = os.path.splitext(filename)
        safe_base = _sanitize_filename(base_name)
        safe_ext = original_ext.lstrip('.').lower() if original_ext else 'noext'
        new_filename = f"{safe_base}_{safe_ext}_{path_hash[:8]}{ext}"
        
        return os.path.join(meta_dir, new_filename)
    except OSError as e:
        logger.error(f"Ошибка создания директории метаданных для {image_path}: {e}")
        raise FileOperationError(f"Не удалось создать директорию метаданных: {e}") from e


def get_metadata_path(image_path: str) -> str:
    return get_metadata_file_path(image_path, ".json")


def get_thumbnail_path(image_path: str) -> str:
    return get_metadata_file_path(image_path, ".webp")


def get_image_paths(folder=None):
    if folder:
        if not os.path.isdir(folder):
            logger.warning(f"Указанный путь не является директорией: {folder}")
            return []
        paths = []
        try:
            with os.scandir(folder) as entries:
                for entry in entries:
                    if entry.is_file():
                        ext = os.path.splitext(entry.name)[1].lower()
                        if ext in config.ALLOWED_EXTENSIONS:
                            paths.append(entry.path)
        except OSError as e:
            logger.warning(f"Ошибка чтения директории {folder}: {e}")
        return paths
    else:
        return list(walk_images())


def get_absolute_path(relative_path: str, root_folder: Optional[str] = None) -> str:
    if root_folder is None:
        root_folder = config.IMAGE_FOLDER
    
    if not relative_path:
        return os.path.normpath(os.path.abspath(root_folder))
    
    root = os.path.normpath(os.path.abspath(root_folder))
    relative_path = relative_path.lstrip('/\\')
    while relative_path.startswith('..'):
        relative_path = relative_path[3:].lstrip('/\\')
    
    full_path = os.path.normpath(os.path.abspath(os.path.join(root, relative_path)))
    
    root_abs = os.path.abspath(root)
    full_abs = os.path.abspath(full_path)
    
    if not (full_abs == root_abs or full_abs.startswith(root_abs + os.sep)):
        logger.warning(f"Попытка доступа к пути вне корневой директории: {relative_path}")
        raise FileOperationError(f"Путь находится вне разрешенной директории")
    
    return full_path


def get_relative_path(absolute_path: str, root_folder: Optional[str] = None) -> str:
    if root_folder is None:
        root_folder = config.IMAGE_FOLDER
    
    try:
        abs_path = os.path.normpath(os.path.abspath(absolute_path))
        root = os.path.normpath(os.path.abspath(root_folder))
        
        rel_path = os.path.relpath(abs_path, root)
        return rel_path.replace("\\", "/")
    except ValueError:
        return absolute_path.replace(root_folder, "").lstrip(os.sep).replace("\\", "/")


def walk_images(root_folder: Optional[str] = None) -> Iterator[str]:
    if root_folder is None:
        root_folder = config.IMAGE_FOLDER
    
    try:
        for root, dirs, files in os.walk(root_folder):
            dirs[:] = [d for d in dirs if not d.startswith(".metadata")]
            for file in files:
                if os.path.splitext(file)[1].lower() in config.ALLOWED_EXTENSIONS:
                    yield os.path.join(root, file)
    except OSError as e:
        logger.error(f"Ошибка обхода дерева директорий {root_folder}: {e}")
        raise FileOperationError(f"Не удалось обойти дерево директорий: {e}") from e


def build_folder_tree(base_path: str, relative: str = "") -> Dict[str, Any]:
    tree: Dict[str, Any] = {}
    full_path = os.path.join(base_path, relative)

    try:
        for entry in os.scandir(full_path):
            if entry.is_dir():
                if entry.name.startswith("."):
                    continue
                rel_path = os.path.join(relative, entry.name).replace("\\", "/")
                
                try:
                    image_count = sum(
                        1 for f in os.listdir(entry.path)
                        if os.path.isfile(os.path.join(entry.path, f)) and
                           os.path.splitext(f)[1].lower() in config.ALLOWED_EXTENSIONS
                    )
                except OSError as e:
                    logger.warning(f"Ошибка подсчета изображений в {entry.path}: {e}")
                    image_count = 0
                
                children = build_folder_tree(base_path, rel_path)
                
                if image_count > 0 or children:
                    tree[rel_path] = {
                        "name": entry.name,
                        "count": image_count,
                        "children": children
                    }
    except OSError as e:
        logger.error(f"Ошибка построения дерева папок для {full_path}: {e}")
        raise FileOperationError(f"Не удалось построить дерево папок: {e}") from e
    
    return tree


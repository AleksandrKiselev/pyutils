"""
Утилиты для операций с файлами и папками.
"""
import os
import logging
from typing import Dict, Any, Iterator, Optional
from config import config
from exceptions import FileOperationError

logger = logging.getLogger(__name__)


# Кэш для созданных директорий, чтобы избежать повторных вызовов os.makedirs
_created_dirs_cache = set()

def get_metadata_file_path(image_path: str, ext: str) -> str:
    """
    Возвращает путь к файлу метаданных в папке .metadata с сохранением структуры подпапок.
    Использует такое же имя файла, как у изображения, только с другим расширением.
    Принимает как абсолютный, так и относительный путь от IMAGE_FOLDER.
    
    Пример: folder1/subfolder/image.jpg -> .metadata/folder1/subfolder/image.json
    """
    try:
        # Нормализуем путь: если относительный, преобразуем в абсолютный
        if not os.path.isabs(image_path):
            image_path = get_absolute_path(image_path)
        
        # Получаем относительный путь от IMAGE_FOLDER
        rel_path = get_relative_path(image_path)
        
        # Проверяем, что файл находится внутри IMAGE_FOLDER
        # Если путь начинается с '..', значит файл вне IMAGE_FOLDER
        if rel_path.startswith(".."):
            # Для файлов вне IMAGE_FOLDER сохраняем в корне .metadata
            rel_dir = ""
            logger.warning(f"Файл {image_path} находится вне IMAGE_FOLDER, метаданные будут в корне .metadata")
        else:
            # Получаем директорию из относительного пути
            rel_dir = os.path.dirname(rel_path) if os.path.dirname(rel_path) else ""
        
        filename = os.path.basename(image_path)
        
        # Создаем путь в .metadata с сохранением структуры подпапок
        meta_base = os.path.join(config.IMAGE_FOLDER, ".metadata")
        if rel_dir:
            meta_dir = os.path.join(meta_base, rel_dir)
        else:
            meta_dir = meta_base
        
        # Создаем директорию если её нет (с кэшированием)
        if meta_dir not in _created_dirs_cache:
            os.makedirs(meta_dir, exist_ok=True)
            _created_dirs_cache.add(meta_dir)
        
        # Получаем имя файла без расширения и добавляем новое расширение
        base_name = os.path.splitext(filename)[0]
        new_filename = base_name + ext
        
        return os.path.join(meta_dir, new_filename)
    except OSError as e:
        logger.error(f"Ошибка создания директории метаданных для {image_path}: {e}")
        raise FileOperationError(f"Не удалось создать директорию метаданных: {e}") from e


def get_metadata_path(image_path: str) -> str:
    return get_metadata_file_path(image_path, ".json")


def get_thumbnail_path(image_path: str) -> str:
    return get_metadata_file_path(image_path, ".webp")


def get_absolute_path(relative_path: str, root_folder: Optional[str] = None) -> str:
    if root_folder is None:
        root_folder = config.IMAGE_FOLDER
    
    # Обработка пустого пути
    if not relative_path:
        return os.path.normpath(os.path.abspath(root_folder))
    
    # Нормализуем пути для предотвращения path traversal атак
    root = os.path.normpath(os.path.abspath(root_folder))
    # Убираем начальные слэши и точки из relative_path
    relative_path = relative_path.lstrip('/\\')
    # Убираем '..' из начала пути
    while relative_path.startswith('..'):
        relative_path = relative_path[3:].lstrip('/\\')
    
    full_path = os.path.normpath(os.path.abspath(os.path.join(root, relative_path)))
    
    # Проверяем, что результирующий путь находится внутри root_folder
    # Нормализуем оба пути для корректного сравнения
    root_abs = os.path.abspath(root)
    full_abs = os.path.abspath(full_path)
    
    # Проверяем, что full_path начинается с root + разделитель пути
    # или равен root (для корневой директории)
    if not (full_abs == root_abs or full_abs.startswith(root_abs + os.sep)):
        logger.warning(f"Попытка доступа к пути вне корневой директории: {relative_path}")
        raise FileOperationError(f"Путь находится вне разрешенной директории")
    
    return full_path


def get_relative_path(absolute_path: str, root_folder: Optional[str] = None) -> str:
    """
    Преобразует абсолютный путь в относительный от root_folder.
    Использует os.path.relpath для безопасной обработки путей.
    """
    if root_folder is None:
        root_folder = config.IMAGE_FOLDER
    
    try:
        # Нормализуем пути для корректного сравнения
        abs_path = os.path.normpath(os.path.abspath(absolute_path))
        root = os.path.normpath(os.path.abspath(root_folder))
        
        # Используем os.path.relpath для безопасного преобразования
        rel_path = os.path.relpath(abs_path, root)
        return rel_path.replace("\\", "/")
    except ValueError:
        # Если пути на разных дисках (Windows), используем старый способ
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


def walk_metadata(root_folder: Optional[str] = None) -> Iterator[str]:
    """
    Обходит все файлы метаданных в папке .metadata рекурсивно (включая подпапки).
    """
    if root_folder is None:
        root_folder = config.IMAGE_FOLDER
    
    meta_dir = os.path.join(root_folder, ".metadata")
    
    if not os.path.exists(meta_dir):
        return
    
    try:
        for root, dirs, files in os.walk(meta_dir):
            for file in files:
                if file.lower().endswith(".json"):
                    yield os.path.join(root, file)
    except OSError as e:
        logger.error(f"Ошибка обхода папки метаданных {meta_dir}: {e}")
        raise FileOperationError(f"Не удалось обойти папку метаданных: {e}") from e


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


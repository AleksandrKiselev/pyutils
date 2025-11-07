"""
Утилиты для операций с файлами и папками.
"""
import os
import hashlib
import logging
from functools import lru_cache
from typing import Dict, Any, Iterator, Optional, Tuple
from config import config

logger = logging.getLogger(__name__)


@lru_cache(maxsize=10000)
def _get_filename_hash(image_path: str) -> str:
    filename = os.path.basename(image_path)
    return hashlib.md5(filename.encode('utf-8')).hexdigest()


def get_metadata_file_path(image_path: str, ext: str) -> str:
    try:
        rel_path = get_relative_path(image_path)
        rel_dir = os.path.dirname(rel_path)
        meta_base = os.path.join(config.IMAGE_FOLDER, ".metadata")
        meta_dir = os.path.join(meta_base, rel_dir)
        os.makedirs(meta_dir, exist_ok=True)

        # Формируем уникальное имя файла метаданных на основе хеша от имени файла (с расширением)
        filename_hash = _get_filename_hash(image_path)
        new_filename = f"{filename_hash}{ext}"

        return os.path.join(meta_dir, new_filename)
    except OSError as e:
        logger.error(f"Ошибка создания директории метаданных для {image_path}: {e}")
        raise OSError(f"Не удалось создать директорию метаданных: {e}") from e


def get_metadata_path(image_path: str) -> str:
    return get_metadata_file_path(image_path, ".json")


def get_thumbnail_path(image_path: str) -> str:
    return get_metadata_file_path(image_path, ".webp")


def get_absolute_path(relative_path: str, root_folder: Optional[str] = None) -> str:
    """
    Преобразует относительный путь в абсолютный.
    """
    if root_folder is None:
        root_folder = config.IMAGE_FOLDER
    
    if os.path.isabs(relative_path):
        return relative_path
    
    return os.path.normpath(os.path.join(root_folder, relative_path))


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


def get_absolute_paths(metadata: Dict[str, Any], root_folder: Optional[str] = None) -> Tuple[str, str, str]:
    """
    Получает все абсолютные пути из метаданных.
    Возвращает кортеж (image_path, thumbnail_path, metadata_path).
    """
    image_path = metadata.get("image_path", "")
    if not image_path:
        raise ValueError("Путь к изображению не найден в метаданных")
    
    thumbnail_path = metadata.get("thumbnail_path", "")
    if not thumbnail_path:
        raise ValueError("Путь к миниатюре не найден в метаданных")
    
    metadata_path = metadata.get("metadata_path", "")
    if not metadata_path:
        raise ValueError("Путь к метаданным не найден в метаданных")
    
    return (
        get_absolute_path(image_path, root_folder),
        get_absolute_path(thumbnail_path, root_folder),
        get_absolute_path(metadata_path, root_folder)
    )


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
        raise OSError(f"Не удалось обойти дерево директорий: {e}") from e


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
        raise OSError(f"Не удалось построить дерево папок: {e}") from e
    
    return tree


"""
Утилиты для операций с файлами и папками.
"""
import os
import logging
from typing import Dict, Any, Iterator, Optional
from config import config
from exceptions import FileOperationError

logger = logging.getLogger(__name__)


def get_metadata_file_path(image_path: str, ext: str) -> str:
    try:
        folder = os.path.dirname(image_path)
        meta_dir = os.path.join(folder, ".metadata")
        os.makedirs(meta_dir, exist_ok=True)
        base = os.path.splitext(os.path.basename(image_path))[0]
        return os.path.join(meta_dir, base + ext)
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
    return os.path.join(root_folder, relative_path)


def get_relative_path(absolute_path: str, root_folder: Optional[str] = None) -> str:
    if root_folder is None:
        root_folder = config.IMAGE_FOLDER
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
    if root_folder is None:
        root_folder = config.IMAGE_FOLDER
    
    try:
        for root, dirs, files in os.walk(root_folder):
            if os.path.basename(root) == ".metadata":
                for file in files:
                    if file.lower().endswith(".json"):
                        yield os.path.join(root, file)
    except OSError as e:
        logger.error(f"Ошибка обхода папок метаданных {root_folder}: {e}")
        raise FileOperationError(f"Не удалось обойти папки метаданных: {e}") from e


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


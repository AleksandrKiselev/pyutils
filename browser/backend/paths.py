import os
import hashlib
import logging
from functools import lru_cache
from pathlib import Path as PathLib
from typing import Dict, Any, Iterator, Optional, List, Tuple

from config import config

logger = logging.getLogger(__name__)


@lru_cache(maxsize=10000)
def _get_filename_hash(image_path: str) -> str:
    filename = os.path.basename(image_path)
    return hashlib.md5(filename.encode('utf-8')).hexdigest()


def count_images_in_dir(dir_path: str) -> int:
    """Подсчитывает количество изображений в директории."""
    try:
        count = sum(
            1 for entry in os.scandir(dir_path)
            if entry.is_file() and os.path.splitext(entry.name)[1].lower() in config.ALLOWED_EXTENSIONS
        )
        return count
    except OSError as e:
        logger.warning(f"Ошибка подсчета изображений в {dir_path}: {e}")
        return 0


def get_thumbnail_path(image_path: str) -> str:
    rel_path = get_relative_path(image_path)
    rel_dir = PathLib(rel_path).parent
    meta_dir = PathLib(config.IMAGE_FOLDER) / config.METADATA_FOLDER / rel_dir
    meta_dir.mkdir(parents=True, exist_ok=True)

    filename_hash = _get_filename_hash(image_path)
    return str(meta_dir / f"{filename_hash}{config.THUMBNAIL_EXTENSION}")


def get_absolute_path(relative_path: str, root_folder: Optional[str] = None) -> str:
    if root_folder is None:
        root_folder = config.IMAGE_FOLDER

    if os.path.isabs(relative_path):
        return relative_path

    return os.path.normpath(os.path.join(root_folder, relative_path))


def get_image_paths(folder: Optional[str] = None) -> List[str]:
    if folder:
        if not os.path.isdir(folder):
            logger.warning(f"Указанный путь не является директорией: {folder}")
            return []

        try:
            with os.scandir(folder) as entries:
                return [
                    entry.path for entry in entries
                    if entry.is_file() and os.path.splitext(entry.name)[1].lower() in config.ALLOWED_EXTENSIONS
                ]
        except OSError as e:
            logger.warning(f"Ошибка чтения директории {folder}: {e}")
            return []

    return list(walk_images())


def get_absolute_paths(metadata: Dict[str, Any], root_folder: Optional[str] = None) -> Tuple[str, str]:
    required_keys = ["image_path", "thumb_path"]
    missing = [key for key in required_keys if not metadata.get(key)]
    if missing:
        raise ValueError(f"В метаданных отсутствуют пути: {', '.join(missing)}")

    return tuple(get_absolute_path(metadata[key], root_folder) for key in required_keys)


def get_relative_path(absolute_path: str, root_folder: Optional[str] = None) -> str:
    if root_folder is None:
        root_folder = config.IMAGE_FOLDER

    try:
        abs_path = PathLib(absolute_path).resolve()
        root = PathLib(root_folder).resolve()
        rel_path = abs_path.relative_to(root)
        return str(rel_path).replace("\\", "/")
    except (ValueError, TypeError):
        try:
            return str(PathLib(absolute_path).relative_to(PathLib(root_folder))).replace("\\", "/")
        except (ValueError, TypeError):
            return absolute_path.replace(root_folder, "").lstrip(os.sep).replace("\\", "/")


def walk_images(root_folder: Optional[str] = None) -> Iterator[str]:
    if root_folder is None:
        root_folder = config.IMAGE_FOLDER

    try:
        for root, dirs, files in os.walk(root_folder):
            dirs[:] = [d for d in dirs if not d.startswith(config.METADATA_FOLDER)]
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
            if not entry.is_dir() or entry.name.startswith("."):
                continue

            rel_path = os.path.join(relative, entry.name).replace("\\", "/")
            total_count = count_images_in_dir(entry.path)
            children = build_folder_tree(base_path, rel_path)

            if total_count > 0 or children:
                tree[rel_path] = {
                    "name": entry.name,
                    "total": total_count,
                    "children": children
                }
    except OSError as e:
        logger.error(f"Ошибка построения дерева папок для {full_path}: {e}")
        raise

    return tree

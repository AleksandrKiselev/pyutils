import os
import uuid
import shutil
import logging
from pathlib import Path
from typing import List, Dict, Optional, Callable
from concurrent.futures import ThreadPoolExecutor

from paths import get_absolute_path, get_relative_path, get_absolute_paths, get_metadata_path, get_thumbnail_path
from metadata import metadata_store
from image import collect_images, filter_images, sort_images
from config import config

logger = logging.getLogger(__name__)

PARALLEL_THRESHOLD = 100
MAX_WORKERS = 16


def _get_filtered_images(folder_path: Optional[str], search: str) -> List[Dict]:
    images = collect_images(folder_path)
    return filter_images(images, search)


def _get_metadata_or_raise(metadata_id: str) -> Dict:
    metadata = metadata_store.get_by_id(metadata_id)
    if not metadata:
        raise FileNotFoundError(f"Метаданные с ID {metadata_id} не найдены")
    return metadata


def _process_images_parallel(images: List[Dict], processor: Callable[[Dict], int]) -> int:
    if len(images) < PARALLEL_THRESHOLD:
        return sum(processor(img) for img in images)

    max_workers = min(MAX_WORKERS, (os.cpu_count() or 1) * 2)
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        return sum(pool.map(processor, images))


class ImageService:
    @staticmethod
    def get_images(folder_path: Optional[str], search: str, sort_by: str,
                   order: str, limit: int, offset: int) -> List[Dict]:
        images = _get_filtered_images(folder_path, search)
        images = sort_images(images, sort_by, order)
        return images[offset:offset + limit]

    @staticmethod
    def delete_image(metadata_id: str) -> None:
        metadata = _get_metadata_or_raise(metadata_id)
        _, thumb, _ = get_absolute_paths(metadata)
        os.remove(get_absolute_path(metadata["image_path"]))
        if os.path.exists(thumb):
            os.remove(thumb)
        metadata_store.delete(metadata_id)


class MetadataService:
    @staticmethod
    def update_metadata(metadata_ids: List[str], updates: Dict) -> None:
        allowed_keys = {"checked", "rating", "tags"}
        metadata_updates = {key: updates[key] for key in allowed_keys if key in updates}
        if not metadata_updates:
            return

        for metadata_id in metadata_ids:
            metadata = metadata_store.get_by_id(metadata_id)
            if not metadata:
                logger.warning(f"Метаданные с ID {metadata_id} не найдены")
                continue
            metadata_store.update(metadata_id, metadata_updates)

    @staticmethod
    def uncheck_all(folder_path: Optional[str], search: str) -> int:
        images = _get_filtered_images(folder_path, search)

        def process_single(img: Dict) -> int:
            metadata_id = img.get("id")
            if not metadata_id:
                return 0

            metadata = metadata_store.get_by_id(metadata_id)
            if not metadata or not metadata.get("checked"):
                return 0

            metadata_store.update(metadata_id, {"checked": False})
            return 1

        return _process_images_parallel(images, process_single)

    @staticmethod
    def delete_metadata(folder_path: Optional[str], search: str) -> int:
        images = _get_filtered_images(folder_path, search)

        def process_single(img: Dict) -> int:
            metadata_id = img.get("id")
            if not metadata_id:
                return 0
            metadata_store.delete(metadata_id)
            return 1

        return sum(process_single(img) for img in images)


class FavoritesService:
    @staticmethod
    def copy_to_favorites(metadata_id: str) -> None:
        metadata = _get_metadata_or_raise(metadata_id)

        if not config.FAVORITES_FOLDER:
            raise ValueError("В конфиге не указана папка избранного")

        src = get_absolute_path(metadata["image_path"])
        dst = os.path.join(config.FAVORITES_FOLDER, os.path.basename(metadata["image_path"]))

        if Path(src).resolve() == Path(dst).resolve():
            raise ValueError("Источник и назначение совпадают")

        Path(config.FAVORITES_FOLDER).mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

        new_metadata = metadata.copy()
        new_metadata["image_path"] = get_relative_path(dst)
        new_metadata["meta_path"] = get_relative_path(get_metadata_path(dst))
        new_metadata["thumb_path"] = get_relative_path(get_thumbnail_path(dst))
        new_metadata["id"] = str(uuid.uuid4())

        tags = set(new_metadata.get("tags", []))
        tags.add("favorite")
        new_metadata["tags"] = sorted(tags)

        metadata_store.save(new_metadata)

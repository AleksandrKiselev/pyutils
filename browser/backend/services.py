import os
import uuid
import shutil
import random
import logging
from pathlib import Path
from typing import List, Dict, Optional

from paths import get_absolute_path, get_relative_path, get_absolute_paths, get_thumbnail_path
from metadata import metadata_store
from image import collect_images, filter_images, sort_images
from thumbnail import ThumbnailService
from config import config
from database import force_save

logger = logging.getLogger(__name__)


def _get_filtered_images(folder_path: Optional[str], search: str) -> List[Dict]:
    images = collect_images(folder_path)
    return filter_images(images, search)


def _get_metadata_or_raise(metadata_id: str) -> Dict:
    metadata = metadata_store.get_by_id(metadata_id)
    if not metadata:
        raise FileNotFoundError(f"Метаданные с ID {metadata_id} не найдены")
    return metadata


class ImageService:
    @staticmethod
    def get_images(folder_path: Optional[str], search: str, sort_by: str,
                   order: str, limit: int, offset: int) -> List[Dict]:
        images = _get_filtered_images(folder_path, search)
        
        if sort_by == "random":
            if not images:
                return []
            page_images = random.sample(images, min(limit, len(images)))
        else:
            images = sort_images(images, sort_by, order)
            page_images = images[offset:offset + limit]
        
        ThumbnailService.ensure_thumbnails_batch(page_images)
        
        return page_images

    @staticmethod
    def delete_image(metadata_id: str) -> None:
        metadata = _get_metadata_or_raise(metadata_id)
        _, thumb = get_absolute_paths(metadata)
        os.remove(get_absolute_path(metadata["image_path"]))
        if os.path.exists(thumb):
            os.remove(thumb)
        metadata_store.delete(metadata_id)
        force_save()


class MetadataService:
    @staticmethod
    def update_metadata(metadata_ids: List[str], updates: Dict) -> None:
        allowed_keys = {"checked", "rating", "tags"}
        metadata_updates = {key: updates[key] for key in allowed_keys if key in updates}
        if not metadata_updates:
            return

        batch_updates = [{"id": metadata_id, **metadata_updates} for metadata_id in metadata_ids]
        updated_count = metadata_store.update_batch(batch_updates)
        if updated_count < len(metadata_ids):
            logger.warning(f"Обновлено {updated_count} из {len(metadata_ids)} метаданных")
        force_save()

    @staticmethod
    def uncheck_all(folder_path: Optional[str], search: str) -> int:
        images = _get_filtered_images(folder_path, search)
        metadata_ids_to_update = [
            img.get("id") for img in images 
            if img.get("id") and img.get("checked")
        ]
        if not metadata_ids_to_update:
            return 0
        batch_updates = [{"id": metadata_id, "checked": False} for metadata_id in metadata_ids_to_update]
        result = metadata_store.update_batch(batch_updates)
        force_save()
        return result

    @staticmethod
    def delete_metadata(folder_path: Optional[str], search: str) -> int:
        images = _get_filtered_images(folder_path, search)
        metadata_ids = [img.get("id") for img in images if img.get("id")]
        if not metadata_ids:
            return 0
        result = metadata_store.delete_batch(metadata_ids)
        force_save()
        return result


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
        new_metadata["thumb_path"] = get_relative_path(get_thumbnail_path(dst))
        new_metadata["id"] = str(uuid.uuid4())

        tags = set(new_metadata.get("tags", []))
        tags.add("favorite")
        new_metadata["tags"] = sorted(tags)

        metadata_store.save(new_metadata)
        force_save()

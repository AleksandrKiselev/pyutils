import os
import uuid
import shutil
import random
import logging
from pathlib import Path
from typing import List, Dict, Optional

from paths import get_absolute_path, get_relative_path, get_absolute_paths, get_thumbnail_path
from metadata import metadata_store
from image import filter_images, sort_images
from thumbnail import ThumbnailService
from config import config
from thumbnail_cache import invalidate_thumbnail_cache

logger = logging.getLogger(__name__)


def _get_filtered_images(folder_path: Optional[str], search: str, hide_checked: bool = False) -> List[Dict]:
    images = metadata_store.get_by_folder(folder_path)
    if hide_checked:
        images = [img for img in images if not img.get("checked", False)]
    return filter_images(images, search)


def _get_metadata_or_raise(metadata_id: str) -> Dict:
    all_metadata = metadata_store.get_by_ids([metadata_id])
    if metadata_id not in all_metadata:
        raise FileNotFoundError(f"Метаданные с ID {metadata_id} не найдены")
    return all_metadata[metadata_id]


class ImageService:
    @staticmethod
    def get_images(folder_path: Optional[str], search: str, sort_by: str,
                   order: str, limit: int, offset: int, hide_checked: bool = False) -> List[Dict]:
        images = _get_filtered_images(folder_path, search, hide_checked)
        
        if sort_by == "random":
            if not images:
                return []
            page_images = random.sample(images, min(limit, len(images)))
        else:
            images = sort_images(images, sort_by, order)
            page_images = images[offset:offset + limit]
        
        ThumbnailService.ensure_thumbnails(page_images)
        
        return page_images

    @staticmethod
    def delete_image(metadata_id: str) -> None:
        metadata = _get_metadata_or_raise(metadata_id)
        _, thumb = get_absolute_paths(metadata)
        os.remove(get_absolute_path(metadata["image_path"]))
        if os.path.exists(thumb):
            # Инвалидируем кэш перед удалением
            invalidate_thumbnail_cache(thumb)
            os.remove(thumb)
        metadata_store.delete([metadata_id])

    @staticmethod
    def delete_checked_images(folder_path: Optional[str], search: str) -> int:
        images = _get_filtered_images(folder_path, search)
        metadata_ids = [
            img.get("id") for img in images 
            if img.get("id") and img.get("checked")
        ]
        if not metadata_ids:
            return 0
        
        all_metadata = metadata_store.get_by_ids(metadata_ids)
        if not all_metadata:
            return 0
        
        ids_to_delete_metadata = []
        for metadata_id, metadata in all_metadata.items():
            try:
                image_path, thumb_path = get_absolute_paths(metadata)
                file_deleted = False
                
                if os.path.exists(image_path):
                    try:
                        os.remove(image_path)
                        file_deleted = True
                    except OSError as e:
                        logger.warning(f"Ошибка удаления файла изображения {image_path}: {e}")
                        continue
                else:
                    file_deleted = True
                
                if os.path.exists(thumb_path):
                    try:
                        # Инвалидируем кэш перед удалением
                        invalidate_thumbnail_cache(thumb_path)
                        os.remove(thumb_path)
                    except OSError as e:
                        logger.warning(f"Ошибка удаления миниатюры {thumb_path}: {e}")
                
                if file_deleted:
                    ids_to_delete_metadata.append(metadata_id)
            except Exception as e:
                logger.warning(f"Ошибка обработки изображения {metadata.get('image_path', 'unknown')}: {e}")
        
        if ids_to_delete_metadata:
            metadata_store.delete(ids_to_delete_metadata)
        
        return len(ids_to_delete_metadata)

    @staticmethod
    def get_unchecked_prompts(folder_path: Optional[str], search: str, sort_by: str = "date", order: str = "desc") -> List[str]:
        images = _get_filtered_images(folder_path, search)
        unchecked_images = [
            img for img in images 
            if not img.get("checked", False)
        ]
        if sort_by == "random":
            if unchecked_images:
                unchecked_images = random.sample(unchecked_images, len(unchecked_images))
        else:
            unchecked_images = sort_images(unchecked_images, sort_by, order)
        unchecked_prompts = []
        seen = set()
        for img in unchecked_images:
            prompt = img.get("prompt", "").strip()
            if prompt and prompt not in seen:
                unchecked_prompts.append(prompt)
                seen.add(prompt)
        return unchecked_prompts


class MetadataService:
    @staticmethod
    def update_metadata(metadata_ids: List[str], updates: Dict) -> None:
        allowed_keys = {"checked", "rating", "tags"}
        metadata_updates = {key: updates[key] for key in allowed_keys if key in updates}
        if not metadata_updates:
            return

        batch_updates = [{"id": metadata_id, **metadata_updates} for metadata_id in metadata_ids]
        updated_count = metadata_store.update(batch_updates)
        if updated_count < len(metadata_ids):
            logger.warning(f"Обновлено {updated_count} из {len(metadata_ids)} метаданных")

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
        result = metadata_store.update(batch_updates)
        return result

    @staticmethod
    def delete_metadata(folder_path: Optional[str], search: str) -> int:
        images = _get_filtered_images(folder_path, search)
        metadata_ids = [img.get("id") for img in images if img.get("id")]
        if not metadata_ids:
            return 0
        result = metadata_store.delete(metadata_ids)
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
        tags.add(config.FAVORITE_TAG)
        new_metadata["tags"] = sorted(tags)

        metadata_store.save([new_metadata])


class BookmarksService:
    @staticmethod
    def get_all() -> List[Dict]:
        return metadata_store._db_manager.get_bookmarks()
    
    @staticmethod
    def add(metadata_id: str, image_data: Dict) -> None:
        image_path = image_data.get("image_path", "")
        path_parts = image_path.split("/") if "/" in image_path else image_path.split("\\")
        filename = path_parts[-1] if path_parts else ""
        folder_path = "/".join(path_parts[:-1]) if len(path_parts) > 1 else ""
        
        bookmark = {
            "id": str(uuid.uuid4()),
            "metadata_id": metadata_id,
            "image_path": image_path,
            "folder_path": folder_path,
            "prompt": image_data.get("prompt", ""),
            "filename": filename,
            "sort_by": image_data.get("sort_by", "date-desc"),
            "search_query": image_data.get("search_query", "")
        }
        
        metadata_store._db_manager.add_bookmark(bookmark)
    
    @staticmethod
    def remove(metadata_id: str) -> bool:
        return metadata_store._db_manager.remove_bookmark(metadata_id)
    
    @staticmethod
    def has(metadata_id: str) -> bool:
        return metadata_store._db_manager.has_bookmark(metadata_id)

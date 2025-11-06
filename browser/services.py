"""
Бизнес-логика сервисов для приложения просмотра изображений.
"""
import os
import json
import shutil
import logging
from typing import List, Dict, Optional

from exceptions import FileOperationError, InvalidRequestError
from paths import get_absolute_path, get_metadata_path, get_thumbnail_path
from metadata import load_metadata, save_metadata
from image import collect_images, filter_images, sort_images
from tag import get_all_tags_cached
from config import config

logger = logging.getLogger(__name__)


class ImageService:
    @staticmethod
    def get_images(folder_path: Optional[str], search: str, sort_by: str, 
                   order: str, limit: int, offset: int) -> List[Dict]:
        images = collect_images(None if folder_path is None else folder_path)
        images = filter_images(images, search)
        images = sort_images(images, sort_by, order)
        return images[offset:offset + limit]
    
    @staticmethod
    def delete_image(filename: str) -> None:
        base = get_absolute_path(filename)
        thumb = get_thumbnail_path(base)
        meta = get_metadata_path(base)
        
        try:
            if os.path.exists(base):
                os.remove(base)
            for path in (thumb, meta):
                if os.path.exists(path):
                    os.remove(path)
        except OSError as e:
            raise FileOperationError(f"Не удалось удалить изображение: {e}")


class MetadataService:
    @staticmethod
    def update_metadata(filenames: List[str], updates: Dict) -> None:
        for filename in filenames:
            image_path = get_absolute_path(filename)
            if not os.path.exists(image_path):
                continue
                
            try:
                mtime = os.path.getmtime(image_path)
                metadata = load_metadata(image_path, mtime)
                
                for key in ("checked", "rating", "tags"):
                    if key in updates:
                        metadata[key] = updates[key]
                        
                save_metadata(image_path, metadata)
            except Exception as e:
                raise FileOperationError(f"Не удалось обновить метаданные для {filename}: {e}")
        
        load_metadata.cache_clear()
        get_all_tags_cached.cache_clear()
    
    @staticmethod
    def uncheck_all(folder_path: Optional[str], search: str) -> int:
        images = collect_images(None if folder_path is None else folder_path)
        images = filter_images(images, search)
        
        count = 0
        for img in images:
            image_path = get_absolute_path(img["filename"])
            if not os.path.exists(image_path):
                continue
                
            try:
                mtime = os.path.getmtime(image_path)
                metadata = load_metadata(image_path, mtime)
                if metadata.get("checked"):
                    metadata["checked"] = False
                    save_metadata(image_path, metadata)
                    count += 1
            except Exception as e:
                logger.warning(f"Не удалось снять отметку с {img['filename']}: {e}")
        
        load_metadata.cache_clear()
        get_all_tags_cached.cache_clear()
        return count


class FavoritesService:
    @staticmethod
    def copy_to_favorites(filename: str) -> None:
        src = get_absolute_path(filename)
        dst_dir = config.get("favorites_folder")
        
        if not dst_dir:
            raise InvalidRequestError("В конфиге не указана папка избранного")
        
        dst = os.path.join(dst_dir, os.path.basename(filename))
        os.makedirs(dst_dir, exist_ok=True)
        
        if os.path.abspath(src) == os.path.abspath(dst):
            raise InvalidRequestError("Источник и назначение совпадают")
        
        try:
            shutil.copy2(src, dst)
            
            src_meta = get_metadata_path(filename)
            dst_meta = get_metadata_path(dst)
            
            meta = {}
            if os.path.exists(src_meta):
                with open(src_meta, "r", encoding="utf-8") as f:
                    meta = json.load(f)
            
            tags = set(meta.get("tags", []))
            tags.add("favorite")
            meta["tags"] = sorted(tags)
            
            with open(dst_meta, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
        except Exception as e:
            raise FileOperationError(f"Не удалось скопировать в избранное: {e}")


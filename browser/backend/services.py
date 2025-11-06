"""
Бизнес-логика сервисов для приложения просмотра изображений.
"""
import os
import json
import shutil
import logging
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor

from exceptions import FileOperationError, InvalidRequestError
from paths import get_absolute_path, get_metadata_path, get_thumbnail_path
from metadata import load_metadata, save_metadata
from image import collect_images, filter_images, sort_images
from tag import get_all_tags_cached
from config import config

logger = logging.getLogger(__name__)


def _get_filtered_images(folder_path: Optional[str], search: str):
    """Вспомогательная функция для получения отфильтрованных изображений."""
    images = collect_images(None if folder_path is None else folder_path)
    return filter_images(images, search)


def _clear_metadata_cache():
    """Очищает кэш метаданных и тегов."""
    load_metadata.cache_clear()
    get_all_tags_cached.cache_clear()


class ImageService:
    @staticmethod
    def get_images(folder_path: Optional[str], search: str, sort_by: str, 
                   order: str, limit: int, offset: int) -> List[Dict]:
        images = _get_filtered_images(folder_path, search)
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
        # Обрабатываем файлы последовательно для безопасности операций с метаданными
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
        
        _clear_metadata_cache()
    
    @staticmethod
    def uncheck_all(folder_path: Optional[str], search: str) -> int:
        images = _get_filtered_images(folder_path, search)
        
        # Используем параллельную обработку для больших коллекций
        def process_single(img):
            image_path = get_absolute_path(img["filename"])
            if not os.path.exists(image_path):
                return 0
            
            try:
                mtime = os.path.getmtime(image_path)
                metadata = load_metadata(image_path, mtime)
                if metadata.get("checked"):
                    metadata["checked"] = False
                    save_metadata(image_path, metadata)
                    return 1
            except Exception as e:
                logger.warning(f"Не удалось снять отметку с {img['filename']}: {e}")
            return 0
        
        # Для небольших коллекций обрабатываем последовательно, для больших - параллельно
        if len(images) < 100:
            count = sum(process_single(img) for img in images)
        else:
            max_workers = min(16, (os.cpu_count() or 1) * 2)
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                results = list(pool.map(process_single, images))
                count = sum(results)
        
        _clear_metadata_cache()
        return count
    
    @staticmethod
    def delete_metadata(folder_path: Optional[str], search: str) -> int:
        """Удаляет файлы метаданных для всех изображений в указанной папке или фильтрах."""
        images = _get_filtered_images(folder_path, search)
        
        # Используем параллельную обработку для больших коллекций
        def process_single(img):
            image_path = get_absolute_path(img["filename"])
            if not os.path.exists(image_path):
                return 0
            
            try:
                meta_path = get_metadata_path(image_path)
                if os.path.exists(meta_path):
                    os.remove(meta_path)
                    return 1
            except Exception as e:
                logger.warning(f"Не удалось удалить метаданные для {img['filename']}: {e}")
            return 0
        
        # Для небольших коллекций обрабатываем последовательно, для больших - параллельно
        if len(images) < 100:
            count = sum(process_single(img) for img in images)
        else:
            max_workers = min(16, (os.cpu_count() or 1) * 2)
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                results = list(pool.map(process_single, images))
                count = sum(results)
        
        _clear_metadata_cache()
        return count


class FavoritesService:
    @staticmethod
    def copy_to_favorites(filename: str) -> None:
        src = get_absolute_path(filename)
        dst_dir = config.FAVORITES_FOLDER
        
        if not dst_dir:
            raise InvalidRequestError("В конфиге не указана папка избранного")
        
        dst = os.path.join(dst_dir, os.path.basename(filename))
        os.makedirs(dst_dir, exist_ok=True)
        
        if os.path.abspath(src) == os.path.abspath(dst):
            raise InvalidRequestError("Источник и назначение совпадают")
        
        try:
            shutil.copy2(src, dst)
            
            src_meta = get_metadata_path(src)
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


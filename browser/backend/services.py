"""
Бизнес-логика сервисов для приложения просмотра изображений.
"""
import os
import json
import shutil
import logging
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor

from paths import get_absolute_path, get_relative_path
from paths import get_absolute_paths
from paths import get_metadata_path, get_thumbnail_path  # Используются только для первичной инициализации
from metadata import load_metadata, save_metadata
from image import collect_images, filter_images, sort_images
from config import config

logger = logging.getLogger(__name__)


def _get_filtered_images(folder_path: Optional[str], search: str):
    images = collect_images(None if folder_path is None else folder_path)
    return filter_images(images, search)


def clear_caches():
    load_metadata.cache_clear()


class ImageService:
    @staticmethod
    def get_images(folder_path: Optional[str], search: str, sort_by: str, 
                   order: str, limit: int, offset: int) -> List[Dict]:
        images = _get_filtered_images(folder_path, search)
        images = sort_images(images, sort_by, order)
        return images[offset:offset + limit]
    
    @staticmethod
    def delete_image(filename: str) -> None:
        """Удаляет изображение и связанные файлы. Пути берутся из метаданных."""
        base = get_absolute_path(filename)
        mtime = os.path.getmtime(base)
        metadata = load_metadata(base, mtime)
        
        _, thumb, meta = get_absolute_paths(metadata)
        
        os.remove(base)
        os.remove(thumb)
        os.remove(meta)


class MetadataService:
    @staticmethod
    def update_metadata(filenames: List[str], updates: Dict) -> None:
        for filename in filenames:
            image_path = get_absolute_path(filename)
            mtime = os.path.getmtime(image_path)
            metadata = load_metadata(image_path, mtime)
            
            for key in ("checked", "rating", "tags"):
                if key in updates:
                    metadata[key] = updates[key]
                    
            save_metadata(metadata)
        
        clear_caches()
    
    @staticmethod
    def uncheck_all(folder_path: Optional[str], search: str) -> int:
        images = _get_filtered_images(folder_path, search)
        
        def process_single(img):
            filename = img.get("metadata", {}).get("image_path", "")
            image_path = get_absolute_path(filename)
            mtime = os.path.getmtime(image_path)
            metadata = load_metadata(image_path, mtime)
            
            if metadata.get("checked"):
                metadata["checked"] = False
                save_metadata(metadata)
                return 1
            return 0
        
        if len(images) < 100:
            count = sum(process_single(img) for img in images)
        else:
            max_workers = min(16, (os.cpu_count() or 1) * 2)
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                results = list(pool.map(process_single, images))
                count = sum(results)
        
        clear_caches()
        return count
    
    @staticmethod
    def delete_metadata(folder_path: Optional[str], search: str) -> int:
        images = _get_filtered_images(folder_path, search)
        
        def process_single(img):
            filename = img.get("metadata", {}).get("image_path", "")
            image_path = get_absolute_path(filename)
            mtime = os.path.getmtime(image_path)
            metadata = load_metadata(image_path, mtime)
            
            _, _, meta_path = get_absolute_paths(metadata)
            os.remove(meta_path)
            return 1
        
        count = sum(process_single(img) for img in images)
        
        clear_caches()
        return count


class FavoritesService:
    @staticmethod
    def copy_to_favorites(filename: str) -> None:
        src = get_absolute_path(filename)
        dst_dir = config.FAVORITES_FOLDER
        
        if not dst_dir:
            raise ValueError("В конфиге не указана папка избранного")
        
        dst = os.path.join(dst_dir, os.path.basename(filename))
        os.makedirs(dst_dir, exist_ok=True)
        
        if os.path.abspath(src) == os.path.abspath(dst):
            raise ValueError("Источник и назначение совпадают")
        
        shutil.copy2(src, dst)
        
        mtime = os.path.getmtime(src)
        src_metadata = load_metadata(src, mtime)
        _, _, src_meta = get_absolute_paths(src_metadata)
        dst_meta = get_metadata_path(dst)
        
        with open(src_meta, "r", encoding="utf-8") as f:
            meta = json.load(f)
        
        meta["image_path"] = get_relative_path(dst)
        meta["metadata_path"] = get_relative_path(dst_meta)
        meta["thumbnail_path"] = get_relative_path(get_thumbnail_path(dst))
        
        tags = set(meta["tags"])
        tags.add("favorite")
        meta["tags"] = sorted(tags)
        
        with open(dst_meta, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)


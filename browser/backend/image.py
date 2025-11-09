import os
import random
import logging
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Dict

from metadata import metadata_store
from paths import get_absolute_path, get_image_paths
from config import config

logger = logging.getLogger(__name__)


def needs_processing(folder=None):
    image_paths = get_image_paths(folder)
    if not image_paths:
        return False

    return any(not metadata_store.has_metadata(path) for path in image_paths)


def collect_images(folder=None, progress_callback=None):
    image_paths = get_image_paths(folder)
    total = len(image_paths)

    if total == 0:
        return []

    if progress_callback:
        progress_callback(0, total, f"Найдено {total} изображений")

    BATCH_SIZE = 1000
    results = []
    new_images = []
    
    logger.info(f"Начало загрузки метаданных для {total} изображений")
    for i in range(0, total, BATCH_SIZE):
        batch_paths = image_paths[i:i + BATCH_SIZE]
        batch_metadata = metadata_store.get_batch(batch_paths)
        
        for idx, path in enumerate(batch_paths):
            batch_idx = i + idx
            if idx < len(batch_metadata) and batch_metadata[idx] is not None:
                results.append((batch_idx, batch_metadata[idx]))
            else:
                new_images.append((batch_idx, path))
        
        processed = min(i + len(batch_paths), total)
        if progress_callback:
            progress_callback(processed, total, f"Загрузка метаданных {processed}/{total}")

    if new_images:
        max_workers = min(32, (os.cpu_count() or 1) * 4, len(new_images))
        new_metadata_list = []
        
        def create_metadata(original_idx: int, path: str) -> Optional[tuple]:
            try:
                metadata = metadata_store._create_metadata(path)
                return (original_idx, metadata)
            except Exception as e:
                logger.error(f"Ошибка обработки изображения {path}: {e}")
                return None
        
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(create_metadata, original_idx, path): (original_idx, path)
                for original_idx, path in new_images
            }
            
            logger.info(f"Начало создания метаданных для {len(new_images)} новых изображений")
            for future in as_completed(futures):
                original_idx, path = futures[future]
                try:
                    result = future.result()
                    if result:
                        idx, metadata = result
                        results.append((idx, metadata))
                        new_metadata_list.append(metadata)
                    processed = len(results)
                    if progress_callback:
                        progress_callback(processed, total, f"Создание метаданных {processed}/{total}")
                except Exception as e:
                    logger.error(f"Ошибка обработки изображения {path}: {e}")
            
            logger.info(f"Завершено создание метаданных для {len(new_metadata_list)} изображений")
        
        if new_metadata_list:
            metadata_store.save_batch(new_metadata_list)

    results.sort(key=lambda x: x[0])
    logger.info(f"Завершена загрузка метаданных для {len(results)} изображений")
    
    # Финальный вызов прогресса - 100% завершено
    if progress_callback:
        progress_callback(total, total, f"Обработка завершена: {len(results)} изображений")
    
    return [metadata for _, metadata in results]


def sort_images(images, sort_by, order):
    if not images:
        return images

    if sort_by == "random":
        return images

    reverse = (order == "desc")
    mtime_cache = {}

    def safe_get_mtime(img):
        filename = img.get("image_path", "")
        if filename not in mtime_cache:
            mtime_cache[filename] = os.path.getmtime(get_absolute_path(filename))
        return mtime_cache[filename]

    key_funcs = {
        "date": safe_get_mtime,
        "filename": lambda img: img.get("image_path", "").lower(),
        "prompt": lambda img: img.get("prompt", "").lower(),
        "rating": lambda img: img.get("rating", 0),
        "tags": lambda img: ", ".join(img.get("tags", [])).lower(),
        "size": lambda img: img.get("size", 0),
        "hash": lambda img: img.get("hash", "")
    }

    key_func = key_funcs.get(sort_by)
    if key_func:
        images.sort(key=key_func, reverse=reverse)

    return images


def filter_images(images, search):
    search = search.strip().lower()
    if not search:
        return images

    def normalize(tag):
        return tag.strip().lower()

    if search.startswith(("tags:", "tag:", "t:")):
        raw = search.split(":", 1)[1].strip().lower()
        if not raw:
            return [img for img in images if not img.get("tags")]

        groups = [
            [normalize(t) for t in part.split("|") if t]
            for part in raw.split(",") if part
        ]

        def match(image_tags):
            image_tags = {normalize(tag) for tag in image_tags}
            return all(any(tag in image_tags for tag in group) for group in groups)

        return [img for img in images if match(img.get("tags", []))]

    if search.startswith(("duplicates:", "duplicate:", "d:")):
        hash_counts = Counter(img.get("hash", "") for img in images if img.get("hash"))
        return [img for img in images if img.get("hash") and hash_counts[img.get("hash")] > 1]

    return [img for img in images if search in img.get("prompt", "").lower()]

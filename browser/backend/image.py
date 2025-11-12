import os
import random
import logging
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Optional

from metadata import metadata_store
from paths import get_absolute_path, get_image_paths
from config import config

logger = logging.getLogger(__name__)

# Блокировки для предотвращения параллельного создания метаданных для одной папки
_folder_locks: Dict[str, threading.Lock] = {}
_locks_lock = threading.Lock()


def _get_folder_lock(folder: Optional[str]) -> threading.Lock:
    """Получает блокировку для конкретной папки. Для folder=None используется ключ ""."""
    folder_key = folder or ""
    with _locks_lock:
        if folder_key not in _folder_locks:
            _folder_locks[folder_key] = threading.Lock()
        return _folder_locks[folder_key]


def needs_processing(folder=None):
    image_paths = get_image_paths(folder)
    if not image_paths:
        return False

    return any(not metadata_store.has_metadata(path) for path in image_paths)


def collect_images(folder=None, progress_callback=None):
    image_paths = get_image_paths(folder)
    if len(image_paths) == 0:
        return []
    
    results = []
    
    folder_lock = _get_folder_lock(folder)
    with folder_lock:
        existing_metadata = metadata_store.get_by_paths(image_paths)
        new_images = []
        for idx, (path, metadata) in enumerate(zip(image_paths, existing_metadata)):
            if metadata is not None:
                results.append((idx, metadata))
            else:
                new_images.append((idx, path))

        if new_images:
            max_workers = min(32, (os.cpu_count() or 1) * 4, len(new_images))
            new_metadata_list = []
            total = len(new_images)
            processed_new = 0
            
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                futures = {
                    pool.submit(metadata_store.create_metadata, path): (original_idx, path)
                    for original_idx, path in new_images
                }
                
                logger.info(f"Начало создания метаданных для {total} новых изображений")
                for future in as_completed(futures):
                    original_idx, path = futures[future]
                    metadata = future.result()
                    results.append((original_idx, metadata))
                    new_metadata_list.append(metadata)
                    processed_new += 1
                    if progress_callback and total >= 10:
                        progress_callback(processed_new, total, f"Создание метаданных {processed_new}/{total}")
                
                logger.info(f"Завершено создание метаданных для {len(new_metadata_list)} изображений")
            
            if new_metadata_list:
                metadata_store.save(new_metadata_list)
                logger.info(f"Сохранено {len(new_metadata_list)} метаданных в БД")
    
    return [metadata for _, metadata in sorted(results)]


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

    if search.startswith("u:"):
        raw = search.split(":", 1)[1].strip().lower()
        unchecked_images = [img for img in images if not img.get("checked", False)]
        if not raw:
            return unchecked_images
        if raw.startswith("u:"):
            return [img for img in unchecked_images if raw in img.get("prompt", "").lower()]
        return filter_images(unchecked_images, raw)

    # Фильтр отмеченных изображений
    if search.startswith("c:"):
        raw = search.split(":", 1)[1].strip().lower()
        checked_images = [img for img in images if img.get("checked", False)]
        if not raw:
            return checked_images
        if raw.startswith("c:"):
            return [img for img in checked_images if raw in img.get("prompt", "").lower()]
        return filter_images(checked_images, raw)

    if search.startswith("t:"):
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

    if search.startswith("dh:"):
        hash_counts = Counter(img.get("hash", "") for img in images if img.get("hash"))
        return [img for img in images if img.get("hash") and hash_counts[img.get("hash")] > 1]

    if search.startswith("dp:"):
        prompt_counts = Counter(img.get("prompt", "").strip().lower() for img in images if img.get("prompt", "").strip())
        duplicate_prompts = {prompt for prompt, count in prompt_counts.items() if count > 1}
        result = []
        for img in images:
            prompt = img.get("prompt", "").strip().lower()
            if prompt in duplicate_prompts:
                result.append(img)
        # Сортируем по промпту, чтобы одинаковые промпты шли рядом (попарно)
        result.sort(key=lambda img: img.get("prompt", "").strip().lower())
        return result

    return [img for img in images if search in img.get("prompt", "").lower()]

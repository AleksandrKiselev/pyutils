"""
Утилиты обработки изображений: сортировка, фильтрация и сбор.
"""
import os
import logging
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from metadata import load_metadata, get_metadata
from paths import get_absolute_path, get_image_paths
from config import config

logger = logging.getLogger(__name__)


def needs_processing(folder=None):
    image_paths = get_image_paths(folder)
    
    if not image_paths:
        return False
    
    for image_path in image_paths:
        mtime = os.path.getmtime(image_path)
        metadata = load_metadata(image_path, mtime)
        if not metadata:
            return True

    return False


def collect_images(folder=None, progress_callback=None):
    image_paths = get_image_paths(folder)
    
    max_workers = min(32, (os.cpu_count() or 1) * 4, len(image_paths))
    
    total = len(image_paths)
    if progress_callback:
        progress_callback(0, total, f"Найдено {total} изображений")
    
    if total == 0:
        return []
    
    results = [None] * total
    processed = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {}
        for idx, path in enumerate(image_paths):
            future = pool.submit(get_metadata, path)
            futures[future] = idx
        
        for future in as_completed(futures):
            idx = futures[future]
            try:
                result = future.result()
                results[idx] = result
                processed += 1
                if progress_callback:
                    progress_callback(processed, total, f"Обработка {processed}/{total}")
            except Exception as e:
                logger.error(f"Ошибка обработки изображения {image_paths[idx]}: {e}")
                raise
    
    return [r for r in results if r is not None]

def sort_images(images, sort_by, order):
    reverse = (order == "desc")
    
    mtime_cache = {}
    def safe_get_mtime(img):
        filename = img.get("metadata", {}).get("image_path", "")
        if filename not in mtime_cache:
            mtime_cache[filename] = os.path.getmtime(get_absolute_path(filename))
        return mtime_cache[filename]
    
    key_funcs = {
        "date": safe_get_mtime,
        "filename": lambda img: img.get("metadata", {}).get("image_path", "").lower(),
        "prompt": lambda img: img.get("metadata", {}).get("prompt", "").lower(),
        "rating": lambda img: img.get("metadata", {}).get("rating", 0),
        "tags": lambda img: ", ".join(img.get("metadata", {}).get("tags", [])).lower(),
        "size": lambda img: img.get("metadata", {}).get("size", 0),
        "hash": lambda img: img.get("metadata", {}).get("hash", "")
    }
    if sort_by in key_funcs:
        images.sort(key=key_funcs[sort_by], reverse=reverse)
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
            return [img for img in images if not img.get("metadata", {}).get("tags")]
        groups = [
            [normalize(t) for t in part.split("|") if t]
            for part in raw.split(",") if part
        ]
        def match(image_tags):
            image_tags = set(normalize(tag) for tag in image_tags)
            for group in groups:
                if not any(tag in image_tags for tag in group):
                    return False
            return True
        return [img for img in images if match(img.get("metadata", {}).get("tags", []))]
    elif search.startswith(("duplicates:", "duplicate:", "d:")):
        # Фильтрация по дубликатам: показываем только изображения с одинаковым содержимым (хеш)
        # Собираем хеши файлов
        hash_counts = Counter()
        for img in images:
            file_hash = img.get("metadata", {}).get("hash", "")
            if file_hash:  # Пропускаем файлы без хеша
                hash_counts[file_hash] += 1
        
        # Возвращаем только те изображения, у которых хеш встречается более одного раза
        return [
            img for img in images 
            if img.get("metadata", {}).get("hash") and hash_counts[img.get("metadata", {}).get("hash", "")] > 1
        ]
    else:
        return [img for img in images if search in img.get("metadata", {}).get("prompt", "").lower()]
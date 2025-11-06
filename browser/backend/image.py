"""
Утилиты обработки изображений: сортировка, фильтрация и сбор.
"""
import os
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from metadata import load_metadata
from thumbnail import process_thumbnail
from paths import get_absolute_path, get_relative_path, walk_images, get_metadata_path
from config import config

logger = logging.getLogger(__name__)


def process_image(image_path):
    mtime = os.path.getmtime(image_path)
    metadata = load_metadata(image_path, mtime)
    thumbnail = process_thumbnail(image_path)
    file_size = os.path.getsize(image_path)
    
    return {
        "filename": get_relative_path(image_path),
        "thumbnail": thumbnail,
        "metadata": metadata,
        "size": file_size
    }

def _get_image_paths(folder=None):
    if folder:
        if not os.path.isdir(folder):
            logger.warning(f"Указанный путь не является директорией: {folder}")
            return []
        paths = []
        try:
            with os.scandir(folder) as entries:
                for entry in entries:
                    if entry.is_file():
                        ext = os.path.splitext(entry.name)[1].lower()
                        if ext in config.ALLOWED_EXTENSIONS:
                            paths.append(entry.path)
        except OSError as e:
            logger.warning(f"Ошибка чтения директории {folder}: {e}")
        return paths
    else:
        return list(walk_images())


def needs_processing(folder=None):
    from thumbnail import needs_thumbnail
    
    image_paths = _get_image_paths(folder)
    
    if not image_paths:
        return False
    
    for image_path in image_paths:
        try:
            if needs_thumbnail(image_path):
                return True

            meta_path = get_metadata_path(image_path)
            if not os.path.exists(meta_path):
                return True
        except Exception as e:
            logger.warning(f"Ошибка проверки изображения {image_path}: {e}")
            return True

    return False


def collect_images(folder=None, progress_callback=None):
    image_paths = _get_image_paths(folder)
    
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
            future = pool.submit(process_image, path)
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
                results[idx] = {
                    "filename": get_relative_path(image_paths[idx]),
                    "thumbnail": "",
                    "metadata": {},
                    "size": 0
                }
                processed += 1
                if progress_callback:
                    progress_callback(processed, total, f"Обработка {processed}/{total} (ошибка)")
    
    return [r for r in results if r is not None]

def sort_images(images, sort_by, order):
    reverse = (order == "desc")
    
    mtime_cache = {}
    def safe_get_mtime(img):
        filename = img["filename"]
        if filename not in mtime_cache:
            try:
                mtime_cache[filename] = os.path.getmtime(get_absolute_path(filename))
            except Exception as e:
                logger.error(f"Ошибка safe_get_mtime: {e}")
                mtime_cache[filename] = 0
        return mtime_cache[filename]
    
    key_funcs = {
        "date": safe_get_mtime,
        "filename": lambda img: img["filename"].lower(),
        "prompt": lambda img: img["metadata"].get("prompt", "").lower(),
        "rating": lambda img: img["metadata"].get("rating", 0),
        "tags": lambda img: ", ".join(img["metadata"].get("tags", [])).lower()
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
            return [img for img in images if not img["metadata"].get("tags")]
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
        return [img for img in images if match(img["metadata"].get("tags", []))]
    else:
        return [img for img in images if search in img["metadata"].get("prompt", "").lower()]
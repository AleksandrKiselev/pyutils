"""
Утилиты обработки изображений: сортировка, фильтрация и сбор.
"""
import os
import logging
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from metadata import load_metadata, save_metadata, extract_prompt_from_image
from metadata import _calculate_file_hash  # noqa: F401
from thumbnail import create_thumbnail, needs_thumbnail
from paths import get_absolute_path, get_relative_path, get_image_paths
from paths import get_metadata_path, get_thumbnail_path, get_absolute_paths
from tag import add_tags_from_prompt
from config import config

logger = logging.getLogger(__name__)


def get_image(image_path):
    """Получает изображение с метаданными. Создает миниатюру и заполняет метаданные при необходимости."""
    mtime = os.path.getmtime(image_path)
    metadata = load_metadata(image_path, mtime)
    modified = False
    
    # Заполняем недостающие поля метаданных
    if "prompt" not in metadata:
        metadata["prompt"] = extract_prompt_from_image(image_path)
        modified = True
    if "checked" not in metadata:
        metadata["checked"] = False
        modified = True
    if "rating" not in metadata:
        metadata["rating"] = 0
        modified = True
    if "tags" not in metadata:
        try:
            add_tags_from_prompt(image_path, metadata)
        except Exception as e:
            logger.error(f"Ошибка добавления тегов для {image_path}: {e}")
            metadata["tags"] = []
        modified = True
    if "size" not in metadata:
        metadata["size"] = os.path.getsize(image_path)
        modified = True
    if "hash" not in metadata:
        metadata["hash"] = _calculate_file_hash(image_path)
        modified = True
    
    # Заполняем пути в метаданных только если их нет (первичная инициализация)
    if "image_path" not in metadata:
        metadata["image_path"] = get_relative_path(image_path)
        modified = True
    if "metadata_path" not in metadata:
        metadata["metadata_path"] = get_relative_path(get_metadata_path(image_path))
        modified = True
    if "thumbnail_path" not in metadata:
        metadata["thumbnail_path"] = get_relative_path(get_thumbnail_path(image_path))
        modified = True
    
    # Создаем миниатюру если нужно
    if needs_thumbnail(metadata):
        create_thumbnail(metadata)
        modified = True
    
    # Сохраняем метаданные если были изменения
    if modified:
        save_metadata(metadata)
        load_metadata.cache_clear()
    
    return {"metadata": metadata}


def needs_processing(folder=None):
    image_paths = get_image_paths(folder)
    
    if not image_paths:
        return False
    
    for image_path in image_paths:
        mtime = os.path.getmtime(image_path)
        metadata = load_metadata(image_path, mtime)
        
        if needs_thumbnail(metadata):
            return True

        if not metadata.get("metadata_path"):
            return True
        
        _, _, meta_path = get_absolute_paths(metadata)
        if not os.path.exists(meta_path):
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
            future = pool.submit(get_image, path)
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
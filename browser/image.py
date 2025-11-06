"""
Утилиты обработки изображений: миниатюры, сортировка, фильтрация и сбор.
"""
import os
import time
import logging
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor
from metadata import load_metadata
from PIL import Image, UnidentifiedImageError
from paths import get_thumbnail_path, get_absolute_path, get_relative_path, walk_images
from config import config

logger = logging.getLogger(__name__)

def create_thumbnail(image_path, thumb_path):
    for _ in range(5):
        try:
            with Image.open(image_path) as img:
                img.thumbnail((config.THUMBNAIL_SIZE, config.THUMBNAIL_SIZE))
                os.makedirs(os.path.dirname(thumb_path), exist_ok=True)
                img.save(thumb_path, "WEBP")
                return
        except (OSError, UnidentifiedImageError):
            logger.warning(f"Ожидание файла {image_path}")
            time.sleep(1)
    logger.error(f"Не удалось создать миниатюру: {image_path}")

def process_image(image_path):
    mtime = os.path.getmtime(image_path)
    metadata = load_metadata(image_path, mtime)
    thumb_path = get_thumbnail_path(image_path)
    if not os.path.exists(thumb_path) or mtime > os.path.getmtime(thumb_path):
        create_thumbnail(image_path, thumb_path)
    return {
        "filename": get_relative_path(image_path),
        "thumbnail": get_relative_path(thumb_path),
        "metadata": metadata
    }

def _get_image_paths(folder=None):
    """Возвращает список путей к изображениям в указанной папке."""
    if folder:
        paths = os.listdir(folder)
        return [
            os.path.join(folder, f) 
            for f in paths 
            if os.path.isfile(os.path.join(folder, f)) and 
               os.path.splitext(f)[1].lower() in config.ALLOWED_EXTENSIONS
        ]
    else:
        return list(walk_images())


def needs_processing(folder=None):
    """
    Проверяет, нужна ли обработка изображений в указанной папке.
    Возвращает True если есть изображения без миниатюр или с устаревшими миниатюрами.
    """
    image_paths = _get_image_paths(folder)
    
    if not image_paths:
        return False
    
    for image_path in image_paths:
        try:
            mtime = os.path.getmtime(image_path)
            thumb_path = get_thumbnail_path(image_path)
            
            if not os.path.exists(thumb_path) or mtime > os.path.getmtime(thumb_path):
                return True
        except Exception as e:
            logger.warning(f"Ошибка проверки изображения {image_path}: {e}")
            return True
    
    return False


def collect_images(folder=None, progress_callback=None):
    image_paths = _get_image_paths(folder)
    
    # Увеличиваем количество воркеров для I/O операций (для CPU-bound задач лучше меньше)
    # Для обработки метаданных и создания миниатюр больше воркеров ускорит процесс
    max_workers = min(32, (os.cpu_count() or 1) * 4, len(image_paths))
    
    total = len(image_paths)
    if progress_callback:
        progress_callback(0, total, f"Найдено {total} изображений")
    
    results = []
    processed = 0
    
    if progress_callback:
        # Используем обычный map для возможности отслеживания прогресса
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = [pool.submit(process_image, path) for path in image_paths]
            for future in futures:
                result = future.result()
                results.append(result)
                processed += 1
                if progress_callback:
                    progress_callback(processed, total, f"Обработка {processed}/{total}")
    else:
        # Старый способ с tqdm для консоли
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            for result in tqdm(pool.map(process_image, image_paths), total=len(image_paths), desc="Обработка изображений"):
                results.append(result)
    
    return results

def sort_images(images, sort_by, order):
    reverse = (order == "desc")
    def safe_get_mtime(img):
        try:
            return os.path.getmtime(get_absolute_path(img["filename"]))
        except Exception as e:
            logger.error(f"Ошибка safe_get_mtime: {e}")
            return 0
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
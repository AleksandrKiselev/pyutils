"""
Утилиты обработки изображений: миниатюры, сортировка, фильтрация и сбор.
"""
import os
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from metadata import load_metadata
from PIL import Image, UnidentifiedImageError
from paths import get_thumbnail_path, get_absolute_path, get_relative_path, walk_images, get_metadata_path
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
    # Используем уже полученный mtime вместо повторного вызова
    try:
        thumb_mtime = os.path.getmtime(thumb_path) if os.path.exists(thumb_path) else 0
        if mtime > thumb_mtime:
            create_thumbnail(image_path, thumb_path)
    except OSError:
        # Если миниатюра не существует или ошибка доступа
        create_thumbnail(image_path, thumb_path)
    return {
        "filename": get_relative_path(image_path),
        "thumbnail": get_relative_path(thumb_path),
        "metadata": metadata
    }

def _get_image_paths(folder=None):
    """Возвращает список путей к изображениям в указанной папке."""
    if folder:
        if not os.path.isdir(folder):
            logger.warning(f"Указанный путь не является директорией: {folder}")
            return []
        # Используем os.scandir для более эффективного обхода
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
    """
    Проверяет, нужна ли обработка изображений в указанной папке.
    Возвращает True если есть изображения без миниатюр, метаданных или с устаревшими миниатюрами.
    Использует параллельную проверку для больших папок для ускорения.
    """
    image_paths = _get_image_paths(folder)
    
    if not image_paths:
        return False
    
    # Для небольших папок проверяем последовательно (быстрее из-за отсутствия overhead)
    if len(image_paths) < 50:
        for image_path in image_paths:
            try:
                mtime = os.path.getmtime(image_path)
                thumb_path = get_thumbnail_path(image_path)
                meta_path = get_metadata_path(image_path)
                
                # Проверяем миниатюру (используем уже полученный mtime)
                try:
                    thumb_mtime = os.path.getmtime(thumb_path) if os.path.exists(thumb_path) else 0
                    if mtime > thumb_mtime:
                        return True
                except OSError:
                    return True
                
                # Проверяем метаданные
                if not os.path.exists(meta_path):
                    return True
            except Exception as e:
                logger.warning(f"Ошибка проверки изображения {image_path}: {e}")
                return True
        
        return False
    
    # Для больших папок используем параллельную проверку
    def check_single_image(image_path):
        try:
            mtime = os.path.getmtime(image_path)
            thumb_path = get_thumbnail_path(image_path)
            meta_path = get_metadata_path(image_path)
            
            # Проверяем миниатюру
            try:
                thumb_mtime = os.path.getmtime(thumb_path) if os.path.exists(thumb_path) else 0
                if mtime > thumb_mtime:
                    return True
            except OSError:
                return True
            
            # Проверяем метаданные
            if not os.path.exists(meta_path):
                return True
            
            return False
        except Exception as e:
            logger.warning(f"Ошибка проверки изображения {image_path}: {e}")
            return True
    
    # Используем параллельную проверку с ограничением воркеров
    # Прерываем проверку как только найдем первый файл, требующий обработки
    max_workers = min(16, (os.cpu_count() or 1) * 2, len(image_paths))
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(check_single_image, path): path for path in image_paths}
        for future in as_completed(futures):
            if future.result():
                # Отменяем оставшиеся задачи для ускорения
                for remaining_future in futures:
                    if remaining_future != future and not remaining_future.done():
                        remaining_future.cancel()
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
    
    if total == 0:
        return []
    
    results = [None] * total  # Предварительно создаем список для сохранения порядка
    processed = 0
    
    # Используем ThreadPoolExecutor для параллельной обработки
    # Используем as_completed для обработки результатов по мере готовности
    # Это позволяет обновлять прогресс сразу, как только первая задача завершится
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        # Отправляем все задачи в пул с сохранением индекса
        # pool.submit() очень быстрая операция, просто добавляет задачу в очередь
        futures = {}
        for idx, path in enumerate(image_paths):
            future = pool.submit(process_image, path)
            futures[future] = idx
        
        # Обрабатываем результаты по мере их готовности
        # as_completed возвращает futures по мере завершения задач, а не последовательно
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
                # Добавляем пустой результат для сохранения порядка
                results[idx] = {
                    "filename": get_relative_path(image_paths[idx]),
                    "thumbnail": "",
                    "metadata": {}
                }
                processed += 1
                if progress_callback:
                    progress_callback(processed, total, f"Обработка {processed}/{total} (ошибка)")
    
    # Фильтруем None значения (на случай если что-то пошло не так)
    return [r for r in results if r is not None]

def sort_images(images, sort_by, order):
    reverse = (order == "desc")
    
    # Кэшируем mtime для сортировки по дате, чтобы избежать повторных вызовов
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
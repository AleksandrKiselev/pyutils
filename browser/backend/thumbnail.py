"""
Утилиты для работы с миниатюрами изображений.
"""
import os
import time
import logging
from typing import Dict, Any
from PIL import Image, UnidentifiedImageError
from paths import get_absolute_paths
from config import config

logger = logging.getLogger(__name__)


def create_thumbnail(metadata: Dict[str, Any]) -> bool:
    """Создает миниатюру для изображения из метаданных."""
    image_path, thumb_path, _ = get_absolute_paths(metadata)
    
    for attempt in range(5):
        try:
            with Image.open(image_path) as img:
                img.thumbnail((config.THUMBNAIL_SIZE, config.THUMBNAIL_SIZE))
                os.makedirs(os.path.dirname(thumb_path), exist_ok=True)
                img.save(thumb_path, "WEBP")
                return True
        except (OSError, UnidentifiedImageError) as e:
            if attempt < 4:
                logger.warning(f"Попытка {attempt + 1}/5: ожидание файла {image_path}")
                time.sleep(1)
            else:
                logger.error(f"Не удалось создать миниатюру для {image_path}: {e}")
                return False
    return False


def needs_thumbnail(metadata: Dict[str, Any]) -> bool:
    """Проверяет, нужна ли миниатюра."""
    image_path, thumb_path, _ = get_absolute_paths(metadata)
    
    if not os.path.exists(thumb_path):
        return True
    
    try:
        image_mtime = os.path.getmtime(image_path)
        thumb_mtime = os.path.getmtime(thumb_path)
        return image_mtime > thumb_mtime
    except OSError:
        return True


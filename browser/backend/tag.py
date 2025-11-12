"""Модуль для автоматической генерации тегов."""

import os
import logging
from typing import List

from config import config

try:
    from auto_tags import get_auto_tags
    AUTO_TAGS_AVAILABLE = True
except ImportError:
    AUTO_TAGS_AVAILABLE = False
    def get_auto_tags(*args, **kwargs):
        return []

logger = logging.getLogger(__name__)


def get_tags_for_image(image_path: str) -> List[str]:
    """
    Генерирует теги для изображения используя автоматическую генерацию.
    
    Args:
        image_path: Путь к изображению
    
    Returns:
        Список тегов
    """
    if not AUTO_TAGS_AVAILABLE:
        logger.debug("Автоматическая генерация тегов недоступна")
        return []
    
    try:
        abs_image_path = os.path.abspath(image_path) if not os.path.isabs(image_path) else image_path
        auto_tags = get_auto_tags(
            abs_image_path,
            enabled=config.AUTO_TAG_ENABLED
        )
        return auto_tags if auto_tags else []
    except Exception as e:
        logger.debug(f"Не удалось сгенерировать автоматические теги для {image_path}: {e}")
        return []

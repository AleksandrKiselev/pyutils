import os
import sys
import logging
import io
from typing import Dict, Any, List, Optional
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor

import cv2
import pillow_avif
from PIL import Image

from paths import get_absolute_path
from config import config
from metadata import metadata_store

logger = logging.getLogger(__name__)


@contextmanager
def suppress_stderr():
    with open(os.devnull, "w") as devnull:
        old_stderr = sys.stderr
        sys.stderr = devnull
        try:
            yield
        finally:
            sys.stderr = old_stderr


class ThumbnailService:
    @staticmethod
    def needs_thumbnail(metadata: Dict[str, Any]) -> bool:
        """Проверяет, нужна ли миниатюра (отсутствует в БД)"""
        return not bool(metadata.get("thumbnail_data"))

    @staticmethod
    def create_thumbnail(metadata: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Создает миниатюру и возвращает обновленные метаданные (без сохранения в БД)"""
        if metadata.get("thumbnail_data"):
            return None

        image_path = get_absolute_path(metadata.get("image_path", ""))
        if not image_path:
            logger.warning(f"Не удалось получить абсолютный путь для {metadata.get('image_path', '')}")
            return None

        try:
            if not os.path.exists(image_path):
                logger.warning(f"Файл не существует: {image_path}")
                return None
            
            with suppress_stderr():
                img = cv2.imread(image_path, cv2.IMREAD_COLOR)
            if img is None:
                logger.warning(f"Не удалось загрузить изображение: {image_path}")
                return None
            
            height, width = img.shape[:2]
            if height > width:
                new_height = config.THUMBNAIL_SIZE
                new_width = int(width * config.THUMBNAIL_SIZE / height)
            else:
                new_width = config.THUMBNAIL_SIZE
                new_height = int(height * config.THUMBNAIL_SIZE / width)
            
            thumbnail = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_AREA)
            
            thumbnail_rgb = cv2.cvtColor(thumbnail, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(thumbnail_rgb)
            
            buffer = io.BytesIO()
            pil_image.save(buffer, format='AVIF', quality=config.THUMBNAIL_QUALITY, method=6)
            thumbnail_bytes = buffer.getvalue()
            
            if not thumbnail_bytes:
                logger.error(f"Созданная миниатюра пуста для {image_path}")
                return None
            
            metadata["thumbnail_data"] = thumbnail_bytes
            
            return metadata
        except Exception as e:
            logger.error(f"Не удалось создать миниатюру для {image_path}: {e}", exc_info=True)
            return None

    @staticmethod
    def ensure_thumbnails(metadata_list: List[Dict[str, Any]]) -> None:
        """Обеспечивает наличие миниатюр для списка метаданных"""
        if not metadata_list:
            return

        def process_single(metadata: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            try:
                if ThumbnailService.needs_thumbnail(metadata):
                    return ThumbnailService.create_thumbnail(metadata)
                return None
            except Exception as e:
                image_path = metadata.get("image_path", "unknown")
                logger.error(f"Ошибка при создании миниатюры для {image_path}: {e}", exc_info=True)
                return None

        updated_metadata_list = []
        if len(metadata_list) == 1:
            updated = process_single(metadata_list[0])
            if updated:
                updated_metadata_list.append(updated)
        else:
            max_workers = min(8, (os.cpu_count() or 1) * 2, len(metadata_list))
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                results = pool.map(process_single, metadata_list)
                updated_metadata_list = [m for m in results if m is not None]
        
        if updated_metadata_list:
            metadata_store.save(updated_metadata_list)


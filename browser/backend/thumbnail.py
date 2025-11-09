import os
import sys
import time
import logging
from pathlib import Path
from typing import Dict, Any, List
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor

import cv2

from paths import get_absolute_paths
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
        image_path, thumb_path = get_absolute_paths(metadata)

        if not os.path.exists(thumb_path):
            return True

        try:
            return os.path.getmtime(image_path) > os.path.getmtime(thumb_path)
        except OSError:
            return True

    @staticmethod
    def create_thumbnail(metadata: Dict[str, Any]) -> bool:
        image_path, thumb_path = get_absolute_paths(metadata)

        if os.path.exists(thumb_path):
            return True

        for attempt in range(5):
            try:
                with suppress_stderr():
                    img = cv2.imread(image_path, cv2.IMREAD_COLOR)
                if img is None:
                    raise OSError(f"Не удалось загрузить изображение: {image_path}")
                
                height, width = img.shape[:2]
                if height > width:
                    new_height = config.THUMBNAIL_SIZE
                    new_width = int(width * config.THUMBNAIL_SIZE / height)
                else:
                    new_width = config.THUMBNAIL_SIZE
                    new_height = int(height * config.THUMBNAIL_SIZE / width)
                
                thumbnail = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_AREA)
                
                Path(thumb_path).parent.mkdir(parents=True, exist_ok=True)
                with suppress_stderr():
                    cv2.imwrite(thumb_path, thumbnail, [cv2.IMWRITE_WEBP_QUALITY, 85])
                return True
            except Exception as e:
                if attempt < 4:
                    logger.warning(f"Попытка {attempt + 1}/5: ожидание файла {image_path}")
                    time.sleep(1)
                else:
                    logger.error(f"Не удалось создать миниатюру для {image_path}: {e}")
                    return False
        return False

    @staticmethod
    def ensure_thumbnail(metadata: Dict[str, Any]) -> Dict[str, Any]:
        if ThumbnailService.needs_thumbnail(metadata):
            if ThumbnailService.create_thumbnail(metadata):
                metadata_id = metadata.get("id")
                if metadata_id:
                    metadata_store.update(metadata_id, {"thumb_path": metadata["thumb_path"]})

        return metadata

    @staticmethod
    def ensure_thumbnails_batch(metadata_list: List[Dict[str, Any]], max_workers: int = None) -> None:
        if not metadata_list:
            return

        if max_workers is None:
            max_workers = min(8, (os.cpu_count() or 1) * 2, len(metadata_list))

        def process_single(metadata: Dict[str, Any]) -> None:
            ThumbnailService.ensure_thumbnail(metadata)

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            pool.map(process_single, metadata_list)


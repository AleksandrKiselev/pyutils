"""
Извлечение, загрузка и сохранение метаданных изображений.
"""
import json
import os
import re
import struct
import zlib
import hashlib
import time
import logging
from functools import lru_cache
from typing import Dict, Any
from PIL import Image, UnidentifiedImageError
from paths import get_relative_path, get_absolute_path, get_metadata_path, get_absolute_paths, get_thumbnail_path
from config import config
from tag import extract_tags_from_prompt

logger = logging.getLogger(__name__)


def extract_prompt_from_image(image_path: str) -> str:
    try:
        with open(image_path, "rb") as f:
            data = f.read()

        chunks = []
        offset = 8
        
        while offset < len(data):
            try:
                length = struct.unpack("!I", data[offset:offset+4])[0]
                chunk_type = data[offset+4:offset+8].decode("utf-8", "ignore")
                chunk_data = data[offset+8:offset+8+length]
                offset += 8 + length + 4

                if chunk_type == "zTXt":
                    try:
                        null_index = chunk_data.index(b'\x00')
                        compressed = chunk_data[null_index + 2:]
                        decompressed = zlib.decompress(compressed).decode("utf-8", "ignore")
                        chunks.append(decompressed)
                    except (ValueError, zlib.error) as e:
                        logger.warning(f"Не удалось распаковать zTXt чанк в {image_path}: {e}")
                elif chunk_type in ("tEXt", "iTXt"):
                    chunks.append(chunk_data.decode("utf-8", "ignore"))
            except (struct.error, IndexError, UnicodeDecodeError) as e:
                logger.warning(f"Ошибка парсинга PNG чанка на смещении {offset} в {image_path}: {e}")
                break

        metadata = "".join(chunks).strip()
        pattern = r'"title"\s*:\s*"PromptTextForBrowser",.*?"widgets_values"\s*:\s*\[\s*\[\s*"([^"]+)"\s*\]\s*\]'
        match = re.search(pattern, metadata, re.DOTALL)
        return match.group(1).strip() if match else "Метаданные не найдены"
    except IOError as e:
        logger.error(f"Ошибка чтения файла {image_path}: {e}")
        return "Метаданные не найдены"
    except Exception as e:
        logger.error(f"Ошибка получения промпта из {image_path}: {e}")
        return "Метаданные не найдены"


def _calculate_file_hash(image_path: str) -> str:
    """Вычисляет MD5 хеш файла."""
    try:
        hash_md5 = hashlib.md5()
        with open(image_path, "rb") as f:
            # Читаем файл блоками для экономии памяти
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        logger.warning(f"Ошибка вычисления хеша для {image_path}: {e}")
        return ""


@lru_cache(maxsize=10000)
def load_metadata(image_path: str, mtime: float) -> Dict[str, Any]:
    """Загружает метаданные из файла. Использует вычисленный путь только при первой загрузке."""
    # Вычисляем путь к метаданным только при первой загрузке
    path = get_metadata_path(image_path)
    
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    return {}


def save_metadata(metadata: Dict[str, Any]) -> None:
    """Сохраняет метаданные. Использует путь из metadata["metadata_path"]."""
    metadata_path = metadata.get("metadata_path")
    if not metadata_path:
        raise ValueError("Путь к метаданным не найден в метаданных")
    
    path = get_absolute_path(metadata_path)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=4)
    except IOError as e:
        error_msg = f"Ошибка сохранения метаданных в {path}: {e}"
        logger.error(error_msg)
        raise OSError(error_msg) from e
    except Exception as e:
        error_msg = f"Неожиданная ошибка сохранения метаданных в {path}: {e}"
        logger.error(error_msg)
        raise OSError(error_msg) from e


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


def get_metadata(image_path):
    """Получает изображение с метаданными. Если не удалось загрузить — создает и заполняет их."""
    mtime = os.path.getmtime(image_path)
    metadata = load_metadata(image_path, mtime)
    modified = False

    if not metadata:
        metadata = {}
        prompt = extract_prompt_from_image(image_path)
        metadata["prompt"] = prompt
        metadata["checked"] = False
        metadata["rating"] = 0
        metadata["tags"] = extract_tags_from_prompt(image_path, prompt)
        metadata["size"] = os.path.getsize(image_path)
        metadata["hash"] = _calculate_file_hash(image_path)
        metadata["image_path"] = get_relative_path(image_path)
        metadata["metadata_path"] = get_relative_path(get_metadata_path(image_path))
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
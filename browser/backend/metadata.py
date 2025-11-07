"""
Извлечение, загрузка и сохранение метаданных изображений.
"""
import json
import os
import re
import struct
import zlib
import hashlib
import logging
from functools import lru_cache
from typing import Dict, Any
from paths import get_relative_path, get_absolute_path, get_metadata_path
from exceptions import FileOperationError

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
        raise FileOperationError("Путь к метаданным не найден в метаданных")
    
    path = get_absolute_path(metadata_path)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=4)
    except IOError as e:
        error_msg = f"Ошибка сохранения метаданных в {path}: {e}"
        logger.error(error_msg)
        raise FileOperationError(error_msg) from e
    except Exception as e:
        error_msg = f"Неожиданная ошибка сохранения метаданных в {path}: {e}"
        logger.error(error_msg)
        raise FileOperationError(error_msg) from e

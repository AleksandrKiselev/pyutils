"""
Извлечение, загрузка и сохранение метаданных изображений.
"""
import json
import os
import re
import struct
import zlib
import logging
from functools import lru_cache
from typing import Dict, Any
from paths import get_metadata_path
from tag import auto_add_tags_from_prompt
from exceptions import FileOperationError

logger = logging.getLogger(__name__)


def extract_prompt_from_png(image_path: str) -> str:
    try:
        with open(image_path, "rb") as f:
            data = f.read()

        chunks: list = []
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
        logger.error(f"Неожиданная ошибка извлечения промпта из {image_path}: {e}")
        return "Метаданные не найдены"


@lru_cache(maxsize=512)
def load_metadata(image_path: str, mtime: float) -> Dict[str, Any]:
    path = get_metadata_path(image_path)
    metadata: Dict[str, Any] = {}
    modified = False

    # Быстрая проверка существования файла
    try:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
            except json.JSONDecodeError as e:
                logger.warning(f"Поврежденный файл метаданных: {path}, ошибка: {e}")
                metadata = {}
            except IOError as e:
                logger.warning(f"Ошибка чтения файла метаданных: {path}, ошибка: {e}")
                metadata = {}
    except Exception as e:
        logger.warning(f"Ошибка проверки метаданных для {image_path}: {e}")

    if "prompt" not in metadata:
        metadata["prompt"] = extract_prompt_from_png(image_path)
        modified = True
    if "checked" not in metadata:
        metadata["checked"] = False
        modified = True
    if "rating" not in metadata:
        metadata["rating"] = 0
        modified = True
    if "tags" not in metadata:
        try:
            auto_add_tags_from_prompt(image_path, metadata)
        except Exception as e:
            logger.error(f"Ошибка автоматического добавления тегов для {image_path}: {e}")
            metadata["tags"] = []
        modified = True

    if modified:
        try:
            save_metadata(image_path, metadata)
        except FileOperationError:
            pass

    return metadata


def save_metadata(image_path: str, metadata: Dict[str, Any]) -> None:
    path = get_metadata_path(image_path)
    try:
        # Директория уже создается в get_metadata_file_path, но оставляем для надежности
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

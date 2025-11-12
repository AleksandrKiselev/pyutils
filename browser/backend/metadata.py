import os
import re
import json
import struct
import sys
import zlib
import hashlib
import logging
import uuid
import atexit
from typing import Dict, Any, Optional, List

from paths import get_relative_path, get_thumbnail_path
from config import config
from tag import get_tags_for_image
from database import DatabaseManager

logger = logging.getLogger(__name__)


class MetadataStore:
    def __init__(self):
        self._db_manager = DatabaseManager()
    
    def initialize(self) -> None:
        self._db_manager.init_database()
        atexit.register(self._db_manager.force_save)

    def _extract_prompt_from_image(self, image_path: str) -> str:
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
            return match.group(1).strip() if match else ""
        except IOError as e:
            logger.error(f"Ошибка чтения файла {image_path}: {e}")
            return ""
        except Exception as e:
            logger.error(f"Ошибка получения промпта из {image_path}: {e}")
            return ""

    def _calculate_file_hash(self, image_path: str) -> str:
        try:
            if sys.version_info >= (3, 11):
                with open(image_path, "rb") as f:
                    return hashlib.file_digest(f, hashlib.md5).hexdigest()
            else:
                hash_md5 = hashlib.md5()
                with open(image_path, "rb") as f:
                    for chunk in iter(lambda: f.read(4096), b""):
                        hash_md5.update(chunk)
                return hash_md5.hexdigest()
        except Exception as e:
            logger.warning(f"Ошибка вычисления хеша для {image_path}: {e}")
            return ""
    
    def get_by_paths(self, image_paths: List[str]) -> List[Optional[Dict[str, Any]]]:
        """Получает существующие метаданные для списка путей изображений. Не создает новые."""
        if not image_paths:
            return []
        rel_paths = [get_relative_path(path) for path in image_paths]
        return self._db_manager.get_by_paths(rel_paths)

    def get_by_ids(self, metadata_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """Получает метаданные для списка ID. Возвращает словарь {id: metadata}"""
        return self._db_manager.get_by_ids(metadata_ids)

    def get_all(self) -> List[Dict[str, Any]]:
        return self._db_manager.get_all()

    def has_metadata(self, image_path: str) -> bool:
        rel_image_path = get_relative_path(image_path)
        return self._db_manager.has_metadata(rel_image_path)
    
    def get_by_folder(self, folder_path: Optional[str]) -> List[Dict[str, Any]]:
        """Получает метаданные для изображений внутри указанной директории (без рекурсии)."""
        if folder_path is None:
            return self._db_manager.get_by_folder(None)
        
        relative = get_relative_path(folder_path).replace("\\", "/")
        normalized = relative.strip("/")
        
        if not normalized:
            return self._db_manager.get_by_folder("")
        
        return self._db_manager.get_by_folder(normalized)
    
    def create_metadata(self, image_path: str) -> Dict[str, Any]:
        prompt = ""
        size = 0
        file_hash = ""
        rel_image_path = ""
        rel_thumb_path = ""
        tags = []
        
        try:
            prompt = self._extract_prompt_from_image(image_path)
        except Exception as e:
            logger.warning(f"Ошибка извлечения промпта из {image_path}: {e}")
        
        try:
            size = os.path.getsize(image_path)
        except (OSError, IOError) as e:
            logger.warning(f"Ошибка получения размера файла {image_path}: {e}")
        
        try:
            file_hash = self._calculate_file_hash(image_path)
        except Exception as e:
            logger.warning(f"Ошибка вычисления хеша для {image_path}: {e}")
        
        try:
            rel_image_path = get_relative_path(image_path)
        except Exception as e:
            logger.warning(f"Ошибка получения относительного пути для {image_path}: {e}")
        
        try:
            thumb_path = get_thumbnail_path(image_path)
            if thumb_path:
                rel_thumb_path = get_relative_path(thumb_path)
        except Exception as e:
            logger.warning(f"Ошибка получения пути миниатюры для {image_path}: {e}")
        
        try:
            tags = get_tags_for_image(image_path)
        except Exception as e:
            logger.warning(f"Ошибка генерации тегов для {image_path}: {e}")
        
        return {
            "prompt": prompt or "",
            "checked": False,
            "rating": 0,
            "tags": tags if isinstance(tags, list) else [],
            "size": int(size) if size else 0,
            "hash": file_hash or "",
            "image_path": rel_image_path or "",
            "thumb_path": rel_thumb_path or "",
            "id": str(uuid.uuid4())
        }
    
    def save(self, metadata_list: List[Dict[str, Any]]) -> None:
        """Сохраняет метаданные. Принимает список метаданных для сохранения."""
        if not metadata_list:
            return
        
        if len(metadata_list) == 1:
            self._db_manager.save(metadata_list, force_save=False)
        else:
            logger.info(f"Начало batch сохранения {len(metadata_list)} метаданных")
            self._db_manager.save(metadata_list, force_save=True)
            logger.info(f"Завершено batch сохранение {len(metadata_list)} метаданных")
    
    def update(self, updates: List[Dict[str, Any]]) -> int:
        """Обновляет метаданные. Принимает список обновлений вида [{"id": "...", "checked": True, ...}, ...]"""
        if not updates:
            return 0
        
        metadata_ids = [update.get("id") for update in updates if update.get("id")]
        if not metadata_ids:
            return 0
        
        logger.info(f"Начало batch обновления {len(updates)} метаданных")
        current_metadata = self.get_by_ids(metadata_ids)
        
        updated_metadata = []
        allowed_keys = {"checked", "rating", "tags"}
        for update in updates:
            metadata_id = update.get("id")
            if not metadata_id or metadata_id not in current_metadata:
                continue
            metadata = current_metadata[metadata_id].copy()
            for key, value in update.items():
                if key != "id" and key in allowed_keys:
                    metadata[key] = value
            updated_metadata.append(metadata)
        
        if updated_metadata:
            self.save(updated_metadata)
        logger.info(f"Завершено batch обновление {len(updated_metadata)} метаданных")
        return len(updated_metadata)
    
    def delete(self, metadata_ids: List[str]) -> int:
        """Удаляет метаданные. Принимает список ID для удаления. Принудительно сохраняет БД, так как это критическая операция."""
        if not metadata_ids:
            return 0
        
        return self._db_manager.delete(metadata_ids, force_save=True)


metadata_store = MetadataStore()

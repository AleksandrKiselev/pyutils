import json
import os
import re
import struct
import sys
import zlib
import hashlib
import logging
import uuid
from pathlib import Path
from typing import Dict, Any, Optional

import fasteners
from tqdm import tqdm

from paths import get_relative_path, get_absolute_path, get_metadata_path, get_thumbnail_path
from config import config
from tag import extract_tags_from_prompt

logger = logging.getLogger(__name__)


class MetadataStore:
    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}
        self._path_index: Dict[str, str] = {}
        self._rwlock = fasteners.ReaderWriterLock()

    def _load_from_file(self, image_path: str) -> Dict[str, Any]:
        path = get_metadata_path(image_path)
        metadata = {}

        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Ошибка чтения метаданных из {path}: {e}")

        return metadata

    def _save_to_file(self, metadata: Dict[str, Any]) -> None:
        meta_path = metadata.get("meta_path")
        if not meta_path:
            raise ValueError("Путь к метаданным не найден в метаданных")

        path = get_absolute_path(meta_path)
        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, ensure_ascii=False, indent=4)
        except Exception as e:
            error_msg = f"Ошибка сохранения метаданных в {path}: {e}"
            logger.error(error_msg)
            raise OSError(error_msg) from e

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
            return match.group(1).strip() if match else "Метаданные не найдены"
        except IOError as e:
            logger.error(f"Ошибка чтения файла {image_path}: {e}")
            return "Метаданные не найдены"
        except Exception as e:
            logger.error(f"Ошибка получения промпта из {image_path}: {e}")
            return "Метаданные не найдены"

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


    def has_metadata(self, image_path: str) -> bool:
        path = get_metadata_path(image_path)
        return os.path.exists(path) and os.path.getsize(path) > 0

    def save(self, metadata: Dict[str, Any]) -> None:
        metadata_id = metadata.get("id")
        if not metadata_id:
            raise ValueError("ID метаданных не найден")

        metadata_copy = metadata.copy()
        self._save_to_file(metadata_copy)

        with self._rwlock.write_lock():
            old_image_path = None
            if metadata_id in self._store:
                old_image_path = self._store[metadata_id].get("image_path")
            
            self._store[metadata_id] = metadata_copy
            image_path = metadata_copy.get("image_path")
            
            if old_image_path and old_image_path != image_path:
                self._path_index.pop(old_image_path, None)
            
            if image_path:
                self._path_index[image_path] = metadata_id

    def update(self, metadata_id: str, updates: Dict[str, Any]) -> None:
        metadata = self.get_by_id(metadata_id)
        if not metadata:
            raise ValueError(f"Метаданные с ID {metadata_id} не найдены")
        metadata.update(updates)
        self.save(metadata)

    def get_by_id(self, metadata_id: str) -> Optional[Dict[str, Any]]:
        with self._rwlock.read_lock():
            if metadata_id in self._store:
                return self._store[metadata_id].copy()
        return None

    def get_all(self) -> list:
        with self._rwlock.read_lock():
            return [metadata.copy() for metadata in self._store.values()]

    def get(self, image_path: str) -> Dict[str, Any]:
        rel_image_path = get_relative_path(image_path)
        metadata = None
        modified = False

        with self._rwlock.read_lock():
            metadata_id = self._path_index.get(rel_image_path)
            if metadata_id and metadata_id in self._store:
                metadata = self._store[metadata_id].copy()

        if not metadata:
            file_metadata = self._load_from_file(image_path)

            if file_metadata and file_metadata.get("id"):
                metadata_id = file_metadata.get("id")
                with self._rwlock.write_lock():
                    self._store[metadata_id] = file_metadata.copy()
                    image_path_from_file = file_metadata.get("image_path")
                    if image_path_from_file:
                        self._path_index[image_path_from_file] = metadata_id
                metadata = file_metadata.copy()

        if not metadata:
            prompt = self._extract_prompt_from_image(image_path)
            metadata = {
                "prompt": prompt,
                "checked": False,
                "rating": 0,
                "tags": extract_tags_from_prompt(image_path, prompt),
                "size": os.path.getsize(image_path),
                "hash": self._calculate_file_hash(image_path),
                "image_path": get_relative_path(image_path),
                "meta_path": get_relative_path(get_metadata_path(image_path)),
                "thumb_path": get_relative_path(get_thumbnail_path(image_path)),
                "id": str(uuid.uuid4())
            }
            modified = True

        if modified:
            self.save(metadata)

        return metadata

    def delete(self, metadata_id: str) -> None:
        metadata = self.get_by_id(metadata_id)
        if not metadata:
            return

        meta_path = metadata.get("meta_path")
        if meta_path:
            path = get_absolute_path(meta_path)
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError as e:
                    logger.warning(f"Не удалось удалить файл метаданных {path}: {e}")

        with self._rwlock.write_lock():
            self._store.pop(metadata_id, None)
            image_path = metadata.get("image_path")
            if image_path:
                self._path_index.pop(image_path, None)

    def initialize(self) -> None:
        metadata_dir = os.path.join(config.IMAGE_FOLDER, ".metadata")
        if not os.path.exists(metadata_dir):
            return

        count = 0
        errors = 0
        
        # Собираем все файлы метаданных
        metadata_files = []
        for root, dirs, files in os.walk(metadata_dir):
            for file in files:
                if file.endswith(".json"):
                    metadata_files.append(os.path.join(root, file))

        with self._rwlock.write_lock():
            for meta_path in tqdm(metadata_files, desc="Загрузка метаданных", unit="файл"):
                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        metadata = json.load(f)
                        metadata_id = metadata.get("id")
                        if metadata_id:
                            self._store[metadata_id] = metadata
                            image_path = metadata.get("image_path")
                            if image_path:
                                self._path_index[image_path] = metadata_id
                            count += 1
                        else:
                            logger.warning(f"Метаданные без ID найдены в {meta_path}")
                except (json.JSONDecodeError, IOError) as e:
                    logger.warning(f"Ошибка чтения метаданных {meta_path}: {e}")
                    errors += 1

        logger.info(f"Загружено метаданных: {count}, ошибок: {errors}")

    def clear_cache(self) -> None:
        with self._rwlock.write_lock():
            self._store.clear()
            self._path_index.clear()


metadata_store = MetadataStore()

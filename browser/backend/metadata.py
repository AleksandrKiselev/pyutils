import json
import os
import re
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
from tag import extract_tags_from_prompt
from database import get_connection, init_database, force_save

logger = logging.getLogger(__name__)


class MetadataStore:
    def _row_to_dict(self, row) -> Dict[str, Any]:
        if not row:
            return {}
        return {
            "id": row["id"],
            "prompt": row["prompt"] or "",
            "checked": bool(row["checked"]),
            "rating": row["rating"] or 0,
            "tags": json.loads(row["tags"]) if row["tags"] else [],
            "size": row["size"] or 0,
            "hash": row["hash"] or "",
            "image_path": row["image_path"],
            "thumb_path": row["thumb_path"] or ""
        }

    def _dict_to_row(self, metadata: Dict[str, Any]) -> tuple:
        return (
            metadata.get("id"),
            metadata.get("prompt", ""),
            1 if metadata.get("checked", False) else 0,
            metadata.get("rating", 0) or 0,
            json.dumps(metadata.get("tags", []), ensure_ascii=False),
            metadata.get("size", 0) or 0,
            metadata.get("hash", ""),
            metadata.get("image_path", ""),
            metadata.get("thumb_path", "")
        )

    def _load_from_db(self, image_path: str) -> Optional[Dict[str, Any]]:
        rel_image_path = get_relative_path(image_path)
        
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM metadata WHERE image_path = ?", (rel_image_path,))
                row = cursor.fetchone()
                if row:
                    return self._row_to_dict(row)
        except Exception as e:
            logger.warning(f"Ошибка чтения метаданных из БД для {image_path}: {e}")
        return None

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
        rel_image_path = get_relative_path(image_path)
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM metadata WHERE image_path = ?", (rel_image_path,))
                row = cursor.fetchone()
                return row[0] > 0 if row else False
        except Exception as e:
            logger.warning(f"Ошибка проверки метаданных для {image_path}: {e}")
            return False

    def save(self, metadata: Dict[str, Any]) -> None:
        if not metadata.get("id"):
            raise ValueError("ID метаданных не найден")

        row_data = self._dict_to_row(metadata)
        
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO metadata 
                (id, prompt, checked, rating, tags, size, hash, image_path, thumb_path, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, row_data)

    def update(self, metadata_id: str, updates: Dict[str, Any]) -> None:
        metadata = self.get_by_id(metadata_id)
        if not metadata:
            raise ValueError(f"Метаданные с ID {metadata_id} не найдены")
        metadata.update(updates)
        self.save(metadata)

    def get_by_id(self, metadata_id: str) -> Optional[Dict[str, Any]]:
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM metadata WHERE id = ?", (metadata_id,))
                row = cursor.fetchone()
                if row:
                    return self._row_to_dict(row)
        except Exception as e:
            logger.warning(f"Ошибка получения метаданных по ID {metadata_id}: {e}")
        return None

    def get_all(self) -> List[Dict[str, Any]]:
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM metadata")
                rows = cursor.fetchall()
                return [self._row_to_dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Ошибка получения всех метаданных: {e}")
            return []

    def get_batch(self, image_paths: List[str]) -> List[Optional[Dict[str, Any]]]:
        if not image_paths:
            return []
        
        rel_paths = [get_relative_path(path) for path in image_paths]
        result: List[Optional[Dict[str, Any]]] = [None] * len(image_paths)
        path_to_index = {rel_path: idx for idx, rel_path in enumerate(rel_paths)}
        
        placeholders = ",".join("?" * len(rel_paths))
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f"SELECT * FROM metadata WHERE image_path IN ({placeholders})", rel_paths)
                rows = cursor.fetchall()
                for row in rows:
                    metadata = self._row_to_dict(row)
                    image_path = metadata.get("image_path")
                    if image_path in path_to_index:
                        result[path_to_index[image_path]] = metadata
        except Exception as e:
            logger.warning(f"Ошибка batch чтения метаданных: {e}")
        return result

    def save_batch(self, metadata_list: List[Dict[str, Any]]) -> None:
        if not metadata_list:
            return
        
        logger.info(f"Начало batch сохранения {len(metadata_list)} метаданных")
        rows_data = [self._dict_to_row(metadata) for metadata in metadata_list]
        
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany("""
                INSERT OR REPLACE INTO metadata 
                (id, prompt, checked, rating, tags, size, hash, image_path, thumb_path, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, rows_data)
        
        logger.info(f"Завершено batch сохранение {len(metadata_list)} метаданных")
        force_save()

    def update_batch(self, updates: List[Dict[str, Any]]) -> int:
        if not updates:
            return 0
        
        metadata_ids = [update.get("id") for update in updates if update.get("id")]
        if not metadata_ids:
            return 0
        
        logger.info(f"Начало batch обновления {len(updates)} метаданных")
        current_metadata = {}
        placeholders = ",".join("?" * len(metadata_ids))
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f"SELECT * FROM metadata WHERE id IN ({placeholders})", metadata_ids)
                rows = cursor.fetchall()
                rows_list = [self._row_to_dict(row) for row in rows]
                for metadata in rows_list:
                    current_metadata[metadata["id"]] = metadata
        except Exception as e:
            logger.warning(f"Ошибка загрузки метаданных для batch update: {e}")
            return 0
        
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
            self.save_batch(updated_metadata)
        logger.info(f"Завершено batch обновление {len(updated_metadata)} метаданных")
        return len(updated_metadata)

    def delete_batch(self, metadata_ids: List[str]) -> int:
        if not metadata_ids:
            return 0
        
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                placeholders = ",".join("?" * len(metadata_ids))
                cursor.execute(f"DELETE FROM metadata WHERE id IN ({placeholders})", metadata_ids)
                return cursor.rowcount
        except Exception as e:
            logger.error(f"Ошибка batch удаления метаданных: {e}")
            raise

    def _create_metadata(self, image_path: str) -> Dict[str, Any]:
        prompt = self._extract_prompt_from_image(image_path)
        return {
            "prompt": prompt,
            "checked": False,
            "rating": 0,
            "tags": extract_tags_from_prompt(image_path, prompt),
            "size": os.path.getsize(image_path),
            "hash": self._calculate_file_hash(image_path),
            "image_path": get_relative_path(image_path),
            "thumb_path": get_relative_path(get_thumbnail_path(image_path)),
            "id": str(uuid.uuid4())
        }

    def get(self, image_path: str) -> Dict[str, Any]:
        metadata = self._load_from_db(image_path)
        if not metadata:
            metadata = self._create_metadata(image_path)
            self.save(metadata)
        return metadata

    def delete(self, metadata_id: str) -> None:
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM metadata WHERE id = ?", (metadata_id,))
        except Exception as e:
            logger.error(f"Ошибка удаления метаданных {metadata_id}: {e}")
            raise

    def initialize(self) -> None:
        init_database()
        atexit.register(force_save)


metadata_store = MetadataStore()

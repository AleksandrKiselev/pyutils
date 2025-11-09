import os
import sqlite3
import json
import logging
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List

from config import config

logger = logging.getLogger(__name__)


class DebounceTimer:
    """Таймер с debounce для отложенного выполнения функции"""
    
    def __init__(self, delay: float):
        self._delay = delay
        self._timer: threading.Timer | None = None
    
    def schedule(self, callback) -> None:
        """Планирует выполнение callback с задержкой, отменяя предыдущий таймер"""
        self.cancel()
        self._timer = threading.Timer(self._delay, callback)
        self._timer.daemon = True
        self._timer.start()
    
    def cancel(self) -> None:
        """Отменяет текущий таймер, если он активен"""
        if self._timer:
            self._timer.cancel()
            self._timer = None


class DatabaseManager:
    """Менеджер для работы с in-memory SQLite базой данных"""
    
    def __init__(self, save_debounce: float = 5.0):
        self._memory_conn: sqlite3.Connection | None = None
        self._save_timer = DebounceTimer(save_debounce)
    
    def init_database(self) -> None:
        """Инициализирует БД: создает соединение, таблицу и загружает данные с диска"""
        self._memory_conn = sqlite3.connect(":memory:", check_same_thread=False)
        self._memory_conn.row_factory = sqlite3.Row
        self._memory_conn.execute("PRAGMA synchronous=OFF")
        self._memory_conn.execute("PRAGMA journal_mode=MEMORY")
        
        if not self._load_from_disk():
            cursor = self._memory_conn.cursor()
            cursor.execute("""
                CREATE TABLE metadata (
                    id TEXT PRIMARY KEY,
                    prompt TEXT NOT NULL DEFAULT '',
                    checked INTEGER NOT NULL DEFAULT 0,
                    rating INTEGER NOT NULL DEFAULT 0,
                    tags TEXT NOT NULL DEFAULT '[]',
                    size INTEGER NOT NULL DEFAULT 0,
                    hash TEXT NOT NULL DEFAULT '',
                    image_path TEXT NOT NULL UNIQUE,
                    thumb_path TEXT NOT NULL DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("CREATE INDEX idx_image_path ON metadata(image_path)")
            cursor.execute("CREATE INDEX idx_checked ON metadata(checked)")
            cursor.execute("CREATE INDEX idx_rating ON metadata(rating)")
            self._memory_conn.commit()
    
    def _get_db_path(self) -> str:
        db_dir = os.path.join(config.IMAGE_FOLDER, ".metadata")
        return os.path.join(db_dir, "metadata.db")
    
    def _load_from_disk(self) -> bool:
        """Загружает БД с диска. Возвращает True если загрузка успешна, False иначе"""
        db_path = self._get_db_path()
        if not os.path.exists(db_path):
            return False
        
        try:
            with sqlite3.connect(db_path, check_same_thread=False) as disk_conn:
                cursor = disk_conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='metadata'")
                if not cursor.fetchone():
                    return False
                
                cursor.execute("PRAGMA table_info(metadata)")
                columns = {row[1]: row[2].upper() for row in cursor.fetchall()}
                
                expected_columns = {
                    "id": "TEXT",
                    "prompt": "TEXT",
                    "checked": "INTEGER",
                    "rating": "INTEGER",
                    "tags": "TEXT",
                    "size": "INTEGER",
                    "hash": "TEXT",
                    "image_path": "TEXT",
                    "thumb_path": "TEXT",
                    "created_at": "TIMESTAMP",
                    "updated_at": "TIMESTAMP"
                }
                
                missing_columns = set(expected_columns.keys()) - set(columns.keys())
                if missing_columns:
                    logger.warning(f"В таблице на диске отсутствуют колонки: {missing_columns}")
                    return False
                
                type_mismatches = []
                text_types = {"TEXT", "VARCHAR", "CHAR", "CLOB"}
                integer_types = {"INTEGER", "INT"}
                timestamp_types = {"TIMESTAMP", "DATETIME", "TEXT"}
                
                for col_name, expected_type in expected_columns.items():
                    actual_type = columns[col_name]
                    if expected_type == "TEXT" and actual_type not in text_types:
                        type_mismatches.append(f"{col_name}: ожидается TEXT, найдено {actual_type}")
                    elif expected_type == "INTEGER" and actual_type not in integer_types:
                        type_mismatches.append(f"{col_name}: ожидается INTEGER, найдено {actual_type}")
                    elif expected_type == "TIMESTAMP" and actual_type not in timestamp_types:
                        type_mismatches.append(f"{col_name}: ожидается TIMESTAMP, найдено {actual_type}")
                
                if type_mismatches:
                    logger.warning(f"Несоответствие типов в таблице на диске: {type_mismatches}")
                    return False
                
                disk_conn.backup(self._memory_conn)
            
            mem_cursor = self._memory_conn.cursor()
            mem_cursor.execute("SELECT COUNT(*) FROM metadata")
            row = mem_cursor.fetchone()
            row_count = row[0] if row else 0
            if row_count > 0:
                logger.info(f"Загружено {row_count} записей с диска")
            return True
        except Exception as e:
            logger.warning(f"Ошибка загрузки данных с диска: {e}")
            return False
    
    def _save_to_disk(self) -> None:
        if self._memory_conn is None:
            return
        
        self._save_timer.cancel()
        
        db_path = self._get_db_path()
        db_dir = os.path.dirname(db_path)
        Path(db_dir).mkdir(parents=True, exist_ok=True)
        
        try:
            mem_cursor = self._memory_conn.cursor()
            mem_cursor.execute("SELECT COUNT(*) FROM metadata")
            row = mem_cursor.fetchone()
            row_count = row[0] if row else 0
            
            if row_count == 0:
                return
            
            with sqlite3.connect(db_path, check_same_thread=False) as disk_conn:
                self._memory_conn.backup(disk_conn)
            
            logger.info(f"Сохранено {row_count} записей на диск")
        except Exception as e:
            logger.error(f"Ошибка сохранения данных на диск: {e}")
    
    def _schedule_save(self) -> None:
        if self._memory_conn is None:
            return
        self._save_timer.schedule(self._save_to_disk)
    
    def force_save(self) -> None:
        self._save_timer.cancel()
        self._save_to_disk()
    
    def _row_to_dict(self, row) -> Dict[str, Any]:
        """Преобразует SQLite Row в словарь"""
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
        """Преобразует словарь в кортеж для вставки в БД"""
        # Убеждаемся, что все значения имеют правильный тип
        metadata_id = metadata.get("id")
        if not metadata_id:
            raise ValueError(f"ID метаданных не найден или пуст: {metadata}")
        
        prompt = metadata.get("prompt", "") or ""
        checked = 1 if metadata.get("checked", False) else 0
        rating = int(metadata.get("rating", 0) or 0)
        
        tags = metadata.get("tags", [])
        if not isinstance(tags, list):
            tags = []
        tags_json = json.dumps(tags, ensure_ascii=False)
        
        size = int(metadata.get("size", 0) or 0)
        file_hash = metadata.get("hash", "") or ""
        image_path = metadata.get("image_path", "") or ""
        thumb_path = metadata.get("thumb_path", "") or ""
        
        return (
            str(metadata_id),
            str(prompt),
            int(checked),
            int(rating),
            str(tags_json),
            int(size),
            str(file_hash),
            str(image_path),
            str(thumb_path)
        )
    
    def get_by_id(self, metadata_id: str) -> Optional[Dict[str, Any]]:
        """Получает метаданные по ID"""
        if self._memory_conn is None:
            return None
        try:
            cursor = self._memory_conn.cursor()
            cursor.execute("SELECT * FROM metadata WHERE id = ?", (metadata_id,))
            row = cursor.fetchone()
            return self._row_to_dict(row) if row else None
        except Exception as e:
            logger.warning(f"Ошибка получения метаданных по ID {metadata_id}: {e}")
            return None
    
    def get_by_image_path(self, image_path: str) -> Optional[Dict[str, Any]]:
        """Получает метаданные по пути изображения"""
        if self._memory_conn is None:
            return None
        try:
            cursor = self._memory_conn.cursor()
            cursor.execute("SELECT * FROM metadata WHERE image_path = ?", (image_path,))
            row = cursor.fetchone()
            return self._row_to_dict(row) if row else None
        except Exception as e:
            logger.warning(f"Ошибка получения метаданных по пути {image_path}: {e}")
            return None
    
    def has_metadata(self, image_path: str) -> bool:
        """Проверяет наличие метаданных для изображения"""
        if self._memory_conn is None:
            return False
        try:
            cursor = self._memory_conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM metadata WHERE image_path = ?", (image_path,))
            row = cursor.fetchone()
            return row[0] > 0 if row else False
        except Exception as e:
            logger.warning(f"Ошибка проверки метаданных для {image_path}: {e}")
            return False
    
    def get_all(self) -> List[Dict[str, Any]]:
        """Получает все метаданные"""
        if self._memory_conn is None:
            return []
        try:
            cursor = self._memory_conn.cursor()
            cursor.execute("SELECT * FROM metadata")
            rows = cursor.fetchall()
            return [self._row_to_dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Ошибка получения всех метаданных: {e}")
            return []
    
    def get_batch_by_paths(self, image_paths: List[str]) -> List[Optional[Dict[str, Any]]]:
        """Получает метаданные для списка путей изображений"""
        if not image_paths or self._memory_conn is None:
            return []
        
        result: List[Optional[Dict[str, Any]]] = [None] * len(image_paths)
        path_to_index = {path: idx for idx, path in enumerate(image_paths)}
        
        try:
            placeholders = ",".join("?" * len(image_paths))
            cursor = self._memory_conn.cursor()
            cursor.execute(f"SELECT * FROM metadata WHERE image_path IN ({placeholders})", image_paths)
            rows = cursor.fetchall()
            for row in rows:
                metadata = self._row_to_dict(row)
                image_path = metadata.get("image_path")
                if image_path in path_to_index:
                    result[path_to_index[image_path]] = metadata
        except Exception as e:
            logger.warning(f"Ошибка batch чтения метаданных: {e}")
        return result
    
    def get_batch_by_ids(self, metadata_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """Получает метаданные для списка ID. Возвращает словарь {id: metadata}"""
        if not metadata_ids or self._memory_conn is None:
            return {}
        
        result = {}
        try:
            placeholders = ",".join("?" * len(metadata_ids))
            cursor = self._memory_conn.cursor()
            cursor.execute(f"SELECT * FROM metadata WHERE id IN ({placeholders})", metadata_ids)
            rows = cursor.fetchall()
            for row in rows:
                metadata = self._row_to_dict(row)
                result[metadata["id"]] = metadata
        except Exception as e:
            logger.warning(f"Ошибка batch чтения метаданных по ID: {e}")
        return result
    
    def save(self, metadata_list: List[Dict[str, Any]], force_save: bool = False) -> None:
        """Сохраняет метаданные. Принимает список метаданных для сохранения."""
        if not metadata_list or self._memory_conn is None:
            return
        
        for metadata in metadata_list:
            if not metadata.get("id"):
                raise ValueError("ID метаданных не найден")
        
        try:
            if len(metadata_list) == 1:
                row_data = self._dict_to_row(metadata_list[0])
                cursor = self._memory_conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO metadata 
                    (id, prompt, checked, rating, tags, size, hash, image_path, thumb_path, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, row_data)
            else:
                rows_data = []
                for idx, metadata in enumerate(metadata_list):
                    try:
                        row_data = self._dict_to_row(metadata)
                        rows_data.append(row_data)
                    except Exception as e:
                        logger.error(f"Ошибка преобразования метаданных {idx}: {e}, metadata: {metadata}")
                        raise
                
                if not rows_data:
                    logger.warning("Нет данных для сохранения после преобразования")
                    return
                
                cursor = self._memory_conn.cursor()
                cursor.executemany("""
                    INSERT OR REPLACE INTO metadata 
                    (id, prompt, checked, rating, tags, size, hash, image_path, thumb_path, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, rows_data)
            
            self._memory_conn.commit()
            if force_save:
                self.force_save()
            else:
                self._schedule_save()
        except Exception as e:
            logger.error(f"Ошибка сохранения метаданных: {e}, количество: {len(metadata_list)}")
            raise
    
    def delete(self, metadata_ids: List[str], force_save: bool = False) -> int:
        """Удаляет метаданные. Принимает список ID для удаления. Возвращает количество удаленных записей"""
        if not metadata_ids or self._memory_conn is None:
            return 0
        
        try:
            if len(metadata_ids) == 1:
                cursor = self._memory_conn.cursor()
                cursor.execute("DELETE FROM metadata WHERE id = ?", (metadata_ids[0],))
                rowcount = cursor.rowcount
            else:
                placeholders = ",".join("?" * len(metadata_ids))
                cursor = self._memory_conn.cursor()
                cursor.execute(f"DELETE FROM metadata WHERE id IN ({placeholders})", metadata_ids)
                rowcount = cursor.rowcount
            
            self._memory_conn.commit()
            if force_save:
                self.force_save()
            else:
                self._schedule_save()
            return rowcount
        except Exception as e:
            logger.error(f"Ошибка удаления метаданных: {e}")
            raise

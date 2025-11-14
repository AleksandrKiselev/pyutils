import os
import sqlite3
import json
import logging
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List

from config import config
from paths import get_absolute_path

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
        self._read_lock = threading.RLock()
    
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
                    thumbnail_data BLOB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("CREATE INDEX idx_image_path ON metadata(image_path)")
            cursor.execute("CREATE INDEX idx_checked ON metadata(checked)")
            cursor.execute("CREATE INDEX idx_rating ON metadata(rating)")
            cursor.execute("CREATE INDEX idx_prompt ON metadata(prompt)")
            cursor.execute("CREATE INDEX idx_hash ON metadata(hash)")
            cursor.execute("CREATE INDEX idx_size ON metadata(size)")
            cursor.execute("CREATE INDEX idx_created_at ON metadata(created_at)")
            cursor.execute("CREATE INDEX idx_updated_at ON metadata(updated_at)")
            cursor.execute("CREATE INDEX idx_checked_rating ON metadata(checked, rating)")
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bookmarks (
                    id TEXT PRIMARY KEY,
                    metadata_id TEXT NOT NULL,
                    image_path TEXT NOT NULL,
                    folder_path TEXT NOT NULL DEFAULT '',
                    prompt TEXT NOT NULL DEFAULT '',
                    filename TEXT NOT NULL DEFAULT '',
                    sort_by TEXT NOT NULL DEFAULT 'date-desc',
                    search_query TEXT NOT NULL DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_bookmarks_metadata_id ON bookmarks(metadata_id)")
            self._memory_conn.commit()
            
            self._create_missing_indexes()
    
    def _get_db_path(self) -> str:
        db_dir = os.path.join(config.IMAGE_FOLDER, config.METADATA_FOLDER)
        return os.path.join(db_dir, config.DATABASE_NAME)
    
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
                    "thumbnail_data": "BLOB",
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
                blob_types = {"BLOB", "BINARY"}
                
                for col_name, expected_type in expected_columns.items():
                    actual_type = columns[col_name]
                    if expected_type == "TEXT" and actual_type not in text_types:
                        type_mismatches.append(f"{col_name}: ожидается TEXT, найдено {actual_type}")
                    elif expected_type == "INTEGER" and actual_type not in integer_types:
                        type_mismatches.append(f"{col_name}: ожидается INTEGER, найдено {actual_type}")
                    elif expected_type == "TIMESTAMP" and actual_type not in timestamp_types:
                        type_mismatches.append(f"{col_name}: ожидается TIMESTAMP, найдено {actual_type}")
                    elif expected_type == "BLOB" and actual_type not in blob_types:
                        type_mismatches.append(f"{col_name}: ожидается BLOB, найдено {actual_type}")
                
                if type_mismatches:
                    logger.warning(f"Несоответствие типов в таблице на диске: {type_mismatches}")
                    return False
                
                disk_conn.backup(self._memory_conn)
            
            mem_cursor = self._memory_conn.cursor()
            mem_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='bookmarks'")
            if not mem_cursor.fetchone():
                mem_cursor.execute("""
                    CREATE TABLE bookmarks (
                        id TEXT PRIMARY KEY,
                        metadata_id TEXT NOT NULL,
                        image_path TEXT NOT NULL,
                        folder_path TEXT NOT NULL DEFAULT '',
                        prompt TEXT NOT NULL DEFAULT '',
                        filename TEXT NOT NULL DEFAULT '',
                        sort_by TEXT NOT NULL DEFAULT 'date-desc',
                        search_query TEXT NOT NULL DEFAULT '',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                mem_cursor.execute("CREATE INDEX IF NOT EXISTS idx_bookmarks_metadata_id ON bookmarks(metadata_id)")
                self._memory_conn.commit()
            
            mem_cursor.execute("SELECT COUNT(*) FROM metadata")
            row = mem_cursor.fetchone()
            row_count = row[0] if row else 0
            if row_count > 0:
                logger.info(f"Загружено {row_count} записей с диска")
                self._cleanup_invalid_metadata()
            
            self._create_missing_indexes()
            
            return True
        except Exception as e:
            logger.warning(f"Ошибка загрузки данных с диска: {e}")
            return False
    
    def _cleanup_invalid_metadata(self) -> None:
        """Очищает БД от несуществующих метаданных"""
        if self._memory_conn is None:
            return
        
        try:
            cursor = self._memory_conn.cursor()
            cursor.execute("SELECT id, image_path FROM metadata")
            all_rows = cursor.fetchall()
            
            if not all_rows:
                return
            
            deleted_ids = []
            
            logger.info(f"Начало очистки БД: проверка {len(all_rows)} записей")
            
            for row in all_rows:
                metadata_id = row["id"]
                rel_image_path = row["image_path"]
                
                if not rel_image_path:
                    deleted_ids.append(metadata_id)
                    continue
                
                try:
                    abs_image_path = get_absolute_path(rel_image_path)
                    if not os.path.exists(abs_image_path) or not os.path.isfile(abs_image_path):
                        deleted_ids.append(metadata_id)
                except Exception as e:
                    logger.warning(f"Ошибка проверки метаданных {metadata_id} ({rel_image_path}): {e}")
                    deleted_ids.append(metadata_id)
            
            if deleted_ids:
                deleted_count = self.delete(deleted_ids)
                logger.info(f"Очистка БД завершена: удалено {deleted_count} несуществующих записей")
            else:
                logger.info("Очистка БД завершена: все записи актуальны")
        
        except Exception as e:
            logger.error(f"Ошибка очистки БД: {e}")
    
    def _create_missing_indexes(self) -> None:
        if self._memory_conn is None:
            return
        
        indexes = [
            ("idx_image_path", "CREATE INDEX IF NOT EXISTS idx_image_path ON metadata(image_path)"),
            ("idx_checked", "CREATE INDEX IF NOT EXISTS idx_checked ON metadata(checked)"),
            ("idx_rating", "CREATE INDEX IF NOT EXISTS idx_rating ON metadata(rating)"),
            ("idx_prompt", "CREATE INDEX IF NOT EXISTS idx_prompt ON metadata(prompt)"),
            ("idx_hash", "CREATE INDEX IF NOT EXISTS idx_hash ON metadata(hash)"),
            ("idx_size", "CREATE INDEX IF NOT EXISTS idx_size ON metadata(size)"),
            ("idx_created_at", "CREATE INDEX IF NOT EXISTS idx_created_at ON metadata(created_at)"),
            ("idx_updated_at", "CREATE INDEX IF NOT EXISTS idx_updated_at ON metadata(updated_at)"),
            ("idx_checked_rating", "CREATE INDEX IF NOT EXISTS idx_checked_rating ON metadata(checked, rating)")
        ]
        
        try:
            cursor = self._memory_conn.cursor()
            for index_name, create_sql in indexes:
                try:
                    cursor.execute(create_sql)
                except Exception as e:
                    logger.warning(f"Ошибка создания индекса {index_name}: {e}")
            self._memory_conn.commit()
            logger.info("Проверка и создание индексов завершена")
        except Exception as e:
            logger.error(f"Ошибка при создании индексов: {e}")
    
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
            "thumbnail_data": row["thumbnail_data"]
        }
    
    def _dict_to_row(self, metadata: Dict[str, Any]) -> tuple:
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
        if image_path:
            image_path = str(image_path).replace("\\", "/")
        thumbnail_data = metadata.get("thumbnail_data")
        
        return (
            str(metadata_id),
            str(prompt),
            int(checked),
            int(rating),
            str(tags_json),
            int(size),
            str(file_hash),
            str(image_path),
            thumbnail_data
        )
    
    def get_by_ids(self, metadata_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """Получает метаданные для списка ID. Возвращает словарь {id: metadata}"""
        if not metadata_ids or self._memory_conn is None:
            return {}
        
        result = {}
        with self._read_lock:
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
    
    def has_metadata(self, image_path: str) -> bool:
        """Проверяет наличие метаданных для изображения"""
        if self._memory_conn is None:
            return False
        with self._read_lock:
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
        with self._read_lock:
            try:
                cursor = self._memory_conn.cursor()
                cursor.execute("SELECT * FROM metadata")
                rows = cursor.fetchall()
                return [self._row_to_dict(row) for row in rows]
            except Exception as e:
                logger.error(f"Ошибка получения всех метаданных: {e}")
                return []
    
    def get_by_folder(self, relative_folder: Optional[str]) -> List[Dict[str, Any]]:
        """Получает метаданные для изображений в указанной директории (без рекурсии)"""
        if self._memory_conn is None:
            return []
        
        with self._read_lock:
            try:
                cursor = self._memory_conn.cursor()
                if relative_folder is None:
                    cursor.execute("SELECT * FROM metadata")
                elif relative_folder == "":
                    cursor.execute("SELECT * FROM metadata WHERE instr(image_path, '/') = 0")
                else:
                    normalized = relative_folder.replace("\\", "/").rstrip("/")
                    pattern = f"{normalized}/%"
                    start_index = len(normalized) + 2
                    cursor.execute(
                        """
                        SELECT * FROM metadata
                        WHERE image_path LIKE ?
                          AND instr(substr(image_path, ?), '/') = 0
                        """,
                        (pattern, start_index)
                    )
                rows = cursor.fetchall()
                return [self._row_to_dict(row) for row in rows]
            except Exception as e:
                logger.error(f"Ошибка получения метаданных для папки '{relative_folder}': {e}")
                return []
    
    def get_by_paths(self, image_paths: List[str]) -> List[Optional[Dict[str, Any]]]:
        """Получает метаданные для списка путей изображений"""
        if not image_paths or self._memory_conn is None:
            return []
        
        normalized_paths = []
        path_to_index = {}
        for idx, path in enumerate(image_paths):
            if path:
                normalized = str(path).replace("\\", "/")
                normalized_paths.append(normalized)
                path_to_index[normalized] = idx
        
        if not normalized_paths:
            return [None] * len(image_paths)
        
        result: List[Optional[Dict[str, Any]]] = [None] * len(image_paths)
        
        with self._read_lock:
            try:
                placeholders = ",".join("?" * len(normalized_paths))
                cursor = self._memory_conn.cursor()
                cursor.execute(f"SELECT * FROM metadata WHERE image_path IN ({placeholders})", normalized_paths)
                rows = cursor.fetchall()
                for row in rows:
                    metadata = self._row_to_dict(row)
                    image_path = metadata.get("image_path")
                    if image_path:
                        normalized_db_path = str(image_path).replace("\\", "/")
                        if normalized_db_path in path_to_index:
                            result[path_to_index[normalized_db_path]] = metadata
            except Exception as e:
                logger.warning(f"Ошибка batch чтения метаданных: {e}")
        return result
    
    def save(self, metadata_list: List[Dict[str, Any]], force_save: bool = False) -> None:
        """Сохраняет метаданные. Принимает список метаданных для сохранения."""
        if not metadata_list or self._memory_conn is None:
            return
        
        for metadata in metadata_list:
            if not metadata.get("id"):
                raise ValueError("ID метаданных не найден")
        
        with self._read_lock:
            try:
                if len(metadata_list) == 1:
                    row_data = self._dict_to_row(metadata_list[0])
                    cursor = self._memory_conn.cursor()
                    cursor.execute("""
                        INSERT OR REPLACE INTO metadata 
                        (id, prompt, checked, rating, tags, size, hash, image_path, thumbnail_data, updated_at)
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
                        (id, prompt, checked, rating, tags, size, hash, image_path, thumbnail_data, updated_at)
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
    
    def get_bookmarks(self) -> List[Dict[str, Any]]:
        """Получает все закладки"""
        if self._memory_conn is None:
            return []
        try:
            cursor = self._memory_conn.cursor()
            cursor.execute("SELECT * FROM bookmarks ORDER BY created_at DESC")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Ошибка получения закладок: {e}")
            return []
    
    def add_bookmark(self, bookmark: Dict[str, Any]) -> None:
        """Добавляет закладку"""
        if self._memory_conn is None:
            return
        try:
            cursor = self._memory_conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO bookmarks 
                (id, metadata_id, image_path, folder_path, prompt, filename, sort_by, search_query)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                bookmark.get("id"),
                bookmark.get("metadata_id"),
                bookmark.get("image_path", ""),
                bookmark.get("folder_path", ""),
                bookmark.get("prompt", ""),
                bookmark.get("filename", ""),
                bookmark.get("sort_by", "date-desc"),
                bookmark.get("search_query", "")
            ))
            self._memory_conn.commit()
            self._schedule_save()
        except Exception as e:
            logger.error(f"Ошибка добавления закладки: {e}")
            raise
    
    def remove_bookmark(self, metadata_id: str) -> bool:
        """Удаляет закладку по metadata_id. Возвращает True если закладка была удалена"""
        if self._memory_conn is None:
            return False
        try:
            cursor = self._memory_conn.cursor()
            cursor.execute("DELETE FROM bookmarks WHERE metadata_id = ?", (metadata_id,))
            self._memory_conn.commit()
            if cursor.rowcount > 0:
                self._schedule_save()
                return True
            return False
        except Exception as e:
            logger.error(f"Ошибка удаления закладки: {e}")
            raise
    
    def has_bookmark(self, metadata_id: str) -> bool:
        """Проверяет наличие закладки по metadata_id"""
        if self._memory_conn is None:
            return False
        try:
            cursor = self._memory_conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM bookmarks WHERE metadata_id = ?", (metadata_id,))
            row = cursor.fetchone()
            return row[0] > 0 if row else False
        except Exception as e:
            logger.warning(f"Ошибка проверки закладки: {e}")
            return False

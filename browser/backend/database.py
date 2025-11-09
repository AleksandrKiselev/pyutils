import os
import sqlite3
import logging
import threading
import time
from pathlib import Path
from contextlib import contextmanager
from typing import Optional

from config import config

logger = logging.getLogger(__name__)

_memory_conn: Optional[sqlite3.Connection] = None
_memory_lock = threading.Lock()
_unsaved_changes = False
_initialized = False
_save_timer: Optional[threading.Timer] = None
_save_debounce = 5.0


def _get_db_path() -> str:
    db_dir = os.path.join(config.IMAGE_FOLDER, ".metadata")
    return os.path.join(db_dir, "metadata.db")


def _get_memory_connection() -> sqlite3.Connection:
    global _memory_conn
    if _memory_conn is None:
        with _memory_lock:
            if _memory_conn is None:
                _memory_conn = sqlite3.connect(":memory:", check_same_thread=False)
                _memory_conn.row_factory = sqlite3.Row
                _memory_conn.execute("PRAGMA synchronous=OFF")
                _memory_conn.execute("PRAGMA journal_mode=MEMORY")
    return _memory_conn


def _ensure_initialized() -> None:
    global _initialized
    if not _initialized:
        with _memory_lock:
            if not _initialized:
                init_database()
                _initialized = True


def _load_from_disk() -> None:
    db_path = _get_db_path()
    if not os.path.exists(db_path):
        return
    
    try:
        logger.info("Начало загрузки БД с диска")
        with sqlite3.connect(db_path, check_same_thread=False) as disk_conn:
            disk_conn.row_factory = sqlite3.Row
            
            # Проверяем, существует ли таблица на диске
            cursor = disk_conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='metadata'")
            if not cursor.fetchone():
                logger.info("Таблица metadata не найдена на диске, пропуск загрузки")
                return
            
            # Проверяем наличие колонок created_at и updated_at
            cursor.execute("PRAGMA table_info(metadata)")
            columns = {col[1] for col in cursor.fetchall()}
            has_timestamps = "created_at" in columns and "updated_at" in columns
            
            # Загружаем данные из таблицы на диске
            mem_conn = _get_memory_connection()
            cursor.execute("SELECT * FROM metadata")
            rows = cursor.fetchall()
            
            if rows:
                mem_cursor = mem_conn.cursor()
                if has_timestamps:
                    mem_cursor.executemany("""
                        INSERT OR REPLACE INTO metadata 
                        (id, prompt, checked, rating, tags, size, hash, image_path, thumb_path, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, [(row["id"], row["prompt"], row["checked"], row["rating"], row["tags"], 
                           row["size"], row["hash"], row["image_path"], row["thumb_path"],
                           row["created_at"], row["updated_at"]) for row in rows])
                else:
                    mem_cursor.executemany("""
                        INSERT OR REPLACE INTO metadata 
                        (id, prompt, checked, rating, tags, size, hash, image_path, thumb_path, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """, [(row["id"], row["prompt"], row["checked"], row["rating"], row["tags"], 
                           row["size"], row["hash"], row["image_path"], row["thumb_path"]) for row in rows])
                mem_conn.commit()
                logger.info(f"Загружено {len(rows)} записей с диска")
            else:
                logger.info("БД на диске пуста")
        
        logger.info("Завершена загрузка БД с диска в память")
    except Exception as e:
        logger.warning(f"Ошибка загрузки данных с диска: {e}")


def init_database() -> None:
    conn = _get_memory_connection()
    cursor = conn.cursor()
    
    # Сначала создаем таблицу и индексы
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS metadata (
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
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_image_path ON metadata(image_path)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_checked ON metadata(checked)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_rating ON metadata(rating)")
    conn.commit()
    
    # Затем загружаем данные с диска (если есть)
    _load_from_disk()


def _save_to_disk() -> None:
    global _unsaved_changes, _save_timer
    if not _unsaved_changes or not _initialized:
        return
    
    if _save_timer:
        _save_timer.cancel()
        _save_timer = None
    
    db_path = _get_db_path()
    db_dir = os.path.dirname(db_path)
    Path(db_dir).mkdir(parents=True, exist_ok=True)
    
    try:
        logger.info("Начало сохранения БД на диск")
        mem_conn = _get_memory_connection()
        
        mem_cursor = mem_conn.cursor()
        mem_cursor.execute("SELECT COUNT(*) FROM metadata")
        row = mem_cursor.fetchone()
        row_count = row[0] if row else 0
        
        if row_count == 0:
            logger.info("БД в памяти пуста, пропуск сохранения")
            _unsaved_changes = False
            return
        
        logger.info(f"Сохранение {row_count} записей на диск")
        
        # SQLite сам обеспечивает целостность через журнал транзакций
        # Используем прямой backup в основной файл
        max_retries = 5
        retry_delay = 0.1
        for attempt in range(max_retries):
            try:
                with sqlite3.connect(db_path, check_same_thread=False) as disk_conn:
                    mem_conn.backup(disk_conn)
                break
            except (PermissionError, OSError) as e:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                raise
        
        _unsaved_changes = False
        logger.info(f"Завершено сохранение {row_count} записей на диск")
    except Exception as e:
        logger.error(f"Ошибка сохранения данных на диск: {e}")


def _schedule_save() -> None:
    global _save_timer, _unsaved_changes
    if not _unsaved_changes or not _initialized:
        return
    
    if _save_timer:
        _save_timer.cancel()
    
    _save_timer = threading.Timer(_save_debounce, _save_to_disk)
    _save_timer.daemon = True
    _save_timer.start()


@contextmanager
def get_connection():
    global _unsaved_changes
    _ensure_initialized()
    conn = _get_memory_connection()
    
    try:
        yield conn
        conn.commit()
        _unsaved_changes = True
        _schedule_save()
    except Exception:
        conn.rollback()
        raise


def force_save() -> None:
    global _save_timer
    if _save_timer:
        _save_timer.cancel()
        _save_timer = None
    _save_to_disk()


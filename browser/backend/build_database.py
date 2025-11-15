#!/usr/bin/env python3
"""
Скрипт для построения базы данных метаданных изображений.
Рекурсивно обходит папку из config.json, генерирует метаданные, миниатюры и создает БД.
"""

import os
import shutil
import argparse
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

from tqdm import tqdm

from config import config
from metadata import metadata_store
from thumbnail import ThumbnailService
from paths import walk_images

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def process_images_batch(image_paths: List[str], max_workers: int = None) -> tuple:
    """
    Обрабатывает батч изображений: создает метаданные и миниатюры.
    
    Args:
        image_paths: Список путей к изображениям
        max_workers: Количество потоков
    
    Returns:
        Tuple[processed_count, failed_count, skipped_count, metadata_list]
    """
    if not image_paths:
        return (0, 0, 0, [])
    
    if max_workers is None:
        max_workers = min(32, (os.cpu_count() or 1) * 4, len(image_paths))
    
    processed = 0
    failed = 0
    skipped = 0
    metadata_list = []
    
    def process_single(image_path: str):
        """Обрабатывает одно изображение"""
        try:
            existing_list = metadata_store.get_by_paths([image_path])
            if existing_list and existing_list[0]:
                existing = existing_list[0]
                metadata = existing.copy()
                
                if existing.get("thumbnail_data"):
                    return (None, "skipped")
                
                logger.info(f"Метаданные найдены, но миниатюра отсутствует. Создание миниатюры для: {image_path}")
                updated = ThumbnailService.create_thumbnail(metadata)
                if updated:
                    metadata = updated
                    logger.info(f"Миниатюра успешно создана для: {image_path}")
                else:
                    logger.warning(f"Не удалось создать миниатюру для {image_path}, метаданные сохранены без миниатюры")
                return (metadata, "updated")
            else:
                metadata = metadata_store.create_metadata(image_path)
                updated = ThumbnailService.create_thumbnail(metadata)
                if updated:
                    metadata = updated
                
                return (metadata, "new")
        except Exception as e:
            logger.error(f"Ошибка обработки {image_path}: {e}", exc_info=True)
            return (None, "error")
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(process_single, img_path): img_path
            for img_path in image_paths
        }
        
        for future in as_completed(futures):
            img_path = futures[future]
            try:
                result = future.result()
                metadata, status = result
                
                if status == "skipped":
                    skipped += 1
                elif status == "error":
                    failed += 1
                elif metadata is not None:
                    metadata_list.append(metadata)
                    processed += 1
            except Exception as e:
                logger.error(f"Ошибка при обработке {img_path}: {e}", exc_info=True)
                failed += 1
    
    return (processed, failed, skipped, metadata_list)


def backup_database(db_path: str) -> bool:
    """
    Создает бэкап БД, если она существует.
    
    Args:
        db_path: Путь к файлу БД
    
    Returns:
        True если бэкап создан, False если БД не существует
    """
    if not os.path.exists(db_path):
        return False
    
    try:
        db_dir = os.path.dirname(db_path)
        db_name = os.path.basename(db_path)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_name = f"{db_name}.{timestamp}"
        backup_path = os.path.join(db_dir, backup_name)
        
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        
        shutil.copy2(db_path, backup_path)
        logger.info(f"Создан бэкап БД: {backup_path}")
        return True
    except Exception as e:
        logger.error(f"Ошибка создания бэкапа БД: {e}", exc_info=True)
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Строит базу данных метаданных для изображений из папки, указанной в config.json"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Количество потоков для обработки (по умолчанию: количество ядер CPU * 4)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Размер батча для обработки и сохранения (по умолчанию: 100)"
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Пропускать изображения, для которых уже есть метаданные и миниатюры"
    )
    
    args = parser.parse_args()
    
    root_folder = config.IMAGE_FOLDER
    
    if not os.path.isdir(root_folder):
        logger.error(f"Папка с изображениями не существует: {root_folder}")
        logger.error(f"Укажите правильный путь в config.json (параметр 'image_folder')")
        return 1
    
    try:
        db_path = os.path.join(
            root_folder,
            config.METADATA_FOLDER,
            config.DATABASE_NAME
        )
        
        logger.info("Проверка существующей БД и создание бэкапа...")
        if backup_database(db_path):
            logger.info("Бэкап БД успешно создан")
        else:
            logger.info("БД не найдена, бэкап не требуется")
        
        logger.info(f"Инициализация БД для папки: {root_folder}")
        logger.info("Загрузка БД с диска (если существует)...")
        metadata_store.initialize()
        
        all_metadata = metadata_store.get_all()
        if all_metadata:
            logger.info(f"Загружено {len(all_metadata)} записей из существующей БД")
        else:
            logger.info("БД не найдена или пуста, будет создана новая")
        
        logger.info("Очистка БД от невалидных записей...")
        metadata_store._db_manager._cleanup_invalid_metadata()
        
        logger.info("Поиск изображений в папке...")
        with tqdm(desc="Поиск изображений", unit=" файлов") as pbar:
            images = []
            for img_path in walk_images():
                images.append(img_path)
                pbar.update(1)
        
        if not images:
            logger.warning("Изображения не найдены")
            logger.info("Сохранение БД на диск...")
            metadata_store._db_manager._save_timer.cancel()
            metadata_store._db_manager._save_to_disk()
            return 0
        
        logger.info(f"Найдено {len(images)} изображений")
        
        if args.skip_existing:
            images_to_process = []
            with tqdm(desc="Проверка существующих", total=len(images), unit=" файлов") as pbar:
                for img_path in images:
                    existing_list = metadata_store.get_by_paths([img_path])
                    if existing_list and existing_list[0]:
                        existing = existing_list[0]
                        if existing.get("thumbnail_data"):
                            pbar.update(1)
                            continue
                    images_to_process.append(img_path)
                    pbar.update(1)
            
            skipped = len(images) - len(images_to_process)
            if skipped > 0:
                logger.info(f"Пропущено {skipped} уже полностью обработанных изображений (есть метаданные и миниатюра)")
            images = images_to_process
        
        if not images:
            logger.info("Все изображения уже обработаны")
            logger.info("Сохранение БД на диск...")
            metadata_store._db_manager._save_timer.cancel()
            metadata_store._db_manager._save_to_disk()
            return 0
        
        max_workers = args.workers
        if max_workers is None:
            max_workers = min(32, (os.cpu_count() or 1) * 4, len(images))
        
        logger.info(f"Обработка {len(images)} изображений с использованием {max_workers} потоков...")
        logger.info(f"Используются настройки из config.json:")
        logger.info(f"  - Размер миниатюр: {config.THUMBNAIL_SIZE}px")
        logger.info(f"  - Качество миниатюр: {config.THUMBNAIL_QUALITY}")
        logger.info(f"  - Автогенерация тегов: {'включена' if config.AUTO_TAG_ENABLED else 'выключена'}")
        if config.AUTO_TAG_ENABLED:
            logger.info(f"  - Порог тегов: {config.AUTO_TAG_THRESHOLD}")
        
        total_processed = 0
        total_failed = 0
        total_skipped = 0
        batch_size = args.batch_size
        with tqdm(
            desc="Обработка изображений",
            total=len(images),
            unit=" изображений",
            ncols=100,
            bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]'
        ) as main_pbar:
            for i in range(0, len(images), batch_size):
                batch = images[i:i + batch_size]
                batch_num = (i // batch_size) + 1
                total_batches = (len(images) + batch_size - 1) // batch_size
                
                logger.info(f"Обработка батча {batch_num}/{total_batches} ({len(batch)} изображений)...")
                
                processed, failed, skipped, metadata_list = process_images_batch(batch, max_workers)
                
                if metadata_list:
                    logger.info(f"Сохранение {len(metadata_list)} метаданных в БД...")
                    try:
                        metadata_store.save(metadata_list)
                    except Exception as e:
                        logger.error(f"Ошибка сохранения батча: {e}", exc_info=True)
                        save_failed = len(metadata_list)
                        failed += save_failed
                        processed -= save_failed
                        if processed < 0:
                            processed = 0
                
                total_processed += processed
                total_failed += failed
                total_skipped += skipped
                
                actually_processed = processed + failed + skipped
                main_pbar.update(actually_processed)
                main_pbar.set_postfix({
                    'processed': total_processed,
                    'failed': total_failed,
                    'skipped': total_skipped,
                    'batch': f"{batch_num}/{total_batches}"
                })
                
                logger.info(f"Батч {batch_num}/{total_batches} завершен: обработано {processed}, ошибок {failed}, пропущено {skipped}")
        
        logger.info("Сохранение БД на диск...")
        metadata_store._db_manager._save_timer.cancel()
        metadata_store._db_manager._save_to_disk()
        
        logger.info(f"Обработка завершена!")
        logger.info(f"  Обработано: {total_processed}")
        logger.info(f"  Ошибок: {total_failed}")
        logger.info(f"  Пропущено: {total_skipped}")
        logger.info(f"  БД сохранена: {db_path}")
        
        return 0
        
    except KeyboardInterrupt:
        logger.warning("Прервано пользователем")
        logger.info("Сохранение обработанных данных...")
        metadata_store._db_manager._save_timer.cancel()
        metadata_store._db_manager._save_to_disk()
        return 1
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit(main())

#!/usr/bin/env python3
"""Создает zip архивы с изображениями из каждой подпапки."""

import argparse
import sys
import zipfile
from pathlib import Path

from tqdm import tqdm

# Поддерживаемые форматы изображений
IMAGE_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp',
    '.tiff', '.tif', '.ico', '.svg', '.heic', '.heif',
    '.avif', '.jfif', '.jp2', '.jpx', '.j2k', '.j2c',
}


def is_image_file(file_path: Path) -> bool:
    """
    Проверяет, является ли файл изображением.
    
    Args:
        file_path: путь к файлу
    
    Returns:
        True, если файл является изображением
    """
    return file_path.suffix.lower() in IMAGE_EXTENSIONS


def get_image_files(directory: Path) -> list[Path]:
    """
    Получает список файлов изображений в директории (без вложенных папок).
    
    Args:
        directory: директория для поиска
    
    Returns:
        список путей к файлам изображений
    """
    if not directory.is_dir():
        return []
    
    image_files = []
    for item in directory.iterdir():
        if item.is_file() and is_image_file(item):
            image_files.append(item)
    
    return sorted(image_files)


def sanitize_archive_name(name: str) -> str:
    """
    Очищает имя для использования в имени архива.
    Заменяет проблемные символы на подчеркивания.
    
    Args:
        name: исходное имя
    
    Returns:
        очищенное имя
    """
    # Запрещенные символы в именах файлов Windows
    problematic_chars = '<>:"/\\|?*'
    result = []
    for char in name:
        if ord(char) < 32 or char in problematic_chars:
            result.append('_')
        else:
            result.append(char)
    
    # Убираем множественные подчеркивания
    cleaned = ''.join(result)
    cleaned = '_'.join(filter(None, cleaned.split('_')))
    
    return cleaned.strip('_')


def get_unique_archive_path(base_path: Path) -> Path:
    """
    Находит уникальное имя для архива, добавляя суффикс если нужно.
    
    Args:
        base_path: базовый путь к архиву
    
    Returns:
        уникальный путь к архиву
    """
    if not base_path.exists():
        return base_path
    
    stem = base_path.stem
    parent = base_path.parent
    
    counter = 1
    while True:
        new_name = f"{stem}_{counter}.zip"
        new_path = parent / new_name
        if not new_path.exists():
            return new_path
        counter += 1


def create_archive_for_directory(
    source_dir: Path,
    output_dir: Path,
    relative_path: Path,
) -> bool:
    """
    Создает zip архив с изображениями из директории.
    
    Args:
        source_dir: исходная директория
        output_dir: директория для сохранения архивов
        relative_path: относительный путь от source_dir до текущей директории
    
    Returns:
        True, если архив был создан, False если изображений не было
    """
    current_dir = source_dir / relative_path
    image_files = get_image_files(current_dir)
    
    if not image_files:
        return False
    
    # Формируем путь к архиву, сохраняя структуру папок
    if relative_path == Path('.'):
        # Для корневой папки используем её имя
        archive_name = current_dir.name
        archive_dir = output_dir
    else:
        # Для вложенных папок сохраняем структуру
        # Например: folder1/subfolder -> output_dir/folder1/subfolder.zip
        archive_name = relative_path.parts[-1]  # Имя текущей папки
        # Создаем подпапки в выходной директории
        parent_parts = relative_path.parts[:-1]
        if parent_parts:
            archive_dir = output_dir / Path(*parent_parts)
        else:
            archive_dir = output_dir
    
    # Очищаем имя
    archive_name = sanitize_archive_name(archive_name)
    if not archive_name:
        archive_name = 'images'
    
    # Создаем директорию для архива, если её нет
    archive_dir.mkdir(parents=True, exist_ok=True)
    
    # Формируем путь к архиву
    archive_path = archive_dir / f"{archive_name}.zip"
    archive_path = get_unique_archive_path(archive_path)
    
    # Создаем архив
    try:
        with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for image_file in image_files:
                # Добавляем файл в архив с его исходным именем
                zipf.write(image_file, image_file.name)
        
        return True
    except Exception as e:
        tqdm.write(f"Ошибка при создании архива '{archive_path}': {e}")
        return False


def create_archives(
    source_dir: Path,
    output_dir: Path,
) -> dict[str, int]:
    """
    Рекурсивно проходит по директории и создает zip архивы для каждой подпапки.
    
    Args:
        source_dir: исходная директория для обработки
        output_dir: директория для сохранения архивов
    
    Returns:
        словарь со статистикой: {'processed': int, 'created': int, 'skipped': int, 'errors': int}
    """
    # Создаем выходную директорию, если её нет
    output_dir.mkdir(parents=True, exist_ok=True)
    
    stats = {
        'processed': 0,
        'created': 0,
        'skipped': 0,
        'errors': 0,
    }
    
    # Собираем все поддиректории рекурсивно
    all_dirs = [source_dir] + list(source_dir.rglob('*'))
    directories = [d for d in all_dirs if d.is_dir()]
    
    # Обрабатываем директории с прогресс-баром
    progress_bar = tqdm(
        directories,
        desc='Обработка директорий',
        unit=' папок',
    )
    
    for directory in progress_bar:
        try:
            stats['processed'] += 1
            
            # Вычисляем относительный путь
            try:
                relative_path = directory.relative_to(source_dir)
            except ValueError:
                # Если не удалось вычислить относительный путь, пропускаем
                continue
            
            # Показываем текущую директорию
            display_path = str(relative_path) if relative_path != Path('.') else source_dir.name
            progress_bar.set_postfix({'текущая': display_path})
            
            # Создаем архив
            created = create_archive_for_directory(
                source_dir,
                output_dir,
                relative_path,
            )
            
            if created:
                stats['created'] += 1
            else:
                stats['skipped'] += 1
            
            progress_bar.set_postfix({
                'обработано': stats['processed'],
                'создано': stats['created'],
                'пропущено': stats['skipped'],
            })
            
        except Exception as e:
            tqdm.write(f"Ошибка при обработке '{directory}': {e}")
            stats['errors'] += 1
            progress_bar.set_postfix({
                'обработано': stats['processed'],
                'создано': stats['created'],
                'ошибок': stats['errors'],
            })
    
    return stats


def parse_args() -> argparse.Namespace:
    """Парсит аргументы командной строки."""
    parser = argparse.ArgumentParser(
        description='Создает zip архивы с изображениями из каждой подпапки.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='Примеры:\n'
               '  %(prog)s D:\\SourceFolder D:\\OutputFolder\n'
               '  %(prog)s D:\\Images D:\\Archives',
    )
    
    parser.add_argument(
        'source_dir',
        type=Path,
        help='исходная директория для обработки (рекурсивно)',
    )
    
    parser.add_argument(
        'output_dir',
        type=Path,
        help='директория для сохранения zip архивов',
    )
    
    return parser.parse_args()


def main() -> int:
    """Главная функция."""
    args = parse_args()
    
    # Проверяем существование исходной директории
    if not args.source_dir.exists():
        print(f"Ошибка: директория '{args.source_dir}' не найдена", file=sys.stderr)
        return 1
    
    if not args.source_dir.is_dir():
        print(f"Ошибка: '{args.source_dir}' не является директорией", file=sys.stderr)
        return 1
    
    try:
        stats = create_archives(
            args.source_dir,
            args.output_dir,
        )
        
        print()
        print("=" * 50)
        print("Статистика:")
        print(f"  Обработано папок: {stats['processed']}")
        print(f"  Создано архивов: {stats['created']}")
        print(f"  Пропущено папок (без изображений): {stats['skipped']}")
        print(f"  Ошибок: {stats['errors']}")
        print("=" * 50)
        
        return 0
        
    except Exception as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())


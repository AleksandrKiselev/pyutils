#!/usr/bin/env python3
"""Исправляет имена файлов: транслитерация, замена небуквенных символов на подчеркивание, обрезка длины."""

import argparse
import re
import sys
from pathlib import Path

from tqdm import tqdm

# Таблица транслитерации русских символов
TRANSLIT_TABLE = str.maketrans({
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
    'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Е': 'E', 'Ё': 'Yo',
    'Ж': 'Zh', 'З': 'Z', 'И': 'I', 'Й': 'Y', 'К': 'K', 'Л': 'L', 'М': 'M',
    'Н': 'N', 'О': 'O', 'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T', 'У': 'U',
    'Ф': 'F', 'Х': 'H', 'Ц': 'Ts', 'Ч': 'Ch', 'Ш': 'Sh', 'Щ': 'Sch',
    'Ъ': '', 'Ы': 'Y', 'Ь': '', 'Э': 'E', 'Ю': 'Yu', 'Я': 'Ya',
})


def transliterate(text: str) -> str:
    """
    Транслитерирует русские символы в английские.
    
    Args:
        text: исходный текст
    
    Returns:
        транслитерированный текст
    """
    return text.translate(TRANSLIT_TABLE)


def replace_non_letters(text: str) -> str:
    """
    Заменяет все небуквенные символы на нижнее подчеркивание.
    
    Args:
        text: исходный текст
    
    Returns:
        текст с замененными небуквенными символами
    """
    result = []
    for char in text:
        if char.isalpha():
            result.append(char)
        else:
            result.append('_')
    return ''.join(result)


def fix_filename(filename: str, max_length: int = 100) -> str:
    """
    Исправляет имя файла: транслитерация, замена небуквенных символов на подчеркивание, обрезка длины.
    
    Args:
        filename: исходное имя файла
        max_length: максимальная длина имени (по умолчанию 100)
    
    Returns:
        исправленное имя файла
    """
    # Разделяем имя и расширение
    path_obj = Path(filename)
    stem = path_obj.stem
    suffix = path_obj.suffix
    
    # Транслитерируем
    fixed_stem = transliterate(stem)
    
    # Заменяем все небуквенные символы на подчеркивание
    fixed_stem = replace_non_letters(fixed_stem)
    
    # Убираем множественные подчеркивания (заменяем на одно)
    fixed_stem = re.sub(r'_+', '_', fixed_stem)
    
    # Убираем подчеркивания в начале и конце
    fixed_stem = fixed_stem.strip('_')
    
    # Если после обработки имя пустое, используем дефолтное
    if not fixed_stem:
        fixed_stem = 'file'
    
    # Обрезаем до максимальной длины (с учетом расширения)
    max_stem_length = max_length - len(suffix)
    if len(fixed_stem) > max_stem_length:
        fixed_stem = fixed_stem[:max_stem_length]
        # Убираем подчеркивание в конце, если оно осталось после обрезки
        fixed_stem = fixed_stem.rstrip('_')
    
    return fixed_stem + suffix


def fix_filenames_in_directory(
    directory: Path,
    max_length: int = 100,
    dry_run: bool = False,
) -> dict[str, int]:
    """
    Исправляет имена всех файлов в директории рекурсивно.
    
    Args:
        directory: директория для обработки
        max_length: максимальная длина имени файла
        dry_run: если True, только показывает что будет изменено, не переименовывает
    
    Returns:
        словарь со статистикой: {'processed': int, 'renamed': int, 'errors': int}
    """
    # Собираем все файлы рекурсивно
    all_files = list(directory.rglob('*'))
    files_only = [f for f in all_files if f.is_file()]
    
    stats = {
        'processed': 0,
        'renamed': 0,
        'errors': 0,
    }
    
    # Обрабатываем файлы с прогресс-баром
    progress_bar = tqdm(
        files_only,
        desc='Обработка файлов',
        unit=' файл',
    )
    
    for file_path in progress_bar:
        try:
            stats['processed'] += 1
            
            original_name = file_path.name
            fixed_name = fix_filename(original_name, max_length)
            
            # Если имя не изменилось, пропускаем
            if original_name == fixed_name:
                continue
            
            # Формируем новый путь
            new_path = file_path.parent / fixed_name
            
            # Проверяем, не существует ли уже файл с таким именем
            if new_path.exists() and new_path != file_path:
                tqdm.write(f"Пропущено: '{file_path}' -> '{fixed_name}' (файл уже существует)")
                stats['errors'] += 1
                continue
            
            if dry_run:
                tqdm.write(f"[DRY RUN] '{file_path}' -> '{new_path}'")
            else:
                file_path.rename(new_path)
                tqdm.write(f"Переименовано: '{original_name}' -> '{fixed_name}'")
            
            stats['renamed'] += 1
            progress_bar.set_postfix({
                'обработано': stats['processed'],
                'переименовано': stats['renamed'],
                'ошибок': stats['errors'],
            })
            
        except Exception as e:
            tqdm.write(f"Ошибка при обработке '{file_path}': {e}")
            stats['errors'] += 1
            progress_bar.set_postfix({
                'обработано': stats['processed'],
                'переименовано': stats['renamed'],
                'ошибок': stats['errors'],
            })
    
    return stats


def parse_args() -> argparse.Namespace:
    """Парсит аргументы командной строки."""
    parser = argparse.ArgumentParser(
        description='Исправляет имена файлов: транслитерация, замена небуквенных символов на подчеркивание, обрезка длины.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='Примеры:\n'
               '  %(prog)s D:\\MyFolder\n'
               '  %(prog)s D:\\MyFolder --max-length 50\n'
               '  %(prog)s D:\\MyFolder --dry-run',
    )
    
    parser.add_argument(
        'directory',
        type=Path,
        help='директория для обработки (рекурсивно)',
    )
    
    parser.add_argument(
        '-l', '--max-length',
        type=int,
        default=100,
        metavar='LENGTH',
        help='максимальная длина имени файла (по умолчанию: 100)',
    )
    
    parser.add_argument(
        '-n', '--dry-run',
        action='store_true',
        help='показать что будет изменено, не переименовывать файлы',
    )
    
    return parser.parse_args()


def main() -> int:
    """Главная функция."""
    args = parse_args()
    
    # Проверяем существование директории
    if not args.directory.exists():
        print(f"Ошибка: директория '{args.directory}' не найдена", file=sys.stderr)
        return 1
    
    if not args.directory.is_dir():
        print(f"Ошибка: '{args.directory}' не является директорией", file=sys.stderr)
        return 1
    
    # Проверяем максимальную длину
    if args.max_length < 1:
        print("Ошибка: максимальная длина должна быть больше 0", file=sys.stderr)
        return 1
    
    try:
        if args.dry_run:
            print("Режим проверки (dry-run): файлы не будут переименованы\n")
        
        stats = fix_filenames_in_directory(
            args.directory,
            args.max_length,
            args.dry_run,
        )
        
        print()
        print("=" * 50)
        print("Статистика:")
        print(f"  Обработано файлов: {stats['processed']}")
        print(f"  Переименовано файлов: {stats['renamed']}")
        print(f"  Ошибок: {stats['errors']}")
        print("=" * 50)
        
        return 0
        
    except Exception as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())


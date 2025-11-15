#!/usr/bin/env python3
"""Удаляет из входного файла все строки, которые есть в файле исключений."""

import argparse
import sys
from pathlib import Path


def read_lines(file_path: Path) -> list[str]:
    """Читает строки из файла."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return [line.rstrip('\n\r') for line in f]


def exclude_lines(
    input_file: Path,
    exclude_file: Path,
    output_file: Path | None = None,
    ignore_case: bool = False,
) -> tuple[int, int]:
    """
    Удаляет из input_file строки, которые есть в exclude_file.
    
    Args:
        input_file: файл, из которого удаляются строки
        exclude_file: файл со строками для исключения
        output_file: файл для сохранения результата (если None, перезаписывает input_file)
        ignore_case: игнорировать регистр при сравнении
    
    Returns:
        tuple[int, int]: (количество удаленных строк, количество оставшихся строк)
    """
    # Читаем файл с исключениями и создаем множество для быстрого поиска
    lines_to_exclude = read_lines(exclude_file)
    if ignore_case:
        lines_to_exclude = {line.lower() for line in lines_to_exclude}
    else:
        lines_to_exclude = set(lines_to_exclude)
    
    # Читаем входной файл
    input_lines = read_lines(input_file)
    
    # Фильтруем строки
    if ignore_case:
        filtered_lines = [
            line for line in input_lines
            if line.lower() not in lines_to_exclude
        ]
    else:
        filtered_lines = [
            line for line in input_lines
            if line not in lines_to_exclude
        ]
    
    # Определяем файл для записи результата
    output_path = output_file if output_file else input_file
    
    # Записываем результат
    with open(output_path, 'w', encoding='utf-8') as f:
        for line in filtered_lines:
            f.write(line + '\n')
    
    removed_count = len(input_lines) - len(filtered_lines)
    return removed_count, len(filtered_lines)


def parse_args() -> argparse.Namespace:
    """Парсит аргументы командной строки."""
    parser = argparse.ArgumentParser(
        description='Удаляет из входного файла все строки, которые есть в файле исключений.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='Примеры:\n'
               '  %(prog)s input.txt exclude.txt\n'
               '  %(prog)s input.txt exclude.txt -o result.txt\n'
               '  %(prog)s input.txt exclude.txt --ignore-case',
    )
    
    parser.add_argument(
        'input_file',
        type=Path,
        help='входной файл, из которого удаляются строки',
    )
    
    parser.add_argument(
        'exclude_file',
        type=Path,
        help='файл со строками для исключения (удаления)',
    )
    
    parser.add_argument(
        '-o', '--output',
        type=Path,
        default=None,
        metavar='FILE',
        help='файл для сохранения результата (по умолчанию перезаписывает входной файл)',
    )
    
    parser.add_argument(
        '-i', '--ignore-case',
        action='store_true',
        help='игнорировать регистр при сравнении строк',
    )
    
    return parser.parse_args()


def main() -> int:
    """Главная функция."""
    args = parse_args()
    
    # Проверяем существование файлов
    if not args.input_file.exists():
        print(f"Ошибка: входной файл '{args.input_file}' не найден", file=sys.stderr)
        return 1
    
    if not args.exclude_file.exists():
        print(f"Ошибка: файл исключений '{args.exclude_file}' не найден", file=sys.stderr)
        return 1
    
    try:
        removed_count, remaining_count = exclude_lines(
            args.input_file,
            args.exclude_file,
            args.output,
            args.ignore_case,
        )
        
        print(f"Удалено строк: {removed_count}")
        print(f"Осталось строк: {remaining_count}")
        return 0
        
    except Exception as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())


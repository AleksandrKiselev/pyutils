#!/usr/bin/env python3
"""Сортирует строки в файле различными способами."""

import argparse
import random
import sys
from pathlib import Path


def read_lines(file_path: Path) -> list[str]:
    """Читает строки из файла."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return [line.rstrip('\n\r') for line in f]


def write_lines(file_path: Path, lines: list[str]) -> None:
    """Записывает строки в файл."""
    with open(file_path, 'w', encoding='utf-8') as f:
        for line in lines:
            f.write(line + '\n')


def sort_lines(
    input_file: Path,
    mode: str,
    output_file: Path | None = None,
    reverse: bool = False,
    seed: int | None = None,
) -> None:
    """
    Сортирует строки в файле.
    
    Args:
        input_file: файл для сортировки
        mode: режим сортировки ('random', 'alphabetical', 'length')
        output_file: файл для сохранения результата (если None, перезаписывает input_file)
        reverse: обратный порядок (для alphabetical и length)
        seed: seed для генератора случайных чисел (для random)
    """
    # Читаем строки
    lines = read_lines(input_file)
    
    # Сортируем в зависимости от режима
    if mode == 'random':
        if seed is not None:
            random.seed(seed)
        sorted_lines = lines.copy()
        random.shuffle(sorted_lines)
    elif mode == 'alphabetical':
        sorted_lines = sorted(lines, reverse=reverse)
    elif mode == 'length':
        sorted_lines = sorted(lines, key=len, reverse=reverse)
    else:
        raise ValueError(f"Неизвестный режим сортировки: {mode}")
    
    # Определяем файл для записи результата
    output_path = output_file if output_file else input_file
    
    # Записываем результат
    write_lines(output_path, sorted_lines)


def parse_args() -> argparse.Namespace:
    """Парсит аргументы командной строки."""
    parser = argparse.ArgumentParser(
        description='Сортирует строки в файле различными способами.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='Примеры:\n'
               '  %(prog)s input.txt --mode alphabetical\n'
               '  %(prog)s input.txt --mode random -o result.txt\n'
               '  %(prog)s input.txt --mode length --reverse\n'
               '  %(prog)s input.txt --mode random --seed 42',
    )
    
    parser.add_argument(
        'input_file',
        type=Path,
        help='файл для сортировки',
    )
    
    parser.add_argument(
        '-m', '--mode',
        choices=['random', 'alphabetical', 'length'],
        required=True,
        help='режим сортировки: random (случайный), alphabetical (алфавитный), length (по длине)',
    )
    
    parser.add_argument(
        '-o', '--output',
        type=Path,
        default=None,
        metavar='FILE',
        help='файл для сохранения результата (по умолчанию перезаписывает входной файл)',
    )
    
    parser.add_argument(
        '-r', '--reverse',
        action='store_true',
        help='обратный порядок (для alphabetical и length)',
    )
    
    parser.add_argument(
        '-s', '--seed',
        type=int,
        default=None,
        metavar='N',
        help='seed для генератора случайных чисел (для random)',
    )
    
    return parser.parse_args()


def main() -> int:
    """Главная функция."""
    args = parse_args()
    
    # Проверяем существование файла
    if not args.input_file.exists():
        print(f"Ошибка: файл '{args.input_file}' не найден", file=sys.stderr)
        return 1
    
    try:
        sort_lines(
            args.input_file,
            args.mode,
            args.output,
            args.reverse,
            args.seed,
        )
        
        mode_names = {
            'random': 'случайный',
            'alphabetical': 'алфавитный',
            'length': 'по длине',
        }
        print(f"Строки отсортированы ({mode_names[args.mode]} порядок)")
        return 0
        
    except Exception as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())


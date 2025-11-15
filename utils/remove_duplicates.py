#!/usr/bin/env python3
"""Удаляет дубликаты строк из файла с учетом процента схожести."""

import argparse
import sys
from pathlib import Path

from rapidfuzz import fuzz
from tqdm import tqdm


def read_lines(file_path: Path) -> list[str]:
    """Читает строки из файла."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return [line.rstrip('\n\r') for line in f]


def write_lines(file_path: Path, lines: list[str]) -> None:
    """Записывает строки в файл."""
    with open(file_path, 'w', encoding='utf-8') as f:
        for line in lines:
            f.write(line + '\n')


def similarity_ratio(str1: str, str2: str) -> float:
    """Вычисляет коэффициент схожести двух строк (0.0 - 1.0)."""
    return fuzz.ratio(str1, str2) / 100.0


def remove_duplicates(
    input_file: Path,
    similarity_threshold: float,
    output_file: Path | None = None,
    case_sensitive: bool = True,
    verbose: bool = True,
    show_progress: bool = True,
) -> tuple[int, int]:
    """
    Удаляет дубликаты строк из файла с учетом процента схожести.
    Оставляет более длинную строку из пары дубликатов.
    
    Args:
        input_file: файл для обработки
        similarity_threshold: порог схожести (0.0 - 1.0), строки с большей схожестью считаются дубликатами
        output_file: файл для сохранения результата (если None, перезаписывает input_file)
        case_sensitive: учитывать регистр при сравнении
        verbose: выводить информацию о найденных дубликатах
        show_progress: показывать прогресс-бар
    
    Returns:
        tuple[int, int]: (количество удаленных строк, количество оставшихся строк)
    """
    # Читаем строки
    lines = read_lines(input_file)
    
    if not lines:
        # Определяем файл для записи результата
        output_path = output_file if output_file else input_file
        write_lines(output_path, [])
        return 0, 0
    
    # Удаляем дубликаты
    unique_lines = []
    unique_normalized = []
    removed_count = 0
    
    # Используем tqdm для отображения прогресса
    progress_bar = tqdm(
        lines,
        desc='Поиск дубликатов',
        unit=' строк',
        disable=not show_progress,
    )
    
    for line in progress_bar:
        # Нормализуем строку для сравнения
        if case_sensitive:
            normalized_line = line
        else:
            normalized_line = line.lower()
        
        duplicate_found = False
        best_match_idx = -1
        best_similarity = 0.0
        
        # Ищем наиболее похожую строку среди уже добавленных
        for idx, unique_norm in enumerate(unique_normalized):
            similarity = similarity_ratio(normalized_line, unique_norm)
            
            if similarity >= similarity_threshold and similarity > best_similarity:
                duplicate_found = True
                best_match_idx = idx
                best_similarity = similarity
        
        if duplicate_found:
            # Сравниваем длины строк
            existing_line = unique_lines[best_match_idx]
            
            if len(line) > len(existing_line):
                # Текущая строка длиннее - заменяем старую
                if verbose:
                    similarity_percent = best_similarity * 100
                    tqdm.write(f"\nДубликат найден (схожесть: {similarity_percent:.1f}%):")
                    tqdm.write(f"  [УДАЛЕНО] {existing_line}")
                    tqdm.write(f"  [ОСТАВЛЕНО] {line}")
                
                unique_lines[best_match_idx] = line
                unique_normalized[best_match_idx] = normalized_line
                removed_count += 1
                progress_bar.set_postfix({'дубликатов': removed_count, 'уникальных': len(unique_lines)})
            else:
                # Существующая строка длиннее - пропускаем текущую
                if verbose:
                    similarity_percent = best_similarity * 100
                    tqdm.write(f"\nДубликат найден (схожесть: {similarity_percent:.1f}%):")
                    tqdm.write(f"  [ОСТАВЛЕНО] {existing_line}")
                    tqdm.write(f"  [УДАЛЕНО] {line}")
                
                removed_count += 1
                progress_bar.set_postfix({'дубликатов': removed_count, 'уникальных': len(unique_lines)})
        else:
            # Дубликатов не найдено - добавляем строку
            unique_lines.append(line)
            unique_normalized.append(normalized_line)
            progress_bar.set_postfix({'дубликатов': removed_count, 'уникальных': len(unique_lines)})
    
    # Определяем файл для записи результата
    output_path = output_file if output_file else input_file
    
    # Записываем результат
    write_lines(output_path, unique_lines)
    
    return removed_count, len(unique_lines)


def parse_args() -> argparse.Namespace:
    """Парсит аргументы командной строки."""
    parser = argparse.ArgumentParser(
        description='Удаляет дубликаты строк из файла с учетом процента схожести.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='Примеры:\n'
               '  %(prog)s input.txt --similarity 100\n'
               '  %(prog)s input.txt --similarity 90 -o result.txt\n'
               '  %(prog)s input.txt --similarity 80 --ignore-case\n'
               '  %(prog)s input.txt --similarity 90 --quiet',
    )
    
    parser.add_argument(
        'input_file',
        type=Path,
        help='файл для обработки',
    )
    
    parser.add_argument(
        '-s', '--similarity',
        type=float,
        required=True,
        metavar='PERCENT',
        help='процент схожести (0-100), строки с большей схожестью считаются дубликатами',
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
    
    parser.add_argument(
        '-q', '--quiet',
        action='store_true',
        help='не выводить информацию о найденных дубликатах',
    )
    
    return parser.parse_args()


def main() -> int:
    """Главная функция."""
    args = parse_args()
    
    # Проверяем существование файла
    if not args.input_file.exists():
        print(f"Ошибка: файл '{args.input_file}' не найден", file=sys.stderr)
        return 1
    
    # Проверяем диапазон процента схожести
    if not 0 <= args.similarity <= 100:
        print("Ошибка: процент схожести должен быть в диапазоне 0-100", file=sys.stderr)
        return 1
    
    # Преобразуем процент в коэффициент (0.0 - 1.0)
    similarity_threshold = args.similarity / 100.0
    
    try:
        removed_count, remaining_count = remove_duplicates(
            args.input_file,
            similarity_threshold,
            args.output,
            not args.ignore_case,
            not args.quiet,
            not args.quiet,
        )
        
        if not args.quiet:
            print()
        print(f"Удалено дубликатов: {removed_count}")
        print(f"Осталось строк: {remaining_count}")
        return 0
        
    except Exception as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())


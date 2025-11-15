#!/usr/bin/env python3
"""Форматирует промпты в файле согласно правилам."""

import argparse
import re
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


def normalize_token(token: str) -> str:
    """
    Нормализует токен: удаляет пробелы в начале/конце и дублирующиеся пробелы.
    
    Args:
        token: исходный токен
    
    Returns:
        нормализованный токен
    """
    # Удаляем пробелы в начале и конце
    token = token.strip()
    
    # Удаляем дублирующиеся пробелы
    token = re.sub(r'\s+', ' ', token)
    
    return token


def format_prompt(prompt: str) -> str:
    """
    Форматирует промпт согласно правилам.
    
    Разделители: запятая и слово "BREAK" (в верхнем регистре).
    Все токены приводятся к нижнему регистру, кроме случаев, когда в промпте есть "<lora:".
    
    Args:
        prompt: исходный промпт
    
    Returns:
        отформатированный промпт
    """
    # Схлопываем слеши в один
    prompt = prompt.replace('//', '/')
    prompt = prompt.replace('\\\\', '\\')
    
    # Исправляем неправильное экранирование скобок
    prompt = prompt.replace('(\\', '\\(')
    prompt = prompt.replace('(/', '\\(')
    prompt = prompt.replace('/(', '\\(')
    prompt = prompt.replace(')\\', '\\)')
    prompt = prompt.replace(')/', '\\)')
    prompt = prompt.replace('/)', '\\)')
    
    # Проверяем, есть ли в промпте подстрока "<lora:" - если есть, отключаем приведение к нижнему регистру
    has_lora = '<lora:' in prompt
    
    # Используем регулярное выражение для разделения по запятым и "BREAK" с сохранением разделителей
    # Разделяем по запятым и "BREAK" (как целое слово в верхнем регистре)
    # Используем \b для границ слов, чтобы "BREAK" не совпадал внутри других слов
    parts = re.split(r'(,|\bBREAK\b)', prompt)
    
    # Обрабатываем части
    formatted_parts = []
    for part in parts:
        part = part.strip()
        
        # Если это разделитель (запятая или BREAK)
        if part == ',':
            formatted_parts.append(',')
        elif part == 'BREAK':
            formatted_parts.append('BREAK')
        elif part:
            # Это токен - нормализуем пробелы
            normalized = normalize_token(part)
            
            if normalized:
                # Приводим к нижнему регистру только если нет "<lora:"
                if has_lora:
                    formatted_parts.append(normalized)
                else:
                    formatted_parts.append(normalized.lower())
    
    # Объединяем части, добавляя пробелы вокруг разделителей
    result = []
    for i, part in enumerate(formatted_parts):
        # Для BREAK добавляем пробел перед, если предыдущий элемент - не разделитель
        if part == 'BREAK' and i > 0:
            prev_part = formatted_parts[i - 1]
            if prev_part not in (',', 'BREAK'):
                result.append(' ')
        
        result.append(part)
        
        # Добавляем пробел после разделителя
        if part == ',':
            # Для запятой - пробел только после, если следующий элемент - не разделитель
            if i + 1 < len(formatted_parts):
                next_part = formatted_parts[i + 1]
                if next_part not in (',', 'BREAK'):
                    result.append(' ')
        elif part == 'BREAK':
            # Для BREAK - пробел всегда после, если следующий элемент - не разделитель
            if i + 1 < len(formatted_parts):
                next_part = formatted_parts[i + 1]
                if next_part not in (',', 'BREAK'):
                    result.append(' ')
    
    return ''.join(result)


def format_prompts_file(
    input_file: Path,
    output_file: Path | None = None,
) -> tuple[int, int, int]:
    """
    Форматирует промпты в файле.
    
    Args:
        input_file: файл для обработки
        output_file: файл для сохранения результата (если None, перезаписывает input_file)
    
    Returns:
        tuple[int, int, int]: (количество обработанных строк, количество оставшихся строк, количество измененных строк)
    """
    # Читаем строки
    lines = read_lines(input_file)
    
    # Удаляем пустые строки и форматируем
    formatted_lines = []
    changed_count = 0
    
    for line in lines:
        # Пропускаем пустые строки
        if not line.strip():
            continue
        
        # Форматируем промпт
        formatted = format_prompt(line)
        
        # Сравниваем исходную и отформатированную строки
        if line != formatted:
            changed_count += 1
        
        # Добавляем в результат, если после форматирования строка не пустая
        if formatted.strip():
            formatted_lines.append(formatted)
    
    # Определяем файл для записи результата
    output_path = output_file if output_file else input_file
    
    # Записываем результат
    write_lines(output_path, formatted_lines)
    
    return len(lines), len(formatted_lines), changed_count


def parse_args() -> argparse.Namespace:
    """Парсит аргументы командной строки."""
    parser = argparse.ArgumentParser(
        description='Форматирует промпты в файле согласно правилам.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='Правила форматирования:\n'
               '  1. Удаляются пустые строки\n'
               '  2. Все токены приводятся к нижнему регистру (кроме промптов с "<lora:")\n'
               '  3. Удаляются дублирующиеся пробелы и пробелы в начале/конце токенов\n'
               '  4. Разделители: запятая и слово "BREAK" (в верхнем регистре)\n'
               '  5. Исправляется неправильное экранирование скобок: (\\ -> \\(, )\\ -> \\)\n'
               '\n'
               'Примеры:\n'
               '  %(prog)s input.txt\n'
               '  %(prog)s input.txt -o result.txt',
    )
    
    parser.add_argument(
        'input_file',
        type=Path,
        help='файл с промптами для форматирования',
    )
    
    parser.add_argument(
        '-o', '--output',
        type=Path,
        default=None,
        metavar='FILE',
        help='файл для сохранения результата (по умолчанию перезаписывает входной файл)',
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
        total_lines, formatted_lines, changed_lines = format_prompts_file(
            args.input_file,
            args.output,
        )
        
        print(f"Обработано строк: {total_lines}")
        print(f"Осталось строк: {formatted_lines}")
        print(f"Изменено строк: {changed_lines}")
        return 0
        
    except Exception as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())


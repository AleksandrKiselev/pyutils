@echo off
REM Скрипт для сортировки строк в файле
REM Укажите путь к файлу и режим сортировки ниже

set INPUT_FILE=D:\AI-Software\configs\wildcards\prompt\raw.txt
set MODE=random
set OUTPUT_FILE=
set REVERSE=
set SEED=

REM Режимы сортировки:
REM   random       - случайный порядок
REM   alphabetical - алфавитный порядок
REM   length       - по длине строки

REM Опции (раскомментируйте при необходимости):
REM set REVERSE=--reverse
REM set SEED=--seed 42

REM Получаем путь к директории, где находится bat-файл
set SCRIPT_DIR=%~dp0

REM Формируем команду
set COMMAND=python "%SCRIPT_DIR%sort_lines.py" "%INPUT_FILE%" --mode %MODE%

if defined OUTPUT_FILE (
    set COMMAND=%COMMAND% -o "%OUTPUT_FILE%"
)

if defined REVERSE (
    set COMMAND=%COMMAND% %REVERSE%
)

if defined SEED (
    set COMMAND=%COMMAND% %SEED%
)

REM Запускаем скрипт
%COMMAND%

pause


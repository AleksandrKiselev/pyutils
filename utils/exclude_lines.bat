@echo off
REM Скрипт для исключения строк из входного файла
REM Укажите пути к файлам ниже

set INPUT_FILE=D:\AI-Software\configs\wildcards\prompt\raw.txt
set EXCLUDE_FILE=D:\AI-Software\configs\wildcards\prompt\prompt.txt
set OUTPUT_FILE=

REM Опции (раскомментируйте при необходимости):
REM set IGNORE_CASE=--ignore-case

REM Получаем путь к директории, где находится bat-файл
set SCRIPT_DIR=%~dp0

REM Формируем команду
set COMMAND=python "%SCRIPT_DIR%exclude_lines.py" "%INPUT_FILE%" "%EXCLUDE_FILE%"

if defined OUTPUT_FILE (
    set COMMAND=%COMMAND% -o "%OUTPUT_FILE%"
)

if defined IGNORE_CASE (
    set COMMAND=%COMMAND% %IGNORE_CASE%
)

REM Запускаем скрипт
%COMMAND%

pause


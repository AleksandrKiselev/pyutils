@echo off
REM Скрипт для форматирования промптов в файле
REM Укажите путь к файлу ниже

set INPUT_FILE=D:\AI-Software\configs\wildcards\prompt\raw.txt
set OUTPUT_FILE=

REM Получаем путь к директории, где находится bat-файл
set SCRIPT_DIR=%~dp0

REM Формируем команду
set COMMAND=python "%SCRIPT_DIR%format_prompts.py" "%INPUT_FILE%"

if defined OUTPUT_FILE (
    set COMMAND=%COMMAND% -o "%OUTPUT_FILE%"
)

REM Запускаем скрипт
%COMMAND%

pause


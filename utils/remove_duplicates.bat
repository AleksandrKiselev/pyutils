@echo off
REM Скрипт для удаления дубликатов строк из файла
REM Укажите путь к файлу и процент схожести ниже

set INPUT_FILE=D:\AI-Software\configs\wildcards\prompt\raw.txt
set SIMILARITY=90
set OUTPUT_FILE=
set IGNORE_CASE=

REM Процент схожести (0-100):
REM   100 - точное совпадение (удаляет только полностью идентичные строки)
REM   90  - очень похожие строки (90% и более схожести)
REM   80  - похожие строки (80% и более схожести)
REM   0   - удалит все строки (не рекомендуется)

REM Опции (раскомментируйте при необходимости):
REM set IGNORE_CASE=--ignore-case

REM Получаем путь к директории, где находится bat-файл
set SCRIPT_DIR=%~dp0

REM Формируем команду
set COMMAND=python "%SCRIPT_DIR%remove_duplicates.py" "%INPUT_FILE%" --similarity %SIMILARITY%

if defined OUTPUT_FILE (
    set COMMAND=%COMMAND% -o "%OUTPUT_FILE%"
)

if defined IGNORE_CASE (
    set COMMAND=%COMMAND% %IGNORE_CASE%
)

REM Запускаем скрипт
%COMMAND%

pause


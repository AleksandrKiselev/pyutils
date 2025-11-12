# Image Viewer

Веб-приложение для просмотра и управления коллекцией изображений с метаданными.

## Установка

```bash
# Создать/обновить conda окружение
conda env create -f ../environment.yml
# или если окружение уже есть:
conda env update -f ../environment.yml --prune

# Активировать окружение
conda activate neural-networks
```

## Запуск

```bash
cd browser
python backend/app.py
```

Или через bat файл:
```bash
app.bat
```

Приложение будет доступно по адресу: http://127.0.0.1:5000

## Настройка

Настройте `config.json`:

```json
{
    "image_folder": "путь/к/папке/с/изображениями",
    "favorites_folder": "путь/к/папке/избранного",
    "thumbnail_size": 512,
    "items_per_page": 20,
    "allowed_extensions": [".png", ".jpg", ".jpeg", ".webp", ".webm"],
    "auto_tag_enabled": true,
    "auto_tag_threshold": 0.3771
}
```

## Автоматическая генерация тегов

Приложение автоматически генерирует теги для изображений без метаданных используя **WD14 Tagger** от SmilingWolf.

### WD14 Tagger

Специализированная модель [SmilingWolf/wd-v1-4-swinv2-tagger-v2](https://huggingface.co/SmilingWolf/wd-v1-4-swinv2-tagger-v2) для аниме/хентай, обученная на Danbooru. Автоматически загружается с Hugging Face при первом использовании.

### Настройка в config.json:

```json
{
    "auto_tag_enabled": true,
    "auto_tag_threshold": 0.3771
}
```

- `auto_tag_enabled` - включить/выключить автоматическую генерацию тегов
- `auto_tag_threshold` - порог вероятности для включения тега (по умолчанию 0.3771 - оптимальный согласно README модели)

Модель будет автоматически загружена при первом использовании (может занять некоторое время).

## Как это работает

1. При создании метаданных проверяется наличие промпта в файле
2. Если промпт пустой или найдено < 3 тегов, запускается автоматическая генерация тегов через WD14 Tagger
3. Модель анализирует изображение и добавляет теги с вероятностью выше порога

## Решение проблем

**Ошибка pip-script.py:**
```bash
conda env remove -n neural-networks
conda env create -f ../environment.yml
```

**WD14 не работает:**
Убедитесь, что установлены зависимости: `onnxruntime-gpu>=1.17.0` (или `onnxruntime>=1.17.0` для CPU) и `huggingface_hub`. Обновите окружение: `conda env update -f ../environment.yml --prune`. При первой загрузке модели может потребоваться интернет-соединение для скачивания с Hugging Face.

**WD14 работает на CPU вместо GPU:**

**Проблема: отсутствует cuDNN 9.* для CUDA 12.***

1. **Скачайте cuDNN 9.* для CUDA 12.*:**
   - Перейдите на https://developer.nvidia.com/cudnn
   - Зарегистрируйтесь/войдите (бесплатно)
   - Скачайте cuDNN для CUDA 12.x (версия 9.x)

2. **Установите cuDNN:**
   - Распакуйте архив cuDNN
   - Скопируйте файлы в папку CUDA:
     - `bin\cudnn64_9.dll` → `C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6\bin\`
     - `include\cudnn*.h` → `C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6\include\`
     - `lib\x64\cudnn*.lib` → `C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6\lib\x64\`

3. **Проверьте PATH:**
   - Убедитесь, что `C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6\bin` в PATH

4. **Перезапустите приложение** - GPU должен заработать автоматически

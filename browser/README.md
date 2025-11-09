# Image Viewer

Веб-приложение для просмотра и управления коллекцией изображений с метаданными.

## Установка

1. Установите зависимости:
```bash
pip install -r requirements.txt
```

2. Настройте конфигурацию в `config.json`:
```json
{
    "image_folder": "путь/к/папке/с/изображениями",
    "favorites_folder": "путь/к/папке/избранного",
    "thumbnail_size": 512,
    "items_per_page": 20,
    "allowed_extensions": [".png", ".jpg", ".jpeg", ".webp", ".webm"],
    "auto_tags": []
}
```

## Запуск

### Windows
```bash
app.bat
```

### Linux/Mac
```bash
cd backend
python app.py
```

Приложение будет доступно по адресу: http://127.0.0.1:5000

## Переменные окружения

- `FLASK_HOST` - хост (по умолчанию: 0.0.0.0)
- `FLASK_PORT` - порт (по умолчанию: 5000)
- `FLASK_DEBUG` - режим отладки (true/false)
- `IMAGE_FOLDER` - переопределяет image_folder из config.json
- `FAVORITES_FOLDER` - переопределяет favorites_folder из config.json
- `THUMBNAIL_SIZE` - размер миниатюр (по умолчанию: 512)
- `ITEMS_PER_PAGE` - элементов на странице (по умолчанию: 20)


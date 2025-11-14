# neural-networks

Окружение conda для работы с нейронными сетями и машинным обучением. Включает:
- **PyTorch** с поддержкой CUDA для обучения моделей глубокого обучения
- **Классификация изображений** (cat_classifier, MNIST)
- **Веб-приложение** для просмотра и управления коллекцией изображений (browser)
- **Утилиты** для работы с метаданными, промптами и датасетами
- **Обработка изображений** (OpenCV, Pillow) и извлечение метаданных

## Установка, активация и деактивация

```bash
conda env create -f environment.yml
conda activate neural-networks
conda deactivate
```

### Просмотр информации

```bash
conda env list
conda list
```

### Добавление пакета в environment.yml

```bash
conda activate neural-networks
conda install package_name  # Предпочтительно, если пакет есть в conda
pip install package_name    # Если пакета нет в conda или нужна другая версия
```

### Экспорт окружения

```bash
conda env export > environment.yml
```

### Обновление

```bash
# Обновить окружение из environment.yml
conda env update -f environment.yml --prune

# Обновить все пакеты в текущем окружении
conda update --all

# Обновить конкретный пакет
conda update package_name
```

### Удаление

```bash
conda env remove -n neural-networks  # Удалить всё окружение целиком
conda remove package_name            # Удалить конкретный пакет из текущего окружения
```

# neural-networks
conda env create -f environment.yml

## Шпаргалка по командам Conda
### Управление средами
- **Создать среду**: `conda create --name <env_name> python=3.10`
- **Активировать среду**: `conda activate <env_name>`
- **Деактивировать среду**: `conda deactivate`
- **Удалить среду**: `conda remove --name <env_name> --all`
- **Список сред**: `conda env list`
### Работа с environment.yml
- **Создать среду**: `conda env create -f environment.yml`
- **Обновить среду**: `conda env update -f environment.yml --prune`
- **Экспорт среды**: `conda env export --no-builds > environment.yml`
### Управление пакетами
- **Установить пакет**: `conda install <package_name>`
- **Удалить пакет**: `conda remove <package_name>`
- **Обновить пакет**: `conda update <package_name>`
- **Установить из канала**: `conda install -c <channel_name> <package_name>`
- **Список пакетов**: `conda list`
- **Поиск пакетов**: `conda search <package_name>`
### Управление каналами
- **Добавить канал**: `conda config --add channels <channel_name>`
- **Удалить канал**: `conda config --remove channels <channel_name>`
- **Список каналов**: `conda config --show channels`
### Очистка и диагностика
- **Очистка кэша**: `conda clean --all`
- **Обновление Conda**: `conda update -n base -c defaults conda`
- **Информация о среде**: `conda info`

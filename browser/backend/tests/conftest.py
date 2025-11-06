"""
Конфигурация pytest и общие фикстуры.
"""
import os
import sys
import tempfile
import shutil
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Добавляем путь к модулям для импорта
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config, load_config


@pytest.fixture
def temp_dir():
    """Создает временную директорию для тестов."""
    temp_path = tempfile.mkdtemp()
    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def temp_image_folder(temp_dir):
    """Создает временную папку для изображений."""
    image_folder = os.path.join(temp_dir, "images")
    os.makedirs(image_folder, exist_ok=True)
    return image_folder


@pytest.fixture
def temp_metadata_folder(temp_image_folder):
    """Создает временную папку для метаданных."""
    metadata_folder = os.path.join(temp_image_folder, ".metadata")
    os.makedirs(metadata_folder, exist_ok=True)
    return metadata_folder


@pytest.fixture
def sample_config(temp_image_folder):
    """Создает тестовую конфигурацию."""
    config = Config({
        "image_folder": temp_image_folder,
        "favorites_folder": os.path.join(temp_image_folder, "favorites"),
        "thumbnail_size": 256,
        "items_per_page": 10,
        "allowed_extensions": [".png", ".jpg", ".jpeg", ".webp"],
        "auto_tags": ["test", "tag1", "tag2"]
    })
    config.IMAGE_FOLDER = os.path.abspath(config["image_folder"])
    config.FAVORITES_FOLDER = os.path.abspath(config["favorites_folder"])
    config.ALLOWED_EXTENSIONS = set(config["allowed_extensions"])
    config.THUMBNAIL_SIZE = int(config["thumbnail_size"])
    config.ITEMS_PER_PAGE = int(config["items_per_page"])
    config.TAGS = set(config.get("auto_tags", []))
    return config


@pytest.fixture
def sample_image_path(temp_image_folder):
    """Создает тестовое изображение."""
    from PIL import Image
    
    image_path = os.path.join(temp_image_folder, "test_image.png")
    img = Image.new('RGB', (100, 100), color='red')
    img.save(image_path, 'PNG')
    return image_path


@pytest.fixture(autouse=True)
def mock_config(temp_image_folder):
    """Автоматически мокает конфигурацию для всех тестов."""
    mock_config_obj = MagicMock()
    mock_config_obj.IMAGE_FOLDER = temp_image_folder
    mock_config_obj.FAVORITES_FOLDER = os.path.join(temp_image_folder, "favorites")
    mock_config_obj.THUMBNAIL_SIZE = 256
    mock_config_obj.ITEMS_PER_PAGE = 20
    mock_config_obj.ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
    mock_config_obj.TAGS = {"test", "tag1", "tag2"}
    
    # Патчим только те модули, которые действительно импортируют config
    patches = [
        patch("config.config", mock_config_obj),
        patch("paths.config", mock_config_obj),
        patch("image.config", mock_config_obj),
        patch("tag.config", mock_config_obj),
        patch("services.config", mock_config_obj),
        patch("routes.config", mock_config_obj)
    ]
    
    # Применяем все патчи
    for p in patches:
        p.start()
    
    yield mock_config_obj
    
    # Останавливаем все патчи
    for p in patches:
        p.stop()


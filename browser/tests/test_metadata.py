"""
Тесты для модуля metadata.py
"""
import os
import json
import pytest
from unittest.mock import patch, MagicMock, mock_open

from metadata import (
    extract_prompt_from_png,
    load_metadata,
    save_metadata
)
from exceptions import FileOperationError
from paths import get_metadata_path


class TestExtractPromptFromPng:
    """Тесты для extract_prompt_from_png."""
    
    def test_extract_prompt_from_png_no_metadata(self, temp_image_folder):
        """Тест извлечения промпта из PNG без метаданных."""
        from PIL import Image
        
        image_path = os.path.join(temp_image_folder, "test.png")
        img = Image.new('RGB', (100, 100), color='red')
        img.save(image_path, 'PNG')
        
        prompt = extract_prompt_from_png(image_path)
        assert prompt == "Метаданные не найдены"
    
    def test_extract_prompt_from_png_invalid_file(self, temp_image_folder):
        """Тест обработки невалидного файла."""
        invalid_path = os.path.join(temp_image_folder, "invalid.txt")
        with open(invalid_path, "w") as f:
            f.write("not a png")
        
        prompt = extract_prompt_from_png(invalid_path)
        assert prompt == "Метаданные не найдены"
    
    def test_extract_prompt_from_png_nonexistent_file(self, temp_image_folder):
        """Тест обработки несуществующего файла."""
        nonexistent_path = os.path.join(temp_image_folder, "nonexistent.png")
        prompt = extract_prompt_from_png(nonexistent_path)
        assert prompt == "Метаданные не найдены"


class TestLoadMetadata:
    """Тесты для load_metadata."""
    
    def test_load_metadata_new_file(self, temp_image_folder, sample_image_path, monkeypatch):
        """Тест загрузки метаданных для нового файла."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder))
        # Очищаем кэш
        load_metadata.cache_clear()
        
        import time
        mtime = os.path.getmtime(sample_image_path)
        metadata = load_metadata(sample_image_path, mtime)
        
        assert "prompt" in metadata
        assert "checked" in metadata
        assert "rating" in metadata
        assert "tags" in metadata
        assert metadata["checked"] is False
        assert metadata["rating"] == 0
    
    def test_load_metadata_existing_file(self, temp_image_folder, sample_image_path, monkeypatch):
        """Тест загрузки существующих метаданных."""
        import json
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder))
        
        # Создаем файл метаданных
        meta_path = get_metadata_path(sample_image_path)
        os.makedirs(os.path.dirname(meta_path), exist_ok=True)
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({
                "prompt": "test prompt",
                "checked": True,
                "rating": 5,
                "tags": ["tag1", "tag2"]
            }, f)
        
        # Очищаем кэш
        load_metadata.cache_clear()
        mtime = os.path.getmtime(sample_image_path)
        metadata = load_metadata(sample_image_path, mtime)
        
        assert metadata["prompt"] == "test prompt"
        assert metadata["checked"] is True
        assert metadata["rating"] == 5
        assert metadata["tags"] == ["tag1", "tag2"]
    
    def test_load_metadata_invalid_json(self, temp_image_folder, sample_image_path, monkeypatch):
        """Тест обработки невалидного JSON в метаданных."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder))
        
        # Создаем файл с невалидным JSON
        meta_path = get_metadata_path(sample_image_path)
        os.makedirs(os.path.dirname(meta_path), exist_ok=True)
        with open(meta_path, "w", encoding="utf-8") as f:
            f.write("invalid json")
        
        # Очищаем кэш
        load_metadata.cache_clear()
        mtime = os.path.getmtime(sample_image_path)
        metadata = load_metadata(sample_image_path, mtime)
        
        # Должны быть созданы дефолтные значения
        assert "prompt" in metadata
        assert "checked" in metadata
        assert "rating" in metadata
    
    def test_load_metadata_caching(self, temp_image_folder, sample_image_path, monkeypatch):
        """Тест кэширования метаданных."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder))
        
        # Очищаем кэш
        load_metadata.cache_clear()
        mtime = os.path.getmtime(sample_image_path)
        
        # Первый вызов
        metadata1 = load_metadata(sample_image_path, mtime)
        # Второй вызов (должен использовать кэш)
        metadata2 = load_metadata(sample_image_path, mtime)
        
        assert metadata1 == metadata2


class TestSaveMetadata:
    """Тесты для save_metadata."""
    
    def test_save_metadata(self, temp_image_folder, sample_image_path, monkeypatch):
        """Тест сохранения метаданных."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder))
        
        metadata = {
            "prompt": "test prompt",
            "checked": True,
            "rating": 5,
            "tags": ["tag1", "tag2"]
        }
        
        save_metadata(sample_image_path, metadata)
        
        # Проверяем, что файл создан
        meta_path = get_metadata_path(sample_image_path)
        assert os.path.exists(meta_path)
        
        # Проверяем содержимое
        with open(meta_path, "r", encoding="utf-8") as f:
            saved_metadata = json.load(f)
        
        assert saved_metadata == metadata
    
    def test_save_metadata_creates_directory(self, temp_image_folder, monkeypatch):
        """Тест создания директории при сохранении."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder))
        
        image_path = os.path.join(temp_image_folder, "subfolder", "test.png")
        os.makedirs(os.path.dirname(image_path), exist_ok=True)
        from PIL import Image
        Image.new('RGB', (10, 10)).save(image_path, 'PNG')
        
        metadata = {"test": "data"}
        save_metadata(image_path, metadata)
        
        meta_path = get_metadata_path(image_path)
        assert os.path.exists(os.path.dirname(meta_path))
        assert os.path.exists(meta_path)
    
    def test_save_metadata_io_error(self, temp_image_folder, sample_image_path, monkeypatch):
        """Тест обработки ошибки ввода-вывода."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder))
        
        # Мокаем открытие файла для вызова ошибки
        with patch("builtins.open", side_effect=IOError("Permission denied")):
            with pytest.raises(FileOperationError):
                save_metadata(sample_image_path, {"test": "data"})
    
    def test_save_metadata_unicode(self, temp_image_folder, sample_image_path, monkeypatch):
        """Тест сохранения метаданных с unicode символами."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder))
        
        metadata = {
            "prompt": "Тестовый промпт с русскими символами",
            "tags": ["тег1", "тег2"]
        }
        
        save_metadata(sample_image_path, metadata)
        
        meta_path = get_metadata_path(sample_image_path)
        with open(meta_path, "r", encoding="utf-8") as f:
            saved_metadata = json.load(f)
        
        assert saved_metadata["prompt"] == "Тестовый промпт с русскими символами"
        assert saved_metadata["tags"] == ["тег1", "тег2"]


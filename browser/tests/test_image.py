"""
Тесты для модуля image.py
"""
import os
import time
import pytest
from unittest.mock import patch, MagicMock, Mock

from image import (
    create_thumbnail,
    process_image,
    needs_processing,
    collect_images,
    sort_images,
    filter_images,
    _get_image_paths
)
from config import config


class TestCreateThumbnail:
    """Тесты для create_thumbnail."""
    
    def test_create_thumbnail(self, temp_image_folder, sample_image_path, monkeypatch):
        """Тест создания миниатюры."""
        monkeypatch.setattr("config.config", MagicMock(THUMBNAIL_SIZE=128, IMAGE_FOLDER=temp_image_folder))
        from paths import get_thumbnail_path
        
        thumb_path = get_thumbnail_path(sample_image_path)
        create_thumbnail(sample_image_path, thumb_path)
        
        assert os.path.exists(thumb_path)
        assert thumb_path.endswith(".webp")
        
        # Проверяем размер миниатюры
        from PIL import Image
        with Image.open(thumb_path) as thumb:
            assert max(thumb.size) <= 128
    
    def test_create_thumbnail_creates_directory(self, temp_image_folder, sample_image_path, monkeypatch):
        """Тест создания директории для миниатюры."""
        monkeypatch.setattr("config.config", MagicMock(THUMBNAIL_SIZE=128, IMAGE_FOLDER=temp_image_folder))
        from paths import get_thumbnail_path
        
        thumb_path = get_thumbnail_path(sample_image_path)
        thumb_dir = os.path.dirname(thumb_path)
        
        # Удаляем директорию если существует
        if os.path.exists(thumb_dir):
            import shutil
            shutil.rmtree(thumb_dir)
        
        create_thumbnail(sample_image_path, thumb_path)
        assert os.path.exists(thumb_dir)


class TestProcessImage:
    """Тесты для process_image."""
    
    def test_process_image(self, temp_image_folder, sample_image_path, monkeypatch):
        """Тест обработки изображения."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder, THUMBNAIL_SIZE=128))
        
        result = process_image(sample_image_path)
        
        assert "filename" in result
        assert "thumbnail" in result
        assert "metadata" in result
        assert isinstance(result["metadata"], dict)
    
    def test_process_image_creates_thumbnail(self, temp_image_folder, sample_image_path, monkeypatch):
        """Тест создания миниатюры при обработке."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder, THUMBNAIL_SIZE=128))
        from paths import get_thumbnail_path
        
        thumb_path = get_thumbnail_path(sample_image_path)
        # Удаляем миниатюру если существует
        if os.path.exists(thumb_path):
            os.remove(thumb_path)
        
        result = process_image(sample_image_path)
        assert os.path.exists(thumb_path)


class TestNeedsProcessing:
    """Тесты для needs_processing."""
    
    def test_needs_processing_no_images(self, temp_image_folder, monkeypatch):
        """Тест проверки необходимости обработки при отсутствии изображений."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder, ALLOWED_EXTENSIONS={".png"}))
        assert needs_processing(folder=temp_image_folder) is False
    
    def test_needs_processing_missing_thumbnail(self, temp_image_folder, sample_image_path, monkeypatch):
        """Тест проверки при отсутствии миниатюры."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder, ALLOWED_EXTENSIONS={".png"}))
        from paths import get_thumbnail_path
        
        thumb_path = get_thumbnail_path(sample_image_path)
        if os.path.exists(thumb_path):
            os.remove(thumb_path)
        
        assert needs_processing(folder=temp_image_folder) is True
    
    def test_needs_processing_missing_metadata(self, temp_image_folder, sample_image_path, monkeypatch):
        """Тест проверки при отсутствии метаданных."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder, ALLOWED_EXTENSIONS={".png"}))
        from paths import get_metadata_path
        
        meta_path = get_metadata_path(sample_image_path)
        if os.path.exists(meta_path):
            os.remove(meta_path)
        
        # Убеждаемся, что миниатюра существует
        from paths import get_thumbnail_path
        thumb_path = get_thumbnail_path(sample_image_path)
        if not os.path.exists(thumb_path):
            create_thumbnail(sample_image_path, thumb_path)
        
        assert needs_processing(folder=temp_image_folder) is True
    
    def test_needs_processing_all_exist(self, temp_image_folder, sample_image_path, monkeypatch):
        """Тест проверки когда все файлы существуют."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder, ALLOWED_EXTENSIONS={".png"}))
        
        # Создаем миниатюру и метаданные
        from paths import get_thumbnail_path, get_metadata_path
        thumb_path = get_thumbnail_path(sample_image_path)
        meta_path = get_metadata_path(sample_image_path)
        
        create_thumbnail(sample_image_path, thumb_path)
        import json
        os.makedirs(os.path.dirname(meta_path), exist_ok=True)
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({}, f)
        
        # Обновляем время модификации миниатюры
        time.sleep(0.1)
        os.utime(thumb_path, None)
        
        assert needs_processing(folder=temp_image_folder) is False


class TestSortImages:
    """Тесты для sort_images."""
    
    def test_sort_images_by_filename(self, temp_image_folder, monkeypatch):
        """Тест сортировки по имени файла."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder))
        images = [
            {"filename": "zebra.png", "metadata": {}},
            {"filename": "apple.png", "metadata": {}},
            {"filename": "banana.png", "metadata": {}}
        ]
        
        sorted_images = sort_images(images.copy(), "filename", "asc")
        assert sorted_images[0]["filename"] == "apple.png"
        assert sorted_images[1]["filename"] == "banana.png"
        assert sorted_images[2]["filename"] == "zebra.png"
    
    def test_sort_images_by_filename_desc(self, temp_image_folder, monkeypatch):
        """Тест сортировки по имени файла в обратном порядке."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder))
        images = [
            {"filename": "apple.png", "metadata": {}},
            {"filename": "zebra.png", "metadata": {}}
        ]
        
        sorted_images = sort_images(images.copy(), "filename", "desc")
        assert sorted_images[0]["filename"] == "zebra.png"
        assert sorted_images[1]["filename"] == "apple.png"
    
    def test_sort_images_by_rating(self, temp_image_folder, monkeypatch):
        """Тест сортировки по рейтингу."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder))
        images = [
            {"filename": "img1.png", "metadata": {"rating": 5}},
            {"filename": "img2.png", "metadata": {"rating": 1}},
            {"filename": "img3.png", "metadata": {"rating": 3}}
        ]
        
        sorted_images = sort_images(images.copy(), "rating", "asc")
        assert sorted_images[0]["metadata"]["rating"] == 1
        assert sorted_images[1]["metadata"]["rating"] == 3
        assert sorted_images[2]["metadata"]["rating"] == 5
    
    def test_sort_images_by_prompt(self, temp_image_folder, monkeypatch):
        """Тест сортировки по промпту."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder))
        images = [
            {"filename": "img1.png", "metadata": {"prompt": "zebra"}},
            {"filename": "img2.png", "metadata": {"prompt": "apple"}},
            {"filename": "img3.png", "metadata": {"prompt": "banana"}}
        ]
        
        sorted_images = sort_images(images.copy(), "prompt", "asc")
        assert sorted_images[0]["metadata"]["prompt"] == "apple"
        assert sorted_images[1]["metadata"]["prompt"] == "banana"
        assert sorted_images[2]["metadata"]["prompt"] == "zebra"


class TestFilterImages:
    """Тесты для filter_images."""
    
    def test_filter_images_no_search(self, temp_image_folder, monkeypatch):
        """Тест фильтрации без поиска."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder))
        images = [
            {"filename": "img1.png", "metadata": {"prompt": "test"}},
            {"filename": "img2.png", "metadata": {"prompt": "example"}}
        ]
        
        filtered = filter_images(images, "")
        assert len(filtered) == 2
    
    def test_filter_images_by_prompt(self, temp_image_folder, monkeypatch):
        """Тест фильтрации по промпту."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder))
        images = [
            {"filename": "img1.png", "metadata": {"prompt": "test prompt"}},
            {"filename": "img2.png", "metadata": {"prompt": "example prompt"}}
        ]
        
        filtered = filter_images(images, "test")
        assert len(filtered) == 1
        assert filtered[0]["filename"] == "img1.png"
    
    def test_filter_images_by_tags(self, temp_image_folder, monkeypatch):
        """Тест фильтрации по тегам."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder))
        images = [
            {"filename": "img1.png", "metadata": {"tags": ["tag1", "tag2"]}},
            {"filename": "img2.png", "metadata": {"tags": ["tag2", "tag3"]}},
            {"filename": "img3.png", "metadata": {"tags": ["tag1", "tag3"]}}
        ]
        
        filtered = filter_images(images, "tags:tag1")
        assert len(filtered) == 2
        assert all("tag1" in img["metadata"]["tags"] for img in filtered)
    
    def test_filter_images_by_multiple_tags(self, temp_image_folder, monkeypatch):
        """Тест фильтрации по нескольким тегам (AND логика)."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder))
        images = [
            {"filename": "img1.png", "metadata": {"tags": ["tag1", "tag2"]}},
            {"filename": "img2.png", "metadata": {"tags": ["tag2"]}},
            {"filename": "img3.png", "metadata": {"tags": ["tag1"]}}
        ]
        
        filtered = filter_images(images, "tags:tag1,tag2")
        assert len(filtered) == 1
        assert filtered[0]["filename"] == "img1.png"
    
    def test_filter_images_by_tags_or(self, temp_image_folder, monkeypatch):
        """Тест фильтрации по тегам с OR логикой (|)."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder))
        images = [
            {"filename": "img1.png", "metadata": {"tags": ["tag1"]}},
            {"filename": "img2.png", "metadata": {"tags": ["tag2"]}},
            {"filename": "img3.png", "metadata": {"tags": ["tag3"]}}
        ]
        
        filtered = filter_images(images, "tags:tag1|tag2")
        assert len(filtered) == 2
    
    def test_filter_images_empty_tags(self, temp_image_folder, monkeypatch):
        """Тест фильтрации изображений без тегов."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder))
        images = [
            {"filename": "img1.png", "metadata": {"tags": []}},
            {"filename": "img2.png", "metadata": {"tags": ["tag1"]}},
            {"filename": "img3.png", "metadata": {}}
        ]
        
        filtered = filter_images(images, "tags:")
        assert len(filtered) == 2  # img1 и img3 без тегов


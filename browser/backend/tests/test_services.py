"""
Тесты для модуля services.py
"""
import os
import json
import pytest
from unittest.mock import patch, MagicMock, Mock

from services import ImageService, MetadataService, FavoritesService
from exceptions import FileOperationError, InvalidRequestError
from config import config


class TestImageService:
    """Тесты для ImageService."""
    
    def test_get_images(self, temp_image_folder, sample_image_path, monkeypatch):
        """Тест получения изображений."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder, ALLOWED_EXTENSIONS={".png"}))
        
        with patch("services.collect_images") as mock_collect, \
             patch("services.filter_images") as mock_filter, \
             patch("services.sort_images") as mock_sort:
            
            mock_collect.return_value = [
                {"filename": "img1.png", "metadata": {}},
                {"filename": "img2.png", "metadata": {}},
                {"filename": "img3.png", "metadata": {}}
            ]
            mock_filter.return_value = [
                {"filename": "img1.png", "metadata": {}},
                {"filename": "img2.png", "metadata": {}},
                {"filename": "img3.png", "metadata": {}}
            ]
            mock_sort.return_value = [
                {"filename": "img1.png", "metadata": {}},
                {"filename": "img2.png", "metadata": {}},
                {"filename": "img3.png", "metadata": {}}
            ]
            
            result = ImageService.get_images(
                folder_path=temp_image_folder,
                search="",
                sort_by="date",
                order="asc",
                limit=2,
                offset=0
            )
            
            assert len(result) == 2
            mock_collect.assert_called_once()
            mock_filter.assert_called_once()
            mock_sort.assert_called_once()
    
    def test_delete_image(self, temp_image_folder, sample_image_path, monkeypatch):
        """Тест удаления изображения."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder))
        from paths import get_thumbnail_path, get_metadata_path
        
        # Создаем миниатюру и метаданные
        thumb_path = get_thumbnail_path(sample_image_path)
        meta_path = get_metadata_path(sample_image_path)
        
        os.makedirs(os.path.dirname(thumb_path), exist_ok=True)
        with open(thumb_path, "w") as f:
            f.write("dummy")
        with open(meta_path, "w") as f:
            json.dump({}, f)
        
        rel_path = os.path.relpath(sample_image_path, temp_image_folder)
        ImageService.delete_image(rel_path)
        
        assert not os.path.exists(sample_image_path)
        assert not os.path.exists(thumb_path)
        assert not os.path.exists(meta_path)
    
    def test_delete_image_nonexistent(self, temp_image_folder, monkeypatch):
        """Тест удаления несуществующего изображения."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder))
        
        # Не должно вызывать исключение
        ImageService.delete_image("nonexistent.png")


class TestMetadataService:
    """Тесты для MetadataService."""
    
    def test_update_metadata(self, temp_image_folder, sample_image_path, monkeypatch):
        """Тест обновления метаданных."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder))
        
        rel_path = os.path.relpath(sample_image_path, temp_image_folder)
        updates = {
            "checked": True,
            "rating": 5,
            "tags": ["tag1", "tag2"]
        }
        
        MetadataService.update_metadata([rel_path], updates)
        
        from paths import get_metadata_path
        meta_path = get_metadata_path(sample_image_path)
        assert os.path.exists(meta_path)
        
        with open(meta_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        
        assert metadata["checked"] is True
        assert metadata["rating"] == 5
        assert metadata["tags"] == ["tag1", "tag2"]
    
    def test_update_metadata_partial(self, temp_image_folder, sample_image_path, monkeypatch):
        """Тест частичного обновления метаданных."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder))
        
        # Создаем существующие метаданные
        from paths import get_metadata_path
        meta_path = get_metadata_path(sample_image_path)
        os.makedirs(os.path.dirname(meta_path), exist_ok=True)
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({"checked": False, "rating": 0, "tags": []}, f)
        
        rel_path = os.path.relpath(sample_image_path, temp_image_folder)
        MetadataService.update_metadata([rel_path], {"rating": 3})
        
        with open(meta_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        
        assert metadata["rating"] == 3
        assert metadata["checked"] is False  # Не должно измениться
    
    def test_uncheck_all(self, temp_image_folder, sample_image_path, monkeypatch):
        """Тест снятия всех отметок."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder, ALLOWED_EXTENSIONS={".png"}))
        
        # Создаем метаданные с checked=True
        from paths import get_metadata_path
        meta_path = get_metadata_path(sample_image_path)
        os.makedirs(os.path.dirname(meta_path), exist_ok=True)
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({"checked": True}, f)
        
        with patch("services.collect_images") as mock_collect, \
             patch("services.filter_images") as mock_filter:
            
            mock_collect.return_value = [
                {"filename": os.path.relpath(sample_image_path, temp_image_folder), "metadata": {}}
            ]
            mock_filter.return_value = [
                {"filename": os.path.relpath(sample_image_path, temp_image_folder), "metadata": {}}
            ]
            
            count = MetadataService.uncheck_all(folder_path=temp_image_folder, search="")
            assert count == 1
        
        with open(meta_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        assert metadata["checked"] is False
    
    def test_delete_metadata(self, temp_image_folder, sample_image_path, monkeypatch):
        """Тест удаления метаданных."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder, ALLOWED_EXTENSIONS={".png"}))
        
        # Создаем метаданные
        from paths import get_metadata_path
        meta_path = get_metadata_path(sample_image_path)
        os.makedirs(os.path.dirname(meta_path), exist_ok=True)
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({"test": "data"}, f)
        
        with patch("services.collect_images") as mock_collect, \
             patch("services.filter_images") as mock_filter:
            
            mock_collect.return_value = [
                {"filename": os.path.relpath(sample_image_path, temp_image_folder), "metadata": {}}
            ]
            mock_filter.return_value = [
                {"filename": os.path.relpath(sample_image_path, temp_image_folder), "metadata": {}}
            ]
            
            count = MetadataService.delete_metadata(folder_path=temp_image_folder, search="")
            assert count == 1
        
        assert not os.path.exists(meta_path)


class TestFavoritesService:
    """Тесты для FavoritesService."""
    
    def test_copy_to_favorites(self, temp_image_folder, sample_image_path, monkeypatch):
        """Тест копирования в избранное."""
        favorites_folder = os.path.join(temp_image_folder, "favorites")
        monkeypatch.setattr("config.config", MagicMock(
            IMAGE_FOLDER=temp_image_folder,
            FAVORITES_FOLDER=favorites_folder
        ))
        
        rel_path = os.path.relpath(sample_image_path, temp_image_folder)
        FavoritesService.copy_to_favorites(rel_path)
        
        # Проверяем, что файл скопирован
        copied_path = os.path.join(favorites_folder, os.path.basename(sample_image_path))
        assert os.path.exists(copied_path)
        
        # Проверяем, что добавлен тег "favorite"
        from paths import get_metadata_path
        meta_path = get_metadata_path(copied_path)
        if os.path.exists(meta_path):
            with open(meta_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
            assert "favorite" in metadata.get("tags", [])
    
    def test_copy_to_favorites_no_folder(self, temp_image_folder, sample_image_path, monkeypatch):
        """Тест копирования без указанной папки избранного."""
        # Патчим config в services модуле
        with patch("services.config") as mock_config:
            mock_config.IMAGE_FOLDER = temp_image_folder
            mock_config.FAVORITES_FOLDER = ""
            
            rel_path = os.path.relpath(sample_image_path, temp_image_folder)
            with pytest.raises(InvalidRequestError, match="не указана папка избранного"):
                FavoritesService.copy_to_favorites(rel_path)
    
    def test_copy_to_favorites_same_path(self, temp_image_folder, sample_image_path, monkeypatch):
        """Тест копирования в тот же путь."""
        # Патчим config в services модуле
        with patch("services.config") as mock_config:
            mock_config.IMAGE_FOLDER = temp_image_folder
            mock_config.FAVORITES_FOLDER = temp_image_folder
            
            rel_path = os.path.relpath(sample_image_path, temp_image_folder)
            with pytest.raises(InvalidRequestError, match="Источник и назначение совпадают"):
                FavoritesService.copy_to_favorites(rel_path)
    
    def test_copy_to_favorites_with_metadata(self, temp_image_folder, sample_image_path, monkeypatch):
        """Тест копирования с существующими метаданными."""
        favorites_folder = os.path.join(temp_image_folder, "favorites")
        monkeypatch.setattr("config.config", MagicMock(
            IMAGE_FOLDER=temp_image_folder,
            FAVORITES_FOLDER=favorites_folder
        ))
        
        # Создаем метаданные для исходного файла
        from paths import get_metadata_path
        src_meta_path = get_metadata_path(sample_image_path)
        os.makedirs(os.path.dirname(src_meta_path), exist_ok=True)
        with open(src_meta_path, "w", encoding="utf-8") as f:
            json.dump({"tags": ["tag1", "tag2"]}, f)
        
        rel_path = os.path.relpath(sample_image_path, temp_image_folder)
        FavoritesService.copy_to_favorites(rel_path)
        
        # Проверяем метаданные скопированного файла
        copied_path = os.path.join(favorites_folder, os.path.basename(sample_image_path))
        dst_meta_path = get_metadata_path(copied_path)
        
        if os.path.exists(dst_meta_path):
            with open(dst_meta_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
            assert "favorite" in metadata.get("tags", [])
            assert "tag1" in metadata.get("tags", [])
            assert "tag2" in metadata.get("tags", [])


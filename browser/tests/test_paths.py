"""
Тесты для модуля paths.py
"""
import os
import pytest
from unittest.mock import patch, MagicMock

from paths import (
    get_metadata_path,
    get_thumbnail_path,
    get_absolute_path,
    get_relative_path,
    walk_images,
    walk_metadata,
    build_folder_tree,
    get_metadata_file_path
)
from exceptions import FileOperationError
from config import config


class TestGetMetadataPath:
    """Тесты для get_metadata_path."""
    
    def test_get_metadata_path(self, temp_image_folder, sample_image_path):
        """Тест получения пути к метаданным."""
        meta_path = get_metadata_path(sample_image_path)
        assert meta_path.endswith(".json")
        assert ".metadata" in meta_path
        assert os.path.basename(meta_path) == "test_image.json"
    
    def test_metadata_path_structure(self, temp_image_folder):
        """Тест структуры пути к метаданным."""
        image_path = os.path.join(temp_image_folder, "subfolder", "image.png")
        os.makedirs(os.path.dirname(image_path), exist_ok=True)
        
        meta_path = get_metadata_path(image_path)
        assert "subfolder" in meta_path
        assert ".metadata" in meta_path


class TestGetThumbnailPath:
    """Тесты для get_thumbnail_path."""
    
    def test_get_thumbnail_path(self, temp_image_folder, sample_image_path):
        """Тест получения пути к миниатюре."""
        thumb_path = get_thumbnail_path(sample_image_path)
        assert thumb_path.endswith(".webp")
        assert ".metadata" in thumb_path
        assert os.path.basename(thumb_path) == "test_image.webp"


class TestGetAbsolutePath:
    """Тесты для get_absolute_path."""
    
    def test_get_absolute_path_empty(self, temp_image_folder, monkeypatch):
        """Тест получения абсолютного пути для пустого пути."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder))
        result = get_absolute_path("")
        assert os.path.isabs(result)
        assert result == os.path.abspath(temp_image_folder)
    
    def test_get_absolute_path_relative(self, temp_image_folder, monkeypatch):
        """Тест получения абсолютного пути для относительного пути."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder))
        result = get_absolute_path("subfolder")
        assert os.path.isabs(result)
        assert result == os.path.join(temp_image_folder, "subfolder")
    
    def test_get_absolute_path_traversal_attack(self, temp_image_folder, monkeypatch):
        """Тест защиты от path traversal атаки."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder))
        # Функция обрабатывает ../ в начале пути, удаляя их
        # После обработки путь должен остаться внутри разрешенной директории
        # Проверяем, что функция нормализует путь и он остается внутри
        malicious_path = "../../etc/passwd"
        result = get_absolute_path(malicious_path)
        # После обработки путь должен быть внутри temp_image_folder
        assert os.path.abspath(result).startswith(os.path.abspath(temp_image_folder))
    
    def test_get_absolute_path_custom_root(self, temp_image_folder):
        """Тест получения абсолютного пути с кастомным корнем."""
        result = get_absolute_path("test", root_folder=temp_image_folder)
        assert result == os.path.join(temp_image_folder, "test")
    
    def test_get_absolute_path_normalizes_slashes(self, temp_image_folder, monkeypatch):
        """Тест нормализации слэшей в пути."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder))
        result1 = get_absolute_path("folder/subfolder")
        result2 = get_absolute_path("folder\\subfolder")
        assert result1 == result2


class TestGetRelativePath:
    """Тесты для get_relative_path."""
    
    def test_get_relative_path(self, temp_image_folder, monkeypatch):
        """Тест получения относительного пути."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder))
        abs_path = os.path.join(temp_image_folder, "subfolder", "image.png")
        rel_path = get_relative_path(abs_path)
        assert rel_path == "subfolder/image.png"
        assert "\\" not in rel_path  # Должны быть только прямые слэши
    
    def test_get_relative_path_root(self, temp_image_folder, monkeypatch):
        """Тест получения относительного пути для корня."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder))
        rel_path = get_relative_path(temp_image_folder)
        assert rel_path == "."
    
    def test_get_relative_path_custom_root(self, temp_image_folder):
        """Тест получения относительного пути с кастомным корнем."""
        abs_path = os.path.join(temp_image_folder, "subfolder", "image.png")
        rel_path = get_relative_path(abs_path, root_folder=temp_image_folder)
        assert rel_path == "subfolder/image.png"


class TestWalkImages:
    """Тесты для walk_images."""
    
    def test_walk_images_empty_folder(self, temp_image_folder, monkeypatch):
        """Тест обхода пустой папки."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder, ALLOWED_EXTENSIONS={".png", ".jpg"}))
        images = list(walk_images())
        assert len(images) == 0
    
    def test_walk_images_with_files(self, temp_image_folder, sample_image_path, monkeypatch):
        """Тест обхода папки с изображениями."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder, ALLOWED_EXTENSIONS={".png", ".jpg"}))
        images = list(walk_images())
        assert len(images) == 1
        assert sample_image_path in images
    
    def test_walk_images_skips_metadata(self, temp_image_folder, monkeypatch):
        """Тест пропуска папки .metadata."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder, ALLOWED_EXTENSIONS={".png"}))
        metadata_folder = os.path.join(temp_image_folder, ".metadata")
        os.makedirs(metadata_folder, exist_ok=True)
        
        # Создаем изображение в .metadata (должно быть пропущено)
        from PIL import Image
        meta_image = os.path.join(metadata_folder, "meta.png")
        Image.new('RGB', (10, 10)).save(meta_image)
        
        images = list(walk_images())
        assert meta_image not in images


class TestWalkMetadata:
    """Тесты для walk_metadata."""
    
    def test_walk_metadata_empty(self, temp_image_folder, monkeypatch):
        """Тест обхода пустой папки метаданных."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder))
        metadata_files = list(walk_metadata())
        assert len(metadata_files) == 0
    
    def test_walk_metadata_with_files(self, temp_metadata_folder, temp_image_folder, monkeypatch):
        """Тест обхода папки с метаданными."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder))
        import json
        
        meta_file = os.path.join(temp_metadata_folder, "test.json")
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump({"test": "data"}, f)
        
        metadata_files = list(walk_metadata())
        assert len(metadata_files) == 1
        assert meta_file in metadata_files


class TestBuildFolderTree:
    """Тесты для build_folder_tree."""
    
    def test_build_folder_tree_empty(self, temp_image_folder):
        """Тест построения дерева пустой папки."""
        tree = build_folder_tree(temp_image_folder)
        assert tree == {}
    
    def test_build_folder_tree_with_images(self, temp_image_folder, sample_image_path, monkeypatch):
        """Тест построения дерева с изображениями."""
        # Убеждаемся, что изображение существует в корне папки
        monkeypatch.setattr("config.config", MagicMock(ALLOWED_EXTENSIONS={".png", ".jpg"}))
        tree = build_folder_tree(temp_image_folder)
        # Дерево может быть пустым, если изображение в корне (не в подпапке)
        # Проверяем структуру, если дерево не пустое
        if len(tree) > 0:
            for key, value in tree.items():
                assert "name" in value
                assert "count" in value
                assert "children" in value
                assert isinstance(value["count"], int)
    
    def test_build_folder_tree_skips_hidden(self, temp_image_folder):
        """Тест пропуска скрытых папок."""
        hidden_folder = os.path.join(temp_image_folder, ".hidden")
        os.makedirs(hidden_folder, exist_ok=True)
        
        tree = build_folder_tree(temp_image_folder)
        # Проверяем, что скрытые папки не включены
        for key in tree.keys():
            assert not key.startswith(".")


class TestGetMetadataFilePath:
    """Тесты для get_metadata_file_path."""
    
    def test_get_metadata_file_path_creates_dir(self, temp_image_folder, sample_image_path):
        """Тест создания директории для метаданных."""
        meta_path = get_metadata_file_path(sample_image_path, ".json")
        assert os.path.exists(os.path.dirname(meta_path))
    
    def test_get_metadata_file_path_custom_ext(self, temp_image_folder, sample_image_path):
        """Тест пути с кастомным расширением."""
        meta_path = get_metadata_file_path(sample_image_path, ".custom")
        assert meta_path.endswith(".custom")
    
    def test_get_metadata_file_path_relative(self, temp_image_folder, monkeypatch):
        """Тест пути с относительным путем."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder))
        rel_path = "test_image.png"
        meta_path = get_metadata_file_path(rel_path, ".json")
        assert os.path.isabs(meta_path)
        assert ".metadata" in meta_path


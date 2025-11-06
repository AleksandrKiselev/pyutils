"""
Тесты для модуля tag.py
"""
import os
import pytest
from unittest.mock import patch, MagicMock

from tag import (
    normalize_text,
    get_image_tags,
    extract_seed,
    auto_add_tags_from_prompt,
    get_all_tags_cached
)
from config import config


class TestNormalizeText:
    """Тесты для normalize_text."""
    
    def test_normalize_text_lowercase(self):
        """Тест приведения к нижнему регистру."""
        assert normalize_text("TEST") == "test"
    
    def test_normalize_text_strip(self):
        """Тест обрезки пробелов."""
        assert normalize_text("  test  ") == "test"
        assert normalize_text('"test"') == "test"
        assert normalize_text("'test'") == "test"
    
    def test_normalize_text_replace_dashes(self):
        """Тест замены дефисов и подчеркиваний."""
        assert normalize_text("test-case") == "test case"
        assert normalize_text("test_case") == "test case"
    
    def test_normalize_text_remove_punctuation(self):
        """Тест удаления пунктуации."""
        # Функция удаляет пунктуацию, но сохраняет пробелы
        assert normalize_text("test, case.") == "test case"
        # Функция удаляет скобки, но не сохраняет пробел между словами без пробела
        assert normalize_text("test(case)") == "testcase"
        # Проверяем, что запятая удаляется
        assert normalize_text("test,case") == "testcase"
        # Проверяем с пробелами
        assert normalize_text("test (case)") == "test case"
    
    def test_normalize_text_multiple_spaces(self):
        """Тест нормализации множественных пробелов."""
        assert normalize_text("test    case") == "test case"
    
    def test_normalize_text_unicode(self):
        """Тест нормализации unicode."""
        assert normalize_text("test'case") == "test'case"
        assert normalize_text('test"case') == 'test"case'


class TestGetImageTags:
    """Тесты для get_image_tags."""
    
    def test_get_image_tags_landscape(self, temp_image_folder):
        """Тест получения тегов для горизонтального изображения."""
        from PIL import Image
        
        image_path = os.path.join(temp_image_folder, "landscape.png")
        img = Image.new('RGB', (200, 100), color='blue')
        img.save(image_path, 'PNG')
        
        tags = get_image_tags(image_path)
        assert "landscape" in tags
        assert "200x100" in tags
    
    def test_get_image_tags_portrait(self, temp_image_folder):
        """Тест получения тегов для вертикального изображения."""
        from PIL import Image
        
        image_path = os.path.join(temp_image_folder, "portrait.png")
        img = Image.new('RGB', (100, 200), color='green')
        img.save(image_path, 'PNG')
        
        tags = get_image_tags(image_path)
        assert "portrait" in tags
        assert "100x200" in tags
    
    def test_get_image_tags_invalid_file(self, temp_image_folder):
        """Тест обработки невалидного файла."""
        invalid_path = os.path.join(temp_image_folder, "invalid.txt")
        with open(invalid_path, "w") as f:
            f.write("not an image")
        
        tags = get_image_tags(invalid_path)
        assert tags == set()


class TestExtractSeed:
    """Тесты для extract_seed."""
    
    def test_extract_seed(self, temp_image_folder):
        """Тест извлечения seed из имени файла."""
        image_path = os.path.join(temp_image_folder, "12345.png")
        seed = extract_seed(image_path)
        assert seed == "12345"
    
    def test_extract_seed_with_path(self, temp_image_folder):
        """Тест извлечения seed из полного пути."""
        image_path = os.path.join(temp_image_folder, "subfolder", "67890.jpg")
        os.makedirs(os.path.dirname(image_path), exist_ok=True)
        seed = extract_seed(image_path)
        assert seed == "67890"


class TestAutoAddTagsFromPrompt:
    """Тесты для auto_add_tags_from_prompt."""
    
    def test_auto_add_tags_no_prompt(self, temp_image_folder, sample_image_path, monkeypatch):
        """Тест добавления тегов без промпта."""
        monkeypatch.setattr("config.config", MagicMock(AUTO_TAGS={"test", "tag1"}))
        metadata = {}
        auto_add_tags_from_prompt(sample_image_path, metadata)
        
        assert "tags" in metadata
        assert len(metadata["tags"]) > 0
        # Должны быть добавлены базовые теги (orientation, resolution, seed)
    
    def test_auto_add_tags_with_matching_prompt(self, temp_image_folder, sample_image_path, monkeypatch):
        """Тест добавления тегов с совпадающим промптом."""
        monkeypatch.setattr("config.config", MagicMock(AUTO_TAGS={"solo", "test"}))
        metadata = {"prompt": "A beautiful solo character"}
        auto_add_tags_from_prompt(sample_image_path, metadata)
        
        assert "tags" in metadata
        tags = metadata["tags"]
        # Проверяем, что теги отсортированы
        assert tags == sorted(tags)
    
    def test_auto_add_tags_preserves_existing(self, temp_image_folder, sample_image_path, monkeypatch):
        """Тест сохранения существующих тегов."""
        monkeypatch.setattr("config.config", MagicMock(AUTO_TAGS={"solo"}))
        metadata = {"prompt": "solo character", "tags": ["existing_tag"]}
        auto_add_tags_from_prompt(sample_image_path, metadata)
        
        assert "existing_tag" in metadata["tags"]
    
    def test_auto_add_tags_similarity_matching(self, temp_image_folder, sample_image_path, monkeypatch):
        """Тест добавления тегов по похожести."""
        monkeypatch.setattr("config.config", MagicMock(AUTO_TAGS={"solo"}))
        metadata = {"prompt": "sol character"}  # Похоже на "solo"
        auto_add_tags_from_prompt(sample_image_path, metadata, threshold=0.8)
        
        assert "tags" in metadata


class TestGetAllTagsCached:
    """Тесты для get_all_tags_cached."""
    
    def test_get_all_tags_cached_empty(self, temp_metadata_folder, temp_image_folder, monkeypatch):
        """Тест получения тегов из пустой папки."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder))
        # Очищаем кэш
        get_all_tags_cached.cache_clear()
        tags = get_all_tags_cached()
        assert tags == []
    
    def test_get_all_tags_cached_with_metadata(self, temp_metadata_folder, temp_image_folder, monkeypatch):
        """Тест получения тегов из метаданных."""
        import json
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder))
        
        # Создаем файл метаданных
        meta_file = os.path.join(temp_metadata_folder, "test.json")
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump({"tags": ["tag1", "tag2", "tag3"]}, f)
        
        # Очищаем кэш
        get_all_tags_cached.cache_clear()
        tags = get_all_tags_cached()
        
        assert "tag1" in tags
        assert "tag2" in tags
        assert "tag3" in tags
        assert tags == sorted(tags)  # Теги должны быть отсортированы
    
    def test_get_all_tags_cached_deduplication(self, temp_metadata_folder, temp_image_folder, monkeypatch):
        """Тест дедупликации тегов."""
        import json
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder))
        
        # Создаем несколько файлов с одинаковыми тегами
        for i in range(3):
            meta_file = os.path.join(temp_metadata_folder, f"test{i}.json")
            with open(meta_file, "w", encoding="utf-8") as f:
                json.dump({"tags": ["tag1", "tag2"]}, f)
        
        # Очищаем кэш
        get_all_tags_cached.cache_clear()
        tags = get_all_tags_cached()
        
        # Теги не должны дублироваться
        assert tags.count("tag1") == 1
        assert tags.count("tag2") == 1
    
    def test_get_all_tags_cached_invalid_json(self, temp_metadata_folder, temp_image_folder, monkeypatch):
        """Тест обработки невалидного JSON."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder))
        
        # Создаем файл с невалидным JSON
        meta_file = os.path.join(temp_metadata_folder, "invalid.json")
        with open(meta_file, "w", encoding="utf-8") as f:
            f.write("invalid json content")
        
        # Очищаем кэш
        get_all_tags_cached.cache_clear()
        # Функция не должна падать
        tags = get_all_tags_cached()
        assert isinstance(tags, list)


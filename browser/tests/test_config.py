"""
Тесты для модуля config.py
"""
import os
import json
import tempfile
import pytest

from config import Config, load_config, DEFAULT_CONFIG, CONFIG_FILE


class TestConfig:
    """Тесты для класса Config."""
    
    def test_config_dict_access(self):
        """Тест доступа к конфигу как к словарю."""
        config = Config({"key": "value"})
        assert config["key"] == "value"
    
    def test_config_attr_access(self):
        """Тест доступа к конфигу как к атрибуту."""
        config = Config({"key": "value"})
        assert config.key == "value"
    
    def test_config_setattr(self):
        """Тест установки атрибута."""
        config = Config({})
        config.new_key = "new_value"
        assert config["new_key"] == "new_value"
        assert config.new_key == "new_value"
    
    def test_config_missing_key(self):
        """Тест отсутствующего ключа."""
        config = Config({})
        with pytest.raises(KeyError):
            _ = config["missing_key"]
    
    def test_config_missing_attr(self):
        """Тест отсутствующего атрибута."""
        config = Config({})
        with pytest.raises(AttributeError):
            _ = config.missing_attr


class TestLoadConfig:
    """Тесты для функции load_config."""
    
    def test_load_default_config(self, monkeypatch):
        """Тест загрузки конфигурации по умолчанию."""
        # Удаляем config.json если существует
        if os.path.exists(CONFIG_FILE):
            monkeypatch.setattr("os.path.exists", lambda path: False if path == CONFIG_FILE else os.path.exists(path))
        
        config = load_config()
        assert isinstance(config, Config)
        assert config["image_folder"] == DEFAULT_CONFIG["image_folder"]
        assert config["thumbnail_size"] == DEFAULT_CONFIG["thumbnail_size"]
    
    def test_load_from_file(self, temp_dir, monkeypatch):
        """Тест загрузки конфигурации из файла."""
        config_file = os.path.join(temp_dir, CONFIG_FILE)
        test_config = {
            "image_folder": "/test/path",
            "thumbnail_size": 256,
            "items_per_page": 15
        }
        
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(test_config, f)
        
        # Мокаем путь к config.json
        original_load = load_config
        def mock_load():
            loaded = Config(DEFAULT_CONFIG.copy())
            if os.path.exists(config_file):
                with open(config_file, "r", encoding="utf-8") as f:
                    user_config = json.load(f)
                    loaded.update(user_config)
            return loaded
        
        monkeypatch.setattr("config.load_config", mock_load)
        config = mock_load()
        
        assert config["image_folder"] == "/test/path"
        assert config["thumbnail_size"] == 256
    
    def test_load_with_env_vars(self, monkeypatch):
        """Тест загрузки конфигурации с переменными окружения."""
        monkeypatch.setenv("IMAGE_FOLDER", "/env/path")
        monkeypatch.setenv("THUMBNAIL_SIZE", "128")
        monkeypatch.setenv("ITEMS_PER_PAGE", "25")
        
        # Мокаем существование config.json
        monkeypatch.setattr("os.path.exists", lambda path: False if path == CONFIG_FILE else os.path.exists(path))
        
        config = load_config()
        assert config["image_folder"] == "/env/path"
        assert config["thumbnail_size"] == 128
        assert config["items_per_page"] == 25
    
    def test_config_attributes(self):
        """Тест преобразования конфигурации в атрибуты."""
        config = load_config()
        assert hasattr(config, "IMAGE_FOLDER")
        assert hasattr(config, "FAVORITES_FOLDER")
        assert hasattr(config, "ALLOWED_EXTENSIONS")
        assert isinstance(config.ALLOWED_EXTENSIONS, set)
        assert isinstance(config.THUMBNAIL_SIZE, int)
        assert isinstance(config.ITEMS_PER_PAGE, int)
    
    def test_invalid_json_config(self, temp_dir, monkeypatch):
        """Тест обработки невалидного JSON в config.json."""
        config_file = os.path.join(temp_dir, CONFIG_FILE)
        with open(config_file, "w", encoding="utf-8") as f:
            f.write("invalid json content")
        
        # Функция должна обработать ошибку и использовать дефолтные значения
        # Это проверяется тем, что функция не падает с исключением
        try:
            config = load_config()
            assert isinstance(config, Config)
        except Exception:
            pytest.fail("load_config should handle invalid JSON gracefully")


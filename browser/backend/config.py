"""
Управление конфигурацией для приложения просмотра изображений.
"""
import json
import os
from typing import Dict, Any


CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
DEFAULT_CONFIG: Dict[str, Any] = {
    "image_folder": "static/images",
    "favorites_folder": "static/images/favorites",
    "thumbnail_size": 512,
    "items_per_page": 20,
    "allowed_extensions": [".png", ".jpg", ".jpeg", ".webp", ".webm"]
}


class Config(dict):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError:
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
    
    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


def load_config() -> Config:
    loaded_config = Config(DEFAULT_CONFIG.copy())
    
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                user_config = json.load(f)
                loaded_config.update(user_config)
        except Exception as e:
            print(f"Предупреждение: Не удалось загрузить config.json: {e}")
    
    loaded_config["image_folder"] = os.getenv("IMAGE_FOLDER", loaded_config["image_folder"])
    loaded_config["favorites_folder"] = os.getenv("FAVORITES_FOLDER", loaded_config["favorites_folder"])
    loaded_config["thumbnail_size"] = int(os.getenv("THUMBNAIL_SIZE", loaded_config["thumbnail_size"]))
    loaded_config["items_per_page"] = int(os.getenv("ITEMS_PER_PAGE", loaded_config["items_per_page"]))
    
    loaded_config.IMAGE_FOLDER = os.path.abspath(loaded_config["image_folder"])
    loaded_config.FAVORITES_FOLDER = os.path.abspath(loaded_config["favorites_folder"])
    loaded_config.ALLOWED_EXTENSIONS = set(loaded_config["allowed_extensions"])
    loaded_config.THUMBNAIL_SIZE = int(loaded_config["thumbnail_size"])
    loaded_config.ITEMS_PER_PAGE = int(loaded_config["items_per_page"])
    loaded_config.AUTO_TAGS = set(loaded_config.get("auto_tags", []))
    
    return loaded_config


config = load_config()

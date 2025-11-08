import json
import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
DEFAULT_CONFIG: Dict[str, Any] = {
    "image_folder": "static/images",
    "favorites_folder": "static/images/favorites",
    "thumbnail_size": 512,
    "items_per_page": 20,
    "allowed_extensions": [".png", ".jpg", ".jpeg", ".webp", ".webm"]
}

_config: Optional["Config"] = None


class Config(dict):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError:
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
    
    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


def load_config() -> Config:
    config = Config(DEFAULT_CONFIG.copy())
    
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config.update(json.load(f))
        except Exception as e:
            logger.warning(f"Не удалось загрузить config.json: {e}")
    
    config["image_folder"] = os.getenv("IMAGE_FOLDER", config["image_folder"])
    config["favorites_folder"] = os.getenv("FAVORITES_FOLDER", config["favorites_folder"])
    config["thumbnail_size"] = int(os.getenv("THUMBNAIL_SIZE", config["thumbnail_size"]))
    config["items_per_page"] = int(os.getenv("ITEMS_PER_PAGE", config["items_per_page"]))
    
    config.IMAGE_FOLDER = os.path.abspath(config["image_folder"])
    config.FAVORITES_FOLDER = os.path.abspath(config["favorites_folder"])
    config.ALLOWED_EXTENSIONS = set(config["allowed_extensions"])
    config.THUMBNAIL_SIZE = int(config["thumbnail_size"])
    config.ITEMS_PER_PAGE = int(config["items_per_page"])
    config.AUTO_TAGS = set(config.get("auto_tags", []))
    
    return config


def get_config() -> Config:
    global _config
    if _config is None:
        _config = load_config()
    return _config


config = get_config()

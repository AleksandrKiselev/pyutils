"""
Configuration management for the image browser application.
"""
import json
import os
from pathlib import Path
from typing import Dict, Any, Set


CONFIG_FILE = "config.json"
DEFAULT_CONFIG: Dict[str, Any] = {
    "image_folder": "static/images",
    "favorites_folder": "static/images/favorites",
    "thumbnail_size": 512,
    "items_per_page": 20,
    "allowed_extensions": [".png", ".jpg", ".jpeg", ".webp"]
}


class Config(dict):
    """
    Dictionary subclass that allows attribute access.
    
    Example:
        config = Config({"key": "value"})
        print(config.key)  # "value"
        print(config["key"])  # "value"
    """
    
    def __getattr__(self, name: str) -> Any:
        """Allow attribute access to dictionary keys."""
        try:
            return self[name]
        except KeyError:
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
    
    def __setattr__(self, name: str, value: Any) -> None:
        """Allow setting attributes as dictionary keys."""
        self[name] = value


def load_config() -> Config:
    """
    Load configuration from config.json and environment variables, falling back to defaults.
    
    Environment variables take precedence over config.json:
    - IMAGE_FOLDER: Path to image folder
    - FAVORITES_FOLDER: Path to favorites folder
    - THUMBNAIL_SIZE: Thumbnail size in pixels
    - ITEMS_PER_PAGE: Default items per page
    
    Returns:
        Config object with loaded configuration
    """
    loaded_config = Config(DEFAULT_CONFIG.copy())
    
    # Load from config.json if exists
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                user_config = json.load(f)
                loaded_config.update(user_config)
        except Exception as e:
            print(f"Warning: Failed to load config.json: {e}")
    
    # Override with environment variables
    loaded_config["image_folder"] = os.getenv("IMAGE_FOLDER", loaded_config["image_folder"])
    loaded_config["favorites_folder"] = os.getenv("FAVORITES_FOLDER", loaded_config["favorites_folder"])
    loaded_config["thumbnail_size"] = int(os.getenv("THUMBNAIL_SIZE", loaded_config["thumbnail_size"]))
    loaded_config["items_per_page"] = int(os.getenv("ITEMS_PER_PAGE", loaded_config["items_per_page"]))
    
    # Derived fields
    loaded_config.IMAGE_FOLDER = os.path.abspath(loaded_config["image_folder"])
    loaded_config.FAVORITES_FOLDER = os.path.abspath(loaded_config["favorites_folder"])
    loaded_config.ALLOWED_EXTENSIONS = set(loaded_config["allowed_extensions"])
    loaded_config.THUMBNAIL_SIZE = int(loaded_config["thumbnail_size"])
    loaded_config.ITEMS_PER_PAGE = int(loaded_config["items_per_page"])
    loaded_config.AUTO_TAGS = set(loaded_config.get("auto_tags", []))
    
    return loaded_config


# Global config instance
config = load_config()

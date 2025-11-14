import json
import os
import logging
from types import SimpleNamespace

logger = logging.getLogger(__name__)

CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
DEFAULT_CONFIG = {
    "image_folder": "static/images",
    "favorites_folder": "static/images/favorites",
    "thumbnail_size": 512,
    "items_per_page": 20,
    "allowed_extensions": [".png", ".jpg", ".jpeg", ".webp"],
    "metadata_folder": ".metadata",
    "database_name": "metadata.db",
    "favorite_tag": "favorite",
    "thumbnail_quality": 85,
    "auto_tag_enabled": False,
    "auto_tag_threshold": 0.3771
}

_config = DEFAULT_CONFIG.copy()

if os.path.exists(CONFIG_FILE):
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            _config.update(json.load(f))
    except Exception as e:
        logger.warning(f"Не удалось загрузить config.json: {e}")

config = SimpleNamespace(
    IMAGE_FOLDER=os.path.abspath(_config["image_folder"]),
    FAVORITES_FOLDER=os.path.abspath(_config["favorites_folder"]),
    ALLOWED_EXTENSIONS=set(_config["allowed_extensions"]),
    THUMBNAIL_SIZE=int(_config["thumbnail_size"]),
    ITEMS_PER_PAGE=int(_config["items_per_page"]),
    METADATA_FOLDER=_config["metadata_folder"],
    DATABASE_NAME=_config["database_name"],
    FAVORITE_TAG=_config["favorite_tag"],
    THUMBNAIL_QUALITY=int(_config["thumbnail_quality"]),
    AUTO_TAG_ENABLED=bool(_config.get("auto_tag_enabled", False)),
    AUTO_TAG_THRESHOLD=float(_config.get("auto_tag_threshold", 0.3771))
)

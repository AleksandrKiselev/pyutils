import json
import os


CONFIG_FILE = "config.json"
DEFAULT_CONFIG = {
    "image_folder": "static/images",
    "favorites_folder": "static/images/favorites",
    "images_per_row": 5,
    "thumbnail_size": 512,
    "items_per_page": 20,
    "allowed_extensions": [".png", ".jpg", ".jpeg", ".webp"]
}


class Config(dict):
    def __getattr__(self, name):
        return self[name]

    def __setattr__(self, name, value):
        self[name] = value


def load_config():
    loaded_config = Config(DEFAULT_CONFIG.copy())

    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                user_config = json.load(f)
                loaded_config.update(user_config)
        except Exception as e:
            print(f"Failed to load config.json: {e}")

    # Производные поля
    loaded_config.IMAGE_FOLDER = os.path.abspath(loaded_config["image_folder"])
    loaded_config.FAVORITES_FOLDER = os.path.abspath(loaded_config["favorites_folder"])
    loaded_config.ALLOWED_EXTENSIONS = set(loaded_config["allowed_extensions"])
    loaded_config.IMAGES_PER_ROW = int(loaded_config["images_per_row"])
    loaded_config.THUMBNAIL_SIZE = int(loaded_config["thumbnail_size"])
    loaded_config.ITEMS_PER_PAGE = int(loaded_config["items_per_page"])

    return loaded_config


config = load_config()

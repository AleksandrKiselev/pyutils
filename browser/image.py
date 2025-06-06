import os
import time
import logging
from concurrent.futures import ThreadPoolExecutor
from rapidfuzz import fuzz
from metadata import load_metadata
from PIL import Image, UnidentifiedImageError
from file_utils import get_thumbnail_path, get_absolute_path, get_relative_path, walk_images
from config import config


logger = logging.getLogger(__name__)


def create_thumbnail(image_path, thumb_path):
    for _ in range(5):
        try:
            with Image.open(image_path) as img:
                img.thumbnail((config.THUMBNAIL_SIZE, config.THUMBNAIL_SIZE))
                os.makedirs(os.path.dirname(thumb_path), exist_ok=True)
                img.save(thumb_path, "WEBP")
                return
        except (OSError, UnidentifiedImageError):
            logger.warning(f"Waiting on file {image_path}")
            time.sleep(1)
    logger.error(f"Thumbnail creation failed: {image_path}")


def process_image(image_path):
    mtime = os.path.getmtime(image_path)
    metadata = load_metadata(image_path, mtime)
    thumb_path = get_thumbnail_path(image_path)

    if not os.path.exists(thumb_path) or mtime > os.path.getmtime(thumb_path):
        create_thumbnail(image_path, thumb_path)

    return {
        "filename": get_relative_path(image_path),
        "thumbnail": get_relative_path(thumb_path),
        "metadata": metadata
    }


def collect_images(folder=None):
    image_paths = []

    if folder:
        paths = os.listdir(folder)
        image_paths = [os.path.join(folder, f) for f in paths if f.lower().endswith(".png")]
    else:
        for image_path in walk_images():
            image_paths.append(image_path)

    with ThreadPoolExecutor(max_workers=10) as pool:
        return list(pool.map(process_image, image_paths))


def sort_images(images, sort_by, order):
    reverse = (order == "desc")

    def safe_get_mtime(img):
        try:
            return os.path.getmtime(get_absolute_path(img["filename"]))
        except Exception as e:
            logger.error(f"Error safe_get_mtime: {e}")

    key_funcs = {
        "date": safe_get_mtime,
        "filename": lambda img: img["filename"].lower(),
        "prompt": lambda img: img["metadata"].get("prompt", "").lower(),
        "rating": lambda img: img["metadata"].get("rating", 0),
        "tags": lambda img: ", ".join(img["metadata"].get("tags", [])).lower()
    }

    if sort_by in key_funcs:
        images.sort(key=key_funcs[sort_by], reverse=reverse)

    return images


def filter_images(images, search):
    search = search.strip().lower()
    if not search:
        return images

    if search.startswith(("tags:", "tag:", "t:")):
        raw = search.split(":", 1)[1].strip().lower()
        if not raw:
            return [img for img in images if not img["metadata"].get("tags")]
        tags = [t.strip() for t in raw.split(",") if t]
        return [
            img for img in images
            if all(
                any(fuzz.partial_ratio(t, tag.lower()) >= 85 for tag in img["metadata"].get("tags", []))
                for t in tags
            )
        ]
    else:
        return [img for img in images if search in img["metadata"].get("prompt", "").lower()]
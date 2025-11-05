"""
Image processing utilities for the image browser application: thumbnails, sorting, filtering, and collection.
"""
import os
import time
import logging
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor
from metadata import load_metadata
from PIL import Image, UnidentifiedImageError
from paths import get_thumbnail_path, get_absolute_path, get_relative_path, walk_images
from config import config

logger = logging.getLogger(__name__)

def create_thumbnail(image_path, thumb_path):
    """Create a thumbnail for the given image and save it as WEBP."""
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
    """Process an image: ensure thumbnail exists and return its metadata."""
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
    """Collect and process all images in the given folder (or recursively if None)."""
    image_paths = []
    if folder:
        paths = os.listdir(folder)
        image_paths = [
            os.path.join(folder, f) 
            for f in paths 
            if os.path.isfile(os.path.join(folder, f)) and 
               os.path.splitext(f)[1].lower() in config.ALLOWED_EXTENSIONS
        ]
    else:
        image_paths = list(walk_images())
    results = []
    with ThreadPoolExecutor(max_workers=10) as pool:
        for result in tqdm(pool.map(process_image, image_paths), total=len(image_paths), desc="Processing images"):
            results.append(result)
    return results

def sort_images(images, sort_by, order):
    """Sort a list of image dicts by the given field and order."""
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
    """Filter images by search string (supports tag and prompt search)."""
    search = search.strip().lower()
    if not search:
        return images
    def normalize(tag):
        return tag.strip().lower()
    if search.startswith(("tags:", "tag:", "t:")):
        raw = search.split(":", 1)[1].strip().lower()
        if not raw:
            return [img for img in images if not img["metadata"].get("tags")]
        # Split into groups: each group is a disjunction of tags
        groups = [
            [normalize(t) for t in part.split("|") if t]
            for part in raw.split(",") if part
        ]
        def match(image_tags):
            image_tags = set(normalize(tag) for tag in image_tags)
            for group in groups:
                if not any(tag in image_tags for tag in group):
                    return False
            return True
        return [img for img in images if match(img["metadata"].get("tags", []))]
    else:
        return [img for img in images if search in img["metadata"].get("prompt", "").lower()]
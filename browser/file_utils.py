"""
Utility functions for file and directory operations in the image browser application.
"""
import os
import logging
from config import config

logger = logging.getLogger(__name__)

def get_metadata_file_path(image_path, ext):
    """Return the path to the metadata or thumbnail file for a given image."""
    folder = os.path.dirname(image_path)
    meta_dir = os.path.join(folder, ".metadata")
    os.makedirs(meta_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(image_path))[0]
    return os.path.join(meta_dir, base + ext)

def get_metadata_path(image_path):
    """Return the path to the metadata JSON file for a given image."""
    return get_metadata_file_path(image_path, ".json")

def get_thumbnail_path(image_path):
    """Return the path to the thumbnail WEBP file for a given image."""
    return get_metadata_file_path(image_path, ".webp")

def get_absolute_path(relative_path, root_folder=config.IMAGE_FOLDER):
    """Convert a relative path to an absolute path based on the root folder."""
    return os.path.join(root_folder, relative_path)

def get_relative_path(absolute_path, root_folder=config.IMAGE_FOLDER):
    """Convert an absolute path to a relative path based on the root folder."""
    return absolute_path.replace(root_folder, "").lstrip(os.sep).replace("\\", "/")

def walk_images(root_folder=config.IMAGE_FOLDER):
    """Yield absolute paths to all images in the directory tree, skipping .metadata folders."""
    for root, dirs, files in os.walk(root_folder):
        dirs[:] = [d for d in dirs if not d.startswith(".metadata")]
        for file in files:
            if os.path.splitext(file)[1].lower() in config.ALLOWED_EXTENSIONS:
                yield os.path.join(root, file)

def walk_metadata(root_folder=config.IMAGE_FOLDER):
    """Yield absolute paths to all metadata JSON files in .metadata folders."""
    for root, dirs, files in os.walk(root_folder):
        if os.path.basename(root) == ".metadata":
            for file in files:
                if file.lower().endswith(".json"):
                    yield os.path.join(root, file)

def build_folder_tree(base_path, relative=""):
    """Recursively build a tree structure of folders and image counts for the UI."""
    tree = {}
    full_path = os.path.join(base_path, relative)

    for entry in os.scandir(full_path):
        if entry.is_dir():
            if entry.name.startswith("."):
                continue
            rel_path = os.path.join(relative, entry.name).replace("\\", "/")
            image_count = sum(
                1 for f in os.listdir(entry.path)
                if os.path.splitext(f)[1].lower() in config.ALLOWED_EXTENSIONS
            )
            children = build_folder_tree(base_path, rel_path)
            if image_count > 0 or children:
                tree[rel_path] = {
                    "name": entry.name,
                    "count": image_count,
                    "children": children
                }
    return tree
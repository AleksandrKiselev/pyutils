"""
Utility functions for file and directory operations in the image browser application.
"""
import os
import logging
from typing import Dict, Any, Iterator, Optional
from config import config
from exceptions import FileOperationError

logger = logging.getLogger(__name__)


def get_metadata_file_path(image_path: str, ext: str) -> str:
    """
    Return the path to the metadata or thumbnail file for a given image.
    
    Args:
        image_path: Absolute path to the image file
        ext: File extension (e.g., ".json" or ".webp")
        
    Returns:
        Absolute path to the metadata/thumbnail file
        
    Raises:
        FileOperationError: If directory creation fails
    """
    try:
        folder = os.path.dirname(image_path)
        meta_dir = os.path.join(folder, ".metadata")
        os.makedirs(meta_dir, exist_ok=True)
        base = os.path.splitext(os.path.basename(image_path))[0]
        return os.path.join(meta_dir, base + ext)
    except OSError as e:
        logger.error(f"Error creating metadata directory for {image_path}: {e}")
        raise FileOperationError(f"Failed to create metadata directory: {e}") from e


def get_metadata_path(image_path: str) -> str:
    """
    Return the path to the metadata JSON file for a given image.
    
    Args:
        image_path: Absolute path to the image file
        
    Returns:
        Absolute path to the metadata JSON file
    """
    return get_metadata_file_path(image_path, ".json")


def get_thumbnail_path(image_path: str) -> str:
    """
    Return the path to the thumbnail WEBP file for a given image.
    
    Args:
        image_path: Absolute path to the image file
        
    Returns:
        Absolute path to the thumbnail WEBP file
    """
    return get_metadata_file_path(image_path, ".webp")


def get_absolute_path(relative_path: str, root_folder: Optional[str] = None) -> str:
    """
    Convert a relative path to an absolute path based on the root folder.
    
    Args:
        relative_path: Relative path from the root folder
        root_folder: Root folder path (defaults to config.IMAGE_FOLDER)
        
    Returns:
        Absolute path to the file or directory
    """
    if root_folder is None:
        root_folder = config.IMAGE_FOLDER
    return os.path.join(root_folder, relative_path)


def get_relative_path(absolute_path: str, root_folder: Optional[str] = None) -> str:
    """
    Convert an absolute path to a relative path based on the root folder.
    
    Args:
        absolute_path: Absolute path to convert
        root_folder: Root folder path (defaults to config.IMAGE_FOLDER)
        
    Returns:
        Relative path with forward slashes as separators
    """
    if root_folder is None:
        root_folder = config.IMAGE_FOLDER
    return absolute_path.replace(root_folder, "").lstrip(os.sep).replace("\\", "/")


def walk_images(root_folder: Optional[str] = None) -> Iterator[str]:
    """
    Yield absolute paths to all images in the directory tree, skipping .metadata folders.
    
    Args:
        root_folder: Root folder to search (defaults to config.IMAGE_FOLDER)
        
    Yields:
        Absolute paths to image files
    """
    if root_folder is None:
        root_folder = config.IMAGE_FOLDER
    
    try:
        for root, dirs, files in os.walk(root_folder):
            # Filter out .metadata directories from traversal
            dirs[:] = [d for d in dirs if not d.startswith(".metadata")]
            for file in files:
                if os.path.splitext(file)[1].lower() in config.ALLOWED_EXTENSIONS:
                    yield os.path.join(root, file)
    except OSError as e:
        logger.error(f"Error walking directory tree {root_folder}: {e}")
        raise FileOperationError(f"Failed to walk directory tree: {e}") from e


def walk_metadata(root_folder: Optional[str] = None) -> Iterator[str]:
    """
    Yield absolute paths to all metadata JSON files in .metadata folders.
    
    Args:
        root_folder: Root folder to search (defaults to config.IMAGE_FOLDER)
        
    Yields:
        Absolute paths to metadata JSON files
    """
    if root_folder is None:
        root_folder = config.IMAGE_FOLDER
    
    try:
        for root, dirs, files in os.walk(root_folder):
            if os.path.basename(root) == ".metadata":
                for file in files:
                    if file.lower().endswith(".json"):
                        yield os.path.join(root, file)
    except OSError as e:
        logger.error(f"Error walking metadata directories {root_folder}: {e}")
        raise FileOperationError(f"Failed to walk metadata directories: {e}") from e


def build_folder_tree(base_path: str, relative: str = "") -> Dict[str, Any]:
    """
    Recursively build a tree structure of folders and image counts for the UI.
    
    Args:
        base_path: Base directory path to build tree from
        relative: Relative path from base_path (used for recursion)
        
    Returns:
        Dictionary representing the folder tree structure:
        {
            "relative/path": {
                "name": "folder_name",
                "count": image_count,
                "children": {...}
            }
        }
        
    Raises:
        FileOperationError: If directory access fails
    """
    tree: Dict[str, Any] = {}
    full_path = os.path.join(base_path, relative)

    try:
        for entry in os.scandir(full_path):
            if entry.is_dir():
                if entry.name.startswith("."):
                    continue
                rel_path = os.path.join(relative, entry.name).replace("\\", "/")
                
                # Count images in this directory
                try:
                    image_count = sum(
                        1 for f in os.listdir(entry.path)
                        if os.path.isfile(os.path.join(entry.path, f)) and
                           os.path.splitext(f)[1].lower() in config.ALLOWED_EXTENSIONS
                    )
                except OSError as e:
                    logger.warning(f"Error counting images in {entry.path}: {e}")
                    image_count = 0
                
                # Recursively build children
                children = build_folder_tree(base_path, rel_path)
                
                # Include folder if it has images or subfolders
                if image_count > 0 or children:
                    tree[rel_path] = {
                        "name": entry.name,
                        "count": image_count,
                        "children": children
                    }
    except OSError as e:
        logger.error(f"Error building folder tree for {full_path}: {e}")
        raise FileOperationError(f"Failed to build folder tree: {e}") from e
    
    return tree


"""
Business logic services for the image browser application.
"""
import os
import json
import shutil
from typing import List, Dict, Optional

from exceptions import PathNotFoundError, FileOperationError, InvalidRequestError
from paths import get_absolute_path, get_metadata_path, get_thumbnail_path
from metadata import load_metadata, save_metadata
from image import collect_images, filter_images, sort_images
from tag import get_all_tags_cached
from config import config


class ImageService:
    """Service for image-related operations."""
    
    @staticmethod
    def get_images(folder_path: Optional[str], search: str, sort_by: str, 
                   order: str, limit: int, offset: int) -> List[Dict]:
        """
        Get filtered and sorted images.
        
        Args:
            folder_path: Path to folder (None for global search)
            search: Search query
            sort_by: Field to sort by
            order: Sort order ('asc' or 'desc')
            limit: Maximum number of results
            offset: Number of results to skip
            
        Returns:
            List of image dictionaries
        """
        images = collect_images(None if folder_path is None else folder_path)
        images = filter_images(images, search)
        images = sort_images(images, sort_by, order)
        return images[offset:offset + limit]
    
    @staticmethod
    def delete_image(filename: str) -> None:
        """
        Delete an image and its associated files.
        
        Args:
            filename: Relative filename of image to delete
            
        Raises:
            FileOperationError: If deletion fails
        """
        base = get_absolute_path(filename)
        thumb = get_thumbnail_path(base)
        meta = get_metadata_path(base)
        
        try:
            if os.path.exists(base):
                os.remove(base)
            for path in (thumb, meta):
                if os.path.exists(path):
                    os.remove(path)
        except OSError as e:
            raise FileOperationError(f"Failed to delete image: {e}")


class MetadataService:
    """Service for metadata operations."""
    
    @staticmethod
    def update_metadata(filenames: List[str], updates: Dict) -> None:
        """
        Update metadata for one or more images.
        
        Args:
            filenames: List of relative filenames
            updates: Dictionary with metadata fields to update
            
        Raises:
            FileOperationError: If update fails
        """
        for filename in filenames:
            image_path = get_absolute_path(filename)
            if not os.path.exists(image_path):
                continue
                
            try:
                mtime = os.path.getmtime(image_path)
                metadata = load_metadata(image_path, mtime)
                
                for key in ("checked", "rating", "tags"):
                    if key in updates:
                        metadata[key] = updates[key]
                        
                save_metadata(image_path, metadata)
            except Exception as e:
                raise FileOperationError(f"Failed to update metadata for {filename}: {e}")
        
        # Clear caches
        load_metadata.cache_clear()
        get_all_tags_cached.cache_clear()
    
    @staticmethod
    def uncheck_all(folder_path: Optional[str], search: str) -> int:
        """
        Uncheck all images matching the search criteria.
        
        Args:
            folder_path: Path to folder (None for global search)
            search: Search query
            
        Returns:
            Number of images unchecked
        """
        images = collect_images(None if folder_path is None else folder_path)
        images = filter_images(images, search)
        
        count = 0
        for img in images:
            image_path = get_absolute_path(img["filename"])
            if not os.path.exists(image_path):
                continue
                
            try:
                mtime = os.path.getmtime(image_path)
                metadata = load_metadata(image_path, mtime)
                if metadata.get("checked"):
                    metadata["checked"] = False
                    save_metadata(image_path, metadata)
                    count += 1
            except Exception as e:
                # Log but continue processing
                import logging
                logging.getLogger(__name__).warning(f"Failed to uncheck {img['filename']}: {e}")
        
        load_metadata.cache_clear()
        get_all_tags_cached.cache_clear()
        return count


class FavoritesService:
    """Service for favorites operations."""
    
    @staticmethod
    def copy_to_favorites(filename: str) -> None:
        """
        Copy an image and its metadata to favorites folder.
        
        Args:
            filename: Relative filename of image to copy
            
        Raises:
            FileOperationError: If copy operation fails
            InvalidRequestError: If favorites folder is not configured
        """
        src = get_absolute_path(filename)
        dst_dir = config.get("favorites_folder")
        
        if not dst_dir:
            raise InvalidRequestError("No favorites_folder defined in config")
        
        dst = os.path.join(dst_dir, os.path.basename(filename))
        os.makedirs(dst_dir, exist_ok=True)
        
        if os.path.abspath(src) == os.path.abspath(dst):
            raise InvalidRequestError("Source and destination are the same")
        
        try:
            # Copy image file
            shutil.copy2(src, dst)
            
            # Copy and update metadata
            src_meta = get_metadata_path(filename)
            dst_meta = get_metadata_path(dst)
            
            meta = {}
            if os.path.exists(src_meta):
                with open(src_meta, "r", encoding="utf-8") as f:
                    meta = json.load(f)
            
            tags = set(meta.get("tags", []))
            tags.add("favorite")
            meta["tags"] = sorted(tags)
            
            with open(dst_meta, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
        except Exception as e:
            raise FileOperationError(f"Failed to copy to favorites: {e}")


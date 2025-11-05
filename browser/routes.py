"""
API routes for the image browser application.
"""
import os
import logging
from urllib.parse import unquote

from flask import Blueprint, request, jsonify, render_template, send_from_directory

from config import config
from paths import build_folder_tree, get_absolute_path
from tag import get_all_tags_cached
from exceptions import PathNotFoundError, InvalidRequestError, FileOperationError
from validators import (
    validate_search_query,
    validate_pagination_params,
    validate_sort_params,
    validate_json_request,
    validate_filename
)
from services import ImageService, MetadataService, FavoritesService

logger = logging.getLogger(__name__)
routes = Blueprint("routes", __name__)


@routes.errorhandler(PathNotFoundError)
def handle_path_not_found(error: PathNotFoundError):
    """Handle path not found errors."""
    return jsonify({"error": str(error)}), 404


@routes.errorhandler(InvalidRequestError)
def handle_invalid_request(error: InvalidRequestError):
    """Handle invalid request errors."""
    return jsonify({"error": str(error)}), 400


@routes.errorhandler(FileOperationError)
def handle_file_operation_error(error: FileOperationError):
    """Handle file operation errors."""
    logger.error(f"File operation error: {error}")
    return jsonify({"error": str(error)}), 500


@routes.route("/")
@routes.route("/<path:subpath>")
def index(subpath: str = ""):
    """
    Render the main page with the folder tree and image grid.
    
    Args:
        subpath: Optional subpath within the image folder
        
    Returns:
        Rendered HTML template or error response
    """
    try:
        folder_path = get_absolute_path(subpath)
        if not os.path.isdir(folder_path):
            raise PathNotFoundError("Path does not exist")
        
        return render_template(
            "index.html",
            folder_tree=build_folder_tree(config.IMAGE_FOLDER)
        )
    except Exception as e:
        logger.exception(f"Error rendering index page: {e}")
        return jsonify({"error": "Internal server error"}), 500


@routes.route("/images/<path:subpath>")
def get_images(subpath: str = ""):
    """
    Return a JSON list of images for the given folder, with filtering, sorting, and pagination.
    
    Args:
        subpath: Optional subpath within the image folder
        
    Returns:
        JSON response with list of images
    """
    try:
        folder_path = get_absolute_path(subpath)
        if not os.path.isdir(folder_path):
            raise PathNotFoundError("Path does not exist")
        
        # Validate and extract parameters
        limit, offset = validate_pagination_params(request, config.ITEMS_PER_PAGE)
        sort_by, order = validate_sort_params(request)
        raw_search = request.args.get("search", "")
        scope, search = validate_search_query(raw_search)
        
        # Determine folder path (None for global search)
        search_folder_path = None if scope == "global" else folder_path
        
        # Get images using service
        images = ImageService.get_images(
            folder_path=search_folder_path,
            search=search,
            sort_by=sort_by,
            order=order,
            limit=limit,
            offset=offset
        )
        
        return jsonify(images)
    except (PathNotFoundError, InvalidRequestError) as e:
        raise
    except Exception as e:
        logger.exception(f"Error getting images: {e}")
        return jsonify({"error": "Internal server error"}), 500


@routes.route("/serve_image/<path:filename>")
@routes.route("/serve_thumbnail/<path:filename>")
def serve_file(filename: str):
    """
    Serve the original image or its thumbnail from the static folder.
    
    Args:
        filename: Relative filename of the image
        
    Returns:
        File response or error response
    """
    try:
        path = get_absolute_path(filename)
        if not os.path.exists(path):
            raise PathNotFoundError("File not found")
        
        return send_from_directory(config.IMAGE_FOLDER, filename)
    except PathNotFoundError:
        raise
    except Exception as e:
        logger.exception(f"Error serving file: {e}")
        return jsonify({"error": "Internal server error"}), 500


@routes.route("/delete_image", methods=["POST"])
def delete_image():
    """
    Delete an image and its associated thumbnail and metadata files.
    
    Returns:
        JSON response with success status
    """
    try:
        data = validate_json_request(request)
        filename = validate_filename(data)
        
        ImageService.delete_image(filename)
        return jsonify({"success": True})
    except (InvalidRequestError, FileOperationError):
        raise
    except Exception as e:
        logger.exception(f"Error deleting image: {e}")
        return jsonify({"error": "Internal server error"}), 500


@routes.route("/update_metadata", methods=["POST"])
def update_metadata():
    """
    Update metadata (checked, rating, tags) for one or more images.
    
    Returns:
        JSON response with success status
    """
    try:
        data = validate_json_request(request)
        filenames = data.get("filenames") or [data.get("filename")]
        
        if not filenames or not isinstance(filenames, list):
            raise InvalidRequestError("No filenames provided")
        
        # Extract metadata updates
        updates = {}
        for key in ("checked", "rating", "tags"):
            if key in data:
                updates[key] = data[key]
        
        if not updates:
            raise InvalidRequestError("No metadata fields to update")
        
        MetadataService.update_metadata(filenames, updates)
        return jsonify({"success": True})
    except (InvalidRequestError, FileOperationError):
        raise
    except Exception as e:
        logger.exception(f"Error updating metadata: {e}")
        return jsonify({"error": "Internal server error"}), 500


@routes.route("/copy_to_favorites", methods=["POST"])
def copy_to_favorites():
    """
    Copy an image and its metadata to the favorites folder, adding the 'favorite' tag.
    
    Returns:
        JSON response with success status
    """
    try:
        data = validate_json_request(request)
        filename = validate_filename(data)
        
        FavoritesService.copy_to_favorites(filename)
        return jsonify({"success": True})
    except (InvalidRequestError, FileOperationError):
        raise
    except Exception as e:
        logger.exception(f"Error copying to favorites: {e}")
        return jsonify({"error": "Internal server error"}), 500


@routes.route("/all_tags")
def get_all_tags():
    """
    Return a JSON list of all unique tags in the dataset.
    
    Returns:
        JSON response with list of tags
    """
    try:
        return jsonify(get_all_tags_cached())
    except Exception as e:
        logger.exception(f"Error getting tags: {e}")
        return jsonify({"error": "Internal server error"}), 500


@routes.route("/uncheck_all", methods=["POST"])
def uncheck_all():
    """
    Uncheck all images in the given folder (or globally) matching the search query.
    
    Returns:
        JSON response with success status and count of unchecked images
    """
    try:
        data = validate_json_request(request)
        subpath = data.get("path", "")
        raw_search = data.get("search", "")
        
        # Decode URL-encoded path
        if subpath:
            subpath = unquote(subpath)
        
        # Validate and get folder path
        try:
            folder_path = get_absolute_path(subpath)
            folder_path = os.path.normpath(folder_path)
            
            if not os.path.isdir(folder_path):
                raise PathNotFoundError(f"Path does not exist: {folder_path}")
        except Exception as e:
            logger.exception(f"Error processing path: {e}")
            raise InvalidRequestError(f"Error processing path: {str(e)}")
        
        # Parse search query
        scope, search = validate_search_query(raw_search)
        search_folder_path = None if scope == "global" else folder_path
        
        # Uncheck images using service
        count = MetadataService.uncheck_all(search_folder_path, search)
        
        return jsonify({"success": True, "count": count})
    except (PathNotFoundError, InvalidRequestError):
        raise
    except Exception as e:
        logger.exception(f"Error unchecking all: {e}")
        return jsonify({"error": "Internal server error"}), 500

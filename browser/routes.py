import json
import os
import logging
from urllib.parse import unquote
from flask import Blueprint, request, jsonify, render_template, send_from_directory
from config import config
from image import collect_images, filter_images, sort_images
from file_utils import build_folder_tree
from metadata import load_metadata, save_metadata
from tag import get_all_tags_cached
from file_utils import get_metadata_path, get_thumbnail_path, get_absolute_path

logger = logging.getLogger(__name__)
routes = Blueprint("routes", __name__)

@routes.route("/")
@routes.route("/<path:subpath>")
def index(subpath=""):
    """Render the main page with the folder tree and image grid."""
    folder_path = get_absolute_path(subpath)
    if not os.path.isdir(folder_path):
        return jsonify({"error": "Path not exist"}), 404
    return render_template(
        "index.html",
        folder_tree=build_folder_tree(config.IMAGE_FOLDER),
        images_per_row=config.IMAGES_PER_ROW
    )

def parse_scope_and_query(search: str):
    """Parse the search string to determine scope and query."""
    search = search.strip()
    if search.lower().startswith("g:"):
        return "global", search[2:].strip()
    return "current", search

@routes.route("/images/<path:subpath>")
def get_images(subpath=""):
    """Return a JSON list of images for the given folder, with filtering, sorting, and pagination."""
    folder_path = get_absolute_path(subpath)
    if not os.path.isdir(folder_path):
        return jsonify({"error": "Path not exist"}), 404

    sort_by = request.args.get("sort_by", "date")
    order = request.args.get("order", "asc")
    limit = int(request.args.get("limit") or config.ITEMS_PER_PAGE)
    offset = int(request.args.get("offset") or 0)

    raw_search = request.args.get("search", "")
    scope, search = parse_scope_and_query(raw_search)
    images = collect_images(None if scope == "global" else folder_path)
    images = filter_images(images, search)
    images = sort_images(images, sort_by, order)

    return jsonify(images[offset:offset + limit])

@routes.route("/serve_image/<path:filename>")
@routes.route("/serve_thumbnail/<path:filename>")
def serve_file(filename):
    """Serve the original image or its thumbnail from the static folder."""
    path = get_absolute_path(filename)
    if not os.path.exists(path):
        return jsonify({"error": "File not found"}), 404
    return send_from_directory(config.IMAGE_FOLDER, filename)

@routes.route("/delete_image", methods=["POST"])
def delete_image():
    """Delete an image and its associated thumbnail and metadata files."""
    data = request.get_json()
    filename = data.get("filename")
    if not filename:
        return jsonify({"error": "Filename is required"}), 400

    base = get_absolute_path(filename)
    thumb = get_thumbnail_path(base)
    meta = get_metadata_path(base)

    try:
        os.remove(base)
        for path in (thumb, meta):
            if os.path.exists(path):
                os.remove(path)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@routes.route("/update_metadata", methods=["POST"])
def update_metadata():
    """Update metadata (checked, rating, tags) for one or more images."""
    data = request.get_json()
    filenames = data.get("filenames") or [data.get("filename")]
    if not filenames or not isinstance(filenames, list):
        return jsonify({"error": "No filenames provided"}), 400

    for filename in filenames:
        image_path = get_absolute_path(filename)
        if not os.path.exists(image_path):
            continue
        mtime = os.path.getmtime(image_path)
        metadata = load_metadata(image_path, mtime)
        for key in ("checked", "rating", "tags"):
            if key in data:
                metadata[key] = data[key]
        save_metadata(image_path, metadata)

    load_metadata.cache_clear()
    get_all_tags_cached.cache_clear()
    return jsonify({"success": True})

@routes.route("/copy_to_favorites", methods=["POST"])
def copy_to_favorites():
    """Copy an image and its metadata to the favorites folder, adding the 'favorite' tag."""
    data = request.get_json()
    filename = data.get("filename")
    if not filename:
        return jsonify({"error": "Filename is required"}), 400

    src = get_absolute_path(filename)
    dst_dir = config.get("favorites_folder")
    if not dst_dir:
        return jsonify({"error": "No favorites_folder defined in config"}), 500

    dst = os.path.join(dst_dir, os.path.basename(filename))
    os.makedirs(dst_dir, exist_ok=True)

    try:
        if os.path.abspath(src) == os.path.abspath(dst):
            return jsonify({"error": "Source and destination are the same"}), 400

        # Copy the image file
        with open(src, "rb") as fsrc, open(dst, "wb") as fdst:
            fdst.write(fsrc.read())

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
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@routes.route('/all_tags')
def get_all_tags():
    """Return a JSON list of all unique tags in the dataset."""
    return jsonify(get_all_tags_cached())

@routes.route("/uncheck_all", methods=["POST"])
def uncheck_all():
    """Uncheck all images in the given folder (or globally) matching the search query."""
    
    if not request.is_json:
        logger.error("Request is not JSON")
        return jsonify({"error": "Request must be JSON"}), 400
    
    data = request.get_json()
    subpath = data.get("path", "")
    raw_search = data.get("search", "")
    
    # Декодируем URL-кодированный путь
    if subpath:
        subpath = unquote(subpath)
    
    # Обрабатываем путь так же, как в get_images
    try:
        folder_path = get_absolute_path(subpath)
        folder_path = os.path.normpath(folder_path)  # Нормализуем путь
        
        if not os.path.isdir(folder_path):
            logger.error(f"Directory does not exist: '{folder_path}'")
            return jsonify({"error": f"Path not exist: {folder_path} (subpath: '{subpath}')"}), 404
    except Exception as e:
        logger.exception(f"Error processing path: {e}")
        return jsonify({"error": f"Error processing path: {str(e)}"}), 500

    scope, search = parse_scope_and_query(raw_search)
    
    # Получаем все изображения согласно scope и search
    images = collect_images(None if scope == "global" else folder_path)
    images = filter_images(images, search)
    
    # Сбрасываем checked для всех найденных изображений
    count = 0
    for img in images:
        image_path = get_absolute_path(img["filename"])
        if not os.path.exists(image_path):
            logger.warning(f"Image file not found: {image_path}")
            continue
        mtime = os.path.getmtime(image_path)
        metadata = load_metadata(image_path, mtime)
        if metadata["checked"]:
            metadata["checked"] = False
            save_metadata(image_path, metadata)
            count += 1

    load_metadata.cache_clear()
    get_all_tags_cached.cache_clear()
    return jsonify({"success": True, "count": count})
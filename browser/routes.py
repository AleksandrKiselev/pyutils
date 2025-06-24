import json
import os
from flask import Blueprint, request, jsonify, render_template, send_from_directory
from config import config
from image import collect_images, filter_images, sort_images
from file_utils import build_folder_tree
from metadata import load_metadata, save_metadata
from tag import get_all_tags_cached
from file_utils import get_metadata_path, get_thumbnail_path, get_absolute_path


routes = Blueprint("routes", __name__)


@routes.route("/")
@routes.route("/<path:subpath>")
def index(subpath=""):
    folder_path = get_absolute_path(subpath)
    if not os.path.isdir(folder_path):
        return jsonify({"error": "Path not exist"}), 404
    return render_template("index.html",
                           folder_tree=build_folder_tree(config.IMAGE_FOLDER),
                           images_per_row=config.IMAGES_PER_ROW)


def parse_scope_and_query(search: str):
    search = search.strip()
    if search.lower().startswith("g:"):
        return "global", search[2:].strip()
    return "current", search

@routes.route("/images/<path:subpath>")
def get_images(subpath=""):
    folder_path = get_absolute_path(subpath)
    if not os.path.isdir(folder_path):
        return jsonify({"error": "Path not exist"}), 404

    sort_by = request.args.get("sort_by", "date")
    order = request.args.get("order", "asc")
    limit = int(request.args.get("limit", config.ITEMS_PER_PAGE))
    offset = int(request.args.get("offset", 0))

    raw_search = request.args.get("search", "")
    scope, search = parse_scope_and_query(raw_search)
    images = collect_images(None if scope == "global" else folder_path)
    images = filter_images(images, search)
    images = sort_images(images, sort_by, order)

    return jsonify(images[offset:offset + limit])


@routes.route("/serve_image/<path:filename>")
@routes.route("/serve_thumbnail/<path:filename>")
def serve_file(filename):
    path = get_absolute_path(filename)
    if not os.path.exists(path):
        return jsonify({"error": "File not found"}), 404
    return send_from_directory(config.IMAGE_FOLDER, filename)


@routes.route("/delete_image", methods=["POST"])
def delete_image():
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

        # 1. Копируем изображение
        with open(src, "rb") as fsrc, open(dst, "wb") as fdst:
            fdst.write(fsrc.read())

        # 2. Путь к .json исходника и копии
        src_meta = get_metadata_path(filename)
        dst_meta = get_metadata_path(dst)

        # 3. Копируем и модифицируем метаданные
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
    return jsonify(get_all_tags_cached())

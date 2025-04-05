import os
import json
import struct
import zlib
import re
import logging
import time
import webbrowser
import threading
from flask import Flask, render_template, jsonify, send_from_directory, request, redirect
from PIL import Image, UnidentifiedImageError
from concurrent.futures import ThreadPoolExecutor

# --- Flask App Setup ---
app = Flask(__name__, static_folder="static", template_folder="templates")
app.logger.setLevel(logging.INFO)

# --- Constants ---
CONFIG_FILE = "config.json"
ALLOWED_EXTENSIONS = {".png", ".jpg"}
DEFAULT_CONFIG = {
    "image_folder": "static/images",
    "images_per_row": 6,
    "thumbnail_size": 512,
    "items_per_page": 20
}

# --- Config ---
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return DEFAULT_CONFIG.copy()

config = load_config()
IMAGE_FOLDER = os.path.abspath(config["image_folder"])

# --- Utilities ---
def get_relative_path(path):
    return path.replace(IMAGE_FOLDER, "").lstrip(os.sep).replace("\\", "/")

def get_metadata_path(image_path):
    return os.path.splitext(image_path)[0] + ".json"

def extract_prompt_from_png(image_path):
    try:
        with open(image_path, "rb") as f:
            data = f.read()

        chunks, offset = [], 8
        while offset < len(data):
            length = struct.unpack("!I", data[offset:offset+4])[0]
            chunk_type = data[offset+4:offset+8].decode("utf-8", "ignore")
            chunk_data = data[offset+8:offset+8+length]
            offset += 8 + length + 4

            if chunk_type == "zTXt":
                try:
                    null_index = chunk_data.index(b'\x00')
                    compressed = chunk_data[null_index + 2:]
                    decompressed = zlib.decompress(compressed).decode("utf-8", "ignore")
                    chunks.append(decompressed)
                except Exception as e:
                    app.logger.warning(f"Failed decompressing zTXt: {e}")
            elif chunk_type in ("tEXt", "iTXt"):
                chunks.append(chunk_data.decode("utf-8", "ignore"))

        metadata = "".join(chunks).strip()
        pattern = r'"title"\s*:\s*"PromptTextForBrowser",.*?"widgets_values"\s*:\s*\[\s*\[\s*"([^"]+)"\s*\]\s*\]'
        match = re.search(pattern, metadata, re.DOTALL)
        return match.group(1).strip() if match else "No metadata found"
    except Exception as e:
        app.logger.error(f"Error reading metadata: {e}")
        return "No metadata found"

def load_metadata(image_path):
    path = get_metadata_path(image_path)
    metadata = {}
    modified = False

    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
        except Exception as e:
            app.logger.warning(f"Corrupted metadata file: {path}, error: {e}")
            metadata = {}

    if "prompt" not in metadata:
        metadata["prompt"] = extract_prompt_from_png(image_path)
        modified = True
    if "checked" not in metadata:
        metadata["checked"] = False
        modified = True
    if "rating" not in metadata:
        metadata["rating"] = 0
        modified = True

    if modified:
        save_metadata(image_path, metadata)

    return metadata

def save_metadata(image_path, metadata):
    try:
        with open(get_metadata_path(image_path), "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=4)
    except Exception as e:
        app.logger.error(f"Error saving metadata: {e}")

def create_thumbnail(image_path, thumb_path):
    for _ in range(5):
        try:
            with Image.open(image_path) as img:
                img.thumbnail((config["thumbnail_size"], config["thumbnail_size"]))
                img.save(thumb_path, "WEBP")
                return
        except (OSError, UnidentifiedImageError):
            app.logger.warning(f"Waiting on file {image_path}")
            time.sleep(1)
    app.logger.error(f"Thumbnail creation failed: {image_path}")

def process_image(image_path):
    metadata = load_metadata(image_path)
    thumb_path = os.path.splitext(image_path)[0] + ".webp"

    if not os.path.exists(thumb_path) or os.path.getmtime(image_path) > os.path.getmtime(thumb_path):
        create_thumbnail(image_path, thumb_path)

    return {
        "filename": get_relative_path(image_path),
        "thumbnail": get_relative_path(thumb_path),
        "metadata": metadata
    }

def get_sorted_images(folder, sort_by="date", order="asc"):
    paths = [os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith(".png")]
    paths.sort(key=os.path.getmtime, reverse=(order == "desc"))

    with ThreadPoolExecutor(max_workers=10) as pool:
        images = list(pool.map(process_image, paths))

    key_funcs = {
        "filename": lambda img: img["filename"].lower(),
        "prompt": lambda img: img["metadata"].get("prompt", "").lower(),
        "rating": lambda img: img["metadata"].get("rating", 0),
    }

    if sort_by in key_funcs:
        images.sort(key=key_funcs[sort_by], reverse=(order == "desc"))

    return images

def build_folder_tree(base_path, relative=""):
    tree = {}
    full_path = os.path.join(base_path, relative)

    for entry in os.scandir(full_path):
        if entry.is_dir():
            rel_path = os.path.join(relative, entry.name).replace("\\", "/")
            image_count = sum(
                1 for f in os.listdir(entry.path)
                if os.path.splitext(f)[1].lower() in ALLOWED_EXTENSIONS
            )
            children = build_folder_tree(base_path, rel_path)
            if image_count > 0 or children:
                tree[rel_path] = {
                    "name": entry.name,
                    "count": image_count,
                    "children": children
                }
    return tree

# --- Routes ---
@app.route("/")
@app.route("/<path:subpath>")
def index(subpath=""):
    folder_path = os.path.abspath(os.path.join(IMAGE_FOLDER, subpath))

    # Если корень — найти первую папку и редирект
    if subpath == "":
        for root, dirs, _ in os.walk(IMAGE_FOLDER):
            if dirs:
                first_folder = os.path.relpath(os.path.join(root, dirs[0]), IMAGE_FOLDER).replace("\\", "/")
                return redirect(f"/{first_folder}")
            break

    if not os.path.isdir(folder_path):
        return jsonify({"error": "Path not exist"}), 404

    return render_template("index.html",
                           folder_tree=build_folder_tree(IMAGE_FOLDER),
                           images_per_row=config["images_per_row"])

@app.route("/images/<path:subpath>")
def get_images(subpath=""):
    folder_path = os.path.abspath(os.path.join(IMAGE_FOLDER, subpath))
    if not os.path.isdir(folder_path):
        return jsonify({"error": "Path not exist"}), 404

    sort_by = request.args.get("sort_by", "date")
    order = request.args.get("order", "asc")
    limit = int(request.args.get("limit", config["items_per_page"]))
    offset = int(request.args.get("offset", 0))
    search = request.args.get("search", "").lower()

    images = get_sorted_images(folder_path, sort_by, order)
    if search:
        images = [img for img in images if search in img["metadata"].get("prompt", "").lower()]

    return jsonify(images[offset:offset + limit])

@app.route("/serve_image/<path:filename>")
@app.route("/serve_thumbnail/<path:filename>")
def serve_file(filename):
    path = os.path.join(IMAGE_FOLDER, filename)
    if not os.path.exists(path):
        return jsonify({"error": "File not found"}), 404
    return send_from_directory(IMAGE_FOLDER, filename)

@app.route("/delete_image", methods=["POST"])
def delete_image():
    data = request.get_json()
    filename = data.get("filename")
    if not filename:
        return jsonify({"error": "Filename is required"}), 400

    base = os.path.join(IMAGE_FOLDER, filename)
    thumb = base.replace(".png", ".webp")
    meta = base.replace(".png", ".json")

    try:
        os.remove(base)
        for path in (thumb, meta):
            if os.path.exists(path):
                os.remove(path)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/update_metadata", methods=["POST"])
def update_metadata():
    data = request.get_json()
    filename = data.get("filename")
    if not filename:
        return jsonify({"error": "Invalid request"}), 400

    image_path = os.path.join(IMAGE_FOLDER, filename)
    if not os.path.exists(image_path):
        return jsonify({"error": "File not found"}), 404

    metadata = load_metadata(image_path)
    for key in ("checked", "rating"):
        if key in data:
            metadata[key] = data[key]
    save_metadata(image_path, metadata)
    return jsonify({"success": True})

# --- Startup ---
def open_browser():
    time.sleep(1)
    webbrowser.open("http://127.0.0.1:5000")

if __name__ == "__main__":
    threading.Thread(target=open_browser, daemon=True).start()
    app.run(host="0.0.0.0", debug=False)
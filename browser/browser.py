import os
import json
import struct
import zlib
import re
import logging
import time
import webbrowser
import threading
from flask import Flask, render_template, jsonify, send_from_directory, abort, request
from PIL import Image, UnidentifiedImageError

app = Flask(__name__, static_folder="static", template_folder="templates")
app.logger.setLevel(logging.INFO)
CONFIG_FILE = "config.json"
ALLOWED_EXTENSIONS = {".png", ".webp"}


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "image_folder": "static/images",
        "thumbnail_folder": "static/thumbnails",
        "images_per_row": 6,
        "thumbnail_size": 512,
        "items_per_page": 20
    }


config = load_config()
IMAGE_FOLDER = os.path.abspath(config["image_folder"])
THUMB_FOLDER = os.path.abspath(config["thumbnail_folder"])


def get_relative_path(absolute_path):
    if absolute_path.startswith(IMAGE_FOLDER):
        relative_path = absolute_path.replace(IMAGE_FOLDER, "").lstrip(os.sep)
    elif absolute_path.startswith(THUMB_FOLDER):
        relative_path = absolute_path.replace(THUMB_FOLDER, "").lstrip(os.sep)
    else:
        relative_path = absolute_path
    return relative_path.replace("\\", "/")


def extract_metadata(image_path):
    try:
        with open(image_path, "rb") as f:
            data = f.read()

        chunks = []
        offset = 8  # PNG header is 8 bytes
        while offset < len(data):
            length = struct.unpack("!I", data[offset:offset + 4])[0]
            chunk_type = data[offset + 4:offset + 8].decode("utf-8", "ignore")
            chunk_data = data[offset + 8:offset + 8 + length]
            offset += 8 + length + 4  # Move to next chunk

            if chunk_type == "zTXt":  # Compressed text, decompressing
                try:
                    null_index = chunk_data.index(b'\x00')
                    compressed_text = chunk_data[null_index + 2:]
                    decompressed_text = zlib.decompress(compressed_text).decode("utf-8", "ignore")
                    chunks.append(decompressed_text)
                except Exception as e:
                    print(f"Error decompressing zTXt in {image_path}: {e}")
            elif chunk_type in ("tEXt", "iTXt"):
                chunks.append(chunk_data.decode("utf-8", "ignore"))

        metadata = "".join(chunks).strip()
        match = re.search(
            r'"title"\s*:\s*"PromptTextForBrowser",.*?"widgets_values"\s*:\s*\[\s*\[\s*"([^"]+)"\s*\]\s*\]',
            metadata,
            re.DOTALL
        )
        if match:
            return match.group(1).strip()
    except Exception as e:
        app.logger.error(f"Error reading metadata from {image_path}: {e}")
    return "No metadata found"


def create_thumbnail(image_path):
    relative_path = os.path.relpath(image_path, IMAGE_FOLDER)
    thumb_path = os.path.join(THUMB_FOLDER, relative_path).replace(".png", ".webp")

    thumb_folder = os.path.dirname(thumb_path)
    os.makedirs(thumb_folder, exist_ok=True)

    if os.path.exists(thumb_path):
        if os.path.getmtime(image_path) <= os.path.getmtime(thumb_path):
            return thumb_path

    for _ in range(5):
        try:
            with Image.open(image_path) as img:
                img.thumbnail((config["thumbnail_size"], config["thumbnail_size"]))
                img.save(thumb_path, "WEBP")
            return thumb_path
        except (OSError, UnidentifiedImageError):
            app.logger.error(f"File {image_path} is not ready yet. Waiting...")
            time.sleep(1)

    app.logger.error(f"Error creating thumbnail for {image_path}: the file is either corrupted or not fully written.")
    return image_path


def get_images_sorted_by_date(folder_path):
    images = []
    file_list = sorted(
        (os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.lower().endswith(".png")),
        key=os.path.getmtime,
        reverse=False
    )

    for file_path in file_list:
        thumb_path = create_thumbnail(file_path)
        prompt = extract_metadata(file_path)
        images.append({
            "filename": get_relative_path(file_path),
            "thumbnail": get_relative_path(thumb_path),
            "prompt": prompt
        })

    return images


@app.route("/")
@app.route("/<path:subpath>")
def index(subpath=""):
    folder_path = os.path.abspath(os.path.join(IMAGE_FOLDER, subpath))

    if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
        return jsonify({"error": "Path not exist"}), 404

    subfolders = []
    folder_counts = {}

    for root, dirs, files in os.walk(folder_path):
        for d in dirs:
            full_path = os.path.join(root, d)
            image_count = sum(
                1 for file in os.listdir(full_path)
                if file.lower().endswith(tuple(ALLOWED_EXTENSIONS)) and os.path.isfile(os.path.join(full_path, file))
            )

            if image_count > 0:
                relative_path = os.path.relpath(full_path, IMAGE_FOLDER).replace("\\", "/")
                subfolders.append(relative_path)
                folder_counts[relative_path] = image_count

    subfolders.sort()

    return render_template("index.html",
                           subfolders=subfolders,
                           folder_counts=folder_counts,
                           images_per_row=config["images_per_row"])


@app.route("/images/<path:subpath>")
def get_images(subpath=""):
    folder_path = os.path.abspath(os.path.join(IMAGE_FOLDER, subpath))

    if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
        return jsonify({"error": "Path not exist"}), 404

    images = get_images_sorted_by_date(folder_path)
    limit = int(request.args.get("limit", config["items_per_page"]))
    offset = int(request.args.get("offset", 0))
    search_query = request.args.get("search", "").strip().lower()

    if search_query:
        images = [img for img in images if search_query in img["prompt"].lower()]

    return jsonify(images[offset:offset + limit])


@app.route("/serve_image/<path:filename>")
def serve_image(filename):
    file_path = os.path.join(IMAGE_FOLDER, filename)
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404
    return send_from_directory(IMAGE_FOLDER, filename)


@app.route("/serve_thumbnail/<path:filename>")
def serve_thumbnail(filename):
    file_path = os.path.join(THUMB_FOLDER, filename)
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404
    return send_from_directory(THUMB_FOLDER, filename)


@app.route("/check_updates/<path:folder>")
def check_updates(folder=""):
    folder_path = os.path.abspath(os.path.join(IMAGE_FOLDER, folder))

    if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
        return jsonify({"count": 0})

    image_count = 0
    for file in os.listdir(folder_path):
        file_path = os.path.join(folder_path, file)
        if file.lower().endswith(tuple(ALLOWED_EXTENSIONS)) and os.path.isfile(file_path):
            image_count += 1
            create_thumbnail(file_path)

    return jsonify({"count": image_count})


@app.route("/delete_image", methods=["POST"])
def delete_image():
    data = request.get_json()
    filename = data.get("filename")

    if not filename:
        return jsonify({"error": "Filename is required"}), 400

    file_path = os.path.join(IMAGE_FOLDER, filename)
    thumb_path = os.path.join(THUMB_FOLDER, filename).replace(".png", ".webp")

    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404

    try:
        os.remove(file_path)
        if os.path.exists(thumb_path):
            os.remove(thumb_path)

        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def open_browser():
    time.sleep(1)
    webbrowser.open("http://127.0.0.1:5000")


if __name__ == "__main__":
    threading.Thread(target=open_browser, daemon=True).start()
    app.run(debug=False)

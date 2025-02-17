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
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__, static_folder="static", template_folder="templates")
app.logger.setLevel(logging.INFO)
CONFIG_FILE = "config.json"
ALLOWED_EXTENSIONS = {".png", ".jpg"}


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "image_folder": "static/images",
        "images_per_row": 6,
        "thumbnail_size": 512,
        "items_per_page": 20
    }


config = load_config()
IMAGE_FOLDER = os.path.abspath(config["image_folder"])


def get_relative_path(absolute_path):
    return absolute_path.replace(IMAGE_FOLDER, "").lstrip(os.sep).replace("\\", "/")


def get_metadata_path(image_path):
    """ Возвращает путь к JSON-файлу метаданных для данного изображения """
    return image_path.rsplit(".", 1)[0] + ".json"


def extract_prompt(image_path):
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


def load_metadata(image_path):
    """ Загружает метаданные из JSON-файла, если он существует, иначе создаёт их """
    metadata_path = get_metadata_path(image_path)
    metadata = {}
    need_save = False  # Флаг, чтобы не сохранять лишний раз

    # Если JSON-файл существует, пробуем его загрузить
    if os.path.exists(metadata_path):
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
        except (json.JSONDecodeError, OSError):
            app.logger.error(f"Ошибка чтения JSON-файла: {metadata_path}")
            metadata = {}  # Если не удалось прочитать, создаём пустой словарь

    # Проверяем, есть ли нужные поля, и добавляем их при необходимости
    if "prompt" not in metadata:
        metadata["prompt"] = extract_prompt(image_path)
        need_save = True

    if "checked" not in metadata:
        metadata["checked"] = False
        need_save = True

    if "rating" not in metadata:
        metadata["rating"] = 0
        need_save = True

    # Если что-то изменилось, сохраняем обновлённые метаданные
    if need_save:
        save_metadata(image_path, metadata)

    return metadata


def save_metadata(image_path, metadata):
    """ Сохраняет метаданные в JSON-файл """
    metadata_path = get_metadata_path(image_path)
    try:
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=4)
    except OSError:
        app.logger.error(f"Ошибка записи JSON-файла: {metadata_path}")


def create_thumbnail(image_path, thumb_path):
    for _ in range(5):
        try:
            with Image.open(image_path) as img:
                img.thumbnail((config["thumbnail_size"], config["thumbnail_size"]))
                img.save(thumb_path, "WEBP")
                return
        except (OSError, UnidentifiedImageError):
            app.logger.error(f"File {image_path} is not ready yet. Waiting...")
            time.sleep(1)
    app.logger.error(f"Error creating thumbnail for {image_path}: the file is either corrupted or not fully written.")


def process_image(image_path):
    """Создаёт миниатюру, загружает/сохраняет метаданные"""
    metadata = load_metadata(image_path)

    thumb_path = image_path.rsplit(".", 1)[0] + ".webp"  # Миниатюра в той же директории
    if not os.path.exists(thumb_path) or os.path.getmtime(image_path) > os.path.getmtime(thumb_path):
        create_thumbnail(image_path, thumb_path)  # Создаём миниатюру

    return {
        "filename": get_relative_path(image_path),
        "thumbnail": get_relative_path(thumb_path),
        "metadata": metadata
    }


def get_sorted_images(folder_path, sort_by="date", order="asc"):
    file_list = sorted(
        (os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.lower().endswith(".png")),
        key=os.path.getmtime,  # По умолчанию сортируем по дате создания
        reverse=(order == "desc")  # Убывающий порядок
    )

    # Обрабатываем файлы и загружаем метаданные
    with ThreadPoolExecutor(max_workers=10) as executor:
        images = list(executor.map(process_image, file_list))

    # Применяем сортировку по параметрам
    if sort_by == "filename":
        images.sort(key=lambda img: img["filename"].lower(), reverse=(order == "desc"))
    elif sort_by == "prompt":
        images.sort(key=lambda img: img["metadata"].get("prompt", "").lower(), reverse=(order == "desc"))
    elif sort_by == "rating":
        images.sort(key=lambda img: img["metadata"].get("rating", 0), reverse=(order == "desc"))

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

    sort_by = request.args.get("sort_by", "date")  # date, filename, prompt
    order = request.args.get("order", "asc")  # asc, desc
    images = get_sorted_images(folder_path, sort_by, order)

    limit = int(request.args.get("limit", config["items_per_page"]))
    offset = int(request.args.get("offset", 0))
    search_query = request.args.get("search", "").strip().lower()

    if search_query:
        images = [img for img in images if search_query in img["metadata"].get("prompt", "").lower()]

    return jsonify(images[offset:offset + limit])


@app.route("/serve_image/<path:filename>")
def serve_image(filename):
    file_path = os.path.join(IMAGE_FOLDER, filename)
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404
    return send_from_directory(IMAGE_FOLDER, filename)


@app.route("/serve_thumbnail/<path:filename>")
def serve_thumbnail(filename):
    file_path = os.path.join(IMAGE_FOLDER, filename)
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404
    return send_from_directory(IMAGE_FOLDER, filename)


@app.route("/delete_image", methods=["POST"])
def delete_image():
    data = request.get_json()
    filename = data.get("filename")

    if not filename:
        return jsonify({"error": "Filename is required"}), 400

    file_path = os.path.join(IMAGE_FOLDER, filename)
    thumb_path = os.path.join(IMAGE_FOLDER, filename).replace(".png", ".webp")
    meta_path = os.path.join(IMAGE_FOLDER, filename).replace(".png", ".json")

    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404

    try:
        os.remove(file_path)
        if os.path.exists(thumb_path):
            os.remove(thumb_path)
        if os.path.exists(meta_path):
            os.remove(meta_path)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/update_metadata", methods=["POST"])
def update_metadata():
    data = request.get_json()
    filename = data.get("filename")
    if filename is None:
        return jsonify({"error": "Invalid request"}), 400

    file_path = os.path.join(IMAGE_FOLDER, filename)
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404

    metadata = load_metadata(file_path)

    checked = data.get("checked")
    if checked is not None:
        metadata["checked"] = checked
    rating = data.get("rating")
    if rating is not None:
        metadata["rating"] = rating

    save_metadata(file_path, metadata)

    return jsonify({"success": True})


def open_browser():
    time.sleep(1)
    webbrowser.open("http://127.0.0.1:5000")


if __name__ == "__main__":
    threading.Thread(target=open_browser, daemon=True).start()
    app.run(host="0.0.0.0", debug=False)

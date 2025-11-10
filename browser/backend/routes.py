import os
import json
import time
import logging
import threading
from functools import wraps
from urllib.parse import unquote

from flask import Blueprint, request, jsonify, render_template, send_from_directory, Response

from config import config
from paths import build_folder_tree, get_absolute_path
from services import ImageService, MetadataService, FavoritesService, BookmarksService
from progress import progress_manager
from image import collect_images, needs_processing
from metadata import metadata_store

logger = logging.getLogger(__name__)
routes = Blueprint("routes", __name__)

ERROR_HANDLERS = {
    FileNotFoundError: (404, lambda e: str(e)),
    ValueError: (400, lambda e: str(e)),
    PermissionError: (403, lambda e: str(e)),
    OSError: (500, lambda e: (logger.error(f"Ошибка операции с файлом: {e}"), str(e))[1])
}


def _validate_json_request():
    if not request.is_json:
        raise ValueError("Запрос должен быть JSON")
    data = request.get_json()
    if not data:
        raise ValueError("Тело запроса не может быть пустым")
    return data


def _get_validated_folder_path(subpath: str):
    if subpath:
        subpath = unquote(subpath)
    folder_path = get_absolute_path(subpath) if subpath else None
    if folder_path and not os.path.isdir(folder_path):
        raise FileNotFoundError(f"Путь не существует: {folder_path}")
    return folder_path


def _parse_search_scope(raw_search: str, folder_path: str):
    raw_search = raw_search.strip()
    if raw_search.lower().startswith("g:"):
        return None, raw_search[2:].strip()
    return folder_path, raw_search


def _get_validated_path_and_search(data):
    subpath = data.get("path", "")
    if subpath:
        subpath = unquote(subpath)
    folder_path = _get_validated_folder_path(subpath)
    search_folder_path, search = _parse_search_scope(data.get("search", ""), folder_path)
    return search_folder_path, search


def handle_route_errors(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except tuple(ERROR_HANDLERS.keys()) as e:
            status, get_message = ERROR_HANDLERS[type(e)]
            return jsonify({"error": get_message(e)}), status
        except Exception as e:
            logger.exception(f"Ошибка в {f.__name__}: {e}")
            return jsonify({"error": "Внутренняя ошибка сервера"}), 500
    return wrapper


@routes.errorhandler(FileNotFoundError)
def handle_file_not_found(error: FileNotFoundError):
    return jsonify({"error": str(error)}), 404


@routes.errorhandler(ValueError)
def handle_value_error(error: ValueError):
    return jsonify({"error": str(error)}), 400


@routes.errorhandler(PermissionError)
def handle_permission_error(error: PermissionError):
    return jsonify({"error": str(error)}), 403


@routes.errorhandler(OSError)
def handle_os_error(error: OSError):
    logger.error(f"Ошибка операции с файлом: {error}")
    return jsonify({"error": str(error)}), 500


@routes.route("/")
@routes.route("/<path:subpath>")
@handle_route_errors
def index(subpath: str = ""):
    folder_path = get_absolute_path(subpath)
    if not os.path.isdir(folder_path):
        raise FileNotFoundError("Путь не существует")

    return render_template(
        "index.html",
        folder_tree=build_folder_tree(config.IMAGE_FOLDER)
    )


@routes.route("/images/<path:subpath>")
@handle_route_errors
def get_images(subpath: str = ""):
    folder_path = get_absolute_path(subpath)
    if not os.path.isdir(folder_path):
        raise FileNotFoundError("Путь не существует")

    try:
        limit = int(request.args.get("limit") or config.ITEMS_PER_PAGE)
        offset = int(request.args.get("offset") or 0)
    except ValueError:
        raise ValueError("Неверные параметры пагинации")

    if limit < 1 or limit > 1000:
        raise ValueError("Лимит должен быть от 1 до 1000")
    if offset < 0:
        raise ValueError("Смещение должно быть неотрицательным")

    sort_by = request.args.get("sort_by", "date")
    order = request.args.get("order", "asc")
    valid_sort_fields = {"date", "filename", "prompt", "rating", "tags", "size", "hash", "random"}
    valid_orders = {"asc", "desc"}
    if sort_by not in valid_sort_fields:
        raise ValueError(f"Неверное sort_by: {sort_by}")
    if order not in valid_orders:
        raise ValueError(f"Неверный order: {order}")

    search_folder_path, search = _parse_search_scope(request.args.get("search", ""), folder_path)

    images = ImageService.get_images(
        folder_path=search_folder_path,
        search=search,
        sort_by=sort_by,
        order=order,
        limit=limit,
        offset=offset
    )

    return jsonify(images)


@routes.route("/serve_image/<path:filename>")
@routes.route("/serve_thumbnail/<path:filename>")
@handle_route_errors
def serve_file(filename: str):
    path = get_absolute_path(filename)
    if not os.path.exists(path):
        raise FileNotFoundError("Файл не найден")

    if not os.path.abspath(path).startswith(os.path.abspath(config.IMAGE_FOLDER)):
        raise PermissionError("Доступ к файлу запрещен")

    return send_from_directory(config.IMAGE_FOLDER, filename)


@routes.route("/delete_image", methods=["POST"])
@handle_route_errors
def delete_image():
    data = _validate_json_request()
    metadata_id = data.get("id")
    if not metadata_id or not isinstance(metadata_id, str):
        raise ValueError("ID метаданных обязательно и должно быть строкой")

    ImageService.delete_image(metadata_id)
    return jsonify({"success": True})


@routes.route("/update_metadata", methods=["POST"])
@handle_route_errors
def update_metadata():
    data = _validate_json_request()

    metadata_ids = data.get("ids") or ([data.get("id")] if data.get("id") else [])
    if not metadata_ids or not isinstance(metadata_ids, list):
        raise ValueError("Не указаны ID метаданных")

    metadata_ids = [id for id in metadata_ids if id]
    if not metadata_ids:
        raise ValueError("Не указаны ID метаданных")

    updates = {key: data[key] for key in ("checked", "rating", "tags") if key in data}
    if not updates:
        raise ValueError("Нет полей метаданных для обновления")

    MetadataService.update_metadata(metadata_ids, updates)
    return jsonify({"success": True})


@routes.route("/copy_to_favorites", methods=["POST"])
@handle_route_errors
def copy_to_favorites():
    data = _validate_json_request()
    metadata_id = data.get("id")
    if not metadata_id or not isinstance(metadata_id, str):
        raise ValueError("ID метаданных обязательно и должно быть строкой")

    FavoritesService.copy_to_favorites(metadata_id)
    return jsonify({"success": True})


@routes.route("/uncheck_all", methods=["POST"])
@handle_route_errors
def uncheck_all():
    data = _validate_json_request()
    search_folder_path, search = _get_validated_path_and_search(data)
    count = MetadataService.uncheck_all(search_folder_path, search)
    return jsonify({"success": True, "count": count})


@routes.route("/delete_metadata", methods=["POST"])
@handle_route_errors
def delete_metadata():
    data = _validate_json_request()
    search_folder_path, search = _get_validated_path_and_search(data)
    count = MetadataService.delete_metadata(search_folder_path, search)
    return jsonify({"success": True, "count": count})


@routes.route("/check_processing_needed", methods=["POST"])
@handle_route_errors
def check_processing_needed():
    data = _validate_json_request()
    folder_path = _get_validated_folder_path(data.get("path", ""))
    return jsonify({"needs_processing": needs_processing(folder=folder_path)})


@routes.route("/progress/<task_id>")
def progress_stream(task_id: str):
    def generate():
        while True:
            progress = progress_manager.get(task_id)
            if not progress:
                yield f"data: {json.dumps({'error': 'Task not found'})}\n\n"
                break

            percentage = (progress["processed"] / progress["total"] * 100) if progress["total"] > 0 else 0
            progress_data = {
                "processed": progress["processed"],
                "total": progress["total"],
                "status": progress["status"],
                "message": progress["message"],
                "percentage": percentage
            }

            if progress.get("error"):
                progress_data["error"] = progress["error"]

            yield f"data: {json.dumps(progress_data)}\n\n"

            if progress["status"] in ("completed", "error"):
                break

            time.sleep(0.5)

    response = Response(generate(), mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    return response


@routes.route("/process_images", methods=["POST"])
@handle_route_errors
def process_images():
    data = _validate_json_request()
    folder_path = _get_validated_folder_path(data.get("path", ""))
    task_id = progress_manager.create_task()

    def process_task():
        try:
            def progress_callback(processed, total, message):
                progress_manager.update(task_id, processed, total, message)
            collect_images(folder=folder_path, progress_callback=progress_callback)
            progress_manager.complete(task_id, "")
        except Exception as e:
            logger.exception(f"Ошибка обработки изображений: {e}")
            progress_manager.error(task_id, str(e))

    threading.Thread(target=process_task, daemon=True).start()
    return jsonify({"success": True, "task_id": task_id})


@routes.route("/bookmarks", methods=["GET"])
@handle_route_errors
def get_bookmarks():
    bookmarks = BookmarksService.get_all()
    return jsonify(bookmarks)


@routes.route("/bookmarks", methods=["POST"])
@handle_route_errors
def add_bookmark():
    data = _validate_json_request()
    metadata_id = data.get("id")
    if not metadata_id or not isinstance(metadata_id, str):
        raise ValueError("ID метаданных обязательно и должно быть строкой")
    
    metadata = MetadataService.get_by_id(metadata_id) if hasattr(MetadataService, "get_by_id") else None
    if not metadata:
        metadata = metadata_store.get_by_id(metadata_id)
    if not metadata:
        raise FileNotFoundError(f"Метаданные с ID {metadata_id} не найдены")
    
    image_data = {
        "image_path": metadata.get("image_path", ""),
        "prompt": metadata.get("prompt", ""),
        "sort_by": data.get("sort_by", "date-desc"),
        "search_query": data.get("search_query", "")
    }
    
    BookmarksService.add(metadata_id, image_data)
    return jsonify({"success": True})


@routes.route("/bookmarks/<metadata_id>", methods=["DELETE"])
@handle_route_errors
def remove_bookmark(metadata_id: str):
    if not metadata_id:
        raise ValueError("ID метаданных обязательно")
    
    removed = BookmarksService.remove(metadata_id)
    return jsonify({"success": True, "removed": removed})


@routes.route("/bookmarks/<metadata_id>/has", methods=["GET"])
@handle_route_errors
def has_bookmark(metadata_id: str):
    if not metadata_id:
        raise ValueError("ID метаданных обязательно")
    
    has = BookmarksService.has(metadata_id)
    return jsonify({"has": has})

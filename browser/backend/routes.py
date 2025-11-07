"""
API маршруты для приложения просмотра изображений.
"""
import os
import json
import time
import logging
import threading
from urllib.parse import unquote

from flask import Blueprint, request, jsonify, render_template, send_from_directory, Response

from config import config
from paths import build_folder_tree, get_absolute_path
from services import ImageService, MetadataService, FavoritesService
from progress import create_progress_task, update_progress, complete_progress, error_progress, get_progress
from image import collect_images, needs_processing

logger = logging.getLogger(__name__)
routes = Blueprint("routes", __name__)


def _get_validated_folder_path(subpath: str):
    if subpath:
        subpath = unquote(subpath)
    
    folder_path = get_absolute_path(subpath) if subpath else None
    if folder_path and not os.path.isdir(folder_path):
        raise FileNotFoundError(f"Путь не существует: {folder_path}")
    
    return folder_path


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
def index(subpath: str = ""):
    try:
        folder_path = get_absolute_path(subpath)
        if not os.path.isdir(folder_path):
            raise FileNotFoundError("Путь не существует")
        
        return render_template(
            "index.html",
            folder_tree=build_folder_tree(config.IMAGE_FOLDER)
        )
    except Exception as e:
        logger.exception(f"Ошибка рендеринга главной страницы: {e}")
        return jsonify({"error": "Внутренняя ошибка сервера"}), 500


@routes.route("/images/<path:subpath>")
def get_images(subpath: str = ""):
    try:
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
        valid_sort_fields = {"date", "filename", "prompt", "rating", "tags", "size", "hash"}
        valid_orders = {"asc", "desc"}
        if sort_by not in valid_sort_fields:
            raise ValueError(f"Неверное sort_by: {sort_by}")
        if order not in valid_orders:
            raise ValueError(f"Неверный order: {order}")
        
        raw_search = request.args.get("search", "").strip()
        if raw_search.lower().startswith("g:"):
            scope, search = "global", raw_search[2:].strip()
        else:
            scope, search = "current", raw_search
        
        search_folder_path = None if scope == "global" else folder_path
        
        images = ImageService.get_images(
            folder_path=search_folder_path,
            search=search,
            sort_by=sort_by,
            order=order,
            limit=limit,
            offset=offset
        )
        
        return jsonify(images)
    except (FileNotFoundError, ValueError, PermissionError, OSError):
        raise
    except Exception as e:
        logger.exception(f"Ошибка получения изображений: {e}")
        return jsonify({"error": "Внутренняя ошибка сервера"}), 500


@routes.route("/serve_image/<path:filename>")
@routes.route("/serve_thumbnail/<path:filename>")
def serve_file(filename: str):
    try:
        path = get_absolute_path(filename)
        if not os.path.exists(path):
            raise FileNotFoundError("Файл не найден")
        
        if not os.path.abspath(path).startswith(os.path.abspath(config.IMAGE_FOLDER)):
            raise PermissionError("Доступ к файлу запрещен")
        
        return send_from_directory(config.IMAGE_FOLDER, filename)
    except (FileNotFoundError, ValueError, PermissionError, OSError):
        raise
    except Exception as e:
        logger.exception(f"Ошибка отдачи файла: {e}")
        return jsonify({"error": "Внутренняя ошибка сервера"}), 500


@routes.route("/delete_image", methods=["POST"])
def delete_image():
    try:
        if not request.is_json:
            raise ValueError("Запрос должен быть JSON")
        data = request.get_json()
        if not data:
            raise ValueError("Тело запроса не может быть пустым")
        
        filename = data.get("filename")
        if not filename or not isinstance(filename, str):
            raise ValueError("Имя файла обязательно и должно быть строкой")
        
        ImageService.delete_image(filename)
        return jsonify({"success": True})
    except (FileNotFoundError, ValueError, PermissionError, OSError):
        raise
    except Exception as e:
        logger.exception(f"Ошибка удаления изображения: {e}")
        return jsonify({"error": "Внутренняя ошибка сервера"}), 500


@routes.route("/update_metadata", methods=["POST"])
def update_metadata():
    try:
        if not request.is_json:
            raise ValueError("Запрос должен быть JSON")
        data = request.get_json()
        if not data:
            raise ValueError("Тело запроса не может быть пустым")
        
        filenames = data.get("filenames")
        if not filenames:
            filename = data.get("filename")
            if filename:
                filenames = [filename]
        
        if not filenames or not isinstance(filenames, list):
            raise ValueError("Не указаны имена файлов")
        
        # Фильтруем None значения
        filenames = [f for f in filenames if f]
        if not filenames:
            raise ValueError("Не указаны имена файлов")
        
        updates = {}
        for key in ("checked", "rating", "tags"):
            if key in data:
                updates[key] = data[key]
        
        if not updates:
            raise ValueError("Нет полей метаданных для обновления")
        
        MetadataService.update_metadata(filenames, updates)
        return jsonify({"success": True})
    except (FileNotFoundError, ValueError, PermissionError, OSError):
        raise
    except Exception as e:
        logger.exception(f"Ошибка обновления метаданных: {e}")
        return jsonify({"error": "Внутренняя ошибка сервера"}), 500


@routes.route("/copy_to_favorites", methods=["POST"])
def copy_to_favorites():
    try:
        if not request.is_json:
            raise ValueError("Запрос должен быть JSON")
        data = request.get_json()
        if not data:
            raise ValueError("Тело запроса не может быть пустым")
        
        filename = data.get("filename")
        if not filename or not isinstance(filename, str):
            raise ValueError("Имя файла обязательно и должно быть строкой")
        
        FavoritesService.copy_to_favorites(filename)
        return jsonify({"success": True})
    except (FileNotFoundError, ValueError, PermissionError, OSError):
        raise
    except Exception as e:
        logger.exception(f"Ошибка копирования в избранное: {e}")
        return jsonify({"error": "Внутренняя ошибка сервера"}), 500


def _get_validated_path_and_search(data):
    subpath = data.get("path", "")
    raw_search = data.get("search", "").strip()
    
    if subpath:
        subpath = unquote(subpath)
    
    folder_path = _get_validated_folder_path(subpath)
    if raw_search.lower().startswith("g:"):
        scope, search = "global", raw_search[2:].strip()
    else:
        scope, search = "current", raw_search
    search_folder_path = None if scope == "global" else folder_path
    
    return search_folder_path, search


@routes.route("/uncheck_all", methods=["POST"])
def uncheck_all():
    try:
        if not request.is_json:
            raise ValueError("Запрос должен быть JSON")
        data = request.get_json()
        if not data:
            raise ValueError("Тело запроса не может быть пустым")
        
        search_folder_path, search = _get_validated_path_and_search(data)
        
        count = MetadataService.uncheck_all(search_folder_path, search)
        return jsonify({"success": True, "count": count})
    except (FileNotFoundError, ValueError, PermissionError, OSError):
        raise
    except Exception as e:
        logger.exception(f"Ошибка снятия отметок: {e}")
        return jsonify({"error": "Внутренняя ошибка сервера"}), 500


@routes.route("/delete_metadata", methods=["POST"])
def delete_metadata():
    try:
        if not request.is_json:
            raise ValueError("Запрос должен быть JSON")
        data = request.get_json()
        if not data:
            raise ValueError("Тело запроса не может быть пустым")
        
        search_folder_path, search = _get_validated_path_and_search(data)
        
        count = MetadataService.delete_metadata(search_folder_path, search)
        return jsonify({"success": True, "count": count})
    except (FileNotFoundError, ValueError, PermissionError, OSError):
        raise
    except Exception as e:
        logger.exception(f"Ошибка удаления метаданных: {e}")
        return jsonify({"error": "Внутренняя ошибка сервера"}), 500


@routes.route("/check_processing_needed", methods=["POST"])
def check_processing_needed():
    try:
        if not request.is_json:
            raise ValueError("Запрос должен быть JSON")
        data = request.get_json()
        if not data:
            raise ValueError("Тело запроса не может быть пустым")
        
        folder_path = _get_validated_folder_path(data.get("path", ""))
        
        return jsonify({"needs_processing": needs_processing(folder=folder_path)})
    except (FileNotFoundError, ValueError, PermissionError, OSError):
        raise
    except Exception as e:
        logger.exception(f"Ошибка проверки необходимости обработки: {e}")
        return jsonify({"error": "Внутренняя ошибка сервера"}), 500


@routes.route("/progress/<task_id>")
def progress_stream(task_id: str):
    def generate():
        while True:
            progress = get_progress(task_id)
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
def process_images():
    try:
        if not request.is_json:
            raise ValueError("Запрос должен быть JSON")
        data = request.get_json()
        if not data:
            raise ValueError("Тело запроса не может быть пустым")
        
        folder_path = _get_validated_folder_path(data.get("path", ""))
        
        task_id = create_progress_task()
        
        def process_task():
            try:
                def progress_callback(processed, total, message):
                    update_progress(task_id, processed, total, message)
                
                collect_images(folder=folder_path, progress_callback=progress_callback)
                complete_progress(task_id, "Обработка завершена")
            except Exception as e:
                logger.exception(f"Ошибка обработки изображений: {e}")
                error_progress(task_id, str(e))
        
        threading.Thread(target=process_task, daemon=True).start()
        
        return jsonify({"success": True, "task_id": task_id})
    except (FileNotFoundError, ValueError, PermissionError, OSError):
        raise
    except Exception as e:
        logger.exception(f"Ошибка запуска обработки: {e}")
        return jsonify({"error": "Внутренняя ошибка сервера"}), 500

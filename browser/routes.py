"""
API маршруты для приложения просмотра изображений.
"""
import os
import logging
from urllib.parse import unquote

from flask import Blueprint, request, jsonify, render_template, send_from_directory, Response
import threading

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
from progress import create_progress_task, update_progress, complete_progress, error_progress, get_progress
from image import collect_images, needs_processing

logger = logging.getLogger(__name__)
routes = Blueprint("routes", __name__)


def _get_validated_folder_path(subpath: str):
    """Валидирует и возвращает абсолютный путь к папке."""
    if subpath:
        subpath = unquote(subpath)
    
    folder_path = get_absolute_path(subpath) if subpath else None
    if folder_path and not os.path.isdir(folder_path):
        raise PathNotFoundError(f"Путь не существует: {folder_path}")
    
    return folder_path


@routes.errorhandler(PathNotFoundError)
def handle_path_not_found(error: PathNotFoundError):
    return jsonify({"error": str(error)}), 404


@routes.errorhandler(InvalidRequestError)
def handle_invalid_request(error: InvalidRequestError):
    return jsonify({"error": str(error)}), 400


@routes.errorhandler(FileOperationError)
def handle_file_operation_error(error: FileOperationError):
    logger.error(f"Ошибка операции с файлом: {error}")
    return jsonify({"error": str(error)}), 500


@routes.route("/")
@routes.route("/<path:subpath>")
def index(subpath: str = ""):
    try:
        folder_path = get_absolute_path(subpath)
        if not os.path.isdir(folder_path):
            raise PathNotFoundError("Путь не существует")
        
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
            raise PathNotFoundError("Путь не существует")
        
        limit, offset = validate_pagination_params(request, config.ITEMS_PER_PAGE)
        sort_by, order = validate_sort_params(request)
        raw_search = request.args.get("search", "")
        scope, search = validate_search_query(raw_search)
        
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
    except (PathNotFoundError, InvalidRequestError):
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
            raise PathNotFoundError("Файл не найден")
        
        return send_from_directory(config.IMAGE_FOLDER, filename)
    except PathNotFoundError:
        raise
    except Exception as e:
        logger.exception(f"Ошибка отдачи файла: {e}")
        return jsonify({"error": "Внутренняя ошибка сервера"}), 500


@routes.route("/delete_image", methods=["POST"])
def delete_image():
    try:
        data = validate_json_request(request)
        filename = validate_filename(data)
        
        ImageService.delete_image(filename)
        return jsonify({"success": True})
    except (InvalidRequestError, FileOperationError):
        raise
    except Exception as e:
        logger.exception(f"Ошибка удаления изображения: {e}")
        return jsonify({"error": "Внутренняя ошибка сервера"}), 500


@routes.route("/update_metadata", methods=["POST"])
def update_metadata():
    try:
        data = validate_json_request(request)
        filenames = data.get("filenames") or [data.get("filename")]
        
        if not filenames or not isinstance(filenames, list):
            raise InvalidRequestError("Не указаны имена файлов")
        
        updates = {}
        for key in ("checked", "rating", "tags"):
            if key in data:
                updates[key] = data[key]
        
        if not updates:
            raise InvalidRequestError("Нет полей метаданных для обновления")
        
        MetadataService.update_metadata(filenames, updates)
        return jsonify({"success": True})
    except (InvalidRequestError, FileOperationError):
        raise
    except Exception as e:
        logger.exception(f"Ошибка обновления метаданных: {e}")
        return jsonify({"error": "Внутренняя ошибка сервера"}), 500


@routes.route("/copy_to_favorites", methods=["POST"])
def copy_to_favorites():
    try:
        data = validate_json_request(request)
        filename = validate_filename(data)
        
        FavoritesService.copy_to_favorites(filename)
        return jsonify({"success": True})
    except (InvalidRequestError, FileOperationError):
        raise
    except Exception as e:
        logger.exception(f"Ошибка копирования в избранное: {e}")
        return jsonify({"error": "Внутренняя ошибка сервера"}), 500


@routes.route("/all_tags")
def get_all_tags():
    try:
        return jsonify(get_all_tags_cached())
    except Exception as e:
        logger.exception(f"Ошибка получения тегов: {e}")
        return jsonify({"error": "Внутренняя ошибка сервера"}), 500


@routes.route("/uncheck_all", methods=["POST"])
def uncheck_all():
    try:
        data = validate_json_request(request)
        subpath = data.get("path", "")
        raw_search = data.get("search", "")
        
        if subpath:
            subpath = unquote(subpath)
        
        try:
            folder_path = get_absolute_path(subpath)
            folder_path = os.path.normpath(folder_path)
            
            if not os.path.isdir(folder_path):
                raise PathNotFoundError(f"Путь не существует: {folder_path}")
        except Exception as e:
            logger.exception(f"Ошибка обработки пути: {e}")
            raise InvalidRequestError(f"Ошибка обработки пути: {str(e)}")
        
        scope, search = validate_search_query(raw_search)
        search_folder_path = None if scope == "global" else folder_path
        
        count = MetadataService.uncheck_all(search_folder_path, search)
        
        return jsonify({"success": True, "count": count})
    except (PathNotFoundError, InvalidRequestError):
        raise
    except Exception as e:
        logger.exception(f"Ошибка снятия отметок: {e}")
        return jsonify({"error": "Внутренняя ошибка сервера"}), 500


@routes.route("/delete_metadata", methods=["POST"])
def delete_metadata():
    try:
        data = validate_json_request(request)
        subpath = data.get("path", "")
        raw_search = data.get("search", "")
        
        if subpath:
            subpath = unquote(subpath)
        
        try:
            folder_path = get_absolute_path(subpath)
            folder_path = os.path.normpath(folder_path)
            
            if not os.path.isdir(folder_path):
                raise PathNotFoundError(f"Путь не существует: {folder_path}")
        except Exception as e:
            logger.exception(f"Ошибка обработки пути: {e}")
            raise InvalidRequestError(f"Ошибка обработки пути: {str(e)}")
        
        scope, search = validate_search_query(raw_search)
        search_folder_path = None if scope == "global" else folder_path
        
        count = MetadataService.delete_metadata(search_folder_path, search)
        
        return jsonify({"success": True, "count": count})
    except (PathNotFoundError, InvalidRequestError):
        raise
    except Exception as e:
        logger.exception(f"Ошибка удаления метаданных: {e}")
        return jsonify({"error": "Внутренняя ошибка сервера"}), 500


@routes.route("/check_processing_needed", methods=["POST"])
def check_processing_needed():
    """Проверяет, нужна ли обработка изображений для указанной папки."""
    try:
        data = validate_json_request(request)
        folder_path = _get_validated_folder_path(data.get("path", ""))
        
        return jsonify({"needs_processing": needs_processing(folder=folder_path)})
    except (PathNotFoundError, InvalidRequestError):
        raise
    except Exception as e:
        logger.exception(f"Ошибка проверки необходимости обработки: {e}")
        return jsonify({"error": "Внутренняя ошибка сервера"}), 500


@routes.route("/progress/<task_id>")
def progress_stream(task_id: str):
    """SSE эндпоинт для получения прогресса обработки изображений."""
    import json
    import time
    
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
    """Запускает обработку изображений в фоновом режиме и возвращает task_id."""
    try:
        data = validate_json_request(request)
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
    except (PathNotFoundError, InvalidRequestError):
        raise
    except Exception as e:
        logger.exception(f"Ошибка запуска обработки: {e}")
        return jsonify({"error": "Внутренняя ошибка сервера"}), 500

"""
API маршруты для приложения просмотра изображений.
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

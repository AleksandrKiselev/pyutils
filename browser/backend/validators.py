"""
Утилиты валидации входных данных.
"""
from typing import Tuple
from flask import Request
from exceptions import InvalidRequestError


def validate_search_query(search: str) -> Tuple[str, str]:
    search = search.strip()
    if search.lower().startswith("g:"):
        return "global", search[2:].strip()
    return "current", search


def validate_pagination_params(request: Request, default_limit: int = 20) -> Tuple[int, int]:
    try:
        limit = int(request.args.get("limit") or default_limit)
        offset = int(request.args.get("offset") or 0)
        
        if limit < 1 or limit > 1000:
            raise InvalidRequestError("Лимит должен быть от 1 до 1000")
        if offset < 0:
            raise InvalidRequestError("Смещение должно быть неотрицательным")
            
        return limit, offset
    except ValueError as e:
        raise InvalidRequestError(f"Неверные параметры пагинации: {e}")


def validate_sort_params(request: Request) -> Tuple[str, str]:
    sort_by = request.args.get("sort_by", "date")
    order = request.args.get("order", "asc")
    
    valid_sort_fields = {"date", "filename", "prompt", "rating", "tags", "size"}
    valid_orders = {"asc", "desc"}
    
    if sort_by not in valid_sort_fields:
        raise InvalidRequestError(f"Неверное sort_by: {sort_by}. Должно быть одно из {valid_sort_fields}")
    if order not in valid_orders:
        raise InvalidRequestError(f"Неверный order: {order}. Должно быть одно из {valid_orders}")
        
    return sort_by, order


def validate_json_request(request: Request) -> dict:
    if not request.is_json:
        raise InvalidRequestError("Запрос должен быть JSON")
    
    data = request.get_json()
    if not data:
        raise InvalidRequestError("Тело запроса не может быть пустым")
        
    return data


def validate_filename(data: dict) -> str:
    filename = data.get("filename")
    if not filename or not isinstance(filename, str):
        raise InvalidRequestError("Имя файла обязательно и должно быть строкой")
    return filename


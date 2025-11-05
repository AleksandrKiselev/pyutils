"""
Input validation utilities for the image browser application.
"""
from typing import Optional, Tuple
from flask import Request
from exceptions import InvalidRequestError


def validate_search_query(search: str) -> Tuple[str, str]:
    """
    Validate and parse search query.
    
    Args:
        search: Raw search string
        
    Returns:
        Tuple of (scope, query) where scope is 'global' or 'current'
    """
    search = search.strip()
    if search.lower().startswith("g:"):
        return "global", search[2:].strip()
    return "current", search


def validate_pagination_params(request: Request, default_limit: int = 20) -> Tuple[int, int]:
    """
    Validate and extract pagination parameters from request.
    
    Args:
        request: Flask request object
        default_limit: Default items per page
        
    Returns:
        Tuple of (limit, offset)
    """
    try:
        limit = int(request.args.get("limit") or default_limit)
        offset = int(request.args.get("offset") or 0)
        
        if limit < 1 or limit > 1000:
            raise InvalidRequestError("Limit must be between 1 and 1000")
        if offset < 0:
            raise InvalidRequestError("Offset must be non-negative")
            
        return limit, offset
    except ValueError as e:
        raise InvalidRequestError(f"Invalid pagination parameters: {e}")


def validate_sort_params(request: Request) -> Tuple[str, str]:
    """
    Validate and extract sort parameters from request.
    
    Args:
        request: Flask request object
        
    Returns:
        Tuple of (sort_by, order)
    """
    sort_by = request.args.get("sort_by", "date")
    order = request.args.get("order", "asc")
    
    valid_sort_fields = {"date", "filename", "prompt", "rating", "tags"}
    valid_orders = {"asc", "desc"}
    
    if sort_by not in valid_sort_fields:
        raise InvalidRequestError(f"Invalid sort_by: {sort_by}. Must be one of {valid_sort_fields}")
    if order not in valid_orders:
        raise InvalidRequestError(f"Invalid order: {order}. Must be one of {valid_orders}")
        
    return sort_by, order


def validate_json_request(request: Request) -> dict:
    """
    Validate that request contains valid JSON.
    
    Args:
        request: Flask request object
        
    Returns:
        Parsed JSON data
        
    Raises:
        InvalidRequestError: If request is not JSON or is empty
    """
    if not request.is_json:
        raise InvalidRequestError("Request must be JSON")
    
    data = request.get_json()
    if not data:
        raise InvalidRequestError("Request body cannot be empty")
        
    return data


def validate_filename(data: dict) -> str:
    """
    Validate and extract filename from request data.
    
    Args:
        data: Request JSON data
        
    Returns:
        Filename string
        
    Raises:
        InvalidRequestError: If filename is missing or invalid
    """
    filename = data.get("filename")
    if not filename or not isinstance(filename, str):
        raise InvalidRequestError("Filename is required and must be a string")
    return filename


"""
Тесты для модуля validators.py
"""
import pytest
from unittest.mock import Mock

from validators import (
    validate_search_query,
    validate_pagination_params,
    validate_sort_params,
    validate_json_request,
    validate_filename
)
from exceptions import InvalidRequestError


class TestValidateSearchQuery:
    """Тесты для validate_search_query."""
    
    def test_global_search(self):
        """Тест глобального поиска с префиксом g:."""
        scope, search = validate_search_query("g:test query")
        assert scope == "global"
        assert search == "test query"
    
    def test_current_search(self):
        """Тест локального поиска без префикса."""
        scope, search = validate_search_query("test query")
        assert scope == "current"
        assert search == "test query"
    
    def test_empty_search(self):
        """Тест пустого поиска."""
        scope, search = validate_search_query("")
        assert scope == "current"
        assert search == ""
    
    def test_stripped_search(self):
        """Тест обрезки пробелов."""
        scope, search = validate_search_query("  test  ")
        assert scope == "current"
        assert search == "test"
    
    def test_global_search_lowercase(self):
        """Тест глобального поиска с заглавными буквами."""
        scope, search = validate_search_query("G:test")
        assert scope == "global"
        assert search == "test"


class TestValidatePaginationParams:
    """Тесты для validate_pagination_params."""
    
    def test_default_params(self):
        """Тест параметров по умолчанию."""
        request = Mock()
        request.args = {}
        limit, offset = validate_pagination_params(request, default_limit=20)
        assert limit == 20
        assert offset == 0
    
    def test_custom_params(self):
        """Тест пользовательских параметров."""
        request = Mock()
        request.args = {"limit": "50", "offset": "10"}
        limit, offset = validate_pagination_params(request, default_limit=20)
        assert limit == 50
        assert offset == 10
    
    def test_limit_too_small(self):
        """Тест слишком маленького лимита."""
        request = Mock()
        request.args = {"limit": "0"}
        with pytest.raises(InvalidRequestError, match="Лимит должен быть от 1 до 1000"):
            validate_pagination_params(request)
    
    def test_limit_too_large(self):
        """Тест слишком большого лимита."""
        request = Mock()
        request.args = {"limit": "2000"}
        with pytest.raises(InvalidRequestError, match="Лимит должен быть от 1 до 1000"):
            validate_pagination_params(request)
    
    def test_negative_offset(self):
        """Тест отрицательного смещения."""
        request = Mock()
        request.args = {"offset": "-5"}
        with pytest.raises(InvalidRequestError, match="Смещение должно быть неотрицательным"):
            validate_pagination_params(request)
    
    def test_invalid_limit_type(self):
        """Тест неверного типа лимита."""
        request = Mock()
        request.args = {"limit": "not_a_number"}
        with pytest.raises(InvalidRequestError):
            validate_pagination_params(request)
    
    def test_invalid_offset_type(self):
        """Тест неверного типа смещения."""
        request = Mock()
        request.args = {"offset": "not_a_number"}
        with pytest.raises(InvalidRequestError):
            validate_pagination_params(request)


class TestValidateSortParams:
    """Тесты для validate_sort_params."""
    
    def test_default_params(self):
        """Тест параметров по умолчанию."""
        request = Mock()
        request.args = {}
        sort_by, order = validate_sort_params(request)
        assert sort_by == "date"
        assert order == "asc"
    
    def test_valid_params(self):
        """Тест валидных параметров."""
        request = Mock()
        request.args = {"sort_by": "filename", "order": "desc"}
        sort_by, order = validate_sort_params(request)
        assert sort_by == "filename"
        assert order == "desc"
    
    def test_all_valid_sort_fields(self):
        """Тест всех валидных полей сортировки."""
        valid_fields = {"date", "filename", "prompt", "rating", "tags"}
        request = Mock()
        for field in valid_fields:
            request.args = {"sort_by": field}
            sort_by, _ = validate_sort_params(request)
            assert sort_by == field
    
    def test_invalid_sort_field(self):
        """Тест неверного поля сортировки."""
        request = Mock()
        request.args = {"sort_by": "invalid_field"}
        with pytest.raises(InvalidRequestError):
            validate_sort_params(request)
    
    def test_invalid_order(self):
        """Тест неверного порядка сортировки."""
        request = Mock()
        request.args = {"order": "invalid_order"}
        with pytest.raises(InvalidRequestError):
            validate_sort_params(request)


class TestValidateJsonRequest:
    """Тесты для validate_json_request."""
    
    def test_valid_json_request(self):
        """Тест валидного JSON запроса."""
        request = Mock()
        request.is_json = True
        request.get_json.return_value = {"key": "value"}
        result = validate_json_request(request)
        assert result == {"key": "value"}
    
    def test_non_json_request(self):
        """Тест не-JSON запроса."""
        request = Mock()
        request.is_json = False
        with pytest.raises(InvalidRequestError, match="Запрос должен быть JSON"):
            validate_json_request(request)
    
    def test_empty_json_request(self):
        """Тест пустого JSON запроса."""
        request = Mock()
        request.is_json = True
        request.get_json.return_value = None
        with pytest.raises(InvalidRequestError, match="Тело запроса не может быть пустым"):
            validate_json_request(request)


class TestValidateFilename:
    """Тесты для validate_filename."""
    
    def test_valid_filename(self):
        """Тест валидного имени файла."""
        data = {"filename": "test.png"}
        result = validate_filename(data)
        assert result == "test.png"
    
    def test_missing_filename(self):
        """Тест отсутствующего имени файла."""
        data = {}
        with pytest.raises(InvalidRequestError, match="Имя файла обязательно"):
            validate_filename(data)
    
    def test_non_string_filename(self):
        """Тест не-строкового имени файла."""
        data = {"filename": 123}
        with pytest.raises(InvalidRequestError, match="должно быть строкой"):
            validate_filename(data)
    
    def test_empty_string_filename(self):
        """Тест пустой строки как имени файла."""
        data = {"filename": ""}
        with pytest.raises(InvalidRequestError, match="Имя файла обязательно"):
            validate_filename(data)


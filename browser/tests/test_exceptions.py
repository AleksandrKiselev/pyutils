"""
Тесты для модуля exceptions.py
"""
import pytest

from exceptions import PathNotFoundError, InvalidRequestError, FileOperationError


def test_path_not_found_error():
    """Тест создания исключения PathNotFoundError."""
    error = PathNotFoundError("Путь не найден")
    assert str(error) == "Путь не найден"
    assert isinstance(error, Exception)


def test_invalid_request_error():
    """Тест создания исключения InvalidRequestError."""
    error = InvalidRequestError("Неверный запрос")
    assert str(error) == "Неверный запрос"
    assert isinstance(error, Exception)


def test_file_operation_error():
    """Тест создания исключения FileOperationError."""
    error = FileOperationError("Ошибка операции с файлом")
    assert str(error) == "Ошибка операции с файлом"
    assert isinstance(error, Exception)


def test_exceptions_inheritance():
    """Тест наследования исключений от Exception."""
    assert issubclass(PathNotFoundError, Exception)
    assert issubclass(InvalidRequestError, Exception)
    assert issubclass(FileOperationError, Exception)


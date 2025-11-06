"""
Тесты для модуля routes.py
"""
import os
import json
import pytest
from unittest.mock import patch, MagicMock, Mock

from flask import Flask
from routes import routes
from exceptions import PathNotFoundError, InvalidRequestError, FileOperationError


@pytest.fixture
def app(temp_image_folder):
    """Создает Flask приложение для тестов."""
    import sys
    import os
    # Получаем путь к папке browser
    browser_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    templates_dir = os.path.join(browser_dir, "templates")
    
    app = Flask(__name__, template_folder=templates_dir)
    app.config['TESTING'] = True
    app.register_blueprint(routes)
    return app


@pytest.fixture
def client(app):
    """Создает тестовый клиент."""
    return app.test_client()


class TestIndexRoute:
    """Тесты для маршрута index."""
    
    def test_index_route(self, client, temp_image_folder, monkeypatch):
        """Тест главной страницы."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder))
        with patch("routes.build_folder_tree") as mock_tree, \
             patch("routes.get_absolute_path") as mock_get_path:
            mock_tree.return_value = {}
            mock_get_path.return_value = temp_image_folder
            response = client.get("/")
            assert response.status_code == 200
    
    def test_index_route_with_subpath(self, client, temp_image_folder, monkeypatch):
        """Тест главной страницы с подпутем."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder))
        subfolder = os.path.join(temp_image_folder, "subfolder")
        os.makedirs(subfolder, exist_ok=True)
        
        with patch("routes.build_folder_tree") as mock_tree, \
             patch("routes.get_absolute_path") as mock_get_path:
            mock_tree.return_value = {}
            mock_get_path.return_value = subfolder
            response = client.get("/subfolder")
            assert response.status_code == 200
    
    def test_index_route_not_found(self, client, temp_image_folder, monkeypatch):
        """Тест главной страницы с несуществующим путем."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder))
        response = client.get("/nonexistent")
        assert response.status_code in [404, 500]  # Может быть 404 или 500 в зависимости от обработки


class TestGetImagesRoute:
    """Тесты для маршрута get_images."""
    
    def test_get_images(self, client, temp_image_folder, monkeypatch):
        """Тест получения изображений."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder, ITEMS_PER_PAGE=20))
        
        with patch("routes.ImageService.get_images") as mock_get, \
             patch("routes.get_absolute_path") as mock_get_path, \
             patch("os.path.isdir") as mock_isdir:
            mock_get_path.return_value = temp_image_folder
            mock_isdir.return_value = True
            mock_get.return_value = [
                {"filename": "img1.png", "metadata": {}}
            ]
            # Используем URL с подпутем, чтобы гарантированно попасть в маршрут /images/<path:subpath>
            response = client.get("/images/subfolder")
            assert response.status_code == 200
            # Проверяем, что ответ валидный JSON
            assert response.is_json
            data = response.get_json()
            assert isinstance(data, list)
            assert len(data) == 1
    
    def test_get_images_with_pagination(self, client, temp_image_folder, monkeypatch):
        """Тест получения изображений с пагинацией."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder, ITEMS_PER_PAGE=20))
        
        with patch("routes.ImageService.get_images") as mock_get, \
             patch("routes.get_absolute_path") as mock_get_path, \
             patch("os.path.isdir") as mock_isdir:
            mock_get_path.return_value = temp_image_folder
            mock_isdir.return_value = True
            mock_get.return_value = []
            response = client.get("/images/subfolder?limit=10&offset=0")
            assert response.status_code == 200
    
    def test_get_images_with_search(self, client, temp_image_folder, monkeypatch):
        """Тест получения изображений с поиском."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder, ITEMS_PER_PAGE=20))
        
        with patch("routes.ImageService.get_images") as mock_get, \
             patch("routes.get_absolute_path") as mock_get_path, \
             patch("os.path.isdir") as mock_isdir:
            mock_get_path.return_value = temp_image_folder
            mock_isdir.return_value = True
            mock_get.return_value = []
            response = client.get("/images/subfolder?search=test")
            assert response.status_code == 200
    
    def test_get_images_invalid_params(self, client, temp_image_folder, monkeypatch):
        """Тест получения изображений с невалидными параметрами."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder, ITEMS_PER_PAGE=20))
        
        with patch("routes.get_absolute_path") as mock_get_path, \
             patch("os.path.isdir") as mock_isdir, \
             patch("routes.validate_pagination_params") as mock_validate:
            mock_get_path.return_value = temp_image_folder
            mock_isdir.return_value = True
            # Мокаем валидацию, чтобы она выбрасывала исключение
            from exceptions import InvalidRequestError
            mock_validate.side_effect = InvalidRequestError("Неверные параметры пагинации")
            # Используем URL с подпутем, чтобы гарантированно попасть в правильный маршрут
            response = client.get("/images/subfolder?limit=invalid")
            assert response.status_code == 400


class TestServeFileRoute:
    """Тесты для маршрута serve_file."""
    
    def test_serve_image(self, client, temp_image_folder, sample_image_path, monkeypatch):
        """Тест отдачи изображения."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder))
        
        rel_path = os.path.relpath(sample_image_path, temp_image_folder)
        response = client.get(f"/serve_image/{rel_path}")
        assert response.status_code == 200
    
    def test_serve_thumbnail(self, client, temp_image_folder, sample_image_path, monkeypatch):
        """Тест отдачи миниатюры."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder))
        
        rel_path = os.path.relpath(sample_image_path, temp_image_folder)
        response = client.get(f"/serve_thumbnail/{rel_path}")
        assert response.status_code == 200
    
    def test_serve_file_not_found(self, client, temp_image_folder, monkeypatch):
        """Тест отдачи несуществующего файла."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder))
        
        response = client.get("/serve_image/nonexistent.png")
        assert response.status_code == 404


class TestDeleteImageRoute:
    """Тесты для маршрута delete_image."""
    
    def test_delete_image(self, client, temp_image_folder, sample_image_path, monkeypatch):
        """Тест удаления изображения."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder))
        
        rel_path = os.path.relpath(sample_image_path, temp_image_folder)
        with patch("routes.ImageService.delete_image") as mock_delete:
            response = client.post(
                "/delete_image",
                json={"filename": rel_path},
                content_type="application/json"
            )
            assert response.status_code == 200
            mock_delete.assert_called_once()
    
    def test_delete_image_invalid_request(self, client):
        """Тест удаления изображения с невалидным запросом."""
        response = client.post("/delete_image", data="not json")
        assert response.status_code == 400


class TestUpdateMetadataRoute:
    """Тесты для маршрута update_metadata."""
    
    def test_update_metadata(self, client, temp_image_folder, sample_image_path, monkeypatch):
        """Тест обновления метаданных."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder))
        
        rel_path = os.path.relpath(sample_image_path, temp_image_folder)
        with patch("routes.MetadataService.update_metadata") as mock_update:
            response = client.post(
                "/update_metadata",
                json={
                    "filename": rel_path,
                    "rating": 5,
                    "checked": True
                },
                content_type="application/json"
            )
            assert response.status_code == 200
            mock_update.assert_called_once()
    
    def test_update_metadata_multiple_files(self, client, temp_image_folder, monkeypatch):
        """Тест обновления метаданных для нескольких файлов."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder))
        
        with patch("routes.MetadataService.update_metadata") as mock_update:
            response = client.post(
                "/update_metadata",
                json={
                    "filenames": ["img1.png", "img2.png"],
                    "rating": 3
                },
                content_type="application/json"
            )
            assert response.status_code == 200
            mock_update.assert_called_once()
    
    def test_update_metadata_no_updates(self, client):
        """Тест обновления метаданных без полей для обновления."""
        response = client.post(
            "/update_metadata",
            json={"filename": "test.png"},
            content_type="application/json"
        )
        assert response.status_code == 400


class TestCopyToFavoritesRoute:
    """Тесты для маршрута copy_to_favorites."""
    
    def test_copy_to_favorites(self, client, temp_image_folder, sample_image_path, monkeypatch):
        """Тест копирования в избранное."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder))
        
        rel_path = os.path.relpath(sample_image_path, temp_image_folder)
        with patch("routes.FavoritesService.copy_to_favorites") as mock_copy:
            response = client.post(
                "/copy_to_favorites",
                json={"filename": rel_path},
                content_type="application/json"
            )
            assert response.status_code == 200
            mock_copy.assert_called_once()


class TestGetAllTagsRoute:
    """Тесты для маршрута get_all_tags."""
    
    def test_get_all_tags(self, client, monkeypatch):
        """Тест получения всех тегов."""
        with patch("routes.get_all_tags_cached") as mock_tags:
            mock_tags.return_value = ["tag1", "tag2", "tag3"]
            response = client.get("/all_tags")
            assert response.status_code == 200
            data = json.loads(response.data)
            assert isinstance(data, list)


class TestUncheckAllRoute:
    """Тесты для маршрута uncheck_all."""
    
    def test_uncheck_all(self, client, temp_image_folder, monkeypatch):
        """Тест снятия всех отметок."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder))
        
        with patch("routes.MetadataService.uncheck_all") as mock_uncheck:
            mock_uncheck.return_value = 5
            response = client.post(
                "/uncheck_all",
                json={"path": "", "search": ""},
                content_type="application/json"
            )
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["count"] == 5


class TestDeleteMetadataRoute:
    """Тесты для маршрута delete_metadata."""
    
    def test_delete_metadata(self, client, temp_image_folder, monkeypatch):
        """Тест удаления метаданных."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder))
        
        with patch("routes.MetadataService.delete_metadata") as mock_delete:
            mock_delete.return_value = 3
            response = client.post(
                "/delete_metadata",
                json={"path": "", "search": ""},
                content_type="application/json"
            )
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["count"] == 3


class TestErrorHandlers:
    """Тесты для обработчиков ошибок."""
    
    def test_path_not_found_handler(self, client, monkeypatch):
        """Тест обработчика PathNotFoundError."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER="/nonexistent"))
        
        with patch("routes.get_absolute_path", side_effect=PathNotFoundError("Path not found")):
            response = client.get("/images/nonexistent")
            assert response.status_code == 404
    
    def test_invalid_request_handler(self, client):
        """Тест обработчика InvalidRequestError."""
        with patch("routes.validate_json_request", side_effect=InvalidRequestError("Invalid request")):
            response = client.post("/delete_image", data="not json")
            assert response.status_code == 400
    
    def test_file_operation_error_handler(self, client, temp_image_folder, monkeypatch):
        """Тест обработчика FileOperationError."""
        monkeypatch.setattr("config.config", MagicMock(IMAGE_FOLDER=temp_image_folder))
        
        with patch("routes.ImageService.delete_image", side_effect=FileOperationError("File error")):
            response = client.post(
                "/delete_image",
                json={"filename": "test.png"},
                content_type="application/json"
            )
            assert response.status_code == 500


import os
import threading
import webbrowser
import time
import logging

from flask import Flask, jsonify

from config import load_config
from routes import routes
from metadata import metadata_store

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 5000
BROWSER_URL = "http://127.0.0.1:5000"


def create_app() -> Flask:
    app = Flask(
        __name__,
        static_folder=os.path.join(BASE_DIR, "static"),
        template_folder=os.path.join(BASE_DIR, "templates")
    )
    app.register_blueprint(routes)
    app.config.update(load_config())
    
    @app.errorhandler(404)
    def handle_not_found(error):
        return jsonify({"error": "Не найдено"}), 404
    
    @app.errorhandler(500)
    def handle_internal_error(error):
        logger.exception("Внутренняя ошибка сервера")
        return jsonify({"error": "Внутренняя ошибка сервера"}), 500
    
    return app


def _is_debug_mode() -> bool:
    return (
        os.getenv("FLASK_DEBUG", "False").lower() == "true" or
        os.getenv("FLASK_ENV") == "development"
    )


def _should_open_browser(debug_mode: bool) -> bool:
    return os.getenv("WERKZEUG_RUN_MAIN") == "true" or not debug_mode


def open_browser() -> None:
    time.sleep(1)
    try:
        webbrowser.open(BROWSER_URL)
    except Exception as e:
        logger.warning(f"Не удалось открыть браузер: {e}")


app = create_app()
metadata_store.initialize()


if __name__ == "__main__":
    debug_mode = _is_debug_mode()
    
    if _should_open_browser(debug_mode):
        threading.Thread(target=open_browser, daemon=True).start()
    
    app.run(
        host=os.getenv("FLASK_HOST", DEFAULT_HOST),
        port=int(os.getenv("FLASK_PORT", str(DEFAULT_PORT))),
        debug=debug_mode,
        use_reloader=debug_mode,
        threaded=True
    )

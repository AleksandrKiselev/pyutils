"""
Точка входа Flask приложения для просмотра изображений.
"""
import os
import threading
import webbrowser
import time
import logging

from flask import Flask

from config import load_config
from routes import routes

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder="static", template_folder="templates")
app.register_blueprint(routes)
app.config.update(load_config())


def open_browser() -> None:
    """Открывает браузер."""
    time.sleep(1)
    try:
        webbrowser.open("http://127.0.0.1:5000")
    except Exception as e:
        logger.warning(f"Не удалось открыть браузер: {e}")


@app.errorhandler(404)
def handle_not_found(error):
    return {"error": "Не найдено"}, 404


@app.errorhandler(500)
def handle_internal_error(error):
    logger.exception("Внутренняя ошибка сервера")
    return {"error": "Внутренняя ошибка сервера"}, 500


if __name__ == "__main__":
    debug_mode = (
        os.getenv("FLASK_DEBUG", "False").lower() == "true" or
        os.getenv("FLASK_ENV") == "development"
    )
    
    if os.getenv("WERKZEUG_RUN_MAIN") == "true" or not debug_mode:
        threading.Thread(target=open_browser, daemon=True).start()
    
    app.run(
        host=os.getenv("FLASK_HOST", "0.0.0.0"),
        port=int(os.getenv("FLASK_PORT", "5000")),
        debug=debug_mode,
        use_reloader=debug_mode,
        threaded=True
    )

"""
Main entry point for the Flask image browser application.
"""
import os
import threading
import webbrowser
import time
from flask import Flask
from config import load_config
from routes import routes

app = Flask(__name__, static_folder="static", template_folder="templates")
app.register_blueprint(routes)
app.config.update(load_config())

def open_browser():
    """Open the default web browser after a short delay."""
    time.sleep(1)
    webbrowser.open("http://127.0.0.1:5000")

if __name__ == "__main__":
    debug_mode = os.getenv("FLASK_DEBUG", "False").lower() == "true" or os.getenv("FLASK_ENV") == "development"
    
    # Open browser only once:
    # - In reloader mode: only in the subprocess (WERKZEUG_RUN_MAIN="true")
    # - Without reloader: always (WERKZEUG_RUN_MAIN is not set)
    if os.getenv("WERKZEUG_RUN_MAIN") == "true" or not debug_mode:
        threading.Thread(target=open_browser, daemon=True).start()
    
    app.run(host="0.0.0.0", debug=debug_mode, use_reloader=debug_mode, threaded=True)
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
    time.sleep(1)
    webbrowser.open("http://127.0.0.1:5000")


if __name__ == "__main__":
    threading.Thread(target=open_browser, daemon=True).start()
    app.run(host="0.0.0.0", debug=False)
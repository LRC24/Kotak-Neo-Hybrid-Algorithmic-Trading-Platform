import os
from dotenv import load_dotenv

# Load environmental variables from .env
load_dotenv()

# Import dynamic imports because of space-containing package folder structure
import importlib
app_package = importlib.import_module("Algo Kotak Neo Trader.app")

app = app_package.create_app()

if __name__ == "__main__":
    host = os.getenv("FLASK_HOST", "127.0.0.1")
    port = int(os.getenv("FLASK_PORT", 5000))
    
    app_package.socketio.run(
        app,
        host=host,
        port=port,
        debug=app.config.get("DEBUG", False),
        allow_unsafe_werkzeug=True
    )

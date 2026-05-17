"""
server.py
─────────
Flask application entry point.

Serves the existing HTML/CSS/JS frontend and exposes REST API endpoints
for the AI pipeline (transcription, summarisation, RAG chat).

Usage:
    python server.py
    → http://localhost:5000
"""

import os
import logging
from dotenv import load_dotenv

# Load environment variables BEFORE any core/ imports
load_dotenv()

# Diagnostic: Verify if JavaScript runtime is active for yt-dlp signature decryption
import subprocess
try:
    node_ver = subprocess.check_output(["node", "--version"]).decode().strip()
    print(f"INFO: JavaScript runtime (node) is active! Version: {node_ver}")
except Exception as e:
    print(f"WARNING: No Node.js runtime found under 'node': {e}")
    try:
        node_ver = subprocess.check_output(["nodejs", "--version"]).decode().strip()
        print(f"INFO: JavaScript runtime (nodejs) is active! Version: {node_ver}")
    except Exception as e2:
        print(f"CRITICAL: No JavaScript runtime found in system PATH! yt-dlp n-challenge decryption will fail: {e2}")

from flask import Flask, send_from_directory
from flask_cors import CORS

from routes.process import process_bp
from routes.chat import chat_bp
from routes.auth import auth_bp


def create_app():
    """Flask application factory."""

    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
        static_url_path="/static",
    )

    # ── Configuration ───────────────────────────────────────────────────────
    app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "aurix-dev-secret-key")
    app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024  # 500 MB max upload
    app.config["UPLOAD_FOLDER"] = os.path.join(os.path.dirname(__file__), "uploads")

    # ── CORS ────────────────────────────────────────────────────────────────
    CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

    # ── Logging ─────────────────────────────────────────────────────────────
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )

    # ── Register API Blueprints ─────────────────────────────────────────────
    app.register_blueprint(process_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(auth_bp)

    # ── Serve Frontend Pages ────────────────────────────────────────────────

    @app.route("/")
    def index():
        """Serve the landing page."""
        return send_from_directory("templates", "index.html")

    @app.route("/index.html")
    def index_html():
        """Alias for landing page."""
        return send_from_directory("templates", "index.html")

    @app.route("/dashboard.html")
    def dashboard():
        """Serve the dashboard page."""
        return send_from_directory("templates", "dashboard.html")

    # ── Health Check ────────────────────────────────────────────────────────

    @app.route("/api/health", methods=["GET"])
    def health():
        return {"status": "ok", "server": "Aurix AI Flask Backend"}

    return app


# ── Entry Point ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = create_app()

    host = os.getenv("FLASK_HOST", "0.0.0.0")
    port = int(os.getenv("FLASK_PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "true").lower() == "true"

    print(f"\n"
          f"  ==========================================\n"
          f"   Aurix AI - Flask Backend\n"
          f"  ==========================================\n"
          f"   Server:   http://localhost:{port}\n"
          f"   Health:   http://localhost:{port}/api/health\n"
          f"   Debug:    {debug}\n"
          f"  ==========================================\n")

    app.run(host=host, port=port, debug=debug, threaded=True, use_reloader=False)

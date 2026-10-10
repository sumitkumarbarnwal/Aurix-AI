"""
Aurix AI — Flask API Server
Connects the HTML/JS frontend dashboard to the Python AI pipeline.
"""

import sys
import os
import json
import time
import uuid
import threading
import tempfile
from concurrent.futures import ThreadPoolExecutor
from functools import wraps

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from flask import Flask, request, jsonify, send_from_directory, Response, session
from flask_cors import CORS
from dotenv import load_dotenv
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

# Load environment variables
load_dotenv()

# ── Import core pipeline modules ─────────────────────────────────────────────
from core.audio_processor import process_input
from core.transcriber import transcribe_all
from core.summarizer import summarize, generate_title
from core.extractor import extract_action_items, extract_key_decisions, extract_questions
from core.rag_engine import build_rag_chain, ask_question

# ── Flask App Setup ──────────────────────────────────────────────────────────
app = Flask(__name__, static_folder="frontend", static_url_path="")
app.secret_key = os.getenv("FLASK_SECRET_KEY", "aurix-ai-secret-key-change-in-production")
CORS(app, supports_credentials=True, resources={
    r"/api/*": {
        "origins": "*",
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})

# Google OAuth Client ID
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()

# ── In-memory state ──────────────────────────────────────────────────────────
# Pipeline status per session
pipeline_status = {}  # session_id -> { step, progress, error, result }
# RAG chains per session
rag_chains = {}       # session_id -> rag_chain object
# Upload directory
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  STATIC FILE SERVING
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/")
def serve_index():
    return send_from_directory("frontend", "index.html")


@app.route("/<path:path>")
def serve_static(path):
    return send_from_directory("frontend", path)


# ═══════════════════════════════════════════════════════════════════════════════
#  AUTH — Google OAuth
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/auth/google", methods=["POST"])
def google_login():
    """Verify Google ID token and create session."""
    data = request.get_json()
    token = data.get("credential")

    if not token:
        return jsonify({"error": "No credential provided"}), 400

    try:
        # Verify the token with Google
        if GOOGLE_CLIENT_ID:
            idinfo = id_token.verify_oauth2_token(
                token, google_requests.Request(), GOOGLE_CLIENT_ID
            )
        else:
            # If no client ID configured, decode without verification (dev mode)
            import base64
            payload = token.split('.')[1]
            payload += '=' * (4 - len(payload) % 4)
            idinfo = json.loads(base64.b64decode(payload))

        # Extract user info
        user = {
            "id": idinfo.get("sub", ""),
            "email": idinfo.get("email", ""),
            "name": idinfo.get("name", ""),
            "picture": idinfo.get("picture", ""),
            "email_verified": idinfo.get("email_verified", False),
        }

        # Store in session
        session["user"] = user
        session["session_id"] = str(uuid.uuid4())

        return jsonify({
            "success": True,
            "user": user,
            "session_id": session["session_id"],
        })

    except ValueError as e:
        return jsonify({"error": f"Invalid token: {str(e)}"}), 401
    except Exception as e:
        return jsonify({"error": f"Auth error: {str(e)}"}), 500


@app.route("/api/auth/session", methods=["GET"])
def check_session():
    """Check if user has active session."""
    user = session.get("user")
    if user:
        return jsonify({"authenticated": True, "user": user})
    return jsonify({"authenticated": False}), 401


@app.route("/api/auth/logout", methods=["POST"])
def logout():
    """Clear user session."""
    sid = session.get("session_id")
    if sid:
        rag_chains.pop(sid, None)
        pipeline_status.pop(sid, None)
    session.clear()
    return jsonify({"success": True})


# ═══════════════════════════════════════════════════════════════════════════════
#  PIPELINE — Process URL or File
# ═══════════════════════════════════════════════════════════════════════════════

def update_status(sid, step, progress, detail=""):
    """Update pipeline status for a session."""
    if sid not in pipeline_status:
        pipeline_status[sid] = {}
    pipeline_status[sid].update({
        "step": step,
        "progress": progress,
        "detail": detail,
        "timestamp": time.time(),
    })


def run_pipeline_async(sid, source, language):
    """Run the full AI pipeline in a background thread."""
    try:
        # Step 1: Audio Processing
        update_status(sid, "audio", 10, "Downloading & processing audio...")
        chunks = process_input(source)
        update_status(sid, "audio_done", 20, f"Audio ready — {len(chunks)} chunk(s)")

        # Step 2: Transcription
        update_status(sid, "transcription", 25, "Transcribing audio...")
        transcript = transcribe_all(chunks, language)
        update_status(sid, "transcription_done", 45, "Transcription complete")

        # Step 3: Title Generation
        update_status(sid, "title", 48, "Generating title...")
        title = generate_title(transcript)
        update_status(sid, "title_done", 50, f"Title: {title}")

        # Step 4: Summarization
        update_status(sid, "summary", 55, "Summarizing transcript...")
        summary = summarize(transcript)
        update_status(sid, "summary_done", 70, "Summary complete")

        # Step 5: Extraction
        update_status(sid, "extraction", 72, "Extracting action items & decisions...")
        time.sleep(0.8)  # Respect Mistral free tier 1 req/sec rate limit
        action_items = extract_action_items(transcript)
        time.sleep(0.8)
        decisions    = extract_key_decisions(transcript)
        time.sleep(0.8)
        questions    = extract_questions(transcript)
        update_status(sid, "extraction_done", 85, "Extraction complete")

        # Step 6: RAG Engine
        update_status(sid, "rag", 88, "Building knowledge base...")
        rag_chain = build_rag_chain(transcript)
        rag_chains[sid] = rag_chain
        update_status(sid, "rag_done", 95, "RAG engine ready")

        # Done
        result = {
            "title": title,
            "transcript": transcript[:5000],  # Limit for JSON
            "summary": summary,
            "action_items": action_items,
            "key_decisions": decisions,
            "open_questions": questions,
        }

        pipeline_status[sid]["result"] = result
        update_status(sid, "complete", 100, "Analysis complete!")

    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        update_status(sid, "error", -1, str(e))
        pipeline_status[sid]["error"] = str(e)
        print(f"Pipeline error: {e}")
        print(f"Full traceback:\n{error_trace}")


@app.route("/api/process", methods=["POST"])
def process():
    """Start processing a URL or uploaded file."""
    # Extract session_id and request data
    if request.is_json:
        data = request.get_json()
        sid = data.get("session_id", "")
        source = data.get("url", "")
        language = data.get("language", "english")
    else:
        sid = request.form.get("session_id", "")
        source = request.form.get("url", "")
        language = request.form.get("language", "english")

        # Handle file upload
        if "file" in request.files:
            file = request.files["file"]
            if file.filename:
                if not sid:
                    sid = str(uuid.uuid4())
                filepath = os.path.join(UPLOAD_DIR, f"{sid}_{file.filename}")
                file.save(filepath)
                source = filepath
    
    if not sid:
        sid = str(uuid.uuid4())

    if not source:
        return jsonify({"error": "No URL or file provided"}), 400

    # Reset status
    pipeline_status[sid] = {"step": "starting", "progress": 0, "detail": "Initializing..."}

    # Run pipeline in background thread
    thread = threading.Thread(target=run_pipeline_async, args=(sid, source, language))
    thread.daemon = True
    thread.start()

    return jsonify({"success": True, "session_id": sid, "message": "Processing started"})


@app.route("/api/status/<sid>", methods=["GET"])
def get_status(sid):
    """Get current pipeline status."""
    status = pipeline_status.get(sid, {"step": "unknown", "progress": 0})
    return jsonify(status)


@app.route("/api/status/stream/<sid>")
def stream_status(sid):
    """Server-Sent Events stream for real-time pipeline progress."""
    def generate():
        last_step = ""
        while True:
            status = pipeline_status.get(sid, {})
            current_step = status.get("step", "")

            if current_step != last_step:
                data = json.dumps(status)
                yield f"data: {data}\n\n"
                last_step = current_step

            if current_step in ("complete", "error"):
                break

            time.sleep(0.5)

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/api/result/<sid>", methods=["GET"])
def get_result(sid):
    """Get the final pipeline result."""
    status = pipeline_status.get(sid, {})
    result = status.get("result")
    if result:
        return jsonify({"success": True, "result": result})
    error = status.get("error")
    if error:
        return jsonify({"success": False, "error": error}), 500
    return jsonify({"success": False, "message": "Processing not complete yet"}), 202


# ═══════════════════════════════════════════════════════════════════════════════
#  RAG CHAT
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/chat", methods=["POST"])
def chat():
    """Ask a question about the processed content via RAG."""
    data = request.get_json()
    sid = data.get("session_id", "")
    question = data.get("question", "").strip()

    if not question:
        return jsonify({"error": "No question provided"}), 400

    rag_chain = rag_chains.get(sid)
    if not rag_chain:
        return jsonify({"error": "No active session. Please process a video first."}), 400

    try:
        answer = ask_question(rag_chain, question)
        return jsonify({"success": True, "answer": answer})
    except Exception as e:
        return jsonify({"error": f"Chat error: {str(e)}"}), 500


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print("\n" + "=" * 60)
    print("  > Aurix AI Server")
    print(f"  - http://0.0.0.0:{port}")
    print(f"  Dashboard: http://127.0.0.1:{port}/dashboard.html")
    print("=" * 60 + "\n")

    app.run(debug=False, host="0.0.0.0", port=port, threaded=True, use_reloader=False)

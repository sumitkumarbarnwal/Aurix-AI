"""
Aurix AI — Flask API Server
Connects the HTML/JS frontend dashboard to the Python AI pipeline.
Supports PDF, Text documents, Audio recordings, and Video files.
Generates structured AI summaries, action items, key decisions, and RAG Q&A.
"""

import sys
import os
import json
import time
import uuid
import threading
from concurrent.futures import ThreadPoolExecutor

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from flask import Flask, request, jsonify, send_from_directory, Response, session
from flask_cors import CORS
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

# Load environment variables
load_dotenv()

# ── Import core pipeline modules ─────────────────────────────────────────────
from core.pdf_processor import extract_text_from_file
from core.summarizer import summarize, generate_title
from core.extractor import extract_all_insights
from core.rag_engine import build_rag_chain, ask_question
from core.audio_processor import process_input
from core.transcriber import transcribe_all

# ── Flask App Setup ──────────────────────────────────────────────────────────
app = Flask(__name__, static_folder="frontend", static_url_path="")
app.secret_key = os.getenv("FLASK_SECRET_KEY", "aurix-ai-secret-key-change-in-production")
# Allow uploads up to 500 MB (large audio/video files)
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024
CORS(app, supports_credentials=True, resources={
    r"/api/*": {
        "origins": "*",
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})

# Google OAuth Client ID
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()

# ── Supported File Extensions ────────────────────────────────────────────────
DOC_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".csv", ".json", ".log", ".rtf"}
MEDIA_EXTENSIONS = {
    ".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".wma",
    ".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".wmv", ".m4v"
}

# ── In-memory state ──────────────────────────────────────────────────────────
pipeline_status = {}  # sid -> { step, progress, error, result }
rag_chains = {}       # sid -> rag_chain object
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
#  AUTH — Google OAuth & Session Check
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/auth/google", methods=["POST"])
def google_login():
    """Verify Google ID token and create session."""
    data = request.get_json() or {}
    token = data.get("credential")

    if not token:
        return jsonify({"error": "No credential provided"}), 400

    try:
        if GOOGLE_CLIENT_ID:
            idinfo = id_token.verify_oauth2_token(
                token, google_requests.Request(), GOOGLE_CLIENT_ID
            )
        else:
            import base64
            payload = token.split('.')[1]
            payload += '=' * (4 - len(payload) % 4)
            idinfo = json.loads(base64.b64decode(payload))

        user = {
            "id": idinfo.get("sub", ""),
            "email": idinfo.get("email", ""),
            "name": idinfo.get("name", ""),
            "picture": idinfo.get("picture", ""),
            "email_verified": idinfo.get("email_verified", False),
        }

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
#  PIPELINE — PDF, Document, Audio & Video Analysis
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


def run_pipeline_async(sid, source, language="english"):
    """
    Unified AI pipeline for PDF, text documents, audio recordings, and video files.
    """
    try:
        ext = os.path.splitext(source)[1].lower()

        # ── 1. Document Extraction (.pdf, .docx, .txt, .md, etc.) ───────────────
        if ext in DOC_EXTENSIONS:
            update_status(sid, "extracting", 15, f"Reading and extracting text from {ext.upper()} document...")
            content_text = extract_text_from_file(source)
            char_count = len(content_text)
            update_status(sid, "extracted", 30, f"Extracted {char_count:,} characters from document")
            file_category = "document"

        # ── 2. Audio / Video Processing & Speech-to-Text (.mp3, .mp4, etc.) ──────
        elif ext in MEDIA_EXTENSIONS:
            update_status(sid, "audio", 12, "Extracting audio stream & converting to 16kHz WAV...")
            chunks = process_input(source)
            update_status(sid, "audio_done", 22, f"Audio prepared — {len(chunks)} chunk(s)")

            lang_label = "Hinglish (Hindi → English)" if language == "hinglish" else "English"
            update_status(sid, "transcription", 28, f"Transcribing speech with Whisper ({lang_label})...")
            content_text = transcribe_all(chunks, language)

            if not content_text or not content_text.strip():
                raise ValueError("No speech could be detected or transcribed from this audio/video file.")

            update_status(sid, "transcription_done", 45, f"Transcription complete ({len(content_text):,} characters)")
            file_category = "media"

        else:
            raise ValueError(
                f"Unsupported file format '{ext}'. "
                "Please upload a PDF, document (.txt, .docx), audio (.mp3, .wav), or video (.mp4, .mov) file."
            )

        # ── 3. Title Generation ────────────────────────────────────────────────
        update_status(sid, "title", 50, "Analyzing content and generating title...")
        title = generate_title(content_text)
        update_status(sid, "title_done", 58, f"Title: {title}")

        # ── 4. Comprehensive AI Summarization ──────────────────────────────────
        update_status(sid, "summary", 65, "Generating comprehensive AI summary...")
        summary = summarize(content_text)
        update_status(sid, "summary_done", 75, "Summary complete")

        # ── 5. Extraction of Action Items, Decisions, & Questions ──────────────
        update_status(sid, "extraction", 80, "Extracting action items, key findings & open questions...")
        insights = extract_all_insights(content_text)
        action_items = insights.get("action_items", "")
        decisions = insights.get("key_decisions", "")
        questions = insights.get("open_questions", "")
        update_status(sid, "extraction_done", 88, "Insights extracted")

        # ── 6. RAG Vector Store & Chain Indexing ──────────────────────────────
        update_status(sid, "rag", 90, "Indexing content in vector database for interactive Q&A...")
        rag_chain = build_rag_chain(content_text, session_id=sid)
        rag_chains[sid] = rag_chain
        update_status(sid, "rag_done", 98, "RAG engine ready for Q&A")

        # ── 7. Final Result ───────────────────────────────────────────────────
        result = {
            "title": title,
            "transcript": content_text[:10000],
            "summary": summary,
            "action_items": action_items,
            "key_decisions": decisions,
            "open_questions": questions,
            "file_category": file_category,
        }

        pipeline_status[sid]["result"] = result
        update_status(sid, "complete", 100, "Analysis complete! You can now ask questions about this content below.")

    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        update_status(sid, "error", -1, str(e))
        pipeline_status[sid]["error"] = str(e)
        print(f"[Pipeline Error] {e}")
        print(f"Full traceback:\n{error_trace}")


@app.route("/api/process", methods=["POST"])
def process():
    """Start processing an uploaded PDF, text document, audio, or video file."""
    sid = request.form.get("session_id", "").strip()
    language = request.form.get("language", "english").strip().lower()
    source = ""

    if not sid:
        sid = str(uuid.uuid4())

    # Handle file upload
    if "file" in request.files:
        file = request.files["file"]
        if file and file.filename:
            safe_name = secure_filename(file.filename)
            if not safe_name:
                return jsonify({"error": "Invalid file name"}), 400
            
            filepath = os.path.join(UPLOAD_DIR, f"{sid}_{safe_name}")
            file.save(filepath)
            source = filepath
            print(f"[Upload] Saved: {safe_name} -> {filepath} ({os.path.getsize(filepath):,} bytes)")

    if not source:
        return jsonify({"error": "No file uploaded. Please select and upload a PDF, document, audio, or video file."}), 400

    # Reset status
    pipeline_status[sid] = {"step": "starting", "progress": 5, "detail": "Initializing analysis..."}

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
        start_time = time.time()
        max_duration = 300  # 5 min timeout to prevent thread starvation
        while time.time() - start_time < max_duration:
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
#  RAG CHAT — Ask Questions Based on Content
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/chat", methods=["POST"])
def chat():
    """Ask a question about the uploaded document or media via RAG."""
    data = request.get_json() or {}
    sid = data.get("session_id", "").strip()
    question = data.get("question", "").strip()

    if not question:
        return jsonify({"error": "No question provided. Please enter a question."}), 400

    rag_chain = rag_chains.get(sid)
    if not rag_chain:
        return jsonify({
            "error": "No active content found for this session. Please upload a PDF, audio, video, or document first."
        }), 400

    try:
        answer = ask_question(rag_chain, question)
        return jsonify({"success": True, "answer": answer})
    except Exception as e:
        print(f"[Chat Error] {e}")
        return jsonify({"error": f"Error answering question: {str(e)}"}), 500


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("\n" + "=" * 60)
    print("  > Aurix AI Multi-Format Intelligence Server")
    print(f"  - http://127.0.0.1:{port}")
    print(f"  Dashboard: http://127.0.0.1:{port}/dashboard.html")
    print("=" * 60 + "\n")

    app.run(debug=False, host="0.0.0.0", port=port, threaded=True, use_reloader=False)

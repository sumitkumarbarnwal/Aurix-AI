"""
routes/process.py
─────────────────
Handles video/audio processing, status polling, SSE streaming, and result retrieval.
Matches the fetch() calls already in dashboard.js.
"""

import os
import json
import time
import uuid
import logging
from queue import Empty

from flask import Blueprint, request, jsonify, Response

from services.pipeline import session_store, start_pipeline

logger = logging.getLogger(__name__)

process_bp = Blueprint("process", __name__)

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@process_bp.route("/api/process", methods=["POST"])
def process_video():
    """
    Start processing a video URL or uploaded file.

    Expects FormData with:
      - url (str) OR file (File)
      - session_id (str, optional)
      - language (str, default "english")

    Returns:
      { success: true, session_id: "..." }
    """
    try:
        url = request.form.get("url", "").strip()
        language = request.form.get("language", "english").strip()
        session_id = request.form.get("session_id", "").strip() or None
        uploaded_file = request.files.get("file")

        source = None

        if uploaded_file and uploaded_file.filename:
            # Save uploaded file to uploads/ directory
            safe_name = f"{uuid.uuid4().hex}_{uploaded_file.filename}"
            file_path = os.path.join(UPLOAD_DIR, safe_name)
            uploaded_file.save(file_path)
            source = file_path
            logger.info("File uploaded: %s → %s", uploaded_file.filename, file_path)

        elif url:
            source = url
            logger.info("URL submitted: %s", url)

        else:
            return jsonify({"success": False, "error": "No URL or file provided"}), 400

        # Launch pipeline in background thread
        sid = start_pipeline(source=source, language=language, session_id=session_id)

        return jsonify({"success": True, "session_id": sid})

    except Exception as e:
        logger.exception("Error starting pipeline: %s", e)
        return jsonify({"success": False, "error": str(e)}), 500


@process_bp.route("/api/status/<sid>", methods=["GET"])
def get_status(sid):
    """
    Polling fallback for pipeline status.
    Returns: { step, progress, detail }
    """
    status = session_store.get_status(sid)
    if status is None:
        return jsonify({"step": "unknown", "progress": 0, "detail": "Session not found"}), 404
    return jsonify(status)


@process_bp.route("/api/status/stream/<sid>", methods=["GET"])
def stream_status(sid):
    """
    Server-Sent Events (SSE) endpoint for real-time pipeline progress.
    The frontend's EventSource connects here.
    """
    def event_stream():
        events_queue = session_store.get_events_queue(sid)
        if events_queue is None:
            yield f"data: {json.dumps({'step': 'error', 'progress': 0, 'detail': 'Session not found'})}\n\n"
            return

        while True:
            try:
                event = events_queue.get(timeout=30)
                yield f"data: {json.dumps(event)}\n\n"

                if event.get("step") in ("complete", "error"):
                    break
            except Empty:
                # Send heartbeat to keep connection alive
                yield f": heartbeat\n\n"

    return Response(
        event_stream(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@process_bp.route("/api/result/<sid>", methods=["GET"])
def get_result(sid):
    """
    Retrieve the completed pipeline result for a session.
    Returns: { success, result: { title, summary, action_items, ... } }
    """
    result = session_store.get_result(sid)
    if result is None:
        return jsonify({"success": False, "error": "No result available yet"}), 404

    return jsonify({"success": True, "result": result})

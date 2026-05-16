"""
routes/chat.py
──────────────
RAG-powered Q&A chat endpoint.
Matches the fetch() call in dashboard.js.
"""

import logging
from flask import Blueprint, request, jsonify

from services.pipeline import chat_with_session

logger = logging.getLogger(__name__)

chat_bp = Blueprint("chat", __name__)


@chat_bp.route("/api/chat", methods=["POST"])
def chat():
    """
    Answer a question using the session's RAG chain.

    Expects JSON:
      { "session_id": "...", "question": "..." }

    Returns:
      { "success": true, "answer": "..." }
    """
    try:
        data = request.get_json(force=True)
        session_id = data.get("session_id", "").strip()
        question = data.get("question", "").strip()

        if not session_id:
            return jsonify({"success": False, "error": "Missing session_id"}), 400

        if not question:
            return jsonify({"success": False, "error": "Missing question"}), 400

        logger.info("Chat question [%s]: %s", session_id, question)
        answer = chat_with_session(session_id, question)
        logger.info("Chat answer [%s]: %s", session_id, answer[:200])

        return jsonify({"success": True, "answer": answer})

    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

    except Exception as e:
        logger.exception("Chat error: %s", e)
        return jsonify({"success": False, "error": str(e)}), 500

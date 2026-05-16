"""
services/pipeline.py
────────────────────
Thread-safe session store and background pipeline runner.
Bridges the existing core/ AI modules with Flask API routes.
"""

import uuid
import threading
import logging
from queue import Queue, Empty
from datetime import datetime

from utils.audio_processor import process_input
from core.transcriber import transcribe_all
from core.summarizer import summarize, generate_title
from core.extractor import extract_action_items, extract_key_decisions, extract_questions
from core.rag_engine import build_rag_chain, ask_question

logger = logging.getLogger(__name__)


class SessionStore:
    """
    In-memory store for all active sessions.
    Each session tracks: processing status, pipeline result, RAG chain,
    and an event queue for Server-Sent Events.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._sessions = {}

    def create(self, session_id=None):
        """Create a new session and return its ID."""
        sid = session_id or str(uuid.uuid4())
        with self._lock:
            self._sessions[sid] = {
                "status": {"step": "idle", "progress": 0, "detail": ""},
                "result": None,
                "rag_chain": None,
                "events": Queue(),
                "created_at": datetime.utcnow().isoformat(),
            }
        logger.info("Session created: %s", sid)
        return sid

    def exists(self, sid):
        with self._lock:
            return sid in self._sessions

    def get_status(self, sid):
        with self._lock:
            session = self._sessions.get(sid)
            if session:
                return dict(session["status"])
        return None

    def set_status(self, sid, step, progress, detail=""):
        with self._lock:
            session = self._sessions.get(sid)
            if session:
                status = {"step": step, "progress": progress, "detail": detail}
                session["status"] = status
                # Push event for SSE consumers
                session["events"].put(status)
        logger.info("Session %s → step=%s progress=%d%% %s", sid, step, progress, detail)

    def set_result(self, sid, result):
        with self._lock:
            session = self._sessions.get(sid)
            if session:
                session["result"] = result

    def get_result(self, sid):
        with self._lock:
            session = self._sessions.get(sid)
            if session:
                return session.get("result")
        return None

    def set_rag_chain(self, sid, chain):
        with self._lock:
            session = self._sessions.get(sid)
            if session:
                session["rag_chain"] = chain

    def get_rag_chain(self, sid):
        with self._lock:
            session = self._sessions.get(sid)
            if session:
                return session.get("rag_chain")
        return None

    def get_events_queue(self, sid):
        with self._lock:
            session = self._sessions.get(sid)
            if session:
                return session["events"]
        return None


# ── Global session store ────────────────────────────────────────────────────────
session_store = SessionStore()


def run_pipeline_background(sid, source, language="english"):
    """
    Execute the full AI pipeline in a background thread.
    Updates the session store at each step so the frontend can
    poll / stream progress via SSE.
    """
    try:
        # ── Step 1: Audio Processing ────────────────────────────────────────
        session_store.set_status(sid, "audio", 5, "Downloading and processing audio…")
        chunks = process_input(source)
        session_store.set_status(sid, "audio_done", 15, "Audio processed successfully")

        # ── Step 2: Transcription ───────────────────────────────────────────
        session_store.set_status(sid, "transcription", 20, "Transcribing audio with Whisper…")
        transcript = transcribe_all(chunks, language)
        session_store.set_status(sid, "transcription_done", 40, "Transcription complete")

        # ── Step 3: Title Generation ────────────────────────────────────────
        session_store.set_status(sid, "title", 45, "Generating title…")
        title = generate_title(transcript)
        session_store.set_status(sid, "title_done", 50, f"Title: {title}")

        # ── Step 4: Summarisation ───────────────────────────────────────────
        session_store.set_status(sid, "summary", 55, "Summarising transcript…")
        summary = summarize(transcript)
        session_store.set_status(sid, "summary_done", 70, "Summary generated")

        # ── Step 5: Extraction ──────────────────────────────────────────────
        session_store.set_status(sid, "extraction", 72, "Extracting action items, decisions & questions…")
        action_items = extract_action_items(transcript)
        decisions = extract_key_decisions(transcript)
        questions = extract_questions(transcript)
        session_store.set_status(sid, "extraction_done", 85, "Extraction complete")

        # ── Step 6: RAG Engine ──────────────────────────────────────────────
        session_store.set_status(sid, "rag", 88, "Building RAG chain & vector store…")
        rag_chain = build_rag_chain(transcript)
        session_store.set_rag_chain(sid, rag_chain)
        session_store.set_status(sid, "rag_done", 95, "RAG engine ready")

        # ── Complete ────────────────────────────────────────────────────────
        result = {
            "title": title,
            "transcript": transcript,
            "summary": summary,
            "action_items": action_items,
            "key_decisions": decisions,
            "open_questions": questions,
        }
        session_store.set_result(sid, result)
        session_store.set_status(sid, "complete", 100, "Analysis complete!")

        logger.info("Pipeline complete for session %s", sid)

    except Exception as e:
        logger.exception("Pipeline error for session %s: %s", sid, e)
        session_store.set_status(sid, "error", 0, str(e))


def start_pipeline(source, language="english", session_id=None):
    """
    Create (or reuse) a session and launch the pipeline in a background thread.
    Returns the session ID immediately.
    """
    sid = session_id
    if not sid or not session_store.exists(sid):
        sid = session_store.create(sid)
    else:
        # Reset existing session for reprocessing
        session_store.create(sid)

    thread = threading.Thread(
        target=run_pipeline_background,
        args=(sid, source, language),
        daemon=True,
    )
    thread.start()
    return sid


def chat_with_session(sid, question):
    """
    Ask a question against the session's RAG chain.
    Returns the answer string or raises an error.
    """
    rag_chain = session_store.get_rag_chain(sid)
    if not rag_chain:
        raise ValueError("No RAG chain available. Process a video first.")
    return ask_question(rag_chain, question)

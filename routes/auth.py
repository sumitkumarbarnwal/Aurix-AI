"""
routes/auth.py
──────────────
Authentication endpoints.
Supports Google OAuth token verification and guest/demo mode.
Matches the fetch() calls in script.js and dashboard.js.
"""

import os
import uuid
import json
import logging

from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__)


def _decode_google_jwt(credential):
    """
    Decode a Google ID token JWT.
    Uses google-auth library if available, otherwise falls back
    to base64 decoding of the payload (for dev/demo use).
    """
    try:
        from google.oauth2 import id_token
        from google.auth.transport import requests as google_requests

        client_id = os.getenv("GOOGLE_CLIENT_ID", "")
        if client_id:
            idinfo = id_token.verify_oauth2_token(
                credential,
                google_requests.Request(),
                client_id,
            )
            return {
                "id": idinfo.get("sub"),
                "email": idinfo.get("email"),
                "name": idinfo.get("name"),
                "picture": idinfo.get("picture"),
            }
    except ImportError:
        logger.warning("google-auth not installed — falling back to JWT decode")
    except Exception as e:
        logger.warning("Google token verification failed: %s — falling back", e)

    # Fallback: decode JWT payload without verification (dev mode)
    import base64

    try:
        parts = credential.split(".")
        if len(parts) >= 2:
            payload = parts[1]
            # Add padding
            payload += "=" * (4 - len(payload) % 4)
            decoded = json.loads(base64.urlsafe_b64decode(payload))
            return {
                "id": decoded.get("sub", "unknown"),
                "email": decoded.get("email", "unknown@unknown.com"),
                "name": decoded.get("name", "User"),
                "picture": decoded.get("picture", ""),
            }
    except Exception:
        pass

    return None


@auth_bp.route("/api/auth/google", methods=["POST"])
def google_signin():
    """
    Handle Google Sign-In.

    Expects JSON: { "credential": "<Google ID token JWT>" }
    Returns: { "success": true, "user": {...}, "session_id": "..." }
    """
    try:
        data = request.get_json(force=True)
        credential = data.get("credential", "")

        if not credential:
            return jsonify({"success": False, "error": "No credential provided"}), 400

        user = _decode_google_jwt(credential)
        if not user:
            return jsonify({"success": False, "error": "Invalid credential"}), 401

        session_id = str(uuid.uuid4())
        logger.info("Google sign-in: %s (%s)", user["name"], user["email"])

        return jsonify({
            "success": True,
            "user": user,
            "session_id": session_id,
        })

    except Exception as e:
        logger.exception("Auth error: %s", e)
        return jsonify({"success": False, "error": str(e)}), 500


@auth_bp.route("/api/auth/logout", methods=["POST"])
def logout():
    """Sign out — clears server-side session if any."""
    logger.info("User logged out")
    return jsonify({"success": True})

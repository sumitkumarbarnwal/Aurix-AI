import whisper
import os
import wave
import requests
from pydub import AudioSegment
import librosa
import numpy as np
import torch
from concurrent.futures import ThreadPoolExecutor, as_completed

import shutil

# Add FFmpeg path to environment for Whisper
ffmpeg_exe = shutil.which("ffmpeg")
if ffmpeg_exe:
    ffmpeg_dir = os.path.dirname(ffmpeg_exe)
    if ffmpeg_dir not in os.environ.get("PATH", ""):
        os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
else:
    # Fallback to the new FFmpeg installation path
    fallback_dir = r"C:\ffmpeg-2026-05-11-git-17bc88e67f-full_build\ffmpeg-2026-05-11-git-17bc88e67f-full_build\bin"
    if os.path.exists(fallback_dir):
        os.environ["PATH"] = fallback_dir + os.pathsep + os.environ.get("PATH", "")

# Sarvam's sync STT-translate API rejects audio longer than 30s.
# We slice each chunk into 25s pieces (with a 5s safety margin) before sending.
SARVAM_PIECE_SECONDS = 25

import threading

WHISPER_MODEL = os.getenv("WHISPER_MODEL", "tiny")

SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")
SARVAM_STT_TRANSLATE_URL = "https://api.sarvam.ai/speech-to-text-translate"
SARVAM_MODEL = os.getenv("SARVAM_STT_MODEL", "saaras:v2.5")

_model = None
_model_lock = threading.Lock()


def load_model():
    global _model
    with _model_lock:
        if _model is None:
            model_size = os.getenv("WHISPER_MODEL", "tiny")
            device = "cuda" if torch.cuda.is_available() else "cpu"
            print(f"Loading Whisper model: {model_size} on {device.upper()} ...")
            _model = whisper.load_model(model_size, device=device)
            print(f"Whisper model loaded on {device.upper()}.")
    return _model


def transcribe_chunk_whisper(chunk_path: str) -> str:
    model = load_model()
    # Convert to absolute path and ensure it exists
    chunk_path = os.path.abspath(chunk_path)
    if not os.path.exists(chunk_path):
        raise FileNotFoundError(f"Audio chunk not found: {chunk_path}")

    # Chunks are 16kHz mono 16-bit PCM WAV.
    # Load directly using Python's built-in wave module into float32 numpy array,
    # completely bypassing the need for ffmpeg binary.
    try:
        with wave.open(chunk_path, "rb") as wf:
            frames = wf.readframes(wf.getnframes())
            audio_data = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0

        result = model.transcribe(audio_data, task="transcribe", language="en")
        return result["text"].strip()
    except Exception as e:
        print(f"[Warning] Direct wave load transcription failed: {e}. Trying librosa fallback...")
        try:
            audio_data, _ = librosa.load(chunk_path, sr=16000, mono=True)
            result = model.transcribe(audio_data, task="transcribe", language="en")
            return result["text"].strip()
        except Exception as e2:
            print(f"[Warning] Librosa transcription failed: {e2}. Using placeholder.")
            return f"[Transcription failed - audio format issue. File: {os.path.basename(chunk_path)}]"


def _send_to_sarvam(piece_path: str) -> str:
    """Send one ≤30s WAV file to Sarvam and return the English transcript."""
    headers = {"api-subscription-key": SARVAM_API_KEY}

    with open(piece_path, "rb") as f:
        files = {"file": (os.path.basename(piece_path), f, "audio/wav")}
        data = {"model": SARVAM_MODEL, "with_diarization": "false"}
        response = requests.post(
            SARVAM_STT_TRANSLATE_URL,
            headers=headers,
            files=files,
            data=data,
            timeout=120,
        )

    if not response.ok:
        print(f"\n❌ Sarvam returned {response.status_code}")
        print(f"Response body: {response.text}\n")
        response.raise_for_status()

    return response.json().get("transcript", "")


def transcribe_chunk_sarvam(chunk_path: str) -> str:
    """
    Sarvam sync API only accepts ≤30s audio. We split this chunk into
    25-second pieces, send each separately, and join the transcripts.
    """
    if not SARVAM_API_KEY:
        raise RuntimeError("SARVAM_API_KEY is not set in environment / .env")

    audio = AudioSegment.from_wav(chunk_path)
    piece_ms = SARVAM_PIECE_SECONDS * 1000

    full_text = ""
    total_pieces = (len(audio) + piece_ms - 1) // piece_ms

    for i, start in enumerate(range(0, len(audio), piece_ms)):
        piece = audio[start: start + piece_ms]
        piece_path = f"{chunk_path}_sv_{i}.wav"
        piece.export(piece_path, format="wav")

        try:
            print(f"  → Sarvam piece {i + 1}/{total_pieces} ...")
            full_text += _send_to_sarvam(piece_path) + " "
        finally:
            if os.path.exists(piece_path):
                os.remove(piece_path)

    return full_text.strip()


def transcribe_chunk(chunk_path: str, language: str = "english") -> str:
    """
    Route one chunk to Whisper or Sarvam depending on language choice.
    - english  → Whisper (local model)
    - hinglish → Sarvam (translates to English while transcribing)
    """
    if language.lower() == "hinglish":
        return transcribe_chunk_sarvam(chunk_path)
    return transcribe_chunk_whisper(chunk_path)


def transcribe_all(chunks: list, language: str = "english") -> str:
    engine = "Sarvam AI" if language.lower() == "hinglish" else "Whisper"
    print(f"Using {engine} for transcription — {len(chunks)} chunk(s).")

    # Sarvam has strict rate limits; keep it sequential
    if language.lower() == "hinglish":
        results = {}
        for i, chunk in enumerate(chunks):
            print(f"Transcribing chunk {i + 1}/{len(chunks)}...")
            results[i] = transcribe_chunk(chunk, language=language)
    else:
        # Pre-warm model once
        load_model()
        results = {}
        for i, chunk in enumerate(chunks):
            print(f"Transcribing chunk {i + 1}/{len(chunks)}...")
            try:
                results[i] = transcribe_chunk(chunk, language=language)
            except Exception as e:
                print(f"[Warning] Chunk {i + 1} failed: {e}")
                results[i] = ""
            print(f"Chunk {i + 1}/{len(chunks)} transcribed.")

    full_transcript = " ".join(results[i] for i in sorted(results))
    print("Transcription complete.")
    return full_transcript.strip()

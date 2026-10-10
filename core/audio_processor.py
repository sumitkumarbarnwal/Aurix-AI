"""
audio_processor.py — Audio extraction and chunking pipeline.

Uses PyAV (bundled ffmpeg libraries) instead of an external ffmpeg binary.
PyAV handles: MP4, MKV, AVI, MOV, WebM, MP3, M4A, WAV, FLAC, OGG, and more.
"""

import av
import wave
import os
import glob
import yt_dlp

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

SAMPLE_RATE = 16000  # Whisper requires 16kHz


def convert_to_wav_pyav(input_path: str) -> str:
    """
    Convert any audio or video file to a 16kHz mono WAV using PyAV.
    No external ffmpeg binary needed — PyAV bundles its own libraries.
    """
    output_path = os.path.splitext(input_path)[0] + "_converted.wav"

    with av.open(input_path) as container:
        audio_stream = next(
            (s for s in container.streams if s.type == "audio"), None
        )
        if audio_stream is None:
            raise ValueError(f"No audio stream found in: {input_path}")

        resampler = av.AudioResampler(
            format="s16",   # 16-bit signed PCM
            layout="mono",
            rate=SAMPLE_RATE,
        )

        with wave.open(output_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)          # 16-bit = 2 bytes per sample
            wf.setframerate(SAMPLE_RATE)

            for packet in container.demux(audio_stream):
                for frame in packet.decode():
                    for resampled in resampler.resample(frame):
                        wf.writeframes(resampled.to_ndarray().tobytes())

            # Flush any remaining frames from the resampler
            for resampled in resampler.resample(None):
                wf.writeframes(resampled.to_ndarray().tobytes())

    print(f"  [OK] Converted -> {os.path.basename(output_path)}")
    return output_path


def _get_ffmpeg_path() -> str | None:
    """
    Locate a usable ffmpeg binary — tries imageio-ffmpeg (bundled, no install needed)
    then falls back to system PATH.
    """
    try:
        import imageio_ffmpeg
        path = imageio_ffmpeg.get_ffmpeg_exe()
        if path and os.path.exists(path):
            return path
    except Exception:
        pass

    import shutil
    return shutil.which("ffmpeg")  # None if not found on system PATH


def _prepare_cookie_file() -> str | None:
    """
    Prepares a valid Netscape cookie file for yt-dlp.
    Preserves #HttpOnly_ prefixes which contain critical YouTube session tokens
    (__Secure-3PSID, LOGIN_INFO, SID, HSID, SSID).
    """
    if os.path.exists("cookies.txt"):
        return os.path.abspath("cookies.txt")

    raw = os.getenv("YOUTUBE_COOKIES", "").strip()
    if not raw:
        return None

    import tempfile

    # Case 1: JSON format (e.g. from extensions like EditThisCookie)
    if raw.startswith("[") and raw.endswith("]"):
        try:
            import json
            cookies_json = json.loads(raw)
            lines = ["# Netscape HTTP Cookie File\n"]
            for c in cookies_json:
                domain = c.get("domain", "")
                flag = "TRUE" if domain.startswith(".") else "FALSE"
                path = c.get("path", "/")
                secure = "TRUE" if c.get("secure", False) else "FALSE"
                expiry = int(c.get("expirationDate", c.get("expiry", 0)))
                name = c.get("name", "")
                value = c.get("value", "")
                prefix = "#HttpOnly_" if c.get("httpOnly", False) else ""
                lines.append(f"{prefix}{domain}\t{flag}\t{path}\t{secure}\t{expiry}\t{name}\t{value}\n")
            tmp_cookie = os.path.join(tempfile.gettempdir(), "yt_cookies.txt")
            with open(tmp_cookie, "w", encoding="utf-8") as f:
                f.writelines(lines)
            print(f"  [Cookie] Converted {len(cookies_json)} JSON cookies to Netscape format.")
            return tmp_cookie
        except Exception as e:
            print(f"  [Cookie] Failed to parse JSON cookies: {e}")

    # Case 2: Netscape format (standard cookies.txt)
    # Handle literal escaped newlines or tabs from cloud env vars
    if "\\n" in raw and "\n" not in raw:
        raw = raw.replace("\\n", "\n")
    if "\\t" in raw:
        raw = raw.replace("\\t", "\t")

    lines = raw.splitlines()
    normalized = []
    has_header = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if "Netscape" in stripped:
            has_header = True
            normalized.append(stripped + "\n")
            continue
        # CRITICAL: Preserve #HttpOnly_ cookies! They contain the actual login session tokens.
        if stripped.startswith("#") and not (stripped.startswith("#HttpOnly_") or stripped.startswith("#HttpOnly.")):
            continue

        if "\t" in stripped:
            # Already valid tab-delimited line
            normalized.append(stripped + "\n")
        else:
            # Fallback for space-delimited text from copy-pasting
            parts = stripped.split()
            if len(parts) >= 7:
                domain, flag, path, secure, expiry, name = parts[:6]
                value = " ".join(parts[6:])
                normalized.append(f"{domain}\t{flag}\t{path}\t{secure}\t{expiry}\t{name}\t{value}\n")

    if not has_header:
        normalized.insert(0, "# Netscape HTTP Cookie File\n")

    tmp_cookie = os.path.join(tempfile.gettempdir(), "yt_cookies.txt")
    with open(tmp_cookie, "w", encoding="utf-8") as f:
        f.writelines(normalized)

    cookie_count = len([l for l in normalized if not l.startswith("#") or l.startswith("#HttpOnly_")])
    print(f"  [Cookie] Loaded {cookie_count} valid cookies (including HttpOnly session tokens) from YOUTUBE_COOKIES.")
    return tmp_cookie


def download_youtube_audio(url: str) -> str:
    """
    Download audio from a YouTube URL.
    Attempts best available audio streams with fallback to unconstrained stream download.
    Returns path to converted 16kHz WAV file.
    """
    output_template = os.path.join(DOWNLOAD_DIR, "%(id)s.%(ext)s")

    # Clean up any leftover .part files to prevent HTTP 416 (Requested range not satisfiable)
    for part_file in glob.glob(os.path.join(DOWNLOAD_DIR, "*.part")):
        try:
            os.remove(part_file)
        except OSError:
            pass

    cookie_file = _prepare_cookie_file()

    ydl_opts = {
        "format": "ba/b/bestaudio/best",
        "outtmpl": output_template,
        "quiet": True,
        "overwrites": True,
        "continuedl": False,
        "nopart": True,  # Avoids file locking on rename
        "extractor_args": {
            "youtube": {
                "player_client": ["default", "mweb"]
            }
        }
    }

    if cookie_file:
        ydl_opts["cookiefile"] = cookie_file

    downloaded_path = None
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            downloaded_path = ydl.prepare_filename(info)
    except Exception as e:
        print(f"[Warning] Primary format selection failed ({e}), attempting unconstrained stream fallback...")
        raw_opts = {
            "outtmpl": output_template,
            "quiet": True,
            "overwrites": True,
            "continuedl": False,
            "nopart": True,
            # No 'format' specified: lets yt-dlp select whatever valid stream exists
        }
        if cookie_file:
            raw_opts["cookiefile"] = cookie_file
        with yt_dlp.YoutubeDL(raw_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            downloaded_path = ydl.prepare_filename(info)

    # Resolve the actual file on disk (extension may differ from template)
    if downloaded_path and not os.path.exists(downloaded_path):
        base = os.path.splitext(downloaded_path)[0]
        # Search for any non-temporary file matching the base filename
        matches = [m for m in glob.glob(f"{base}*") if not m.endswith((".part", ".ytdl", ".aria2"))]
        if matches:
            downloaded_path = matches[0]
        else:
            for ext in (".webm", ".m4a", ".mp4", ".opus", ".ogg", ".mp3", ".flac"):
                candidate = base + ext
                if os.path.exists(candidate):
                    downloaded_path = candidate
                    break

    if not downloaded_path or not os.path.exists(downloaded_path):
        raise FileNotFoundError(f"Could not locate downloaded audio file for {url}")

    print(f"  [OK] Downloaded -> {os.path.basename(downloaded_path)}")
    print("  Converting to WAV via PyAV...")
    wav_path = convert_to_wav_pyav(downloaded_path)
    return wav_path




def chunk_audio(wav_path: str, chunk_minutes: int = 2) -> list:
    """
    Split a WAV file into equal-length chunks using Python's built-in wave module.
    No external dependencies required.
    """
    wav_path = os.path.abspath(wav_path)

    with wave.open(wav_path, "rb") as wf:
        frame_rate  = wf.getframerate()
        n_channels  = wf.getnchannels()
        sampwidth   = wf.getsampwidth()
        total_frames = wf.getnframes()
        audio_data  = wf.readframes(total_frames)

    chunk_frames = chunk_minutes * 60 * frame_rate
    bytes_per_frame = n_channels * sampwidth
    chunk_bytes = chunk_frames * bytes_per_frame

    chunks = []
    for i, byte_start in enumerate(range(0, len(audio_data), chunk_bytes)):
        chunk_data = audio_data[byte_start: byte_start + chunk_bytes]
        chunk_path = f"{wav_path}_chunk_{i}.wav"

        with wave.open(chunk_path, "wb") as cf:
            cf.setnchannels(n_channels)
            cf.setsampwidth(sampwidth)
            cf.setframerate(frame_rate)
            cf.writeframes(chunk_data)

        chunks.append(chunk_path)

    return chunks


def process_input(source: str) -> list:
    """Entry point: accepts a YouTube URL or a local file path."""
    if source.startswith("http://") or source.startswith("https://"):
        print("Detected YouTube URL - downloading audio...")
        wav_path = download_youtube_audio(source)
    else:
        print(f"Detected local file - converting to WAV...")
        wav_path = convert_to_wav_pyav(source)

    print("Chunking audio...")
    chunks = chunk_audio(wav_path)
    print(f"Audio ready - {len(chunks)} chunk(s) created.")
    return chunks

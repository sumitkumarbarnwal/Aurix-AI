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


def download_youtube_audio(url: str) -> str:
    """
    Download the best audio stream from a YouTube URL using yt-dlp (no postprocessor),
    then convert it to 16kHz mono WAV using PyAV.
    No ffmpeg/ffprobe binary required.
    """
    output_template = os.path.join(DOWNLOAD_DIR, "%(id)s.%(ext)s")

    # Clean up any leftover .part files to prevent HTTP 416 (Requested range not satisfiable)
    for part_file in glob.glob(os.path.join(DOWNLOAD_DIR, "*.part")):
        try:
            os.remove(part_file)
        except OSError:
            pass

    cookie_file = None
    if os.path.exists("cookies.txt"):
        cookie_file = "cookies.txt"
    elif os.getenv("YOUTUBE_COOKIES"):
        import tempfile
        tmp_cookie = os.path.join(tempfile.gettempdir(), "yt_cookies.txt")
        with open(tmp_cookie, "w", encoding="utf-8") as f:
            f.write(os.getenv("YOUTUBE_COOKIES"))
        cookie_file = tmp_cookie

    ydl_opts = {
        "format": "bestaudio/best/ba*/b*",
        "outtmpl": output_template,
        "quiet": True,
        "overwrites": True,
        "continuedl": False,
        "nopart": True,  # Avoids Windows file locking WinError 32 on rename
        "extractor_args": {
            "youtube": {
                "player_client": ["web", "ios", "android"]
            }
        },
        # No postprocessors — PyAV handles format conversion
    }

    if cookie_file:
        ydl_opts["cookiefile"] = cookie_file

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            downloaded_path = ydl.prepare_filename(info)
    except Exception as e:
        print(f"[Warning] Primary format selection failed ({e}), attempting fallback format...")
        fallback_opts = dict(ydl_opts)
        fallback_opts.pop("extractor_args", None)
        fallback_opts["format"] = "b/ba/worst/best"
        with yt_dlp.YoutubeDL(fallback_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            downloaded_path = ydl.prepare_filename(info)

    # Resolve the actual file on disk (extension may differ from template)
    if not os.path.exists(downloaded_path):
        base = os.path.splitext(downloaded_path)[0]
        for ext in (".webm", ".m4a", ".mp4", ".opus", ".ogg", ".mp3", ".flac"):
            candidate = base + ext
            if os.path.exists(candidate):
                downloaded_path = candidate
                break

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

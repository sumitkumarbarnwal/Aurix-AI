import yt_dlp
from pydub import AudioSegment
import os

DOWNLOAD_DIR = 'downloads'
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def download_youtube_audio(url: str) -> str:
    print("=== Extraction Start ===")
    print(f"Target URL: {url}")

    cookie_path = "/app/cookies.txt"
    # Local fallback for development workspace compatibility
    if not os.path.exists(cookie_path) and os.path.exists("cookies.txt"):
        cookie_path = "cookies.txt"

    print(f"Cookies status: {'FOUND' if os.path.exists(cookie_path) else 'NOT FOUND'} at {cookie_path}")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": "downloads/%(id)s.%(ext)s",
        "quiet": False,
        "noplaylist": True,
        "cookiefile": cookie_path,
        "nocheckcertificate": True,
        "retries": 10,
        "fragment_retries": 10,
        "source_address": "0.0.0.0",
        "extractor_args": {
            "youtube": {
                "player_client": ["android"]
            }
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print("Initiating clean yt-dlp extraction...")
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            print(f"yt-dlp download completed successfully: {filename}")
            
            # Keep Whisper-compatible audio output by ensuring conversion to WAV works
            if not filename.lower().endswith(".wav"):
                print(f"Downloaded file: {filename} is not WAV. Converting to WAV format...")
                filename = convert_to_wav(filename)
                print(f"Conversion complete: {filename}")
                
            return filename
    except Exception as e:
        print(f"Extraction failed with error: {e}. Trying fallback format...")
        # Fallback handling if bestaudio is unavailable
        ydl_opts["format"] = "best"
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                print(f"Fallback download completed: {filename}")
                if not filename.lower().endswith(".wav"):
                    filename = convert_to_wav(filename)
                    print(f"Fallback conversion complete: {filename}")
                return filename
        except Exception as fallback_err:
            print(f"CRITICAL: All download and fallback attempts failed: {fallback_err}")
            raise RuntimeError(f"YouTube download failed: {fallback_err}")



def convert_to_wav(input_path: str) -> str:
    """Convert any audio/video file to WAV format using pydub."""
    output_path = os.path.splitext(input_path)[0] + "_converted.wav"
    audio = AudioSegment.from_file(input_path)
    audio = audio.set_channels(1).set_frame_rate(16000) #16khz
    audio.export(output_path, format="wav")
    return output_path



def chunk_audio(wav_path : str , chunk_minutes : int = 10) -> list:
    audio = AudioSegment.from_wav(wav_path)
    chunk_ms = chunk_minutes * 60 * 1000 

    chunks = []

    for i, start in enumerate(range(0,len(audio),chunk_ms)):
        chunk = audio[start : start + chunk_ms]
        chunk_path = f"{wav_path}_chunk_{i}.wav"
        chunk.export(chunk_path , format = "wav")

        chunks.append(chunk_path)
    
    return chunks

def process_input(source: str) -> list:
    if source.startswith("http://") or source.startswith("https://"):
        print("Detected YouTube URL. Downloading audio...")
        wav_path = download_youtube_audio(source)
    else:
        print("Detected local file. Converting to WAV...")
        wav_path = convert_to_wav(source)

    print("Chunking audio...")
    chunks = chunk_audio(wav_path)
    print(f"Audio ready — {len(chunks)} chunk(s) created.")
    return chunks



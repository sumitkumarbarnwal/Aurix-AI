import yt_dlp
from pydub import AudioSegment
import os

DOWNLOAD_DIR = 'downloades'
os.makedirs(DOWNLOAD_DIR,exist_ok = True)

def download_youtube_audio(url :str) ->str:
    output_path = os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s")
    
    # Securely generate cookies.txt from environment variable if provided (Hugging Face Secret)
    # This prevents leaking sensitive YouTube session cookies in a public Git repository.
    cookies_content = os.getenv("COOKIES_CONTENT")
    if cookies_content:
        with open("cookies.txt", "w") as f:
            f.write(cookies_content)

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_path,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "192",
            }
        ],
        "quiet": True,
        # Prefer Python's built-in urllib handler over the requests library (bypasses requests TLS handshake blocks)
        "compat_options": ["prefer-legacy-http-handler"],
        # Allow yt-dlp to download the official EJS signature decryption scripts directly from GitHub at runtime
        "remote_components": ["ejs:github"],
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
    }
    
    # Try to impersonate a browser TLS fingerprint to bypass cloud server blocking (UNEXPECTED_EOF_WHILE_READING)
    try:
        from yt_dlp.networking.impersonate import ImpersonateTarget
        ydl_opts["impersonate"] = ImpersonateTarget.from_str("chrome")
        print("Successfully enabled TLS impersonation for YouTube downloads!")
    except Exception as e:
        print(f"WARNING: TLS impersonation failed to load (falling back to standard): {e}")
    
    # Check if cookies.txt is provided to bypass YouTube bot detection (critical for cloud hosting)
    cookie_path = "cookies.txt"
    if os.path.exists(cookie_path):
        print(f"INFO: cookies.txt was successfully created and found in workspace! Size: {os.path.getsize(cookie_path)} bytes")
        ydl_opts["cookiefile"] = cookie_path
    elif os.path.exists("cookies.txt.txt"):
        print(f"INFO: cookies.txt.txt was found in workspace! Size: {os.path.getsize('cookies.txt.txt')} bytes")
        ydl_opts["cookiefile"] = "cookies.txt.txt"
    else:
        print("WARNING: No cookies file found! YouTube downloads will likely fail.")
        
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info).replace(".webm", ".wav").replace(".m4a", ".wav")
    except Exception as e:
        # Bulletproof self-healing: If any error occurs while impersonation is enabled, retry without it
        if "impersonate" in ydl_opts:
            print(f"WARNING: Download failed with TLS impersonation enabled: {e}")
            print("Retrying download cleanly without TLS impersonation...")
            ydl_opts.pop("impersonate", None)
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    filename = ydl.prepare_filename(info).replace(".webm", ".wav").replace(".m4a", ".wav")
            except Exception as retry_err:
                print(f"ERROR: Download failed even without TLS impersonation: {retry_err}")
                raise retry_err
        else:
            raise e
            
    return filename



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



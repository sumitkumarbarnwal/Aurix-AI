import yt_dlp
from pydub import AudioSegment
import os

DOWNLOAD_DIR = 'downloads'
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def download_youtube_audio(url: str) -> str:
    print(f"=== Extraction Start ===")
    print(f"Target URL: {url}")
    
    cookie_file = "cookies.txt"
    cookies_exist = os.path.exists(cookie_file)
    print(f"Cookies status: {'FOUND' if cookies_exist else 'NOT FOUND'} ({cookie_file})")
    
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": "downloads/%(id)s.%(ext)s",
        "quiet": False,
        "noplaylist": True,
        "cookiefile": cookie_file,
        "nocheckcertificate": True,

        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web"]
            }
        },

        "retries": 10,
        "fragment_retries": 10,
        "source_address": "0.0.0.0",

        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "192",
            }
        ]
    }
    
    try:
        print("Initiating yt-dlp download with primary format ('bestaudio/best')...")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            # Post-processed extension will be converted to .wav
            raw_filename = ydl.prepare_filename(info)
            filename = os.path.splitext(raw_filename)[0] + ".wav"
            
            if os.path.exists(filename):
                print(f"Extraction SUCCESS: {filename}")
                return filename
            else:
                raise FileNotFoundError(f"Expected WAV file not found at: {filename}")
                
    except Exception as e:
        print(f"WARNING: Primary extraction failed: {e}")
        print("Initiating fallback format extraction ('best')...")
        
        # Graceful fallback: adjust format to best merged format
        ydl_opts["format"] = "best"
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                raw_filename = ydl.prepare_filename(info)
                filename = os.path.splitext(raw_filename)[0] + ".wav"
                
                if os.path.exists(filename):
                    print(f"Fallback Extraction SUCCESS: {filename}")
                    return filename
                    
                # If WAV wasn't extracted, look for raw file and manually convert
                if os.path.exists(raw_filename):
                    print(f"Raw file downloaded without WAV post-processing: {raw_filename}. Converting manually...")
                    converted_path = convert_to_wav(raw_filename)
                    print(f"Manual conversion SUCCESS: {converted_path}")
                    return converted_path
                else:
                    raise FileNotFoundError(f"Expected raw file not found at: {raw_filename}")
                    
        except Exception as fallback_err:
            print(f"CRITICAL: All download and fallback attempts failed. Fallback error: {fallback_err}")
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



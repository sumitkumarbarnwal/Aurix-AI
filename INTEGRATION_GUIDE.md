# Aurix AI — Backend Pipeline & Frontend Dashboard Integration Guide

## ✅ Integration Complete

The Aurix AI backend pipeline has been successfully integrated with the custom HTML/CSS/JS frontend dashboard via a Flask API server.

---

## 🚀 Quick Start

### 1. **Prerequisites**
- Python 3.10+
- All dependencies installed (see `requirements.txt`)
- MISTRAL_API_KEY configured in `.env`

### 2. **Environment Setup**

Edit `.env` file and ensure:
```env
MISTRAL_API_KEY=your_api_key_here
WHISPER_MODEL=small
```

### 3. **Start the Server**

```bash
cd "d:\Projects\Aurix AI"
python server.py
```

Expected output:
```
============================================================
  🚀 Aurix AI Server
  📍 http://127.0.0.1:8080
  Dashboard: http://127.0.0.1:8080/dashboard.html
============================================================

 * Running on http://127.0.0.1:8080
```

### 4. **Access the Dashboard**

Open browser to: **http://127.0.0.1:8080/**

1. Click "Get Started Free" or "Sign in with Google"
2. After authentication, you'll be redirected to `/dashboard.html`
3. Paste a YouTube URL or upload a file
4. Select language (English or Hinglish)
5. Click validate and watch the pipeline progress

---

## 📋 Architecture Overview

### Backend Components (Python)

```
core/
├── audio_processor.py     → Download YouTube audio, convert to WAV, chunk
├── transcriber.py         → Whisper (English) or Sarvam API (Hinglish)
├── summarizer.py          → LangChain + Mistral LLM (map-reduce)
├── extractor.py           → Extract action items, decisions, questions
├── rag_engine.py          → Build RAG chain for Q&A
└── vector_store.py        → ChromaDB + HuggingFace embeddings

server.py                   → Flask API server with CORS & SSE
```

### Frontend Components (JavaScript)

```
frontend/
├── index.html             → Landing page with Google OAuth login
├── dashboard.html         → Main dashboard UI
├── dashboard.js           → Real API integration, SSE polling, chat
├── dashboard.css          → Dashboard styling
├── script.js              → Index page logic
└── style.css              → Index page styling
```

---

## 🔌 API Endpoints

### Authentication

**POST** `/api/auth/google`
- Request: `{ credential: "jwt_token" }`
- Response: `{ success: true, user: {...}, session_id: "uuid" }`

**GET** `/api/auth/session`
- Response: `{ authenticated: true, user: {...} }` or `{ authenticated: false }` (401)

**POST** `/api/auth/logout`
- Response: `{ success: true }`

### Pipeline Processing

**POST** `/api/process`
- Request (Form Data or JSON):
  - `session_id`: UUID (optional, generated if not provided)
  - `url` or `file`: YouTube URL or file upload
  - `language`: "english" or "hinglish"
- Response: `{ success: true, session_id: "uuid", message: "Processing started" }`

**GET** `/api/status/<session_id>`
- Response: `{ step: "current_step", progress: 0-100, detail: "message" }`
- Possible steps:
  - `starting` → `audio` → `audio_done` → `transcription` → `transcription_done`
  - `title` → `title_done` → `summary` → `summary_done`
  - `extraction` → `extraction_done` → `rag` → `rag_done` → `complete` or `error`

**GET** `/api/status/stream/<session_id>` (Server-Sent Events)
- Stream real-time progress updates
- Client receives JSON objects with step, progress, detail

**GET** `/api/result/<session_id>`
- Response:
  ```json
  {
    "success": true,
    "result": {
      "title": "Meeting title",
      "summary": "Bullet-point summary",
      "action_items": "Numbered list",
      "key_decisions": "Numbered list",
      "open_questions": "Numbered list",
      "transcript": "First 5000 chars of transcript"
    }
  }
  ```

### RAG Chat

**POST** `/api/chat`
- Request: `{ session_id: "uuid", question: "Your question?" }`
- Response: `{ success: true, answer: "Answer based on transcript" }`

---

## 🔄 Pipeline Flow

```
1. User uploads URL or file via dashboard
   ↓
2. Flask server receives /api/process request
   ↓
3. Background thread starts pipeline:
   - Audio Processing (download YouTube / convert file)
   - Transcription (Whisper or Sarvam)
   - Title Generation (Mistral)
   - Summarization (LangChain map-reduce)
   - Extraction (Action items, decisions, questions)
   - RAG Engine (Build vector store)
   ↓
4. Status updates sent via SSE or polled via GET
   ↓
5. Frontend displays progress in real-time
   ↓
6. Results populated in analysis tabs:
   - Smart Summary → summary
   - Fact Checked Research → action_items
   - Synthesis Overview → key_decisions
   - Verification Report → open_questions
   ↓
7. User can ask questions via RAG chat
```

---

## 🎨 Frontend Features

### Upload Panel
- **Language Selector**: English (Whisper) or Hinglish (Sarvam)
- **URL Input**: Paste YouTube URL
- **File Upload**: Drag & drop or browse
- **Pipeline Progress**: Visual 4-step progress indicator

### Analysis Panel
- **Tabs**: Smart Summary, Fact Check, Synthesis, Verification
- **Dynamic Content**: Results auto-populate after processing
- **Chat Section**: Ask questions about the transcript
- **Light/Dark Mode**: Theme toggle in navbar
- **Real-time Updates**: SSE + fallback polling

---

## ⚙️ Configuration

### .env File

```env
# REQUIRED: Mistral AI API Key
MISTRAL_API_KEY=your_key_here

# OPTIONAL: Sarvam AI for Hinglish
SARVAM_API_KEY=

# OPTIONAL: Whisper model size (tiny, base, small, medium, large)
WHISPER_MODEL=small

# OPTIONAL: Google OAuth
GOOGLE_CLIENT_ID=

# OPTIONAL: Flask secret
FLASK_SECRET_KEY=change-in-production
```

### requirements.txt

All dependencies pre-configured:
- Flask, Flask-CORS
- yt-dlp, pydub, ffmpeg-python
- openai-whisper, torch, torchaudio
- langchain, langchain-mistralai, mistralai
- chromadb, sentence-transformers, langchain-huggingface
- And 20+ others

---

## 🐛 Troubleshooting

### Issue: "MISTRAL_API_KEY is not set"
**Solution**: Add your API key to `.env` file and restart server.

### Issue: "Couldn't find ffmpeg"
**Solution**: Install FFmpeg (Windows):
```powershell
# Option 1: Chocolatey
choco install ffmpeg

# Option 2: Manual
# Download from https://ffmpeg.org/download.html
# Add to PATH
```

### Issue: "ModuleNotFoundError: No module named..."
**Solution**: Install missing package:
```bash
pip install langchain-chroma sentence-transformers langchain-huggingface
```

### Issue: Server won't start / slow startup
**Note**: First startup is slow due to TensorFlow + Transformer models loading.
- Sentence-transformers downloads embedding model (~500MB)
- TensorFlow loads CUDA/CPU acceleration
- Subsequent startups are faster (cached)

### Issue: Dashboard redirects to index.html
**Note**: This is expected if not authenticated. Sign in with Google first.

### Issue: API returns 500 error
**Check**: Server logs for traceback. Most likely causes:
- Missing `MISTRAL_API_KEY`
- File upload too large
- Audio processing failed (ffmpeg missing)
- Transcript too short for summarization

---

## 📊 Performance Notes

### Processing Time Estimates
- **Audio Download & Convert**: 30-60 sec (depends on video length)
- **Transcription**: 1-2 min per 10-minute chunk
- **Summarization**: 30-45 sec
- **Extraction**: 20-30 sec
- **RAG Build**: 10-15 sec
- **Total**: 2-5 min for 30-min video

### Memory Usage
- Initial load: ~500-800MB (TensorFlow, transformers)
- Per-session: ~200MB (transcript, vector store)
- Multiple sessions: Stack memory up

### Disk Space
- Vector DB: ~50MB per session (ChromaDB persists to `vector_db/`)
- Downloaded audio: ~10-50MB per video (in `downloads/`)
- Uploads: Temp storage in `uploads/`

---

## 🔐 Security

### Implemented
✅ CORS configured (API endpoints accessible from frontend)  
✅ Session-based state management  
✅ Google OAuth for authentication  
✅ Input validation on file upload  
✅ Backend processes run in isolated threads  

### Recommended for Production
- Use HTTPS (install SSL certificate)
- Implement rate limiting on `/api/process`
- Add request authentication middleware
- Store sensitive data in secure vault (not .env)
- Use production WSGI server (Gunicorn, uWSGI)
- Add request logging & monitoring

---

## 📝 Example Usage

### Via JavaScript (Frontend)
```javascript
// 1. Start processing
const response = await fetch('http://127.0.0.1:8080/api/process', {
  method: 'POST',
  body: formData, // { session_id, url, language, file }
});
const { session_id } = await response.json();

// 2. Listen to real-time progress
const eventSource = new EventSource(`/api/status/stream/${session_id}`);
eventSource.onmessage = (event) => {
  const { step, progress, detail } = JSON.parse(event.data);
  console.log(`${step}: ${progress}%`);
};

// 3. Get results
const resultRes = await fetch(`/api/result/${session_id}`);
const { result } = await resultRes.json();
console.log(result.summary);

// 4. Ask a question
const chatRes = await fetch('/api/chat', {
  method: 'POST',
  body: JSON.stringify({ session_id, question: "What are the action items?" }),
});
const { answer } = await chatRes.json();
console.log(answer);
```

### Via cURL (Testing)
```bash
# Test API endpoint
curl -v http://127.0.0.1:8080/api/status/test-session

# Submit URL
curl -X POST http://127.0.0.1:8080/api/process \
  -F "url=https://www.youtube.com/watch?v=..." \
  -F "language=english" \
  -F "session_id=test-123"

# Ask a question
curl -X POST http://127.0.0.1:8080/api/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"test-123","question":"What were the decisions?"}'
```

---

## 📚 File Structure

```
d:\Projects\Aurix AI\
├── server.py              ← Main Flask app (START HERE)
├── .env                   ← Configuration (API keys)
├── requirements.txt       ← Python dependencies
├── INTEGRATION_GUIDE.md   ← This file
│
├── core/
│   ├── __init__.py
│   ├── audio_processor.py
│   ├── transcriber.py
│   ├── summarizer.py
│   ├── extractor.py
│   ├── rag_engine.py
│   └── vector_store.py
│
├── frontend/
│   ├── index.html         ← Landing page
│   ├── dashboard.html     ← Main dashboard
│   ├── dashboard.js       ← Dashboard logic
│   ├── dashboard.css      ← Dashboard styles
│   ├── script.js
│   └── style.css
│
├── downloads/             ← YouTube audio (auto-created)
├── uploads/               ← Uploaded files (auto-created)
└── vector_db/             ← ChromaDB storage (auto-created)
```

---

## 🎯 Next Steps

### Development
1. ✅ Run `python server.py`
2. ✅ Open `http://127.0.0.1:8080/`
3. ✅ Sign in with Google
4. ✅ Submit a YouTube URL or upload file
5. ✅ Watch real-time pipeline progress
6. ✅ Ask questions via RAG chat

### Customization
- Edit `frontend/dashboard.css` for custom styling
- Modify `core/summarizer.py` prompts for different output format
- Adjust chunk sizes in `core/audio_processor.py` (longer = faster but less detailed)
- Change Mistral model in `core/summarizer.py` to "mistral-large-latest"

### Production Deployment
- Use Gunicorn + Nginx
- Add database (PostgreSQL) for session persistence
- Implement task queue (Redis + Celery) for async processing
- Add monitoring (Prometheus, Grafana)
- Set up CI/CD pipeline (GitHub Actions)

---

## 📞 Support

For issues or feature requests, check:
1. Server logs in terminal (check for errors)
2. Browser console (F12 → Console tab)
3. `.env` configuration (ensure MISTRAL_API_KEY is set)
4. Network tab in DevTools (verify API calls are reaching server)

---

**Aurix AI Integration — Status: ✅ COMPLETE & RUNNING**

Happy analyzing! 🚀

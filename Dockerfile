FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies (ffmpeg, nodejs for YouTube challenge solving, curl)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    nodejs \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install PyTorch CPU first to keep image lightweight (<200MB vs >1.5GB CUDA)
RUN pip install --no-cache-dir torch torchaudio --index-url https://download.pytorch.org/whl/cpu

# Install remaining requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Ensure upload/download directories exist
RUN mkdir -p downloads uploads vector_db

# Expose port (Render sets $PORT dynamically)
ENV PORT=8080
EXPOSE 8080

# Run with Gunicorn (timeout 300s for audio processing)
CMD ["sh", "-c", "gunicorn -w 1 --threads 4 --timeout 300 -b 0.0.0.0:$PORT server:app"]

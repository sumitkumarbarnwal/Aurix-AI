# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_APP=server.py \
    FLASK_RUN_HOST=0.0.0.0 \
    FLASK_PORT=7860

# Install system dependencies (ffmpeg is required for audio/video processing, nodejs solves the YouTube signature challenge)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    gcc \
    ca-certificates \
    nodejs \
    && rm -rf /var/lib/apt/lists/*

# Set up a new user named "user" with user ID 1000
# Hugging Face Spaces require the app to run as a non-root user (uid 1000)
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"

# Set work directory
WORKDIR /app

# Install python dependencies
COPY --chown=user Requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r Requirements.txt

# Copy project with proper permissions
COPY --chown=user . /app/

# Ensure the upload and vector_db directories exist with correct permissions
RUN mkdir -p /app/uploads /app/vector_db

# Hugging Face uses port 7860
EXPOSE 7860

# Run the application
CMD ["python", "server.py"]

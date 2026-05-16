# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_APP=server.py \
    FLASK_RUN_HOST=0.0.0.0

# Set work directory
WORKDIR /app

# Install system dependencies (ffmpeg is required for audio/video processing)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY Requirements.txt /app/
RUN pip install --upgrade pip && \
    pip install -r Requirements.txt

# Copy project
COPY . /app/

# Expose port
EXPOSE 5000

# Run the application
CMD ["python", "server.py"]

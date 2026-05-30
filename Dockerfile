# ── AI Smart Traffic Monitor — Docker Image ───────────────────────────────────
# GPU-enabled build (requires nvidia-docker on host)
# Build:  docker build -t ai-traffic-monitor .
# Run:    docker run --gpus all -p 8501:8501 -p 8000:8000 ai-traffic-monitor

FROM nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04

# System dependencies
RUN apt-get update && apt-get install -y \
    python3.11 python3-pip \
    libgl1 libglib2.0-0 libsm6 libxext6 libxrender-dev \
    ffmpeg libavcodec-dev libavformat-dev libswscale-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python dependencies (cached layer)
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Create runtime directories
RUN mkdir -p logs results/violations results/output_videos assets models

# Expose ports
EXPOSE 8501 8000

# Default: run Streamlit dashboard
# Override CMD to run FastAPI: docker run ... uvicorn api.main:app --host 0.0.0.0
CMD ["streamlit", "run", "dashboard/app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]

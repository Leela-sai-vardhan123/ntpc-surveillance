# 🚦 AI Smart Traffic Monitoring System

[![CI](https://github.com/YOUR_USERNAME/ai-smart-traffic-monitor/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_USERNAME/ai-smart-traffic-monitor/actions)
![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)
![YOLOv8](https://img.shields.io/badge/YOLOv8-Ultralytics-00BFFF)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi)
![Streamlit](https://img.shields.io/badge/Streamlit-1.35-FF4B4B?logo=streamlit)
![Docker](https://img.shields.io/badge/Docker-GPU--enabled-2496ED?logo=docker)
![License](https://img.shields.io/badge/License-MIT-green)

> **Production-grade AI traffic surveillance system** built during NTPC internship.
> Detects vehicles, estimates speed, reads Indian license plates, and flags helmet violations — all in real time.

---

## 📸 Demo

> *(Add a screen-recorded GIF of the Streamlit dashboard here)*
> Tool: [ScreenToGif](https://www.screentogif.com/) — record your desktop → export as GIF → drag into README

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   Traffic Camera Feed                        │
│              (Video File / Webcam / RTSP)                    │
└───────────────────────────┬─────────────────────────────────┘
                            │
                   ┌────────▼────────┐
                   │  YOLOv8 Vehicle │  GPU-optimized
                   │    Detector     │  FP16 inference
                   └────────┬────────┘
                            │
                   ┌────────▼────────┐
                   │  DeepSORT       │  Appearance embedding
                   │  Multi-Tracker  │  Occlusion handling
                   └────────┬────────┘
                            │
          ┌─────────────────┼──────────────────┐
          │                 │                  │
  ┌───────▼──────┐ ┌────────▼───────┐ ┌───────▼──────┐
  │ Speed        │ │ Plate          │ │ Helmet       │
  │ Estimator    │ │ Detector + OCR │ │ Detector     │
  │ (line cross) │ │ (YOLOv8+EasyOCR│ │ (YOLOv8)     │
  └───────┬──────┘ └────────┬───────┘ └───────┬──────┘
          │                 │                  │
          └─────────────────▼──────────────────┘
                            │
                   ┌────────▼────────┐
                   │ Violation Logger │  CSV + SQLite
                   │ Evidence Saver  │  JPEG images
                   │ Alert System    │  Buzzer sound
                   └────────┬────────┘
                            │
              ┌─────────────┴─────────────┐
              │                           │
     ┌────────▼────────┐        ┌────────▼────────┐
     │ Streamlit        │        │ FastAPI REST     │
     │ Dashboard        │        │ /violations      │
     │ Live feed + KPIs │        │ /stats  /health  │
     └─────────────────┘        └─────────────────┘
```

---

## ✨ Features

| Feature | Details |
|---|---|
| 🚗 **Vehicle Detection** | YOLOv8 — car, truck, bus, motorcycle |
| 🎯 **DeepSORT Tracking** | Stable IDs through occlusion, appearance features |
| ⚡ **GPU Optimized** | FP16 half-precision, layer fusion, kernel warmup |
| 🔢 **Speed Estimation** | Dual virtual line crossing + timestamp delta |
| 🪪 **Plate Detection** | YOLOv8 trained on Indian number plate dataset |
| 📖 **OCR** | EasyOCR with Indian plate format regex validation |
| ⛑️ **Helmet Detection** | YOLOv8 for construction + bike rider helmets |
| 🔊 **Buzzer Alert** | Auto-generated WAV, plays on every violation |
| 📋 **Violation Logging** | CSV + SQLite + JPEG evidence images |
| 📊 **Streamlit Dashboard** | Live feed, KPIs, Plotly charts, CSV export |
| 🌐 **FastAPI Backend** | REST API with Swagger docs at `/docs` |
| 🐳 **Docker** | GPU-enabled container, docker-compose ready |
| 🤖 **GitHub Actions CI** | Auto lint on every push |

---

## 📁 Project Structure

```
ai-smart-traffic-monitor/
├── core/
│   ├── pipeline.py           # Main detection + tracking engine
│   ├── deepsort_tracker.py   # DeepSORT wrapper
│   └── gpu_config.py         # Device selection + FP16 + warmup
├── utils/
│   ├── speed.py              # Virtual line speed estimator
│   ├── helmet.py             # Helmet detection module
│   ├── plate_ocr.py          # Plate detection + EasyOCR
│   ├── alert.py              # Buzzer sound alert system
│   └── logger.py             # CSV + SQLite + evidence images
├── api/
│   └── main.py               # FastAPI REST backend
├── dashboard/
│   └── app.py                # Streamlit dashboard
├── models/                   # Place .pt files here
├── assets/                   # Auto-generated buzzer.wav
├── logs/                     # violations.csv + violations.db
├── results/violations/       # Evidence JPEG images
├── Dockerfile                # GPU-enabled Docker image
├── docker-compose.yml        # Dashboard + API services
├── .github/workflows/ci.yml  # GitHub Actions CI
├── .env.example              # Environment variable template
└── requirements.txt
```

---

## 🚀 Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/YOUR_USERNAME/ai-smart-traffic-monitor.git
cd ai-smart-traffic-monitor

pip install -r requirements.txt
```

### 2. Add Your Models

```
models/
├── yolov8n.pt          ← auto-downloaded by ultralytics
├── plate_best.pt       ← your trained plate model
└── helmet_best.pt      ← your trained helmet model
```

### 3. Run Dashboard

```bash
streamlit run dashboard/app.py
# Open: http://localhost:8501
```

### 4. Run API (separate terminal)

```bash
uvicorn api.main:app --reload --port 8000
# Swagger UI: http://localhost:8000/docs
```

### 5. Docker (optional)

```bash
docker-compose up --build
# Dashboard → http://localhost:8501
# API       → http://localhost:8000/docs
```

---

## 🧠 Model Training

### Helmet Detection (Google Colab)

```python
from roboflow import Roboflow
rf = Roboflow(api_key="YOUR_KEY")
project = rf.workspace("joseph-nelson").project("hard-hat-workers")
dataset = project.version(1).download("yolov8")

from ultralytics import YOLO
model = YOLO("yolov8n.pt")
model.train(data=f"{dataset.location}/data.yaml", epochs=50, imgsz=640, device=0)
# → copy runs/detect/train/weights/best.pt to models/helmet_best.pt
```

### Plate Detection

```python
from ultralytics import YOLO
model = YOLO("yolov8n.pt")
model.train(data="Indian number plate.v2i.yolov8/data.yaml", epochs=50, imgsz=640)
# → copy runs/detect/train/weights/best.pt to models/plate_best.pt
```

---

## 🌐 API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | System info |
| `/health` | GET | Health check |
| `/violations` | GET | List violations (filterable) |
| `/violations/{id}` | GET | Single violation |
| `/violations/{id}/evidence` | GET | Download evidence image |
| `/stats` | GET | Aggregated analytics |
| `/docs` | GET | Swagger UI |

---

## ⚙️ Configuration

Copy `.env.example` → `.env` and set your values:

```bash
cp .env.example .env
```

Key settings:
- `ENTRY_LINE_Y` / `EXIT_LINE_Y` — calibrate to your camera angle
- `REAL_DISTANCE_METERS` — actual road distance between lines
- `SPEED_LIMIT_*` — per vehicle type limits

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Detection | YOLOv8 (Ultralytics) |
| Tracking | DeepSORT (deep-sort-realtime) |
| OCR | EasyOCR |
| GPU | CUDA + FP16 (PyTorch) |
| Dashboard | Streamlit + Plotly |
| Backend | FastAPI + Uvicorn |
| Database | SQLite (via Python stdlib) |
| Container | Docker + nvidia-docker |
| CI | GitHub Actions |

---

## 📄 License

MIT — free to use, modify, and distribute.



https://ntpc-surveillance-nlsvardhan.streamlit.app/

---

<p align="center">
  Built with ❤️ during <strong>NTPC Internship 2024</strong><br>
  <sub>Computer Vision · Deep Learning · Real-Time Systems</sub>
</p>

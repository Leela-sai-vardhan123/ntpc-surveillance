"""
Downloads a working pretrained helmet detection model.
Run: python download_helmet.py
"""

import subprocess
import sys
import os

subprocess.run([sys.executable, "-m", "pip", "install", "huggingface_hub", "-q"])

from huggingface_hub import hf_hub_download

os.makedirs("models", exist_ok=True)

print("Downloading helmet model from HuggingFace...")

try:
    path = hf_hub_download(
        repo_id   = "keremberke/yolov8n-helmet-detection",
        filename  = "best.pt",
        local_dir = "models",
    )
    dest = os.path.join("models", "helmet_best.pt")
    if os.path.exists(path) and path != dest:
        os.replace(path, dest)
    print(f"Saved to: {dest}")

    from ultralytics import YOLO
    m = YOLO(dest)
    print("Classes:", m.names)
    print("\nSuccess! helmet_best.pt is ready in models/")

except Exception as e:
    print(f"HuggingFace failed: {e}")
    print("\nManual download instructions:")
    print("1. Open browser and go to:")
    print("   https://huggingface.co/keremberke/yolov8n-helmet-detection/tree/main")
    print("2. Click 'best.pt' then click Download")
    print("3. Rename downloaded file to: helmet_best.pt")
    print("4. Move it to: E:\\NTPC-INT\\models\\helmet_best.pt")
    print("5. Then run:")
    print("   python -c \"from ultralytics import YOLO; m=YOLO('models/helmet_best.pt'); print(m.names)\"")

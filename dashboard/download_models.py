import os
import gdown

os.makedirs("models", exist_ok=True)

MODEL_CONFIG = {
    "models/yolov8n.pt": {
        "gdrive_id": "1XFw_YnV5RqoPf-fafIC0sWmAUrSTFAtv",
    },
    "models/detect_license.pt": {
        "gdrive_id": "1UflZGDhwQM8EDh77rpccULdrB0mgiKo1",
    },
    "models/helmet_best.pt": {
        "gdrive_id": "1TryEYSomkgVsReLk7TcD4TnmSHmRoKyg",
    },
}

for model_path, config in MODEL_CONFIG.items():
    
    if not os.path.exists(model_path):
        print(f"Downloading {model_path}...")
        
        url = f"https://drive.google.com/uc?id={config['gdrive_id']}"
        
        gdown.download(url, model_path, quiet=False)

print("All models ready.")
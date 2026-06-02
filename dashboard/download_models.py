import os
import re
import urllib.request
import urllib.parse

# Get absolute path to the repository root
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def root_path(rel):
    return os.path.join(ROOT, rel)

# Create models directory if it doesn't exist
models_dir = root_path("models")
os.makedirs(models_dir, exist_ok=True)

MODEL_CONFIG = {
    root_path("models/yolov8n.pt"): {
        "gdrive_id": "1XFw_YnV5RqoPf-fafIC0sWmAUrSTFAtv",
    },
    root_path("models/detect_license.pt"): {
        "gdrive_id": "1UflZGDhwQM8EDh77rpccULdrB0mgiKo1",
    },
    root_path("models/helmet_best.pt"): {
        "gdrive_id": "1TryEYSomkgVsReLk7TcD4TnmSHmRoKyg",
    },
}

def download_file_from_google_drive(file_id, destination):
    # Setup opener with cookie support to handle the session cookies
    cookie_processor = urllib.request.HTTPCookieProcessor()
    opener = urllib.request.build_opener(cookie_processor)
    opener.addheaders = [('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)')]
    urllib.request.install_opener(opener)

    url = "https://docs.google.com/uc?export=download"
    req_url = f"{url}&id={file_id}"

    try:
        # First request to get the warning page
        with urllib.request.urlopen(req_url) as response:
            html = response.read().decode('utf-8', errors='ignore')

        # Check if Google Drive virus warning page was returned
        if "Google Drive - Virus scan warning" in html or "confirm" in html:
            # Parse form action
            action_match = re.search(r'<form[^>]*action="([^"]+)"[^>]*>', html)
            action_url = action_match.group(1) if action_match else "https://drive.usercontent.google.com/download"
            if action_url.startswith('/'):
                action_url = "https://drive.usercontent.google.com" + action_url

            # Parse inputs (confirm, uuid, id, export)
            inputs = re.findall(r'<input[^>]*name="([^"]+)"[^>]*value="([^"]*)"[^>]*>', html)
            if not inputs:
                inputs = re.findall(r'<input[^>]*value="([^"]*)"[^>]*name="([^"]+)"[^>]*>', html)
                inputs = [(n, v) for v, n in inputs]

            params = {}
            for name, value in inputs:
                if name in ['id', 'export', 'confirm', 'uuid']:
                    params[name] = value

            if 'confirm' not in params:
                confirm_match = re.search(r'confirm=([a-zA-Z0-9_-]+)', html)
                if confirm_match:
                    params['confirm'] = confirm_match.group(1)

            query_string = urllib.parse.urlencode(params)
            download_url = f"{action_url}?{query_string}"
        else:
            download_url = req_url

        # Stream download the file
        print(f"Downloading from Google Drive: {download_url[:100]}...")
        with urllib.request.urlopen(download_url) as response:
            content_type = response.headers.get('Content-Type', '')
            if 'text/html' in content_type:
                print("Error: The download request returned HTML (page layout) instead of binary weights.")
                return False
                
            with open(destination, 'wb') as f:
                while True:
                    chunk = response.read(32768)
                    if not chunk:
                        break
                    f.write(chunk)
        return True
    except Exception as e:
        print(f"Error during Google Drive download for {file_id}: {e}")
        return False

# Download any missing models
for model_path, config in MODEL_CONFIG.items():
    if not os.path.exists(model_path):
        print(f"Model file missing: {os.path.basename(model_path)}")
        print(f"Starting download to {model_path}...")
        success = download_file_from_google_drive(config['gdrive_id'], model_path)
        if success:
            print(f"Successfully downloaded: {os.path.basename(model_path)}")
        else:
            print(f"FAILED to download: {os.path.basename(model_path)}")
            # Cleanup if empty/corrupted file was created
            if os.path.exists(model_path) and os.path.getsize(model_path) < 10000:
                try:
                    os.remove(model_path)
                except:
                    pass
    else:
        print(f"Model file ready: {os.path.basename(model_path)}")

print("All models ready.")
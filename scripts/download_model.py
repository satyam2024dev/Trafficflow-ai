"""Download the YOLO weights into ai/models/.   Usage:  python scripts/download_model.py [model_name]"""
import sys
import urllib.request
from pathlib import Path

name = sys.argv[1] if len(sys.argv) > 1 else "yolo11n.pt"
dest = Path(__file__).resolve().parent.parent / "ai" / "models" / name
dest.parent.mkdir(parents=True, exist_ok=True)
if dest.exists():
    print(f"Already present: {dest}")
    sys.exit(0)
url = f"https://github.com/ultralytics/assets/releases/download/v8.4.0/{name}"
print(f"Downloading {url}")
try:
    urllib.request.urlretrieve(url, dest)
except Exception as e:
    dest.unlink(missing_ok=True)
    print(f"Direct download failed ({e}). Trying via ultralytics...")
    from ultralytics import YOLO
    YOLO(name)  # downloads into the current folder
    Path(name).replace(dest)
print(f"Saved {dest} ({dest.stat().st_size / 1e6:.1f} MB)")

"""Yuz modellari (OpenCV Zoo, Apache-2.0) va PDF shrifti (DejaVu, bepul litsenziya) yuklanadi, SHA-256 bilan tekshiriladi."""

import hashlib
import sys
import urllib.request
from pathlib import Path

BASE = "https://github.com/opencv/opencv_zoo/raw/main/models"
MODELS = {
    "face_detection_yunet_2023mar.onnx": (
        f"{BASE}/face_detection_yunet/face_detection_yunet_2023mar.onnx",
        "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
    ),
    "face_recognition_sface_2021dec.onnx": (
        f"{BASE}/face_recognition_sface/face_recognition_sface_2021dec.onnx",
        "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79",
    ),
    # PDF hisobotlar uchun (kirill va o'zbek lotin harflari)
    "fonts/DejaVuSans.ttf": (
        "https://cdn.jsdelivr.net/npm/dejavu-fonts-ttf@2.37.3/ttf/DejaVuSans.ttf",
        "7da195a74c55bef988d0d48f9508bd5d849425c1770dba5d7bfc6ce9ed848954",
    ),
    "fonts/DejaVuSans-Bold.ttf": (
        "https://cdn.jsdelivr.net/npm/dejavu-fonts-ttf@2.37.3/ttf/DejaVuSans-Bold.ttf",
        "e6476c1b80502924294eed40894c5b18e06c181444ca953e5334262df9c27724",
    ),
}


def main(dest: str) -> int:
    out = Path(dest)
    out.mkdir(parents=True, exist_ok=True)
    for name, (url, sha) in MODELS.items():
        path = out / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            urllib.request.urlretrieve(url, path)  # noqa: S310
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != sha:
            path.unlink()
            print(f"SHA-256 mos kelmadi: {name}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "/opt/models"))

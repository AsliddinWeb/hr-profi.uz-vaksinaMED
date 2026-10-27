"""Yuz aniqlash va tanish (OpenCV YuNet + SFace, ONNX). Serverda ishlaydi; rasm saqlanmaydi.

`FaceEngine` interfeysi testlarda soxta dvigatel bilan almashtiriladi.
"""

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np

MAX_IMAGE_BYTES = 1_500_000
MAX_SIDE = 1280
MIN_SIDE = 160
MIN_DET_SCORE = 0.85
MIN_FACE_RATIO = 0.18  # yuz kengligi / kadr kengligi
MIN_BLUR = 25.0  # Laplacian dispersiyasi (112x112 yuz kesmasi)
BRIGHTNESS_RANGE = (50, 210)
MULTI_FACE_RATIO = 0.5  # ikkinchi yuz birinchining shuncha qismidan katta bo'lsa rad etiladi


@dataclass
class FrameResult:
    ok: bool
    reason: str | None = None
    yaw: float | None = None  # >0: xodim o'z chap tomoniga burilgan
    quality: float = 0.0
    embedding: np.ndarray | None = None  # L2-normallangan, 128


class FaceEngine(Protocol):
    model_name: str

    def analyze(self, data: bytes) -> FrameResult: ...


class OpenCVEngine:
    model_name = "yunet2023mar+sface2021dec"

    def __init__(self, model_dir: str):
        import cv2

        self.cv2 = cv2
        d = Path(model_dir)
        self.detector = cv2.FaceDetectorYN.create(
            str(d / "face_detection_yunet_2023mar.onnx"), "", (320, 320), 0.8, 0.3, 10
        )
        self.recognizer = cv2.FaceRecognizerSF.create(str(d / "face_recognition_sface_2021dec.onnx"), "")
        self._lock = threading.Lock()  # OpenCV modellari ko'p oqimli emas

    def analyze(self, data: bytes) -> FrameResult:
        cv2 = self.cv2
        if len(data) > MAX_IMAGE_BYTES:
            return FrameResult(False, "image_too_large")
        if not (data[:3] == b"\xff\xd8\xff" or data[:8] == b"\x89PNG\r\n\x1a\n"):
            return FrameResult(False, "image_invalid")
        img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            return FrameResult(False, "image_invalid")
        h, w = img.shape[:2]
        if min(h, w) < MIN_SIDE:
            return FrameResult(False, "image_too_small")
        if max(h, w) > MAX_SIDE:
            scale = MAX_SIDE / max(h, w)
            img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
            h, w = img.shape[:2]
        with self._lock:
            self.detector.setInputSize((w, h))
            _, faces = self.detector.detect(img)
            if faces is None or len(faces) == 0:
                return FrameResult(False, "no_face")
            faces = sorted(faces, key=lambda f: -f[2] * f[3])
            if len(faces) > 1 and faces[1][2] * faces[1][3] > MULTI_FACE_RATIO * faces[0][2] * faces[0][3]:
                return FrameResult(False, "multiple_faces")
            f = faces[0]
            if f[14] < MIN_DET_SCORE:
                return FrameResult(False, "low_confidence")
            if f[2] / w < MIN_FACE_RATIO:
                return FrameResult(False, "face_too_small")
            x, y, fw, fh = (int(max(v, 0)) for v in f[:4])
            crop = cv2.cvtColor(img[y : y + fh, x : x + fw], cv2.COLOR_BGR2GRAY)
            if crop.size == 0:
                return FrameResult(False, "no_face")
            crop = cv2.resize(crop, (112, 112))
            blur = float(cv2.Laplacian(crop, cv2.CV_64F).var())
            mean = float(crop.mean())
            if mean < BRIGHTNESS_RANGE[0]:
                return FrameResult(False, "too_dark")
            if mean > BRIGHTNESS_RANGE[1]:
                return FrameResult(False, "too_bright")
            if blur < MIN_BLUR:
                return FrameResult(False, "blurry")
            eye_r, eye_l, nose = f[4:6], f[6:8], f[8:10]
            dist = abs(float(eye_l[0] - eye_r[0])) or 1.0
            yaw = float((nose[0] - (eye_r[0] + eye_l[0]) / 2) / dist)
            feat = self.recognizer.feature(self.recognizer.alignCrop(img, f))[0].astype(np.float32)
        feat /= np.linalg.norm(feat) or 1.0
        quality = float(f[14]) * min(blur / 100, 1.0) * min(f[2] / w / 0.35, 1.0)
        return FrameResult(True, None, yaw, quality, feat)


_engine: FaceEngine | None = None


def get_engine(app_state=None) -> FaceEngine:
    """`app.state.face_engine` (testlarda soxta) yoki bir marta yaratiladigan OpenCV dvigateli."""
    global _engine
    injected = getattr(app_state, "face_engine", None) if app_state is not None else None
    if injected is not None:
        return injected
    if _engine is None:
        from app.config import get_settings

        _engine = OpenCVEngine(get_settings().face_model_dir)
    return _engine

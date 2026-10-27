"""Yuz shablonlarini AES-256-GCM bilan shifrlash. Kalit `FACE_ENCRYPTION_KEY` dan (yo'q bo'lsa SECRET_KEY dan) HKDF bilan olinadi."""

import os

import numpy as np
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.config import get_settings

DIM = 128


def _key() -> bytes:
    s = get_settings()
    secret = (s.face_encryption_key or s.secret_key).encode()
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"vaksina-face-template-v1").derive(secret)


def encrypt_vector(vec: np.ndarray, employee_id: int) -> bytes:
    """nonce(12) + ciphertext. Xodim ID si AAD: shablonni boshqa xodimga ko'chirib bo'lmaydi."""
    raw = np.asarray(vec, dtype=np.float32).tobytes()
    nonce = os.urandom(12)
    return nonce + AESGCM(_key()).encrypt(nonce, raw, str(employee_id).encode())


def decrypt_vector(blob: bytes, employee_id: int) -> np.ndarray:
    raw = AESGCM(_key()).decrypt(blob[:12], blob[12:], str(employee_id).encode())
    return np.frombuffer(raw, dtype=np.float32).copy()

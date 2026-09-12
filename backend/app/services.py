"""Authentication services. The spectral ML adapter is deliberately a demo baseline,
not a claim of production-grade ECAPA-TDNN or spoof-detection accuracy."""
from collections import defaultdict
from datetime import datetime
import hashlib
import json
import secrets
import wave
from io import BytesIO
import numpy as np
from fastapi import HTTPException
from .config import settings

_memory = defaultdict(lambda: {"count": 0, "until": 0.0})


def challenge() -> dict:
    phrases = ["Сегодня вечером будет дождь", "Красный автомобиль стоит возле дома", "Безопасность начинается с меня"]
    return {"id": secrets.token_urlsafe(16), "phrase": secrets.choice(phrases), "expires_in": 120}


def check_lock(username: str) -> int:
    entry = _memory[username]
    now = datetime.now().timestamp()
    if entry["until"] > now:
        return int(entry["until"] - now)
    return 0


def failed(username: str) -> bool:
    entry = _memory[username]
    entry["count"] += 1
    if entry["count"] >= settings().max_attempts:
        entry.update(count=0, until=datetime.now().timestamp() + settings().lock_seconds)
        return True
    return False


def succeeded(username: str) -> None:
    _memory[username]["count"] = 0


def audio_embedding(data: bytes) -> tuple[list[float], dict]:
    if len(data) > settings().max_audio_bytes:
        raise HTTPException(422, "Аудиофайл превышает допустимый размер")
    try:
        with wave.open(BytesIO(data), "rb") as source:
            channels, rate, frames, width = source.getnchannels(), source.getframerate(), source.getnframes(), source.getsampwidth()
            raw = source.readframes(frames)
    except (wave.Error, EOFError):
        raise HTTPException(422, "Неподдерживаемый аудиоконтейнер: требуется WAV PCM")
    duration = frames / rate if rate else 0
    if channels != 1 or rate != 16000 or width != 2:
        raise HTTPException(422, "Требуется моно WAV PCM с sample rate 16 kHz")
    if not settings().min_audio_seconds <= duration <= settings().max_audio_seconds:
        raise HTTPException(422, "Длительность записи должна быть от 2 до 5.5 секунд")
    signal = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768
    rms, clipping = float(np.sqrt(np.mean(signal**2))), float(np.mean(np.abs(signal) > .98))
    if rms < .01 or clipping > .03:
        raise HTTPException(422, "Недостаточное качество сигнала: проверьте громкость и clipping")
    spectrum = np.abs(np.fft.rfft(signal * np.hanning(len(signal))))
    buckets = np.array_split(np.log1p(spectrum), 32)
    vector = np.array([b.mean() for b in buckets], dtype=float)
    vector /= np.linalg.norm(vector) or 1
    # Heuristic baseline: extremely regular/low-variance spectra are suspicious.
    spoof = float(np.clip(0.75 - np.std(np.diff(signal)) * 10 + clipping * 2, 0, 1))
    return vector.tolist(), {"duration": round(duration, 2), "rms": round(rms, 3), "spoof_score": round(spoof, 3)}


def cosine(left: list[float], right: list[float]) -> float:
    a, b = np.array(left), np.array(right)
    return float(np.dot(a, b) / ((np.linalg.norm(a) * np.linalg.norm(b)) or 1))


def save_embedding(vector: list[float]) -> str:
    return json.dumps(vector)


def load_embedding(value: str) -> list[float]:
    return json.loads(value)

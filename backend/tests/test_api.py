import io
import os
import wave
import numpy as np
os.environ["DATABASE_URL"] = "sqlite:///./test_securevoice.db"
from fastapi.testclient import TestClient
from app.main import app


def wav(seconds=2.2, frequency=220):
    signal = (.25 * np.sin(2 * np.pi * frequency * np.arange(int(16000 * seconds)) / 16000) * 32767).astype(np.int16)
    output = io.BytesIO()
    with wave.open(output, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000); w.writeframes(signal.tobytes())
    return output.getvalue()


def test_health_and_register_then_password_login():
    with TestClient(app) as client:
        assert client.get("/api/health").json()["status"] == "ok"
        response = client.post("/api/auth/register", json={"username": "test_user", "password": "a-long-password"})
        assert response.status_code == 201
        login = client.post("/api/auth/password", json={"username": "test_user", "password": "a-long-password"})
        assert login.status_code == 200
        assert "access_token" in login.json()


def test_audio_validation_rejects_short_file():
    with TestClient(app) as client:
        response = client.post("/api/auth/voice", data={"username": "nobody"}, files={"audio": ("sample.wav", wav(.5), "audio/wav")})
        assert response.status_code == 422

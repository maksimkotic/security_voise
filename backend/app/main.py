from datetime import datetime
from typing import Annotated
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
import numpy as np
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from .config import settings
from .database import Base, db_session, engine
from .models import AuthenticationAttempt, User, VoiceTemplate
from .security import hash_password, issue_token, read_token, verify_password
from .services import audio_embedding, challenge, check_lock, cosine, failed, load_embedding, save_embedding, succeeded

app = FastAPI(title="SecureVoice API", version="0.1.0", docs_url="/api/docs", openapi_url="/api/openapi.json")
app.add_middleware(CORSMiddleware, allow_origins=settings().cors_origins, allow_credentials=False, allow_methods=["GET", "POST"], allow_headers=["Authorization", "Content-Type"])


@app.on_event("startup")
def init_database():
    Base.metadata.create_all(engine)
    db = next(db_session())
    try:
        if not db.scalar(select(User).where(User.username == settings().admin_username)):
            db.add(User(username=settings().admin_username, password_hash=hash_password(settings().admin_password), role="admin"))
            db.commit()
    finally:
        db.close()


class Registration(BaseModel):
    username: str = Field(pattern=r"^[a-zA-Z0-9_-]{3,64}$")
    password: str = Field(min_length=12, max_length=128)


class PasswordLogin(Registration):
    pass


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def audit(db: Session, username: str, method: str, result: str, reason: str, request: Request, user: User | None = None, speaker: float | None = None, spoof: float | None = None):
    db.add(AuthenticationAttempt(user_id=user.id if user else None, username=username, method=method, result=result, reason=reason, speaker_score=speaker, spoof_score=spoof, ip_address=client_ip(request), user_agent=request.headers.get("user-agent", "")[:255]))
    db.commit()


def current_user(authorization: Annotated[str | None, Header()] = None, db: Session = Depends(db_session)) -> User:
    token = authorization.removeprefix("Bearer ") if authorization else ""
    identity = read_token(token)
    user = db.get(User, identity[0]) if identity else None
    if not user:
        raise HTTPException(401, "Требуется аутентификация")
    return user


@app.get("/api/health")
def health(): return {"status": "ok", "service": "securevoice"}


@app.post("/api/auth/register", status_code=201)
def register(payload: Registration, db: Session = Depends(db_session)):
    if db.scalar(select(User).where(User.username == payload.username)):
        raise HTTPException(409, "Не удалось создать аккаунт")
    db.add(User(username=payload.username, password_hash=hash_password(payload.password)))
    db.commit()
    return {"message": "Аккаунт создан. Добавьте минимум три голосовых образца."}


@app.post("/api/auth/challenge")
def get_challenge(): return challenge()


@app.post("/api/users/me/voice/enroll")
async def enroll(audio: UploadFile = File(...), user: User = Depends(current_user), db: Session = Depends(db_session)):
    vector, quality = audio_embedding(await audio.read())
    template = db.scalar(select(VoiceTemplate).where(VoiceTemplate.user_id == user.id))
    if template:
        existing = load_embedding(template.embedding)
        vector = ((np.array(existing) + np.array(vector)) / 2).tolist()
        template.embedding = save_embedding(vector)
        template.sample_count += 1
    else:
        db.add(VoiceTemplate(user_id=user.id, embedding=save_embedding(vector)))
    db.commit()
    return {"message": "Голосовой образец сохранён", "quality": quality, "samples_collected": template.sample_count if template else 1, "ready_for_voice_login": bool(template and template.sample_count >= 3)}


@app.post("/api/auth/password")
def password_login(payload: PasswordLogin, request: Request, db: Session = Depends(db_session)):
    user = db.scalar(select(User).where(User.username == payload.username))
    if check_lock(payload.username):
        audit(db, payload.username, "password", "blocked", "ACCOUNT_LOCKED", request, user)
        raise HTTPException(429, "Аутентификация временно заблокирована")
    if not user or not verify_password(payload.password, user.password_hash):
        locked = failed(payload.username)
        audit(db, payload.username, "password", "failure", "ACCOUNT_LOCKED" if locked else "INVALID_CREDENTIALS", request, user)
        raise HTTPException(401, "Аутентификация не пройдена")
    succeeded(payload.username); user.last_login_at = datetime.utcnow(); audit(db, payload.username, "password", "success", "AUTH_SUCCESS", request, user)
    return {"access_token": issue_token(user.id, user.role), "token_type": "bearer"}


@app.post("/api/auth/voice")
async def voice_login(username: str = Form(...), audio: UploadFile = File(...), request: Request = None, db: Session = Depends(db_session)):
    user = db.scalar(select(User).where(User.username == username))
    if check_lock(username):
        audit(db, username, "voice", "blocked", "ACCOUNT_LOCKED", request, user)
        raise HTTPException(429, "Аутентификация временно заблокирована")
    vector, quality = audio_embedding(await audio.read())
    template = db.scalar(select(VoiceTemplate).where(VoiceTemplate.user_id == user.id)) if user else None
    speaker = cosine(vector, load_embedding(template.embedding)) if template else 0.0
    spoof = quality["spoof_score"]
    if not user or not template or template.sample_count < 3 or speaker < settings().speaker_threshold or spoof >= settings().spoof_threshold:
        reason = "SPOOF_DETECTED" if spoof >= settings().spoof_threshold else "VOICE_MISMATCH"
        locked = failed(username); audit(db, username, "voice", "failure", "ACCOUNT_LOCKED" if locked else reason, request, user, speaker, spoof)
        raise HTTPException(401, "Аутентификация не пройдена")
    succeeded(username); user.last_login_at = datetime.utcnow(); audit(db, username, "voice", "success", "AUTH_SUCCESS", request, user, speaker, spoof)
    return {"access_token": issue_token(user.id, user.role), "token_type": "bearer", "quality": {"duration": quality["duration"]}}


@app.get("/api/users/me")
def me(user: User = Depends(current_user), db: Session = Depends(db_session)):
    template = db.scalar(select(VoiceTemplate).where(VoiceTemplate.user_id == user.id))
    enabled = bool(template and template.sample_count >= 3)
    return {"username": user.username, "created_at": user.created_at, "last_login_at": user.last_login_at, "voice_authentication": enabled, "voice_samples": template.sample_count if template else 0, "password_authentication": True}


def admin_user(user: User = Depends(current_user)) -> User:
    if user.role != "admin": raise HTTPException(403, "Недостаточно прав")
    return user


@app.get("/api/admin/logs")
def logs(_: User = Depends(admin_user), db: Session = Depends(db_session)):
    rows = db.scalars(select(AuthenticationAttempt).order_by(AuthenticationAttempt.created_at.desc()).limit(100)).all()
    return [{"timestamp": r.created_at, "username": r.username, "method": r.method, "result": r.result, "reason": r.reason, "speaker_score": r.speaker_score, "spoof_score": r.spoof_score, "ip_address": r.ip_address} for r in rows]


@app.get("/api/admin/statistics")
def statistics(_: User = Depends(admin_user), db: Session = Depends(db_session)):
    total = db.scalar(select(func.count()).select_from(AuthenticationAttempt)) or 0
    success = db.scalar(select(func.count()).select_from(AuthenticationAttempt).where(AuthenticationAttempt.result == "success")) or 0
    spoof = db.scalar(select(func.count()).select_from(AuthenticationAttempt).where(AuthenticationAttempt.reason == "SPOOF_DETECTED")) or 0
    return {"users": db.scalar(select(func.count()).select_from(User)) or 0, "login_attempts": total, "successful": success, "failed": total - success, "spoof_attacks": spoof}

# SecureVoice

Учебная система биометрической аутентификации по голосу с отдельным anti-spoofing решением. Проект реализует сценарий **1:1 speaker verification**: пользователь заявляет логин, а система сопоставляет его запись только с шаблоном этого пользователя.

## Реализованный MVP

- FastAPI REST API и Swagger по адресу `/api/docs`;
- регистрация с Argon2id-хешированием пароля;
- password fallback, подписанные short-lived bearer tokens и admin role;
- голосовой enrollment (три и более образцов), хранение только шаблона, а не исходного аудио;
- строгая валидация WAV PCM: лимит размера, mono, 16 kHz, 2–5.5 секунд, громкость и clipping;
- независимые speaker similarity и spoof score в policy decision;
- единообразная ошибка при неизвестном пользователе/неверных credentials, audit log и временная блокировка после пяти ошибок;
- web-интерфейс, nginx reverse proxy и Compose-окружение PostgreSQL/Redis.

> **Важно:** ML-адаптер в этом репозитории — воспроизводимый spectral baseline для демонстрации pipeline. Он не является ECAPA-TDNN и не должен использоваться для security claims. Перед оценкой или реальным применением его следует заменить на валидированную предобученную speaker-модель и обученный anti-spoofing classifier. См. [архитектуру](docs/architecture.md) и [threat model](docs/threat-model.md).

## Запуск

```bash
cp .env.example .env
docker compose up --build
```

Откройте `http://localhost:8080`; API docs находятся по `http://localhost:8080/api/docs`. Перед развёртыванием замените все development credentials в `.env`.

## Проверки

```bash
python -m pip install -r backend/requirements.txt
cd backend && pytest -q
docker compose config
```

## Privacy and scope

Исходные записи не сохраняются в основной БД, но voice embedding остаётся чувствительным биометрическим шаблоном. Проект не является ASR, не определяет говорящего среди всей базы, не является MFA или production-grade biometric infrastructure и не гарантирует обнаружение каждого deepfake.

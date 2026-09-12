# Threat model SecureVoice

## Scope and assumptions

SecureVoice is an educational, small-scale **1:1** voice-verification system for Russian speech. It compares a claimed user's fresh audio with that user's stored template; it is not 1:N identification and does not perform speech recognition. It deliberately does not promise detection of every present or future deepfake.

An attacker may know usernames, possess recordings, replay audio, submit TTS/voice-conversion samples, send repeated login requests, and possess stolen passwords. The threat model excludes server-memory compromise, database credentials theft, source/model modification, and root access.

## Controls

| Threat | Control | Residual risk |
| --- | --- | --- |
| Account enumeration | Generic external failure response | Timing and side channels require operational review. |
| Brute force / stuffing | Separate password/voice failure counting and temporary lockout | The MVP has an in-process limiter; production must use Redis atomically across instances. |
| Malformed or DoS audio | File-size, container, PCM, duration, sample-rate, channel, RMS, clipping checks before inference | Decoder sandboxing and gateway limits remain required. |
| Replay, TTS, VC | Dynamic phrase plus independent spoof score and speaker score | The supplied classifier is a demonstrative baseline, not validated protection. |
| Template exposure | No raw audio or embedding in normal responses/logs; restricted backend model | Embeddings remain sensitive biometric data; consider encryption at rest and retention limits. |
| Audit tampering | Structured attempts with IP, result, scores, reason, timestamp | Production needs append-only remote log storage and monitoring. |

## Data handling

The primary database stores an Argon2id password hash and a voice embedding, not raw enrollment recordings. A voice embedding is sensitive biometric data; compromise of its database is a security event. Credentials belong in environment-managed secrets, never API responses or source control.

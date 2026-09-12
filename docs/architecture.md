# Architecture

The browser sends REST requests through nginx to FastAPI. PostgreSQL stores users, templates, and audit records; Redis is provisioned by Compose for production rate-limit/challenge state. The current educational implementation contains a deterministic spectral embedding and heuristic anti-spoof baseline so that it remains runnable without downloading model weights. Replace the adapter with an evaluated ECAPA-TDNN and trained anti-spoof classifier before making security claims. Three or more enrollment samples enable voice login.

`audio → validation → embedding + spoof score → policy decision → audit → accept/reject`

The API specification is served at `/api/docs`. Authentication endpoints are `/api/auth/register`, `/api/auth/challenge`, `/api/auth/voice`, and `/api/auth/password`; protected user/admin endpoints are `/api/users/me`, `/api/admin/logs`, and `/api/admin/statistics`.

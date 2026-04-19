# Messenger MVP (Windows + Android + FastAPI)

A simple 1:1 messenger MVP built with:

- Flutter client (Windows desktop and Android)
- FastAPI backend
- PostgreSQL database
- WebSocket real-time events
- JWT auth (access + refresh)
- Chunked file upload

Messages are stored in plaintext on the server (no E2EE). Use HTTPS/WSS in production.

## Project layout

- [`backend/`](backend/) - FastAPI, SQLAlchemy, Alembic
- [`app/`](app/) - Flutter app
- [`scripts/init_messenger_db.sql`](scripts/init_messenger_db.sql) - DB bootstrap SQL
- [`docs/LOCAL_DB_WITHOUT_DOCKER.md`](docs/LOCAL_DB_WITHOUT_DOCKER.md) - local PostgreSQL setup guide

## Requirements

- Python 3.11+
- Flutter SDK (Windows + Android toolchain)
- PostgreSQL 15+ (local install)

## 1. Database setup (local PostgreSQL)

Follow [`docs/LOCAL_DB_WITHOUT_DOCKER.md`](docs/LOCAL_DB_WITHOUT_DOCKER.md), or run the SQL in [`scripts/init_messenger_db.sql`](scripts/init_messenger_db.sql) manually.

Create `backend/.env` from [`backend/.env.example`](backend/.env.example) and set `DATABASE_URL` for your local DB.

## 2. Run backend

```powershell
cd c:\Users\HOME\Desktop\coding\aaaa\backend
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
copy .env.example .env
.\.venv\Scripts\alembic upgrade head
.\.venv\Scripts\uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API docs: `http://127.0.0.1:8000/docs`
- WebSocket endpoint: `ws://127.0.0.1:8000/ws`
- WebSocket auth is done by first message:
  - `{"type":"auth","token":"<access_jwt>"}`

## 3. Run Flutter app

```powershell
cd c:\Users\HOME\Desktop\coding\aaaa\app
flutter pub get
flutter run -d windows
```

For Android emulator:

```powershell
flutter run -d android --dart-define=API_BASE=http://10.0.2.2:8000
```

For physical Android device, use your PC LAN IP, for example:

```text
http://192.168.0.10:8000
```

## 4. Build

Windows release:

```powershell
cd c:\Users\HOME\Desktop\coding\aaaa\app
flutter config --enable-windows-desktop
flutter build windows --release --dart-define=API_BASE=http://YOUR_SERVER:8000
```

Android APK:

```powershell
cd c:\Users\HOME\Desktop\coding\aaaa\app
flutter build apk --release --dart-define=API_BASE=https://your-domain.example
```

## 5. Production notes

- Terminate TLS with Nginx or Caddy and proxy to Uvicorn (`127.0.0.1:8000`).
- Use `https://...` as `API_BASE` so WebSocket is automatically `wss://`.
- Use strong secrets and secure DB/network settings for production.

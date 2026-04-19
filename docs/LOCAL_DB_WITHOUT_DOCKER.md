# Local PostgreSQL Setup (No Docker)

This project now uses local PostgreSQL directly.

## 1. Install PostgreSQL on Windows

1. Download from https://www.postgresql.org/download/windows/
2. Install PostgreSQL 15+ using the interactive installer
3. Keep default port `5432` unless you have a conflict

## 2. Create DB and user

Use SQL Shell (`psql`) or pgAdmin, then run:

```sql
CREATE USER messenger WITH PASSWORD 'messenger';
CREATE DATABASE messenger OWNER messenger;
GRANT ALL PRIVILEGES ON DATABASE messenger TO messenger;
```

Or run [`scripts/init_messenger_db.sql`](../scripts/init_messenger_db.sql).

## 3. Configure backend env

Create `backend/.env` from `backend/.env.example` and set:

```env
DATABASE_URL=postgresql+asyncpg://messenger:messenger@localhost:5432/messenger
```

## 4. Run backend

```powershell
cd c:\Users\HOME\Desktop\coding\aaaa\backend
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
copy .env.example .env
.\.venv\Scripts\alembic upgrade head
.\.venv\Scripts\uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

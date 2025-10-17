# Cheeky FC API (Backend) — Render Ready v3

Includes:
- Python 3.11.9 (`runtime.txt`)
- `fantraxapi==0.2.9`, `soccerdata==1.5.1`, `lxml==4.9.4`
- `/auth/status` route
- Header or `?key=` fallback auth
- CORS middleware

**Render Build Command (recommended):**
pip install --upgrade pip wheel setuptools && pip install --only-binary=:all: lxml==4.9.4 && pip install -r requirements.txt

**Start Command:**
uvicorn api.main:app --host 0.0.0.0 --port $PORT

Set Environment variables on Render:
- `FANTRAX_USERNAME`, `FANTRAX_PASSWORD`, `LEAGUE_ID`
- `SEASON=2025-2026`, `COMPETITION=Premier League`
- `API_KEY=<your secret>`, `TZ=America/Chicago`

Endpoints:
- `GET /` (health)
- `GET /auth/status` (reports if API_KEY is set)
- `GET /run?week=N[&key=...]` (protected; key via header or query)
- `GET /analysis/weekly.csv?week=N`
- `GET /analysis/weekly.parquet?week=N`

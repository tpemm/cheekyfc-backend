# Cheeky FC API (Backend) — Render Ready v2

FastAPI backend that syncs Fantrax league data + FBref stats.

**Key files**
- `requirements.txt` → now uses fantraxapi==0.2.9 and soccerdata==1.5.1
- `runtime.txt` → python-3.11.9

**Render setup**
1. Push to GitHub (`cheekyfc-backend`)
2. Render → New Web Service
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn api.main:app --host 0.0.0.0 --port $PORT`
3. Add env vars for Fantrax + API_KEY
4. Deploy + Clear build cache if upgrading.

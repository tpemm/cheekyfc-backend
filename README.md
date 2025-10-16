# Cheeky FC API (Backend)
FastAPI service for the Cheeky FC league: runs the Fantrax + FBref pipeline and serves weekly CSV/Parquet.

## Endpoints
- `GET /` — health
- `GET /run?week=1` — run pipeline (requires `X-API-Key`)
- `GET /analysis/weekly.csv?week=1`
- `GET /analysis/weekly.parquet?week=1`

## Deploy on Railway
1) Push to GitHub as `cheekyfc-backend`.
2) Railway → New Project → Deploy from GitHub.
3) Add variables: `FANTRAX_USERNAME`, `FANTRAX_PASSWORD`, `LEAGUE_ID`, `SEASON`, `COMPETITION`, `API_KEY`.
4) Start: `uvicorn api.main:app --host 0.0.0.0 --port $PORT`

Test:
```
curl -H "X-API-Key: $API_KEY" "https://<your-app>.railway.app/run?week=1"
curl -I "https://<your-app>.railway.app/analysis/weekly.csv?week=1"
```

## Weekly automation
Add repo secrets: `API_BASE`, `API_KEY`. GitHub will call `/run?week=1` every Monday 03:00 CT.

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import os
import importlib

app = FastAPI(title="Cheeky FC API")

# CORS (tighten allow_origins to your Vercel URL later)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
API_KEY = os.getenv("API_KEY", "")

@app.get("/")
def root():
    return {"ok": True, "message": "Cheeky FC API"}

@app.get("/auth/status")
def auth_status():
    return {"ok": True, "has_api_key": bool(API_KEY)}

def require_api_key(request: Request):
    sent = request.headers.get("X-API-Key") or request.query_params.get("key")
    if not API_KEY:
        raise HTTPException(status_code=401, detail="Server API_KEY is not set")
    if not sent or sent != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

@app.get("/run")
def run_pipeline(week: int = 1, request: Request = None):
    require_api_key(request)
    try:
        pipeline = importlib.import_module("src.pipeline")
        p = pipeline.run(week=week)
        return {"ok": True, "week": week, "artifact": p}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/analysis/weekly.csv")
def weekly_csv(week: int = 1):
    f = DATA_DIR / f"cheekyfc_player_analysis_week{week}.csv"
    if not f.exists():
        raise HTTPException(status_code=404, detail=f"Not found: {f.name}. Hit /run?week={week} first.")
    return FileResponse(str(f), media_type="text/csv", filename=f.name)

@app.get("/analysis/weekly.parquet")
def weekly_parquet(week: int = 1):
    f = DATA_DIR / f"cheekyfc_player_analysis_week{week}.parquet"
    if not f.exists():
        raise HTTPException(status_code=404, detail=f"Not found: {f.name}. Hit /run?week={week} first.")
    return FileResponse(str(f), media_type="application/octet-stream", filename=f.name)

@app.get("/debug/periods")
def debug_periods():
    try:
        import importlib
        pipeline = importlib.import_module("src.fantrax_client")
        # get a League with cookies/session (reuses your existing logic)
        league = pipeline.fetch_league_objects()
        periods = league.scoring_periods()  # dict[int|str, ScoringPeriod]
        out = []
        for key, sp in periods.items():
            # sp has attributes like start, end, number, range
            out.append({
                "key": key,
                "number": getattr(sp, "number", None),
                "start": str(getattr(sp, "start", "")),
                "end": str(getattr(sp, "end", "")),
                "range": getattr(sp, "range", ""),
            })
        # sort by 'number' if available, else by 'start'
        out.sort(key=lambda r: (r["number"] is None, r["number"], r["start"]))
        return {"ok": True, "periods": out}
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/debug/periods")
def debug_periods():
    try:
        import importlib
        fx = importlib.import_module("src.fantrax_client")
        league = fx.fetch_league_objects()
        periods = league.scoring_periods()
        out = []
        for key, sp in periods.items():
            out.append({
                "key": key,
                "number": getattr(sp, "number", None),
                "start": str(getattr(sp, "start", "")),
                "end": str(getattr(sp, "end", "")),
                "range": getattr(sp, "range", ""),
            })
        try:
            out.sort(key=lambda r: (r["number"] is None, r["number"], r["start"]))
        except Exception:
            pass
        return {"ok": True, "periods": out}
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/debug/roster-signature")
def debug_roster_signature():
    try:
        import importlib, inspect
        fx = importlib.import_module("src.fantrax_client")
        league = fx.fetch_league_objects()
        sample_team = next(iter(league.teams))
        sig = str(inspect.signature(sample_team.roster))
        return {"ok": True, "team": sample_team.name, "roster_signature": sig}
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=str(e))

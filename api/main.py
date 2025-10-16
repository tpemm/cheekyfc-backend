from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pathlib import Path
import os
import importlib

app = FastAPI(title="Cheeky FC API")
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
API_KEY = os.getenv("API_KEY", "")

@app.get("/")
def root():
    return {"ok": True, "message": "Cheeky FC API"}

def require_api_key(request: Request):
    key = request.headers.get("X-API-Key", "")
    if not API_KEY or key != API_KEY:
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

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import os
import importlib

app = FastAPI(title="Cheeky FC API")

# -----------------------------
# CORS (open for testing)
# -----------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
API_KEY = os.getenv("API_KEY", "")


# -----------------------------
# Helpers
# -----------------------------
def _ascii(x):
    try:
        return str(x).encode("ascii", "ignore").decode("ascii")
    except Exception:
        try:
            return str(x).encode("utf-8", "ignore").decode("utf-8")
        except Exception:
            return ""


def require_api_key(request: Request):
    sent = request.headers.get("X-API-Key") or request.query_params.get("key")
    if not API_KEY:
        raise HTTPException(status_code=401, detail="Server API_KEY is not set")
    if not sent or sent != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


# -----------------------------
# Basic routes
# -----------------------------
@app.get("/")
def root():
    return {"ok": True, "message": "Cheeky FC API"}


@app.get("/auth/status")
def auth_status():
    return {"ok": True, "has_api_key": bool(API_KEY)}


@app.get("/auth/cookies-status")
def cookies_status():
    raw = os.getenv("FANTRAX_COOKIES_RAW", "")
    has_auth = bool(os.getenv("FANTRAX_COOKIE"))
    names = [p.split("=", 1)[0].strip() for p in raw.split(";") if "=" in p] if raw else []
    return {"ok": True, "has_FANTRAX_COOKIE": has_auth, "cookie_names_loaded": names}


# -----------------------------
# Debug: versions / probe-based periods & roster
# -----------------------------
@app.get("/about/versions")
def versions():
    try:
        import fantraxapi, pandas, fastapi
        return {
            "fantraxapi": getattr(fantraxapi, "__version__", "unknown"),
            "pandas": pandas.__version__,
            "fastapi": fastapi.__version__,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=_ascii(e))


@app.get("/debug/periods_raw")
def debug_periods_raw():
    """
    ASCII-safe endpoint that avoids fantraxapi.scoring_periods() entirely.
    It *probes* which integer period numbers work by calling league.team_roster(...)
    for period numbers 1..60 and returns those that succeed.
    """
    try:
        fx = importlib.import_module("src.fantrax_client")
        league = fx.fetch_league_objects()
        nums = fx.probe_valid_period_numbers(league, max_probe=60)
        return JSONResponse(content={"ok": True, "count": len(nums), "numbers_sample": nums[:20]})
    except Exception as e:
        msg = _ascii(e)
        return JSONResponse(status_code=500, content={"ok": False, "error": msg})


@app.get("/debug/roster_try")
def debug_roster_try(week: int = 1):
    """
    Probe-based roster test:
      1) Discover valid integer period numbers.
      2) Map the requested 1-based 'week' to that list.
      3) Try league.team_roster(...) with common signatures.
    Returns ok:true if any call succeeds for the first team.
    """
    try:
        fx = importlib.import_module("src.fantrax_client")
        league = fx.fetch_league_objects()

        # 1) discover valid period numbers (ints)
        valid = fx.probe_valid_period_numbers(league, max_probe=60)
        if not valid:
            return {"ok": False, "message": "No valid period numbers discovered (cookie may be expired)."}
        if week < 1 or week > len(valid):
            return {"ok": False, "message": f"Week {week} out of range (1..{len(valid)})"}

        period_number = valid[week - 1]

        # 2) pick first team
        try:
            team = next(iter(league.teams))
        except Exception:
            return {"ok": False, "message": "Could not iterate league.teams."}

        # 3) try the common signatures
        for kw in ("period_number", "period", "scoring_period"):
            try:
                league.team_roster(team.id, **{kw: int(period_number)})
                return {"ok": True, "method": f"league.team_roster({kw}=...)", "period_number": int(period_number)}
            except Exception:
                pass
        try:
            league.team_roster(team.id, int(period_number))
            return {"ok": True, "method": "league.team_roster(positional)", "period_number": int(period_number)}
        except Exception:
            pass

        return {
            "ok": False,
            "message": "Tried league.team_roster with period_number/period/scoring_period and positional; none succeeded.",
            "period_number": int(period_number),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=_ascii(e))


# -----------------------------
# Pipeline run + file serving
# -----------------------------
@app.get("/run")
def run_pipeline(week: int = 1, request: Request = None):
    require_api_key(request)
    try:
        pipeline = importlib.import_module("src.pipeline")
        p = pipeline.run(week=week)
        return {"ok": True, "week": week, "artifact": p}
    except Exception as e:
        raise HTTPException(status_code=500, detail=_ascii(e))


@app.get("/analysis/weekly.csv")
def weekly_csv(week: int = 1):
    f = DATA_DIR / f"cheekyfc_player_analysis_week{week}.csv"
    if not f.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Not found: {f.name}. Hit /run?week={week} first.",
        )
    return FileResponse(str(f), media_type="text/csv", filename=f.name)


@app.get("/analysis/weekly.parquet")
def weekly_parquet(week: int = 1):
    f = DATA_DIR / f"cheekyfc_player_analysis_week{week}.parquet"
    if not f.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Not found: {f.name}. Hit /run?week={week} first.",
        )
    return FileResponse(
        str(f), media_type="application/octet-stream", filename=f.name
    )

@app.api_route("/stats/refresh", methods=["GET", "POST"])
def stats_refresh(request: Request):
    require_api_key(request)
    try:
        svc = importlib.import_module("src.stats_service")
        res = svc.refresh(force=True)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=_ascii(e))


@app.get("/players/search")
def players_search(q: str = "", team: str = "", position: str = "", limit: int = 50):
    try:
        svc = importlib.import_module("src.stats_service")
        df = svc.search_players(q=q, team=team, position=position, limit=limit)
        # return a compact JSON
        return {
            "ok": True,
            "count": int(len(df)),
            "players": df.to_dict(orient="records"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=_ascii(e))

@app.get("/players/compare")
def players_compare(name: str):
    """
    name: comma-separated list of player names
    """
    try:
        names = [n.strip() for n in name.split(",") if n.strip()]
        if not names:
            raise HTTPException(status_code=400, detail="Provide ?name=Player A,Player B")
        svc = importlib.import_module("src.stats_service")
        df = svc.compare_players(names)
        return {"ok": True, "count": int(len(df)), "players": df.to_dict(orient="records")}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=_ascii(e))

@app.get("/matchups/table")
def matchups_table():
    try:
        svc = importlib.import_module("src.stats_service")
        df = svc.matchup_table()
        return {"ok": True, "count": int(len(df)), "table": df.to_dict(orient="records")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=_ascii(e))

@app.post("/stats/refresh")
def stats_refresh(request: Request):
    # protect with API key since it triggers scraping
    require_api_key(request)
    try:
        svc = importlib.import_module("src.stats_service")
        res = svc.refresh(force=True)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=_ascii(e))

@app.get("/players/search")
def players_search(q: str = "", team: str = "", position: str = "", limit: int = 50):
    try:
        svc = importlib.import_module("src.stats_service")
        df = svc.search_players(q=q, team=team, position=position, limit=limit)
        # return a compact JSON
        return {
            "ok": True,
            "count": int(len(df)),
            "players": df.to_dict(orient="records"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=_ascii(e))

@app.get("/players/compare")
def players_compare(name: str):
    """
    name: comma-separated list of player names
    """
    try:
        names = [n.strip() for n in name.split(",") if n.strip()]
        if not names:
            raise HTTPException(status_code=400, detail="Provide ?name=Player A,Player B")
        svc = importlib.import_module("src.stats_service")
        df = svc.compare_players(names)
        return {"ok": True, "count": int(len(df)), "players": df.to_dict(orient="records")}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=_ascii(e))

@app.get("/matchups/table")
def matchups_table():
    try:
        svc = importlib.import_module("src.stats_service")
        df = svc.matchup_table()
        return {"ok": True, "count": int(len(df)), "table": df.to_dict(orient="records")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=_ascii(e))

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
# Basic helpers
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
# Debug: versions / periods / roster
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
    Return only plain ASCII ints so latin-1 encoding can never choke.
    """
    try:
        import importlib
        fx = importlib.import_module("src.fantrax_client")
        league = fx.fetch_league_objects()
        periods = league.scoring_periods()

        out = []
        for k in list(periods.keys())[:50]:
            sp = periods[k]
            num = getattr(sp, "number", None)
            if isinstance(num, int):
                out.append(int(num))
            elif isinstance(k, int):
                out.append(int(k))
            else:
                out.append(0)

        return JSONResponse(content={"ok": True, "count": len(periods), "numbers_sample": out})
    except Exception as e:
        msg = str(e).encode("ascii", "ignore").decode("ascii")
        return JSONResponse(status_code=500, content={"ok": False, "error": msg})


@app.get("/debug/roster_try")
def debug_roster_try(week: int = 1):
    try:
        import importlib
        fx = importlib.import_module("src.fantrax_client")
        league = fx.fetch_league_objects()
        candidates, sp = fx._resolve_week_index(league, week)
        team = next(iter(league.teams))

        # team.roster variants
        for label, val in candidates:
            try:
                team.roster(val)
                return {
                    "ok": True,
                    "method": "team.roster(positional)",
                    "used": {"label": _ascii(label), "value": _ascii(val)},
                }
            except Exception:
                pass
            for kw in (
                "week",
                "period",
                "scoring_period",
                "scoringPeriod",
                "period_number",
                "periodNumber",
            ):
                try:
                    team.roster(**{kw: val})
                    return {
                        "ok": True,
                        "method": f"team.roster({kw}=...)",
                        "used": {"label": _ascii(label), "value": _ascii(val)},
                    }
                except Exception:
                    pass

        # league.team_roster variants
        ints = []
        for label, val in candidates:
            if isinstance(val, int):
                ints.append((label, val))
            elif isinstance(val, str) and val.isdigit():
                ints.append((f"{label}->int", int(val)))

        for label, val in ints:
            for kw in ("period_number", "period", "scoring_period"):
                try:
                    league.team_roster(team.id, **{kw: val})
                    return {
                        "ok": True,
                        "method": f"league.team_roster({kw}=...)",
                        "used": {"label": _ascii(label), "value": _ascii(val)},
                    }
                except Exception:
                    pass
            try:
                league.team_roster(team.id, val)
                return {
                    "ok": True,
                    "method": "league.team_roster(positional)",
                    "used": {"label": _ascii(label), "value": _ascii(val)},
                }
            except Exception:
                pass

        return {"ok": False, "message": "Tried all known roster call variants; none succeeded."}
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

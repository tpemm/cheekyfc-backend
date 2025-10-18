import os
from pathlib import Path
import time
import pandas as pd

# soccerdata 1.5.1 providers
from soccerdata import FBref, ClubElo

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
CACHE_DIR = DATA_DIR / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

LEAGUE = os.getenv("COMPETITION", "ENG-Premier League")
SEASON = os.getenv("SEASON", "2024-2025")  # adjust if needed

# Basic in-process memo to avoid refetching during one request burst
_mem = {}

def _cache_write(df: pd.DataFrame, name: str):
    p = CACHE_DIR / f"{name}.parquet"
    df.to_parquet(p, index=False)
    return p

def _cache_read(name: str):
    p = CACHE_DIR / f"{name}.parquet"
    if p.exists():
        return pd.read_parquet(p)
    return None

def refresh(force: bool = False):
    """
    Pull & cache public stats:
      - FBref player standard + shooting + passing for current season
      - ClubElo ratings for team strength proxy
    """
    key = ("refresh_ts",)
    if not force and key in _mem and time.time() - _mem[key] < 300:
        return {"ok": True, "cached": True}

    # FBref
    fb = FBref(leagues=LEAGUE, seasons=SEASON, data_dir=str(CACHE_DIR))
    std = fb.read_player_season_stats(stat_type="standard")
    sht = fb.read_player_season_stats(stat_type="shooting")
    pas = fb.read_player_season_stats(stat_type="passing")

    # Normalize columns (keep useful subset)
    keep_std = ["player", "team", "position", "minutes_90s", "games_starts", "games_subs", "minutes"]
    keep_sht = ["player", "team", "shots_total", "shots_on_target", "xg"]
    keep_pas = ["player", "team", "xa", "assists", "key_passes"]

    std = std[ [c for c in std.columns if c in keep_std] ].copy()
    sht = sht[ [c for c in sht.columns if c in keep_sht] ].copy()
    pas = pas[ [c for c in pas.columns if c in keep_pas] ].copy()

    # Merge on player+team
    players = std.merge(sht, on=["player","team"], how="left").merge(pas, on=["player","team"], how="left")
    players.fillna(0, inplace=True)

    # ClubElo as simple team strength
    ce = ClubElo(leagues=[LEAGUE], seasons=[SEASON], data_dir=str(CACHE_DIR))
    elo = ce.read_team_history()
    # Take the latest Elo per team
    elo = elo.sort_values("date").groupby("team", as_index=False).tail(1)[["team","elo"]]

    _cache_write(players, "players")
    _cache_write(elo, "elo")

    _mem[key] = time.time()
    return {"ok": True, "cached": False, "rows": int(len(players))}

def ensure_data():
    players = _cache_read("players")
    elo = _cache_read("elo")
    if players is None or elo is None:
        refresh(force=True)
        players = _cache_read("players")
        elo = _cache_read("elo")
    return players, elo

def search_players(q: str = "", team: str = "", position: str = "", limit: int = 50):
    players, _ = ensure_data()
    df = players.copy()
    if q:
        ql = q.lower()
        df = df[df["player"].str.lower().str.contains(ql, na=False)]
    if team:
        df = df[df["team"] == team]
    if position:
        df = df[df["position"].str.contains(position, na=False)]
    df = df.sort_values(["xg","xa","shots_total","key_passes"], ascending=False)
    return df.head(limit)

def compare_players(names: list[str]):
    players, _ = ensure_data()
    df = players[players["player"].isin(names)].copy()
    df = df.sort_values("player")
    # keep a compact set of columns
    cols = ["player","team","position","minutes","games_starts","games_subs","shots_total","shots_on_target","xg","xa","assists","key_passes"]
    return df[[c for c in cols if c in df.columns]]

def matchup_table():
    players, elo = ensure_data()
    # crude “fixture difficulty”: team_elo - opponent_elo (we don’t have fixtures here;
    # so show team strength table now—frontend can combine with fixture list later)
    return elo.sort_values("elo", ascending=False)


import os
from .config import settings

# Be compatible with multiple fantraxapi versions
def _get_league_class():
    import fantraxapi
    # 1) Preferred: top-level (docs show this)
    if hasattr(fantraxapi, "League"):
        return fantraxapi.League
    # 2) Older/newer layout: fantraxapi.objs.League (per docs page)
    try:
        from fantraxapi.objs import League as LeagueObj  # may not exist on some builds
        return LeagueObj
    except Exception:
        pass
    # 3) Last-ditch: attribute on submodule if present
    if hasattr(fantraxapi, "objs") and hasattr(fantraxapi.objs, "League"):
        return fantraxapi.objs.League
    raise ImportError("Could not locate League class in fantraxapi (tried top-level and fantraxapi.objs).")

def _parse_cookie_header(raw: str):
    cookies = {}
    for pair in raw.split(";"):
        pair = pair.strip()
        if not pair or "=" not in pair:
            continue
        k, v = pair.split("=", 1)
        cookies[k.strip()] = v.strip()
    return cookies

def fetch_league_objects():
    # Accept either a single _FantraxAuth token or the full Cookie header
    auth = os.getenv("FANTRAX_COOKIE")
    raw  = os.getenv("FANTRAX_COOKIES_RAW")
    if auth:
        cookies = {"_FantraxAuth": auth}
    elif raw:
        cookies = _parse_cookie_header(raw)
    else:
        raise RuntimeError(
            "No cookie provided. Set FANTRAX_COOKIES_RAW (full Cookie header) "
            "or FANTRAX_COOKIE (the _FantraxAuth token)."
        )

    League = _get_league_class()
    return League(settings.league_id, cookies=cookies)

def get_team_roster_slots(league, week: int):
    rows = []
    for team in league.teams:
        roster = team.roster(week=week)
        for slot in roster.slots:
            rows.append({
                "team_id": team.id,
                "team_name": team.name,
                "player_id": slot.player.id,
                "player_name": slot.player.name,
                "position": getattr(slot, "position", None) or getattr(slot, "slot", None),
                "is_bench": getattr(slot, "is_bench", False),
            })
    return rows

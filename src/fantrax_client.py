from .config import settings
from fantraxapi.league import League
import os

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
    # Prefer explicit _FantraxAuth if you later find it
    auth = os.getenv("FANTRAX_COOKIE")  # optional
    raw  = os.getenv("FANTRAX_COOKIES_RAW")  # whole "Cookie" header value
    if auth:
        cookies = {"_FantraxAuth": auth}
    elif raw:
        cookies = _parse_cookie_header(raw)
    else:
        raise RuntimeError("No cookie provided. Set FANTRAX_COOKIES_RAW (full Cookie header) or FANTRAX_COOKIE (_FantraxAuth).")

    # Instantiate the league using the cookies dict
    league = League(settings.league_id, cookies=cookies)
    return league

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

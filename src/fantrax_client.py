import os
import requests
from .config import settings

def _parse_cookie_header(raw: str):
    cookies = {}
    for pair in raw.split(";"):
        pair = pair.strip()
        if not pair or "=" not in pair:
            continue
        k, v = pair.split("=", 1)
        cookies[k.strip()] = v.strip()
    return cookies

def _make_session():
    """Build a requests.Session with your Fantrax cookies loaded."""
    auth = os.getenv("FANTRAX_COOKIE")         # optional: just the _FantraxAuth token
    raw  = os.getenv("FANTRAX_COOKIES_RAW")    # optional: the full Cookie header value
    if not auth and not raw:
        raise RuntimeError(
            "No cookie provided. Set FANTRAX_COOKIES_RAW (full Cookie header) "
            "or FANTRAX_COOKIE (_FantraxAuth token)."
        )
    sess = requests.Session()
    # polite UA to avoid CF blocks
    sess.headers.update({
        "User-Agent": "Mozilla/5.0 (CheekyFC/1.0; +https://cheekyfc.example)"
    })
    if auth:
        sess.cookies.set("_FantraxAuth", auth, domain="www.fantrax.com")
    if raw:
        for k, v in _parse_cookie_header(raw).items():
            sess.cookies.set(k, v, domain="www.fantrax.com")
    return sess

def _get_league_class():
    import fantraxapi
    # Try modern layout
    if hasattr(fantraxapi, "League"):
        return fantraxapi.League
    # Try older layout
    try:
        from fantraxapi.objs import League as LeagueObj
        return LeagueObj
    except Exception:
        pass
    if hasattr(fantraxapi, "objs") and hasattr(fantraxapi.objs, "League"):
        return fantraxapi.objs.League
    raise ImportError("Could not locate League class in fantraxapi (tried top-level and fantraxapi.objs).")

def fetch_league_objects():
    League = _get_league_class()
    sess = _make_session()
    # Try the known constructor variants in order
    try:
        # Most 1.x builds accept session=
        return League(settings.league_id, session=sess)
    except TypeError:
        pass
    try:
        # Some builds accept client= (wrapping a Session)
        return League(settings.league_id, client=sess)
    except TypeError:
        pass
    # Fallback: construct, then attach (some 0.x put .session on the object)
    league = League(settings.league_id)
    # Attach if the attribute exists
    if hasattr(league, "session"):
        league.session = sess
        return league
    if hasattr(league, "_session"):
        league._session = sess  # last-ditch
        return league
    raise TypeError("This fantraxapi build exposes League but provides no way to inject a session/cookies.")

def _resolve_week_key(league, week: int):
    """
    Map a 1-based week like 1,2,3... to the league's actual scoring-period key.
    Some builds use integer numbers; others use short date strings like 'Aug 15'.
    """
    periods = league.scoring_periods()  # dict with keys that the library expects
    # Make an ordered list by 'number' if present, else preserve insertion order
    items = list(periods.items())

    # Prefer sorting by the ScoringPeriod.number if it exists
    try:
        items.sort(key=lambda kv: getattr(kv[1], "number"))
    except Exception:
        # fallback: keep original order
        pass

    if week < 1 or week > len(items):
        raise ValueError(f"Week {week} out of range (1..{len(items)})")

    key, sp = items[week - 1]
    # key is what roster() expects; can be int or 'Aug 15'
    return key

def get_team_roster_slots(league, week: int):
    # Convert user week to the exact key type roster() expects
    week_key = _resolve_week_key(league, week)

    rows = []
    for team in league.teams:
        # Try calling roster() with the derived key; handle variants gracefully
        try:
            roster = team.roster(week=week_key)
        except TypeError:
            # Some builds want the period number specifically
            num = getattr(league.scoring_periods()[week_key], "number", None)
            if num is None:
                raise
            roster = team.roster(week=num)

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


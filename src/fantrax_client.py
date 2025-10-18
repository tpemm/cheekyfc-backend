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

def _resolve_week_key(league, week: int):
    """Return (key, sp) where key is whatever the periods dict uses and sp is the ScoringPeriod object."""
    periods = league.scoring_periods()  # dict-like: { key -> ScoringPeriod }
    items = list(periods.items())

    # Prefer to sort by ScoringPeriod.number if it exists; otherwise keep insertion order
    try:
        items.sort(key=lambda kv: getattr(kv[1], "number"))
    except Exception:
        pass

    if week < 1 or week > len(items):
        raise ValueError(f"Week {week} out of range (1..{len(items)})")

    key, sp = items[week - 1]
    return key, sp

def _call_roster_any(team, key, sp):
    """Try multiple calling conventions for different fantraxapi builds."""
    # candidate numeric period
    num = getattr(sp, "number", None)
    candidates = []

    # 1) Most common: week=<key> (key may be int or string like 'Aug 15')
    candidates.append(("week", key))
    # 2) week=<number> (explicit number)
    if num is not None:
        candidates.append(("week", int(num)))

    # 3) scoring_period=<key> / <number>
    candidates.append(("scoring_period", key))
    if num is not None:
        candidates.append(("scoring_period", int(num)))

    # 4) period=<key> / <number>
    candidates.append(("period", key))
    if num is not None:
        candidates.append(("period", int(num)))

    # Try in order
    last_err = None
    for param, value in candidates:
        try:
            return team.roster(**{param: value})
        except Exception as e:
            last_err = e
            continue
    # If we get here, surface the most informative error
    raise TypeError(f"Failed to call team.roster with any known signature. "
                    f"Tried with key={key!r}, number={num!r}. Last error: {last_err}")

def _resolve_period_number(league, week: int) -> int:
    """
    Map a 1-based 'week' to the league's ScoringPeriod number (int).
    According to docs, League.scoring_periods() => dict[int, ScoringPeriod]
    where the KEY is the period number we can pass to team_roster(...).
    """
    periods = league.scoring_periods()  # { period_number (int) : ScoringPeriod }
    if not isinstance(periods, dict) or not periods:
        raise RuntimeError("Could not load scoring periods from Fantrax.")

    # Sort by the integer key to make week 1 = first period, week 2 = second, etc.
    numbers = sorted(int(n) for n in periods.keys())
    if week < 1 or week > len(numbers):
        raise ValueError(f"Week {week} out of range (1..{len(numbers)})")

    return numbers[week - 1]  # the actual integer period_number to call with

def get_team_roster_slots(league, week: int):
    period_number = _resolve_period_number(league, week)

    rows = []
    # Per docs, use League.team_roster(team_id, period_number)
    for team in league.teams:
        roster = league.team_roster(team.id, period_number=period_number)
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

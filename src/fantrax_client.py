import os
import pandas as pd
from dotenv import load_dotenv
from fantraxapi import FantraxClient
from pydantic import BaseModel

load_dotenv()


# -------------------------------
# CONFIG / SESSION MANAGEMENT
# -------------------------------

class CheekyConfig(BaseModel):
    username: str | None = os.getenv("FANTRAX_USERNAME")
    password: str | None = os.getenv("FANTRAX_PASSWORD")
    league_id: str = os.getenv("FANTRAX_LEAGUE_ID", "")
    cookies: str | None = os.getenv("FANTRAX_COOKIES")


def get_session():
    cfg = CheekyConfig()
    client = FantraxClient()

    if cfg.cookies:
        # Private league cookie authentication
        session = client.session(cookies=cfg.cookies)
    elif cfg.username and cfg.password:
        session = client.session.login(cfg.username, cfg.password)
    else:
        raise RuntimeError("Missing Fantrax login credentials or cookies in environment.")

    league = session.league(cfg.league_id)
    return league


# -------------------------------
# DEBUG UTILITIES
# -------------------------------

def _list_periods(league):
    """Return a stable ordered list of (key, sp) from league.scoring_periods()."""
    periods = league.scoring_periods()
    items = list(periods.items())
    try:
        items.sort(key=lambda kv: getattr(kv[1], "number"))
    except Exception:
        pass
    return items


def _resolve_week_index(league, week: int):
    items = _list_periods(league)
    if week < 1 or week > len(items):
        raise ValueError(f"Week {week} out of range (1..{len(items)})")
    key, sp = items[week - 1]

    candidates = []
    candidates.append(("raw_key", key))
    try:
        candidates.append(("str_key", str(key)))
    except Exception:
        pass

    num = getattr(sp, "number", None)
    if num is not None:
        try:
            candidates.append(("number_int", int(num)))
        except Exception:
            candidates.append(("number_raw", num))

    candidates.append(("index_based", week - 1))
    return candidates, sp


# -------------------------------
# ROSTER CALL TESTERS
# -------------------------------

def _call_roster_any(team, candidates, sp):
    """Try many calling conventions for team.roster(...)"""
    last_err = None
    tried = []
    for label, val in candidates:
        try:
            tried.append({"style": f"positional({label})", "value": repr(val)})
            return team.roster(val)
        except Exception as e:
            last_err = e
        for kw in ("week", "period", "scoring_period", "scoringPeriod", "period_number", "periodNumber"):
            try:
                tried.append({"style": f"kw {kw}={label}", "value": repr(val)})
                return team.roster(**{kw: val})
            except Exception as e:
                last_err = e
    raise TypeError(f"team.roster failed for all variants; last error={last_err}; tried={tried}")


def _league_team_roster_any(league, team, candidates, sp):
    """Try league.team_roster(team.id, period_number=INT) and variants."""
    last_err = None
    tried = []
    ints = []
    for label, val in candidates:
        if isinstance(val, int):
            ints.append((label, val))
        else:
            try:
                if isinstance(val, str) and val.isdigit():
                    ints.append((f"{label}->int", int(val)))
            except Exception:
                pass

    for label, val in ints:
        for kw in ("period_number", "period", "scoring_period"):
            try:
                tried.append({"style": f"league.team_roster kw {kw}={label}", "value": repr(val)})
                return league.team_roster(team.id, **{kw: val})
            except Exception as e:
                last_err = e
        try:
            tried.append({"style": f"league.team_roster positional({label})", "value": repr(val)})
            return league.team_roster(team.id, val)
        except Exception as e:
            last_err = e

    raise TypeError(f"league.team_roster failed for all variants; last error={last_err}; tried={tried}")


# -------------------------------
# MAIN PUBLIC FUNCTION
# -------------------------------

def get_team_roster_slots(league, week: int):
    candidates, sp = _resolve_week_index(league, week)
    rows = []
    for team in league.teams:
        roster = None
        try:
            roster = _call_roster_any(team, candidates, sp)
        except Exception as team_err:
            try:
                roster = _league_team_roster_any(league, team, candidates, sp)
            except Exception as lg_err:
                raise TypeError(
                    f"Roster retrieval failed for team {team.name}. "
                    f"team.roster error: {team_err}; league.team_roster error: {lg_err}"
                )
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


# -------------------------------
# ENTRY POINT USED BY API
# -------------------------------

def run_fantrax_pull(week: int = 1):
    league = get_session()
    roster_rows = get_team_roster_slots(league, week)
    df = pd.DataFrame(roster_rows)
    return df

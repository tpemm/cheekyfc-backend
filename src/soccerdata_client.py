import soccerdata as sd
import pandas as pd
from .config import settings

def pull_fbref_player_stats() -> pd.DataFrame:
    fbref = sd.FBref()
    df = fbref.read_player_season_stats(
        stat_type="summary",
        competition=settings.competition,
        season=settings.season
    )
    df = df.reset_index().rename(columns={
        "player": "fbref_player_name",
        "team": "team_name_fbref",
        "pos": "pos_fbref",
        "gls": "goals",
        "ast": "assists",
        "xg": "xg",
        "xa": "xa",
        "npxg": "npxg",
        "mp": "matches",
        "min": "minutes",
    })
    for c in ["fbref_player_name", "team_name_fbref", "pos_fbref"]:
        if c in df:
            df[c] = df[c].astype(str)
    return df

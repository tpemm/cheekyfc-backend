import pandas as pd
WEIGHTS = {"goal": 6.0, "assist": 4.0}

def per90(val, minutes):
    return (val / minutes) * 90 if minutes and minutes > 0 else 0.0

def add_basic_metrics(df: pd.DataFrame) -> pd.DataFrame:
    df["xG90"] = df.apply(lambda r: per90(r.get("xg", 0.0), r.get("minutes", 0)), axis=1)
    df["xA90"] = df.apply(lambda r: per90(r.get("xa", 0.0), r.get("minutes", 0)), axis=1)
    expected_minutes = df.get("minutes").fillna(0).clip(lower=0, upper=3000)
    df["proj_points_simple"] = ((df["xG90"] * WEIGHTS["goal"]) + (df["xA90"] * WEIGHTS["assist"])) * (expected_minutes / 90.0)
    return df

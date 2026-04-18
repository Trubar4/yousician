import json
import os

import pandas as pd

DATA_ROOT = os.environ.get("YUSICIAN_DATA_ROOT", "data/yousician")
EVENTS_ROOT = os.environ.get("YUSICIAN_EVENTS_ROOT", "data/events")

_SONG_FIELDS = [
    "song_id", "song_title", "song_instrument", "play_mode",
    "duration", "received_at", "score",
    "notes_evaluated", "notes_successful",
    "chords_evaluated", "chords_successful",
    "song_level", "song_category", "status",
]


def _read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_song_events():
    """Load all song_played events from ysapi.jsonl into a raw DataFrame."""
    jsonl_path = os.path.join(EVENTS_ROOT, "ysapi.jsonl")
    if not os.path.exists(jsonl_path):
        return pd.DataFrame(columns=_SONG_FIELDS)
    rows = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                o = json.loads(line)
            except Exception:
                continue
            if o.get("_yap_event_name") != "song_played":
                continue
            rows.append({k: o.get(k) for k in _SONG_FIELDS})
    df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=_SONG_FIELDS)
    if df.empty:
        return df
    df["received_at"] = pd.to_datetime(df["received_at"], errors="coerce", utc=True)
    for col in ["duration", "notes_evaluated", "notes_successful",
                "chords_evaluated", "chords_successful", "score", "song_level"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    mask = df["notes_evaluated"] > 0
    df["accuracy"] = None
    df.loc[mask, "accuracy"] = (
        df.loc[mask, "notes_successful"] / df.loc[mask, "notes_evaluated"]
    )
    return df


def songs_by_instrument(events_df):
    """Aggregate play counts per (instrument, song) from events."""
    if events_df.empty:
        return pd.DataFrame(
            columns=["instrument", "item_name", "plays", "total_min", "first_play", "last_play"]
        )
    grp = (
        events_df.groupby(["song_instrument", "song_title"])
        .agg(
            plays=("duration", "count"),
            total_min=("duration", lambda x: round(x.sum() / 60, 1)),
            first_play=("received_at", "min"),
            last_play=("received_at", "max"),
        )
        .reset_index()
        .rename(columns={"song_instrument": "instrument", "song_title": "item_name"})
        .sort_values(["instrument", "plays"], ascending=[True, False])
    )
    return grp


def load_song_time_summary(events_df):
    """Aggregate duration by (song_id, title, play_mode) for Practice vs Play tab."""
    if events_df.empty:
        return pd.DataFrame(
            columns=["song_id", "title", "play_mode", "total_duration_sec", "sessions"]
        )
    grp = (
        events_df.groupby(["song_id", "song_title", "play_mode"], dropna=False)
        .agg(
            total_duration_sec=("duration", "sum"),
            sessions=("duration", "count"),
        )
        .reset_index()
        .rename(columns={"song_title": "title"})
    )
    return grp


def load_stats():
    path = os.path.join(DATA_ROOT, "stats.json")
    try:
        raw = _read_json(path)
    except FileNotFoundError:
        return pd.DataFrame(columns=["instrument", "week", "duration_sec", "stars", "notes", "chords"])
    rows = []
    for rec in raw:
        base = {k: rec.get(k) for k in ["instrument", "week"]}
        base["week"] = pd.to_datetime(base["week"], errors="coerce", utc=True)
        s = rec.get("stats", {}) or {}
        rows.append({
            **base,
            "duration_sec": s.get("duration", 0),
            "stars": s.get("stars", 0),
            "notes": s.get("notes", 0),
            "chords": s.get("chords", 0),
        })
    return pd.DataFrame(rows)


def load_exercise_progress():
    path = os.path.join(DATA_ROOT, "exercise_progress.json")
    try:
        raw = _read_json(path)
    except FileNotFoundError:
        return pd.DataFrame()
    df = pd.DataFrame(raw)
    if not df.empty and "time" in df.columns:
        df["time"] = pd.to_datetime(df["time"], errors="coerce", utc=True)
    return df


def practice_time_by_week(stats_df):
    df = stats_df.copy()
    if df.empty:
        return df
    df["duration_min"] = df["duration_sec"] / 60.0
    return df

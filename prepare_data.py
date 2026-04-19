#!/usr/bin/env python3
"""
One-time data preparation: ysapi.jsonl → songs.json
Run from your project folder:

    python prepare_data.py

Or pass the path to ysapi.jsonl directly:

    python prepare_data.py C:/path/to/ysapi.jsonl

Output: songs.json (next to this script, load it in dashboard.html)
"""

import json
import os
import shutil
import sys
from collections import defaultdict

# ── Paths ──────────────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

if len(sys.argv) > 1:
    JSONL_PATH = sys.argv[1]
else:
    candidates = [
        os.path.join(SCRIPT_DIR, "data", "events", "ysapi.jsonl"),
        os.path.join(SCRIPT_DIR, "ysapi.jsonl"),
    ]
    JSONL_PATH = next((p for p in candidates if os.path.exists(p)), candidates[0])

STATS_CANDIDATES = [
    os.path.join(SCRIPT_DIR, "data", "yousician", "stats.json"),
    os.path.join(SCRIPT_DIR, "stats.json"),
]

SONGS_OUT = os.path.join(SCRIPT_DIR, "songs.json")
STATS_OUT  = os.path.join(SCRIPT_DIR, "stats.json")

# ── Process ysapi.jsonl ─────────────────────────────────────────────────────────────────────────────
print(f"Reading: {JSONL_PATH}")
if not os.path.exists(JSONL_PATH):
    print(f"ERROR: File not found: {JSONL_PATH}")
    print("Pass the path as argument: python prepare_data.py C:/path/to/ysapi.jsonl")
    sys.exit(1)

songs = defaultdict(lambda: {
    "plays": 0, "practice_sec": 0.0, "play_sec": 0.0,
    "notes_eval": 0.0, "notes_hit": 0.0, "best_score": 0,
    "title": None, "instrument": None, "level": None,
    "category": None, "first_play": None, "last_play": None,
})

total_lines = 0
song_events = 0

with open(JSONL_PATH, "r", encoding="utf-8") as f:
    for line in f:
        total_lines += 1
        if total_lines % 500_000 == 0:
            print(f"  {total_lines:,} lines read, {song_events:,} song_played events…")
        try:
            o = json.loads(line)
        except Exception:
            continue
        if o.get("_yap_event_name") != "song_played":
            continue

        sid = o.get("song_id")
        if not sid:
            continue

        song_events += 1
        s = songs[sid]
        s["plays"] += 1
        s["title"]      = s["title"]      or o.get("song_title") or o.get("song_name")
        s["instrument"] = s["instrument"] or o.get("song_instrument")
        s["level"]      = o.get("song_level")    or s["level"]
        s["category"]   = s["category"]   or o.get("song_category")

        mode = o.get("play_mode") or "unknown"
        dur  = float(o.get("duration") or 0)
        if mode == "practice":
            s["practice_sec"] += dur
        else:
            s["play_sec"] += dur

        s["notes_eval"] += float(o.get("notes_evaluated") or 0)
        s["notes_hit"]  += float(o.get("notes_successful") or 0)

        score = float(o.get("score") or 0)
        if score > s["best_score"]:
            s["best_score"] = int(score)

        ts = (o.get("received_at") or o.get("time_local") or "")[:10]
        if ts:
            if s["first_play"] is None or ts < s["first_play"]:
                s["first_play"] = ts
            if s["last_play"]  is None or ts > s["last_play"]:
                s["last_play"]  = ts

print(f"\n{total_lines:,} lines processed, {song_events:,} song_played events, {len(songs):,} unique songs")

# ── Build output ────────────────────────────────────────────────────────────────────────────────
result = []
for sid, s in songs.items():
    acc = round(s["notes_hit"] / s["notes_eval"] * 100, 1) if s["notes_eval"] > 0 else None
    result.append({
        "song_id":      sid,
        "title":        s["title"] or "Unknown",
        "instrument":   s["instrument"] or "unknown",
        "plays":        s["plays"],
        "practice_min": round(s["practice_sec"] / 60, 1),
        "play_min":     round(s["play_sec"]     / 60, 1),
        "total_min":    round((s["practice_sec"] + s["play_sec"]) / 60, 1),
        "avg_accuracy": acc,
        "best_score":   s["best_score"],
        "level":        s["level"],
        "category":     s["category"],
        "first_play":   s["first_play"],
        "last_play":    s["last_play"],
    })

result.sort(key=lambda x: x["plays"], reverse=True)

with open(SONGS_OUT, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, separators=(",", ":"))

size_kb = os.path.getsize(SONGS_OUT) // 1024
print(f"→ songs.json written ({len(result)} songs, {size_kb} KB)")

# ── Copy stats.json if not already there ─────────────────────────────────────────────────────────────────────────────────
if not os.path.exists(STATS_OUT):
    src = next((p for p in STATS_CANDIDATES if os.path.exists(p)), None)
    if src and src != STATS_OUT:
        shutil.copy2(src, STATS_OUT)
        print(f"→ stats.json copied from {src}")
    else:
        print("  stats.json not found – copy it manually next to dashboard.html")
else:
    print("→ stats.json already present")

print("\nDone! Open dashboard.html and load both JSON files.")

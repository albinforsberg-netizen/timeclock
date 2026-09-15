#!/usr/bin/env python3
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import json
from pathlib import Path

from generate_readme_stats import WORK_LOG_PATH, parse_sessions

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "data" / "dashboard.json"


def main() -> None:
    sessions = parse_sessions(WORK_LOG_PATH)
    daily: dict[str, float] = defaultdict(float)
    weekly: dict[str, float] = defaultdict(float)
    monthly: dict[str, float] = defaultdict(float)
    projects: dict[str, float] = defaultdict(float)
    weekdays: dict[str, float] = defaultdict(float)
    start_hours: dict[str, int] = defaultdict(int)

    for session in sessions:
        day = session.start.strftime("%Y-%m-%d")
        daily[day] += session.hours
        iso = session.start.isocalendar()
        weekly[f"{iso[0]}-W{iso[1]:02d}"] += session.hours
        monthly[session.start.strftime("%Y-%m")] += session.hours
        projects[session.project] += session.hours
        weekdays[session.start.strftime("%A")] += session.hours
        start_hours[f"{session.start.hour:02d}:00"] += 1

    payload = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="minutes"),
        "total_hours": round(sum(daily.values()), 2),
        "session_count": len(sessions),
        "active_days": len(daily),
        "daily": dict(sorted(daily.items())),
        "weekly": dict(sorted(weekly.items())),
        "monthly": dict(sorted(monthly.items())),
        "projects": dict(sorted(projects.items(), key=lambda item: item[1], reverse=True)),
        "weekdays": {day: round(weekdays.get(day, 0.0), 2) for day in (
            "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"
        )},
        "start_hours": dict(sorted(start_hours.items())),
        "sessions": [
            {
                "date": session.start.strftime("%Y-%m-%d"),
                "project": session.project,
                "hours": round(session.hours, 2),
            }
            for session in sorted(sessions, key=lambda item: item.start, reverse=True)[:20]
        ],
    }

    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
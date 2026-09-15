#!/usr/bin/env python3
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import json
from pathlib import Path
from statistics import median

from generate_readme_stats import WORK_LOG_PATH, parse_sessions

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "assets" / "dashboard-data.json"


def main() -> None:
    sessions = parse_sessions(WORK_LOG_PATH)
    daily: dict[str, float] = defaultdict(float)
    weekly: dict[str, float] = defaultdict(float)
    monthly: dict[str, float] = defaultdict(float)
    quarterly: dict[str, float] = defaultdict(float)
    monthly_projects: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    projects: dict[str, float] = defaultdict(float)
    project_sessions: dict[str, int] = defaultdict(int)
    weekdays: dict[str, float] = defaultdict(float)
    start_hours: dict[str, int] = defaultdict(int)
    start_hours_time: dict[str, float] = defaultdict(float)
    session_buckets: dict[str, int] = defaultdict(int)
    day_session_counts: dict[str, int] = defaultdict(int)
    day_projects: dict[str, set[str]] = defaultdict(set)
    weekend_hours = 0.0
    weekend_sessions = 0

    for session in sessions:
        day = session.start.strftime("%Y-%m-%d")
        daily[day] += session.hours
        iso = session.start.isocalendar()
        weekly[f"{iso[0]}-W{iso[1]:02d}"] += session.hours
        monthly[session.start.strftime("%Y-%m")] += session.hours
        quarter = ((session.start.month - 1) // 3) + 1
        quarterly[f"{session.start.year}-Q{quarter}"] += session.hours
        monthly_projects[session.start.strftime("%Y-%m")][session.project] += session.hours
        projects[session.project] += session.hours
        project_sessions[session.project] += 1
        weekdays[session.start.strftime("%A")] += session.hours
        start_hours[f"{session.start.hour:02d}:00"] += 1
        start_hours_time[f"{session.start.hour:02d}:00"] += session.hours
        day_session_counts[day] += 1
        day_projects[day].add(session.project)
        if session.start.weekday() >= 5:
            weekend_hours += session.hours
            weekend_sessions += 1
        if session.hours < 0.5:
            session_buckets["Under 30 min"] += 1
        elif session.hours < 1:
            session_buckets["30-60 min"] += 1
        elif session.hours < 2:
            session_buckets["1-2 hours"] += 1
        elif session.hours < 4:
            session_buckets["2-4 hours"] += 1
        else:
            session_buckets["4+ hours"] += 1

    payload = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="minutes"),
        "total_hours": round(sum(daily.values()), 2),
        "session_count": len(sessions),
        "active_days": len(daily),
        "daily": dict(sorted(daily.items())),
        "weekly": dict(sorted(weekly.items())),
        "monthly": dict(sorted(monthly.items())),
        "quarterly": dict(sorted(quarterly.items())),
        "monthly_projects": {
            month: dict(sorted(project_totals.items()))
            for month, project_totals in sorted(monthly_projects.items())
        },
        "projects": dict(sorted(projects.items(), key=lambda item: item[1], reverse=True)),
        "project_sessions": dict(project_sessions),
        "project_count": len(projects),
        "weekdays": {day: round(weekdays.get(day, 0.0), 2) for day in (
            "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"
        )},
        "start_hours": dict(sorted(start_hours.items())),
        "start_hours_time": {
            hour: round(value, 2) for hour, value in sorted(start_hours_time.items())
        },
        "session_buckets": dict(session_buckets),
        "daily_sessions": dict(sorted(day_session_counts.items())),
        "daily_projects": {
            day: len(projects_for_day) for day, projects_for_day in sorted(day_projects.items())
        },
        "weekend_hours": round(weekend_hours, 2),
        "weekend_sessions": weekend_sessions,
        "session_stats": {
            "average": round(sum(session.hours for session in sessions) / len(sessions), 2) if sessions else 0,
            "median": round(median(session.hours for session in sessions), 2) if sessions else 0,
            "shortest": round(min((session.hours for session in sessions), default=0), 2),
        },
        "target_hours_per_day": 8,
        "longest_session": max(
            (
                {
                    "date": session.start.strftime("%Y-%m-%d"),
                    "project": session.project,
                    "hours": round(session.hours, 2),
                }
                for session in sessions
            ),
            key=lambda item: item["hours"],
            default={"date": "", "project": "", "hours": 0},
        ),
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
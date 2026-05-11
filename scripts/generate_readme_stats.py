#!/usr/bin/env python3
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
README_PATH = ROOT / "README.org"
WORK_LOG_PATH = ROOT / "timelog-work"

START_MARKER = "# STATS:START"
END_MARKER = "# STATS:END"
LINE_RE = re.compile(
    r"^(?P<kind>[io]) (?P<date>\d{4}/\d{2}/\d{2}) (?P<time>\d{2}:\d{2}:\d{2})(?: (?P<label>.*))?$"
)
MAX_SESSION_HOURS = 18.0


@dataclass
class Session:
    start: datetime
    end: datetime
    project: str

    @property
    def hours(self) -> float:
        return max((self.end - self.start).total_seconds() / 3600.0, 0.0)


def parse_sessions(path: Path) -> list[Session]:
    sessions: list[Session] = []
    active: tuple[datetime, str] | None = None

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue

        match = LINE_RE.match(line)
        if not match:
            continue

        kind = match.group("kind")
        timestamp = datetime.strptime(
            f"{match.group('date')} {match.group('time')}", "%Y/%m/%d %H:%M:%S"
        )
        label = (match.group("label") or "").strip() or "Uncategorized"

        if kind == "i":
            active = (timestamp, label)
            continue

        if active is None:
            continue

        start, project = active
        if timestamp <= start:
            active = None
            continue

        session = Session(start=start, end=timestamp, project=project)
        if session.hours > MAX_SESSION_HOURS:
            active = None
            continue

        sessions.append(session)
        active = None

    return sessions


def format_hours(value: float) -> str:
    return f"{value:.2f}"


def sanitize_label(label: str, max_len: int = 36) -> str:
    safe = label.replace('"', "'").replace("`", "'")
    if len(safe) <= max_len:
        return safe
    return f"{safe[: max_len - 1]}…"


def rolling_hours(by_day: dict[str, float], end_day: datetime, days: int) -> float:
    start_day = end_day - timedelta(days=days - 1)
    total = 0.0
    current = start_day
    while current <= end_day:
        total += by_day.get(current.strftime("%Y-%m-%d"), 0.0)
        current += timedelta(days=1)
    return total


def build_scope_section(scope: str, sessions: list[Session]) -> str:
    if not sessions:
        return f"** {scope}\n\n/No entries found./\n"

    total_hours = sum(s.hours for s in sessions)
    by_project: dict[str, float] = defaultdict(float)
    by_day: dict[str, float] = defaultdict(float)
    by_weekday: dict[str, float] = defaultdict(float)

    for session in sessions:
        by_project[session.project] += session.hours
        day_key = session.start.strftime("%Y-%m-%d")
        by_day[day_key] += session.hours
        by_weekday[session.start.strftime("%A")] += session.hours

    active_days = len(by_day)
    avg_day = total_hours / active_days if active_days else 0.0
    avg_session = total_hours / len(sessions) if sessions else 0.0

    top_projects = sorted(by_project.items(), key=lambda item: item[1], reverse=True)[:5]

    latest_day = max(datetime.strptime(day, "%Y-%m-%d") for day in by_day)
    first_day = latest_day - timedelta(days=13)
    chart_days: list[str] = []
    chart_hours: list[str] = []

    current = first_day
    while current <= latest_day:
        key = current.strftime("%Y-%m-%d")
        chart_days.append(key[5:])
        chart_hours.append(f"{by_day.get(key, 0.0):.2f}")
        current += timedelta(days=1)

    max_chart_value = max((float(value) for value in chart_hours), default=0.0)
    chart_ceiling = max(int(max_chart_value * 1.2) + 1, 1)

    longest_session = max(sessions, key=lambda s: s.hours)
    best_day, best_day_hours = max(by_day.items(), key=lambda item: item[1])
    top_weekday, top_weekday_hours = max(by_weekday.items(), key=lambda item: item[1])

    last_7_days_total = rolling_hours(by_day, latest_day, 7)
    last_30_days_total = rolling_hours(by_day, latest_day, 30)

    pie_lines = "\n".join(
        f'    "{sanitize_label(name)}" : {hours:.2f}' for name, hours in top_projects
    )
    x_axis = ", ".join(f'"{day}"' for day in chart_days)
    bars = ", ".join(chart_hours)

    return (
        f"** {scope}\n\n"
        f"- *Total tracked:* {format_hours(total_hours)} h\n"
        f"- *Sessions:* {len(sessions)}\n"
        f"- *Active days:* {active_days}\n"
        f"- *Average / active day:* {format_hours(avg_day)} h\n"
        f"- *Average session:* {format_hours(avg_session)} h\n\n"
        f"*** Insights\n"
        f"- *Last 7 days:* {format_hours(last_7_days_total)} h ({format_hours(last_7_days_total / 7)} h/day)\n"
        f"- *Last 30 days:* {format_hours(last_30_days_total)} h ({format_hours(last_30_days_total / 30)} h/day)\n"
        f"- *Best day:* {best_day} ({format_hours(best_day_hours)} h)\n"
        f"- *Most active weekday:* {top_weekday} ({format_hours(top_weekday_hours)} h total)\n"
        f"- *Longest session:* {format_hours(longest_session.hours)} h on {longest_session.start.strftime('%Y-%m-%d')} ({sanitize_label(longest_session.project)})\n\n"
        f"*** Top projects (hours)\n"
        f"#+begin_src mermaid\n"
        f"pie showData\n"
        f"{pie_lines}\n"
        f"#+end_src\n\n"
        f"*** Last 14 days\n"
        f"#+begin_src mermaid\n"
        f"xychart-beta\n"
        f"    title \"Tracked hours\"\n"
        f"    x-axis [{x_axis}]\n"
        f"    y-axis \"Hours\" 0 --> {chart_ceiling}\n"
        f"    bar [{bars}]\n"
        f"#+end_src\n"
    )


def build_stats_markdown() -> str:
    sessions = parse_sessions(WORK_LOG_PATH)
    generated_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    return (
        "** Time log stats\n\n"
        "Auto-generated from =timelog-work=.\n\n"
        + build_scope_section("Work", sessions)
        + f"\n/Generated: {generated_at}/\n"
    )


def update_readme(content: str) -> None:
    if README_PATH.exists():
        readme = README_PATH.read_text(encoding="utf-8")
    else:
        readme = "* timeclock\n"

    block = f"{START_MARKER}\n{content}\n{END_MARKER}"

    if START_MARKER in readme and END_MARKER in readme:
        pattern = re.compile(
            rf"{re.escape(START_MARKER)}.*?{re.escape(END_MARKER)}",
            flags=re.DOTALL,
        )
        updated = pattern.sub(block, readme)
    else:
        if not readme.endswith("\n"):
            readme += "\n"
        updated = readme + "\n" + block + "\n"

    README_PATH.write_text(updated, encoding="utf-8")


def main() -> None:
    stats = build_stats_markdown()
    update_readme(stats)


if __name__ == "__main__":
    main()

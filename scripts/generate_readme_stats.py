#!/usr/bin/env python3
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
README_PATH = ROOT / "README.md"

LOG_FILES = {
    "Work": ROOT / "timelog-work",
    "Personal": ROOT / "timelog-personal",
}

START_MARKER = "<!-- STATS:START -->"
END_MARKER = "<!-- STATS:END -->"
LINE_RE = re.compile(
    r"^(?P<kind>[io]) (?P<date>\d{4}/\d{2}/\d{2}) (?P<time>\d{2}:\d{2}:\d{2})(?: (?P<label>.*))?$"
)


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

        sessions.append(Session(start=start, end=timestamp, project=project))
        active = None

    return sessions


def format_hours(value: float) -> str:
    return f"{value:.2f}"


def sanitize_label(label: str, max_len: int = 36) -> str:
    safe = label.replace('"', "'").replace("`", "'")
    if len(safe) <= max_len:
        return safe
    return f"{safe[: max_len - 1]}…"


def build_scope_section(scope: str, sessions: list[Session]) -> str:
    if not sessions:
        return f"## {scope}\n\n_No entries found._\n"

    total_hours = sum(s.hours for s in sessions)
    by_project: dict[str, float] = defaultdict(float)
    by_day: dict[str, float] = defaultdict(float)

    for session in sessions:
        by_project[session.project] += session.hours
        by_day[session.start.strftime("%Y-%m-%d")] += session.hours

    active_days = len(by_day)
    avg_day = total_hours / active_days if active_days else 0.0

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

    pie_lines = "\n".join(
        f'    "{sanitize_label(name)}" : {hours:.2f}' for name, hours in top_projects
    )
    x_axis = ", ".join(f'"{day}"' for day in chart_days)
    bars = ", ".join(chart_hours)

    return (
        f"## {scope}\n\n"
        f"- **Total tracked:** {format_hours(total_hours)} h\n"
        f"- **Sessions:** {len(sessions)}\n"
        f"- **Active days:** {active_days}\n"
        f"- **Average / active day:** {format_hours(avg_day)} h\n\n"
        f"### Top projects (hours)\n"
        f"```mermaid\n"
        f"pie showData\n"
        f"{pie_lines}\n"
        f"```\n\n"
        f"### Last 14 days\n"
        f"```mermaid\n"
        f"xychart-beta\n"
        f"    title \"Tracked hours\"\n"
        f"    x-axis [{x_axis}]\n"
        f"    y-axis \"Hours\" 0 --> 12\n"
        f"    bar [{bars}]\n"
        f"```\n"
    )


def build_stats_markdown() -> str:
    sections: list[str] = []
    total_by_scope: dict[str, float] = {}

    for scope, path in LOG_FILES.items():
        sessions = parse_sessions(path)
        total_by_scope[scope] = sum(s.hours for s in sessions)
        sections.append(build_scope_section(scope, sessions))

    scope_pie = "\n".join(
        f'    "{scope}" : {hours:.2f}' for scope, hours in total_by_scope.items() if hours > 0
    ) or '    "No data" : 1'

    generated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    return (
        "## Time log stats\n\n"
        "Auto-generated from `timelog-work` and `timelog-personal`.\n\n"
        "### Hours by scope\n"
        "```mermaid\n"
        "pie showData\n"
        f"{scope_pie}\n"
        "```\n\n"
        + "\n".join(sections)
        + f"\n_Generated: {generated_at}_\n"
    )


def update_readme(content: str) -> None:
    if README_PATH.exists():
        readme = README_PATH.read_text(encoding="utf-8")
    else:
        readme = "# timeclock\n"

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

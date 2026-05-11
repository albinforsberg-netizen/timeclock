#!/usr/bin/env python3
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
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


def iso_week_key(dt: datetime) -> str:
    """Return 'YYYY-Www' ISO week string for a datetime."""
    iso = dt.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def week_start(year: int, week: int) -> date:
    """Return the Monday of the given ISO year/week."""
    return date.fromisocalendar(year, week, 1)


def working_day_streak(by_day: dict[str, float], latest_day: datetime) -> int:
    """Count consecutive days with logged hours ending on latest_day."""
    streak = 0
    current = latest_day
    while True:
        key = current.strftime("%Y-%m-%d")
        if by_day.get(key, 0.0) > 0:
            streak += 1
            current -= timedelta(days=1)
        else:
            break
    return streak


def build_weekly_section(sessions: list[Session]) -> str:
    """Build a weekly breakdown section covering the last 12 ISO weeks."""
    if not sessions:
        return ""

    by_week: dict[str, float] = defaultdict(float)
    by_day: dict[str, float] = defaultdict(float)
    for session in sessions:
        by_week[iso_week_key(session.start)] += session.hours
        by_day[session.start.strftime("%Y-%m-%d")] += session.hours

    latest_day = max(datetime.strptime(d, "%Y-%m-%d") for d in by_day)
    latest_iso = latest_day.isocalendar()
    # Collect the last 12 weeks ending at the week containing latest_day
    weeks: list[tuple[int, int]] = []
    cur_year, cur_week = latest_iso[0], latest_iso[1]
    for _ in range(12):
        weeks.append((cur_year, cur_week))
        # Go back one week
        prev = week_start(cur_year, cur_week) - timedelta(days=1)
        cur_year, cur_week = prev.isocalendar()[0], prev.isocalendar()[1]
    weeks.reverse()

    week_labels: list[str] = []
    week_hours_list: list[float] = []
    for y, w in weeks:
        key = f"{y}-W{w:02d}"
        ws = week_start(y, w)
        label = ws.strftime("%m/%d")
        week_labels.append(label)
        week_hours_list.append(by_week.get(key, 0.0))

    # Current vs previous week
    cur_key = f"{latest_iso[0]}-W{latest_iso[1]:02d}"
    cur_week_hours = by_week.get(cur_key, 0.0)
    prev_ws = week_start(latest_iso[0], latest_iso[1]) - timedelta(days=1)
    prev_key = f"{prev_ws.isocalendar()[0]}-W{prev_ws.isocalendar()[1]:02d}"
    prev_week_hours = by_week.get(prev_key, 0.0)

    delta = cur_week_hours - prev_week_hours
    delta_str = f"+{format_hours(delta)}" if delta >= 0 else format_hours(delta)

    max_val = max(week_hours_list, default=0.0)
    ceiling = max(int(max_val * 1.2) + 1, 1)
    x_axis = ", ".join(f'"{label}"' for label in week_labels)
    bars = ", ".join(f"{h:.2f}" for h in week_hours_list)

    return (
        f"*** Weekly breakdown (last 12 weeks)\n"
        f"- *This week ({cur_key}):* {format_hours(cur_week_hours)} h\n"
        f"- *Previous week ({prev_key}):* {format_hours(prev_week_hours)} h\n"
        f"- *Week-over-week change:* {delta_str} h\n\n"
        f"#+begin_src mermaid\n"
        f"xychart-beta\n"
        f"    title \"Weekly hours\"\n"
        f"    x-axis [{x_axis}]\n"
        f"    y-axis \"Hours\" 0 --> {ceiling}\n"
        f"    bar [{bars}]\n"
        f"#+end_src\n"
    )


def build_monthly_section(sessions: list[Session]) -> str:
    """Build a monthly breakdown section covering the last 12 months."""
    if not sessions:
        return ""

    by_month: dict[str, float] = defaultdict(float)
    by_month_days: dict[str, set[str]] = defaultdict(set)
    for session in sessions:
        month_key = session.start.strftime("%Y-%m")
        by_month[month_key] += session.hours
        by_month_days[month_key].add(session.start.strftime("%Y-%m-%d"))

    # Last 12 months ending at latest month
    all_months = sorted(by_month.keys())
    latest_month = all_months[-1]
    y, m = int(latest_month[:4]), int(latest_month[5:7])

    months: list[tuple[int, int]] = []
    cy, cm = y, m
    for _ in range(12):
        months.append((cy, cm))
        cm -= 1
        if cm == 0:
            cm = 12
            cy -= 1
    months.reverse()

    month_labels: list[str] = []
    month_hours_list: list[float] = []
    for my, mm in months:
        key = f"{my}-{mm:02d}"
        month_labels.append(f"{my}-{mm:02d}")
        month_hours_list.append(by_month.get(key, 0.0))

    # Current vs previous month
    cur_month_key = f"{y}-{m:02d}"
    cur_month_hours = by_month.get(cur_month_key, 0.0)
    pm = m - 1 if m > 1 else 12
    py = y if m > 1 else y - 1
    prev_month_key = f"{py}-{pm:02d}"
    prev_month_hours = by_month.get(prev_month_key, 0.0)

    delta = cur_month_hours - prev_month_hours
    delta_str = f"+{format_hours(delta)}" if delta >= 0 else format_hours(delta)

    cur_active_days = len(by_month_days.get(cur_month_key, set()))
    cur_avg = cur_month_hours / cur_active_days if cur_active_days else 0.0

    max_val = max(month_hours_list, default=0.0)
    ceiling = max(int(max_val * 1.2) + 1, 1)
    x_axis = ", ".join(f'"{label}"' for label in month_labels)
    bars = ", ".join(f"{h:.2f}" for h in month_hours_list)

    return (
        f"*** Monthly breakdown (last 12 months)\n"
        f"- *This month ({cur_month_key}):* {format_hours(cur_month_hours)} h "
        f"({cur_active_days} active days, avg {format_hours(cur_avg)} h/day)\n"
        f"- *Previous month ({prev_month_key}):* {format_hours(prev_month_hours)} h\n"
        f"- *Month-over-month change:* {delta_str} h\n\n"
        f"#+begin_src mermaid\n"
        f"xychart-beta\n"
        f"    title \"Monthly hours\"\n"
        f"    x-axis [{x_axis}]\n"
        f"    y-axis \"Hours\" 0 --> {ceiling}\n"
        f"    bar [{bars}]\n"
        f"#+end_src\n"
    )


def build_scope_section(scope: str, sessions: list[Session]) -> str:
    if not sessions:
        return f"** {scope}\n\n/No entries found./\n"

    total_hours = sum(s.hours for s in sessions)
    by_project: dict[str, float] = defaultdict(float)
    by_day: dict[str, float] = defaultdict(float)
    by_weekday: dict[str, float] = defaultdict(float)
    by_weekday_days: dict[str, set[str]] = defaultdict(set)

    for session in sessions:
        by_project[session.project] += session.hours
        day_key = session.start.strftime("%Y-%m-%d")
        by_day[day_key] += session.hours
        wd = session.start.strftime("%A")
        by_weekday[wd] += session.hours
        by_weekday_days[wd].add(day_key)

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

    streak = working_day_streak(by_day, latest_day)

    # Weekday average (only Mon–Fri)
    weekday_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    weekday_avg_lines = "".join(
        f"  - {wd}: {format_hours(by_weekday.get(wd, 0.0) / len(by_weekday_days[wd]))}"
        f" h/day ({len(by_weekday_days.get(wd, set()))} days)\n"
        for wd in weekday_order
        if by_weekday_days.get(wd)
    )

    pie_lines = "\n".join(
        f'    "{sanitize_label(name)}" : {hours:.2f}' for name, hours in top_projects
    )
    x_axis = ", ".join(f'"{day}"' for day in chart_days)
    bars = ", ".join(chart_hours)

    weekly_section = build_weekly_section(sessions)
    monthly_section = build_monthly_section(sessions)

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
        f"- *Longest session:* {format_hours(longest_session.hours)} h on {longest_session.start.strftime('%Y-%m-%d')} ({sanitize_label(longest_session.project)})\n"
        f"- *Current working-day streak:* {streak} day{'s' if streak != 1 else ''}\n\n"
        f"**** Average hours per weekday\n"
        f"{weekday_avg_lines}\n"
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
        f"#+end_src\n\n"
        f"{weekly_section}\n"
        f"{monthly_section}"
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

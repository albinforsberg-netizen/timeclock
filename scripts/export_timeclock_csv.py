#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
import argparse
import math
import re

ROOT = Path(__file__).resolve().parents[1]
WORK_LOG_PATH = ROOT / "timelog-work"
PROJECTS_PATH = ROOT / "timeclock-projects-work.eld"
EXPORT_DIR = ROOT / "exports"

LINE_RE = re.compile(
    r"^(?P<kind>[ioO]) (?P<date>\d{4}/\d{2}/\d{2}) (?P<time>\d{2}:\d{2}:\d{2})(?: (?P<label>.*))?$"
)


@dataclass
class RawSession:
    day: str
    project: str
    description: str
    hours: float
    start_time: str
    end_time: str


@dataclass
class Session:
    day: str
    project: str
    description: str
    hours: float


def parse_timelog(path: Path) -> list[RawSession]:
    if not path.exists():
        return []

    current_project = ""
    current_start_day: str | None = None
    current_start_time: str | None = None
    accumulated_hours = 0.0
    sessions: list[RawSession] = []

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue

        match = LINE_RE.match(line)
        if not match:
            continue

        event = match.group("kind")
        day = match.group("date").replace("/", "-")
        time = match.group("time")
        text = (match.group("label") or "").strip()

        if event == "i":
            current_project = text
            current_start_day = day
            current_start_time = time
            continue

        if event in ("o", "O") and current_start_day and current_start_time:
            start = datetime.strptime(
                f"{current_start_day} {current_start_time}", "%Y-%m-%d %H:%M:%S"
            )
            end = datetime.strptime(f"{day} {time}", "%Y-%m-%d %H:%M:%S")
            diff_hours = max((end - start).total_seconds() / 3600.0, 0.0)
            accumulated_hours += diff_hours

            if "---BREAK---" in text:
                current_start_time = None
                continue

            if accumulated_hours > 0.0:
                sessions.append(
                    RawSession(
                        day=current_start_day,
                        project=current_project,
                        description=text,
                        hours=accumulated_hours,
                        start_time=current_start_time,
                        end_time=time,
                    )
                )

            accumulated_hours = 0.0
            current_start_time = None

    if accumulated_hours > 0.0 and current_start_day and current_start_time:
        sessions.append(
            RawSession(
                day=current_start_day,
                project=current_project,
                description="Ongoing session",
                hours=accumulated_hours,
                start_time=current_start_time,
                end_time=datetime.now(UTC).strftime("%H:%M:%S"),
            )
        )

    return sessions


def prepare_report_sessions(sessions: list[RawSession]) -> list[Session]:
    prepared: list[Session] = []
    for item in sessions:
        desc = item.description.strip() if item.description else ""
        if not desc:
            desc = "Uncategorized"

        if (
            prepared
            and prepared[-1].day == item.day
            and prepared[-1].project == item.project
            and prepared[-1].description == desc
        ):
            prepared[-1].hours += item.hours
        else:
            prepared.append(
                Session(
                    day=item.day,
                    project=item.project,
                    description=desc,
                    hours=item.hours,
                )
            )
    return prepared


def round_hours_custom(hours: float, resolution: float, round_up: bool) -> float:
    if resolution <= 0:
        return hours
    steps = hours / resolution
    rounded_steps = math.ceil(steps) if round_up else round(steps)
    return rounded_steps * resolution


def load_project_rounding(path: Path) -> dict[str, tuple[float, bool]]:
    if not path.exists():
        return {}

    text = path.read_text(encoding="utf-8")
    entry_re = re.compile(
        r'"\w+"\s+:export-code\s+"(?P<export>[^"]+)"\s+:rounding\s+(?P<rounding>[0-9.]+)\s+:round-up\s+(?P<round_up>nil|t)'
    )

    mapping: dict[str, tuple[float, bool]] = {}
    for match in entry_re.finditer(text):
        project = match.group("export").strip()
        rounding = float(match.group("rounding"))
        round_up = match.group("round_up") == "t"
        mapping[project] = (rounding, round_up)
    return mapping


def apply_time_carry(
    sessions: list[Session], project_rounding: dict[str, tuple[float, bool]]
) -> tuple[list[Session], float]:
    carry = 0.0
    rounded: list[Session] = []
    for session in sessions:
        resolution, round_up = project_rounding.get(session.project, (0.5, False))
        exact_hours = session.hours + carry
        rounded_hours = round_hours_custom(exact_hours, resolution, round_up)
        carry = exact_hours - rounded_hours
        rounded.append(
            Session(
                day=session.day,
                project=session.project,
                description=session.description,
                hours=rounded_hours,
            )
        )
    return rounded, carry


def period_bounds(period: str, now: date) -> tuple[date, date]:
    if period == "daily":
        target = now - timedelta(days=1)
        return target, target
    if period == "weekly":
        current_week_monday = now - timedelta(days=now.weekday())
        start = current_week_monday - timedelta(days=7)
        end = start + timedelta(days=6)
        return start, end
    if period == "monthly":
        first_this_month = now.replace(day=1)
        last_prev_month = first_this_month - timedelta(days=1)
        start_prev_month = last_prev_month.replace(day=1)
        return start_prev_month, last_prev_month
    raise ValueError(f"Unsupported period: {period}")


def csv_escape(value: str) -> str:
    return value.replace('"', '""')


def build_csv(sessions: list[Session], start: date, end: date) -> str:
    lines = ['Project,Description,Date,Duration']
    for session in sessions:
        session_day = datetime.strptime(session.day, "%Y-%m-%d").date()
        if start <= session_day <= end:
            lines.append(
                f'"{csv_escape(session.project)}","{csv_escape(session.description)}","{session.day}","{session.hours:.2f}"'
            )
    return "\n".join(lines) + "\n"


def parse_iso_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def output_path(period: str) -> Path:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    return EXPORT_DIR / f"time_work_{period}.csv"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export timeclock sessions to CSV (daily/weekly/monthly)."
    )
    parser.add_argument(
        "--period",
        choices=["daily", "weekly", "monthly"],
        required=True,
        help="Export period.",
    )
    parser.add_argument(
        "--start-date",
        type=parse_iso_date,
        help="Optional custom start date (YYYY-MM-DD), inclusive.",
    )
    parser.add_argument(
        "--end-date",
        type=parse_iso_date,
        help="Optional custom end date (YYYY-MM-DD), inclusive.",
    )
    args = parser.parse_args()

    if args.start_date and args.end_date:
        start_date = args.start_date
        end_date = args.end_date
    elif args.start_date or args.end_date:
        raise SystemExit("Both --start-date and --end-date must be provided together.")
    else:
        start_date, end_date = period_bounds(args.period, date.today())

    raw_sessions = parse_timelog(WORK_LOG_PATH)
    merged_sessions = prepare_report_sessions(raw_sessions)
    project_rounding = load_project_rounding(PROJECTS_PATH)
    rounded_sessions, _carry = apply_time_carry(merged_sessions, project_rounding)
    csv_content = build_csv(rounded_sessions, start_date, end_date).replace(".", ",")

    out = output_path(args.period)
    out.write_text(csv_content, encoding="utf-8")
    print(f"✅ CSV Exported: {out}")


if __name__ == "__main__":
    main()

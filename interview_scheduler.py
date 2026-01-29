#!/usr/bin/env python3
"""Interview Scheduling Helper — local CLI tool for Outlook users.

Generates proposed time slots, email drafts, and .ics calendar invites
for interview scheduling. No external APIs or ATS required.
"""

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone, date
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OUTPUT_DIR = Path("output")
HISTORY_FILE = Path("schedule_history.json")
DATETIME_FMT = "%Y%m%dT%H%M%SZ"
DISPLAY_FMT = "%A, %B %d, %Y %I:%M %p"

# ---------------------------------------------------------------------------
# ICS generation
# ---------------------------------------------------------------------------


def _ics_event(
    summary: str,
    start_utc: datetime,
    end_utc: datetime,
    location: str,
    description: str,
    organizer_email: str,
    attendees: list[str],
) -> str:
    uid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).strftime(DATETIME_FMT)
    attendee_lines = "\n".join(
        f"ATTENDEE;RSVP=TRUE;CN={email}:mailto:{email}" for email in attendees
    )
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//InterviewScheduler//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:REQUEST",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{now}",
        f"DTSTART:{start_utc.strftime(DATETIME_FMT)}",
        f"DTEND:{end_utc.strftime(DATETIME_FMT)}",
        f"SUMMARY:{summary}",
        f"LOCATION:{location}",
        f"DESCRIPTION:{description}",
        f"ORGANIZER;CN=Recruiter:mailto:{organizer_email}",
    ]
    for email in attendees:
        lines.append(f"ATTENDEE;RSVP=TRUE;CN={email}:mailto:{email}")
    lines += [
        "STATUS:CONFIRMED",
        "SEQUENCE:0",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return "\r\n".join(lines)


def save_ics(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Slot proposal logic
# ---------------------------------------------------------------------------

# Timezone offsets (hours from UTC) for common zones. Extend as needed.
TZ_OFFSETS = {
    "US/Eastern": -5,
    "US/Central": -6,
    "US/Mountain": -7,
    "US/Pacific": -8,
    "UTC": 0,
    "Europe/London": 0,
    "Europe/Berlin": 1,
    "Asia/Kolkata": 5.5,
    "Asia/Tokyo": 9,
    "Australia/Sydney": 11,
}


def _utc_offset_hours(tz_name: str) -> float:
    return TZ_OFFSETS.get(tz_name, 0)


def propose_slots(
    start_date: date,
    end_date: date,
    work_start_hour: int,
    work_end_hour: int,
    duration_min: int,
    buffer_min: int,
    candidate_tz: str,
    count: int = 3,
) -> list[dict]:
    """Return *count* proposed interview slots spread across days/times.

    All returned datetimes are UTC.  The algorithm picks morning, midday, and
    late-afternoon windows across the available date range.
    """
    offset = _utc_offset_hours(candidate_tz)
    total_block = duration_min + buffer_min

    # Build candidate local hours for variety: morning, midday, late
    target_local_hours = [
        work_start_hour + 1,                            # morning
        (work_start_hour + work_end_hour) // 2,         # midday
        work_end_hour - (total_block // 60) - 1,        # late
    ]

    available_days: list[date] = []
    d = start_date
    while d <= end_date:
        if d.weekday() < 5:  # Mon-Fri
            available_days.append(d)
        d += timedelta(days=1)

    if not available_days:
        raise ValueError("No weekdays in the provided date range.")

    slots: list[dict] = []
    day_idx = 0
    hour_idx = 0
    while len(slots) < count and day_idx < len(available_days):
        local_hour = target_local_hours[hour_idx % len(target_local_hours)]
        # Clamp to working hours
        end_hour_needed = local_hour + total_block / 60
        if local_hour < work_start_hour or end_hour_needed > work_end_hour:
            hour_idx += 1
            day_idx += 1
            continue

        day = available_days[day_idx]
        local_start = datetime(day.year, day.month, day.day, local_hour, 0)
        utc_start = local_start - timedelta(hours=offset)
        utc_end = utc_start + timedelta(minutes=duration_min)

        slots.append(
            {
                "option": len(slots) + 1,
                "start_utc": utc_start,
                "end_utc": utc_end,
                "start_local": local_start,
                "end_local": local_start + timedelta(minutes=duration_min),
                "candidate_tz": candidate_tz,
            }
        )
        hour_idx += 1
        day_idx += 1

    if not slots:
        raise ValueError("Could not generate any slots within the given constraints.")
    return slots


# ---------------------------------------------------------------------------
# Email drafts
# ---------------------------------------------------------------------------


def candidate_email_draft(
    candidate_name: str,
    role: str,
    interview_type: str,
    slots: list[dict],
    location: str,
    candidate_tz: str,
) -> str:
    options = "\n".join(
        f"  Option {s['option']}: {s['start_local'].strftime(DISPLAY_FMT)} – "
        f"{s['end_local'].strftime('%-I:%M %p')} ({candidate_tz})"
        for s in slots
    )
    return (
        f"Subject: Interview Scheduling — {role}\n"
        f"\n"
        f"Hi {candidate_name},\n"
        f"\n"
        f"Thank you for your interest in the {role} position. We would like to\n"
        f"schedule a {interview_type} interview with you.\n"
        f"\n"
        f"Please let us know which of the following times works best for you:\n"
        f"\n"
        f"{options}\n"
        f"\n"
        f"Location / Link: {location}\n"
        f"\n"
        f"Please reply with your preferred option number at your earliest\n"
        f"convenience. If none of these times work, let us know your availability\n"
        f"and we will do our best to accommodate.\n"
        f"\n"
        f"Best regards,\n"
        f"Recruiting Team"
    )


def internal_email_draft(
    candidate_name: str,
    role: str,
    interview_type: str,
    panelists: list[dict],
    slots: list[dict],
    location: str,
) -> str:
    panel_list = ", ".join(p["name"] for p in panelists)
    options = "\n".join(
        f"  Option {s['option']}: {s['start_utc'].strftime(DISPLAY_FMT)} UTC"
        for s in slots
    )
    return (
        f"Subject: [Internal] Interview Panel Confirmation — {candidate_name} for {role}\n"
        f"\n"
        f"Hi Team,\n"
        f"\n"
        f"We are scheduling a {interview_type} interview for {candidate_name}\n"
        f"(applying for {role}).\n"
        f"\n"
        f"Panel: {panel_list}\n"
        f"\n"
        f"Proposed times (UTC):\n"
        f"{options}\n"
        f"\n"
        f"Location / Link: {location}\n"
        f"\n"
        f"Please confirm your availability for the above slots. Calendar invites\n"
        f"will follow once the candidate confirms.\n"
        f"\n"
        f"Thanks,\n"
        f"Recruiting Team"
    )


# ---------------------------------------------------------------------------
# History log
# ---------------------------------------------------------------------------


def _load_history() -> list:
    if HISTORY_FILE.exists():
        return json.loads(HISTORY_FILE.read_text())
    return []


def _save_history(records: list) -> None:
    HISTORY_FILE.write_text(json.dumps(records, indent=2, default=str))


def log_schedule(entry: dict) -> None:
    history = _load_history()
    entry["logged_at"] = datetime.now(timezone.utc).isoformat()
    history.append(entry)
    _save_history(history)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def run_schedule(params: dict) -> None:
    """Main pipeline: propose slots, write emails, generate .ics files."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    slots = propose_slots(
        start_date=params["start_date"],
        end_date=params["end_date"],
        work_start_hour=params["work_start_hour"],
        work_end_hour=params["work_end_hour"],
        duration_min=params["duration_min"],
        buffer_min=params["buffer_min"],
        candidate_tz=params["candidate_tz"],
    )

    # --- Email drafts ---
    cand_email = candidate_email_draft(
        candidate_name=params["candidate_name"],
        role=params["role"],
        interview_type=params["interview_type"],
        slots=slots,
        location=params["location"],
        candidate_tz=params["candidate_tz"],
    )
    int_email = internal_email_draft(
        candidate_name=params["candidate_name"],
        role=params["role"],
        interview_type=params["interview_type"],
        panelists=params["panelists"],
        slots=slots,
        location=params["location"],
    )

    cand_path = OUTPUT_DIR / "candidate_email.txt"
    int_path = OUTPUT_DIR / "internal_email.txt"
    cand_path.write_text(cand_email)
    int_path.write_text(int_email)

    # --- .ics files ---
    all_attendees = [params["candidate_email"]] + [
        p["email"] for p in params["panelists"]
    ]
    organizer = params["panelists"][0]["email"] if params["panelists"] else "recruiter@example.com"
    summary = f"{params['interview_type'].title()} Interview — {params['candidate_name']} for {params['role']}"

    for s in slots:
        ics = _ics_event(
            summary=summary,
            start_utc=s["start_utc"],
            end_utc=s["end_utc"],
            location=params["location"],
            description=f"{params['interview_type'].title()} interview for {params['role']}",
            organizer_email=organizer,
            attendees=all_attendees,
        )
        ics_path = OUTPUT_DIR / f"option_{s['option']}.ics"
        save_ics(ics_path, ics)

    # --- Print results ---
    print("=" * 60)
    print("  INTERVIEW SCHEDULING HELPER")
    print("=" * 60)
    print(f"\nCandidate : {params['candidate_name']} ({params['candidate_email']})")
    print(f"Role      : {params['role']}")
    print(f"Type      : {params['interview_type']}")
    print(f"Duration  : {params['duration_min']} min + {params['buffer_min']} min buffer")
    print(f"Location  : {params['location']}")
    print()

    print("Proposed slots:")
    for s in slots:
        print(
            f"  Option {s['option']}: {s['start_local'].strftime(DISPLAY_FMT)} – "
            f"{s['end_local'].strftime('%-I:%M %p')} ({params['candidate_tz']})"
        )
    print()

    print(f"Candidate email draft → {cand_path}")
    print(f"Internal email draft  → {int_path}")
    for s in slots:
        opt = s['option']
        print(f"ICS Option {opt}          → {OUTPUT_DIR / f'option_{opt}.ics'}")
    print()

    # --- Log ---
    log_schedule(
        {
            "candidate_name": params["candidate_name"],
            "candidate_email": params["candidate_email"],
            "role": params["role"],
            "interview_type": params["interview_type"],
            "panelists": params["panelists"],
            "slots": [
                {
                    "option": s["option"],
                    "start_utc": s["start_utc"].isoformat(),
                    "end_utc": s["end_utc"].isoformat(),
                }
                for s in slots
            ],
        }
    )
    print(f"History log updated   → {HISTORY_FILE}")

    # --- Confirm a slot interactively ---
    if sys.stdin.isatty():
        print()
        choice = input(f"Confirm a slot (1-{len(slots)}) or press Enter to skip: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(slots):
            chosen = slots[int(choice) - 1]
            confirmed_ics = _ics_event(
                summary=f"[CONFIRMED] {summary}",
                start_utc=chosen["start_utc"],
                end_utc=chosen["end_utc"],
                location=params["location"],
                description=f"Confirmed {params['interview_type']} interview for {params['role']}",
                organizer_email=organizer,
                attendees=all_attendees,
            )
            confirmed_path = OUTPUT_DIR / "confirmed.ics"
            save_ics(confirmed_path, confirmed_ics)
            print(f"\nConfirmed slot {choice} → {confirmed_path}")


# ---------------------------------------------------------------------------
# Sample / hardcoded data (MVP)
# ---------------------------------------------------------------------------

SAMPLE_PARAMS = {
    "candidate_name": "Jane Doe",
    "candidate_email": "jane.doe@example.com",
    "candidate_tz": "US/Eastern",
    "role": "Senior Backend Engineer",
    "interview_type": "panel",
    "panelists": [
        {"name": "Alice Smith", "email": "alice.smith@company.com"},
        {"name": "Bob Johnson", "email": "bob.johnson@company.com"},
        {"name": "Carol Lee", "email": "carol.lee@company.com"},
    ],
    "start_date": date.today() + timedelta(days=1),
    "end_date": date.today() + timedelta(days=14),
    "work_start_hour": 9,
    "work_end_hour": 17,
    "duration_min": 60,
    "buffer_min": 15,
    "location": "Microsoft Teams — https://teams.microsoft.com/l/meetup-join/example",
}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def parse_panelists(s: str) -> list[dict]:
    """Parse 'Name <email>, Name <email>' format."""
    panelists = []
    for entry in s.split(","):
        entry = entry.strip()
        if "<" in entry and ">" in entry:
            name = entry[: entry.index("<")].strip()
            email = entry[entry.index("<") + 1 : entry.index(">")].strip()
        else:
            name = entry
            email = entry.replace(" ", ".").lower() + "@example.com"
        panelists.append({"name": name, "email": email})
    return panelists


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Interview Scheduling Helper — generate time options, email drafts, and .ics invites."
    )
    p.add_argument("--demo", action="store_true", help="Run with hardcoded sample data")
    p.add_argument("--candidate-name", help="Candidate full name")
    p.add_argument("--candidate-email", help="Candidate email address")
    p.add_argument("--candidate-tz", default="US/Eastern",
                   help="Candidate timezone (default: US/Eastern). Options: " + ", ".join(TZ_OFFSETS))
    p.add_argument("--role", help="Job role title")
    p.add_argument("--type", dest="interview_type", choices=["screen", "onsite", "panel"],
                   help="Interview type")
    p.add_argument("--panelists",
                   help='Comma-separated: "Alice Smith <alice@co.com>, Bob Jones <bob@co.com>"')
    p.add_argument("--start-date", type=parse_date, help="Start of date range (YYYY-MM-DD)")
    p.add_argument("--end-date", type=parse_date, help="End of date range (YYYY-MM-DD)")
    p.add_argument("--work-start", type=int, default=9, help="Work day start hour (default: 9)")
    p.add_argument("--work-end", type=int, default=17, help="Work day end hour (default: 17)")
    p.add_argument("--duration", type=int, default=60, help="Interview length in minutes (default: 60)")
    p.add_argument("--buffer", type=int, default=15, help="Buffer time in minutes (default: 15)")
    p.add_argument("--location", default="Microsoft Teams",
                   help="Location or meeting link text")
    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.demo:
        print("Running with sample data...\n")
        run_schedule(SAMPLE_PARAMS)
        return

    # Check required args for non-demo mode
    missing = []
    for field in ["candidate_name", "candidate_email", "role", "interview_type", "panelists", "start_date", "end_date"]:
        if getattr(args, field, None) is None:
            missing.append(f"--{field.replace('_', '-')}")
    if missing:
        print(f"Error: missing required arguments: {', '.join(missing)}")
        print("Use --demo for sample data or provide all required arguments.")
        print("Run with --help for usage details.")
        sys.exit(1)

    params = {
        "candidate_name": args.candidate_name,
        "candidate_email": args.candidate_email,
        "candidate_tz": args.candidate_tz,
        "role": args.role,
        "interview_type": args.interview_type,
        "panelists": parse_panelists(args.panelists),
        "start_date": args.start_date,
        "end_date": args.end_date,
        "work_start_hour": args.work_start,
        "work_end_hour": args.work_end,
        "duration_min": args.duration,
        "buffer_min": args.buffer,
        "location": args.location,
    }
    run_schedule(params)


if __name__ == "__main__":
    main()

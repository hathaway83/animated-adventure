#!/usr/bin/env python3
"""Interview Scheduling Helper — local CLI tool for Outlook users.

Generates proposed time slots, email drafts, and .ics calendar invites
for interview scheduling. No external APIs or ATS required.

Run with no arguments for an interactive guided walkthrough.
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

INTERVIEW_TYPES = {
    "1": "screen",
    "2": "onsite",
    "3": "panel",
    "screen": "screen",
    "onsite": "onsite",
    "panel": "panel",
}

TZ_CHOICES = {
    "1": ("US/Eastern", "EST, UTC-5"),
    "2": ("US/Central", "CST, UTC-6"),
    "3": ("US/Mountain", "MST, UTC-7"),
    "4": ("US/Pacific", "PST, UTC-8"),
    "5": ("UTC", "UTC"),
    "6": ("Europe/London", "GMT, UTC+0"),
    "7": ("Europe/Berlin", "CET, UTC+1"),
    "8": ("Asia/Kolkata", "IST, UTC+5:30"),
    "9": ("Asia/Tokyo", "JST, UTC+9"),
    "10": ("Australia/Sydney", "AEDT, UTC+11"),
}

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hr():
    print("-" * 60)


def _banner(text):
    print()
    print("=" * 60)
    print(f"  {text}")
    print("=" * 60)


def _ask(prompt, default=None, required=True):
    """Prompt the user with optional default. Loops until a value is given."""
    suffix = f" [{default}]" if default else ""
    while True:
        val = input(f"  {prompt}{suffix}: ").strip()
        if not val and default:
            return default
        if val:
            return val
        if not required:
            return ""
        print("    ^ This field is required. Please enter a value.")


def _ask_choice(prompt, options_dict, default=None):
    """Prompt user to pick from numbered options."""
    suffix = f" [{default}]" if default else ""
    while True:
        val = input(f"  {prompt}{suffix}: ").strip()
        if not val and default:
            val = default
        if val in options_dict:
            return options_dict[val]
        print(f"    ^ Please enter one of: {', '.join(options_dict.keys())}")


def _ask_date(prompt, default=None):
    """Prompt for a date in YYYY-MM-DD format."""
    suffix = f" [{default}]" if default else ""
    while True:
        val = input(f"  {prompt}{suffix}: ").strip()
        if not val and default:
            val = default
        try:
            return datetime.strptime(val, "%Y-%m-%d").date()
        except ValueError:
            print("    ^ Please enter a date in YYYY-MM-DD format (e.g. 2026-02-10)")


def _ask_int(prompt, default=None):
    suffix = f" [{default}]" if default else ""
    while True:
        val = input(f"  {prompt}{suffix}: ").strip()
        if not val and default is not None:
            return default
        try:
            return int(val)
        except ValueError:
            print("    ^ Please enter a number.")


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


def _utc_offset_hours(tz_name: str) -> float:
    return TZ_OFFSETS.get(tz_name, 0)


DAY_NAMES = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


def parse_busy_times(text: str, date_range_start: date, date_range_end: date) -> list[tuple[datetime, datetime]]:
    """Parse busy time strings into (start, end) datetime pairs.

    Supported formats:
      "Mon 9-11"            — every Monday from 9:00-11:00 in the date range
      "Mon 9:30-11:30"      — supports half-hour times
      "2026-02-03 9-11"     — specific date from 9:00-11:00
      "2026-02-03 9:00-11:00" — specific date with minutes

    Multiple entries separated by commas:
      "Mon 9-11, Wed 14-16, 2026-02-05 10-12"
    """
    blocks: list[tuple[datetime, datetime]] = []
    if not text.strip():
        return blocks

    for entry in text.split(","):
        entry = entry.strip()
        if not entry:
            continue

        parts = entry.split()
        if len(parts) != 2:
            continue

        day_part, time_part = parts[0].strip(), parts[1].strip()

        # Parse the time range
        if "-" not in time_part:
            continue
        start_str, end_str = time_part.split("-", 1)

        def _parse_hour(s):
            s = s.strip()
            if ":" in s:
                h, m = s.split(":")
                return int(h) + int(m) / 60
            return int(s)

        try:
            start_h = _parse_hour(start_str)
            end_h = _parse_hour(end_str)
        except ValueError:
            continue

        # Determine which dates this applies to
        target_dates: list[date] = []
        day_lower = day_part.lower()[:3]

        if day_lower in DAY_NAMES:
            # Recurring weekday — find all matching days in range
            target_weekday = DAY_NAMES[day_lower]
            d = date_range_start
            while d <= date_range_end:
                if d.weekday() == target_weekday:
                    target_dates.append(d)
                d += timedelta(days=1)
        else:
            # Try parsing as a specific date
            try:
                specific = datetime.strptime(day_part, "%Y-%m-%d").date()
                if date_range_start <= specific <= date_range_end:
                    target_dates.append(specific)
            except ValueError:
                continue

        for td in target_dates:
            start_mins = int(start_h * 60)
            end_mins = int(end_h * 60)
            block_start = datetime(td.year, td.month, td.day, start_mins // 60, start_mins % 60)
            block_end = datetime(td.year, td.month, td.day, end_mins // 60, end_mins % 60)
            blocks.append((block_start, block_end))

    return blocks


def _slot_conflicts(start: datetime, end: datetime, busy: list[tuple[datetime, datetime]]) -> bool:
    """Check if a proposed slot overlaps any busy block."""
    for busy_start, busy_end in busy:
        if start < busy_end and end > busy_start:
            return True
    return False


def propose_slots(
    start_date: date,
    end_date: date,
    work_start_hour: int,
    work_end_hour: int,
    duration_min: int,
    buffer_min: int,
    candidate_tz: str,
    busy_times: list[tuple[datetime, datetime]] | None = None,
    count: int = 3,
) -> list[dict]:
    """Return *count* proposed interview slots spread across days/times.

    Generates candidate slots at every half-hour across the date range,
    filters out busy-time conflicts, then picks a spread of morning /
    midday / late-afternoon options on different days.
    """
    offset = _utc_offset_hours(candidate_tz)
    total_block = duration_min + buffer_min
    if busy_times is None:
        busy_times = []

    # Build every possible half-hour slot in the range
    available_days: list[date] = []
    d = start_date
    while d <= end_date:
        if d.weekday() < 5:  # Mon-Fri
            available_days.append(d)
        d += timedelta(days=1)

    if not available_days:
        raise ValueError("No weekdays in the provided date range.")

    # Categorize slots by time-of-day for variety
    morning: list[dict] = []     # work_start .. work_start+3
    midday: list[dict] = []      # middle of day
    afternoon: list[dict] = []   # last 3 hours

    mid_boundary = work_start_hour + (work_end_hour - work_start_hour) // 3
    late_boundary = work_end_hour - (work_end_hour - work_start_hour) // 3

    for day in available_days:
        hour = work_start_hour
        while hour + total_block / 60 <= work_end_hour:
            local_start = datetime(day.year, day.month, day.day, int(hour), int((hour % 1) * 60))
            local_end = local_start + timedelta(minutes=duration_min)
            local_end_with_buffer = local_start + timedelta(minutes=total_block)

            # Check busy conflicts (in local/candidate time)
            if not _slot_conflicts(local_start, local_end_with_buffer, busy_times):
                utc_start = local_start - timedelta(hours=offset)
                utc_end = utc_start + timedelta(minutes=duration_min)
                slot = {
                    "start_utc": utc_start,
                    "end_utc": utc_end,
                    "start_local": local_start,
                    "end_local": local_end,
                    "candidate_tz": candidate_tz,
                }
                if hour < mid_boundary:
                    morning.append(slot)
                elif hour < late_boundary:
                    midday.append(slot)
                else:
                    afternoon.append(slot)

            hour += 0.5  # 30-minute increments

    # Pick slots spread across buckets and different days
    slots: list[dict] = []
    used_days: set[date] = set()
    buckets = [morning, midday, afternoon]

    for bucket in buckets:
        if len(slots) >= count:
            break
        for candidate_slot in bucket:
            slot_date = candidate_slot["start_local"].date()
            if slot_date not in used_days:
                candidate_slot["option"] = len(slots) + 1
                slots.append(candidate_slot)
                used_days.add(slot_date)
                break

    # If we still need more, fill from any bucket on unused days
    if len(slots) < count:
        all_slots = morning + midday + afternoon
        for candidate_slot in all_slots:
            if len(slots) >= count:
                break
            slot_date = candidate_slot["start_local"].date()
            if slot_date not in used_days:
                candidate_slot["option"] = len(slots) + 1
                slots.append(candidate_slot)
                used_days.add(slot_date)

    # Last resort: allow same day
    if len(slots) < count:
        all_slots = morning + midday + afternoon
        for candidate_slot in all_slots:
            if len(slots) >= count:
                break
            if candidate_slot not in slots:
                candidate_slot["option"] = len(slots) + 1
                slots.append(candidate_slot)

    if not slots:
        raise ValueError(
            "Could not find any available slots. All times conflict with busy schedules.\n"
            "Try widening the date range, adjusting working hours, or reducing busy times."
        )
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
        f"  Option {s['option']}: {s['start_local'].strftime(DISPLAY_FMT)} - "
        f"{s['end_local'].strftime('%-I:%M %p')} ({candidate_tz})"
        for s in slots
    )
    return (
        f"Subject: Interview Scheduling - {role}\n"
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
        f"Subject: [Internal] Interview Panel Confirmation - {candidate_name} for {role}\n"
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


def reschedule_email_draft(
    candidate_name: str,
    role: str,
    new_slots: list[dict],
    location: str,
    candidate_tz: str,
) -> str:
    options = "\n".join(
        f"  Option {s['option']}: {s['start_local'].strftime(DISPLAY_FMT)} - "
        f"{s['end_local'].strftime('%-I:%M %p')} ({candidate_tz})"
        for s in new_slots
    )
    return (
        f"Subject: Updated Interview Times - {role}\n"
        f"\n"
        f"Hi {candidate_name},\n"
        f"\n"
        f"We need to adjust the interview schedule for the {role} position.\n"
        f"Apologies for any inconvenience.\n"
        f"\n"
        f"Here are the updated time options:\n"
        f"\n"
        f"{options}\n"
        f"\n"
        f"Location / Link: {location}\n"
        f"\n"
        f"Please reply with your preferred option or suggest an alternative.\n"
        f"\n"
        f"Best regards,\n"
        f"Recruiting Team"
    )


def cancellation_email_draft(candidate_name: str, role: str) -> str:
    return (
        f"Subject: Interview Update - {role}\n"
        f"\n"
        f"Hi {candidate_name},\n"
        f"\n"
        f"Thank you for your time and interest in the {role} position.\n"
        f"Unfortunately, we need to cancel the upcoming interview.\n"
        f"\n"
        f"We apologize for the inconvenience and will reach out if we would\n"
        f"like to reschedule in the future.\n"
        f"\n"
        f"Best regards,\n"
        f"Recruiting Team"
    )


def confirmation_email_draft(
    candidate_name: str,
    role: str,
    interview_type: str,
    slot: dict,
    location: str,
    candidate_tz: str,
    panelists: list[dict],
) -> str:
    time_str = (
        f"{slot['start_local'].strftime(DISPLAY_FMT)} - "
        f"{slot['end_local'].strftime('%-I:%M %p')} ({candidate_tz})"
    )
    panel_str = ", ".join(p["name"] for p in panelists)
    return (
        f"Subject: Interview Confirmed - {role}\n"
        f"\n"
        f"Hi {candidate_name},\n"
        f"\n"
        f"Your {interview_type} interview for the {role} position is confirmed:\n"
        f"\n"
        f"  Date/Time: {time_str}\n"
        f"  Location:  {location}\n"
        f"  Panel:     {panel_str}\n"
        f"\n"
        f"A calendar invite is attached. Please let us know if you have any\n"
        f"questions beforehand.\n"
        f"\n"
        f"Good luck!\n"
        f"\n"
        f"Best regards,\n"
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


def show_history() -> None:
    """Display past scheduled interviews."""
    history = _load_history()
    if not history:
        print("\n  No scheduling history found yet.")
        return

    _banner("SCHEDULING HISTORY")
    for i, record in enumerate(history, 1):
        status = record.get("status", "proposed")
        print(f"\n  #{i}  {record['candidate_name']} - {record['role']}")
        print(f"      Type: {record['interview_type']}  |  Status: {status}")
        print(f"      Logged: {record['logged_at'][:16].replace('T', ' ')} UTC")
        if record.get("panelists"):
            names = ", ".join(p["name"] for p in record["panelists"])
            print(f"      Panel: {names}")
        if record.get("slots"):
            for s in record["slots"]:
                start = s.get("start_utc", "?")
                if isinstance(start, str) and len(start) > 10:
                    start = start[:16].replace("T", " ")
                print(f"      Option {s['option']}: {start} UTC")
        if record.get("confirmed_option"):
            print(f"      >>> Confirmed: Option {record['confirmed_option']}")
    print()


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
        busy_times=params.get("busy_times", []),
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
    summary = f"{params['interview_type'].title()} Interview - {params['candidate_name']} for {params['role']}"

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

    # --- Print summary ---
    _banner("SCHEDULE CREATED")
    print(f"""
  Candidate : {params['candidate_name']} ({params['candidate_email']})
  Role      : {params['role']}
  Type      : {params['interview_type']}
  Duration  : {params['duration_min']} min + {params['buffer_min']} min buffer
  Location  : {params['location']}
  Panel     : {', '.join(p['name'] for p in params['panelists'])}
""")
    _hr()
    print("  PROPOSED TIME SLOTS")
    _hr()
    for s in slots:
        print(
            f"    Option {s['option']}:  {s['start_local'].strftime(DISPLAY_FMT)} - "
            f"{s['end_local'].strftime('%-I:%M %p')} ({params['candidate_tz']})"
        )
    print()
    _hr()
    print("  FILES SAVED")
    _hr()
    print(f"    Candidate email  : {cand_path}")
    print(f"    Internal email   : {int_path}")
    for s in slots:
        opt = s['option']
        print(f"    Calendar Option {opt}: {OUTPUT_DIR / f'option_{opt}.ics'}")
    print()

    # --- Log ---
    log_entry = {
        "candidate_name": params["candidate_name"],
        "candidate_email": params["candidate_email"],
        "role": params["role"],
        "interview_type": params["interview_type"],
        "panelists": params["panelists"],
        "status": "proposed",
        "slots": [
            {
                "option": s["option"],
                "start_utc": s["start_utc"].isoformat(),
                "end_utc": s["end_utc"].isoformat(),
            }
            for s in slots
        ],
    }

    # --- Confirm, reschedule, or cancel ---
    if sys.stdin.isatty():
        _hr()
        print("  NEXT STEPS")
        _hr()
        print("    1-3  Confirm a time slot (generates confirmation email + invite)")
        print("    r    Generate reschedule email")
        print("    c    Generate cancellation email")
        print("    Enter to finish")
        print()
        choice = input("  Your choice: ").strip().lower()

        if choice.isdigit() and 1 <= int(choice) <= len(slots):
            chosen = slots[int(choice) - 1]

            # Confirmation .ics
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

            # Confirmation email
            conf_email = confirmation_email_draft(
                candidate_name=params["candidate_name"],
                role=params["role"],
                interview_type=params["interview_type"],
                slot=chosen,
                location=params["location"],
                candidate_tz=params["candidate_tz"],
                panelists=params["panelists"],
            )
            conf_email_path = OUTPUT_DIR / "confirmation_email.txt"
            conf_email_path.write_text(conf_email)

            log_entry["status"] = "confirmed"
            log_entry["confirmed_option"] = int(choice)

            print()
            _hr()
            print(f"  CONFIRMED: Option {choice}")
            _hr()
            print(
                f"    {chosen['start_local'].strftime(DISPLAY_FMT)} - "
                f"{chosen['end_local'].strftime('%-I:%M %p')} ({params['candidate_tz']})"
            )
            print()
            print(f"    Confirmation email : {conf_email_path}")
            print(f"    Calendar invite    : {confirmed_path}")
            print()
            print("    Next: Open the .ics file to add to Outlook, then copy/paste")
            print("    the confirmation email to send to the candidate.")
            print()

        elif choice == "r":
            resched = reschedule_email_draft(
                candidate_name=params["candidate_name"],
                role=params["role"],
                new_slots=slots,
                location=params["location"],
                candidate_tz=params["candidate_tz"],
            )
            resched_path = OUTPUT_DIR / "reschedule_email.txt"
            resched_path.write_text(resched)
            log_entry["status"] = "rescheduling"
            print(f"\n  Reschedule email saved: {resched_path}\n")

        elif choice == "c":
            cancel = cancellation_email_draft(
                candidate_name=params["candidate_name"],
                role=params["role"],
            )
            cancel_path = OUTPUT_DIR / "cancellation_email.txt"
            cancel_path.write_text(cancel)
            log_entry["status"] = "cancelled"
            print(f"\n  Cancellation email saved: {cancel_path}\n")

    log_schedule(log_entry)
    print(f"  History log updated: {HISTORY_FILE}")
    print()


# ---------------------------------------------------------------------------
# Interactive guided mode
# ---------------------------------------------------------------------------


def interactive_mode() -> None:
    """Walk the user through scheduling step by step."""
    _banner("INTERVIEW SCHEDULING HELPER")
    print()
    print("  Let's schedule an interview! I'll walk you through it step by step.")
    print("  (Press Ctrl+C at any time to cancel.)")
    print()

    # --- Candidate info ---
    _hr()
    print("  STEP 1: CANDIDATE INFO")
    _hr()
    candidate_name = _ask("Candidate's full name")
    candidate_email = _ask("Candidate's email")

    print()
    print("  Candidate timezone:")
    for key, (tz_name, tz_desc) in TZ_CHOICES.items():
        print(f"    {key:>2}. {tz_name} ({tz_desc})")
    print()
    tz_result = _ask_choice("Pick a number or type timezone name", {
        **{k: v[0] for k, v in TZ_CHOICES.items()},
        **{v[0]: v[0] for v in TZ_CHOICES.values()},
    }, default="1")

    print()
    _hr()
    print("  STEP 2: ROLE & INTERVIEW TYPE")
    _hr()
    role = _ask("Job title / role")
    print()
    print("  Interview type:")
    print("    1. Phone screen")
    print("    2. Onsite")
    print("    3. Panel")
    print()
    interview_type = _ask_choice("Pick a number", INTERVIEW_TYPES, default="1")

    print()
    _hr()
    print("  STEP 3: INTERVIEW PANEL")
    _hr()
    print("  Enter interviewers one at a time. Leave name blank when done.")
    print()
    panelists = []
    while True:
        name = _ask(f"Interviewer {len(panelists)+1} name (blank to finish)", required=False)
        if not name:
            if not panelists:
                print("    You need at least one interviewer.")
                continue
            break
        email = _ask(f"  {name}'s email")
        panelists.append({"name": name, "email": email})
        print(f"    Added: {name} <{email}>")
    print(f"  Panel: {', '.join(p['name'] for p in panelists)}")

    print()
    _hr()
    print("  STEP 4: BUSY TIMES (optional)")
    _hr()
    print("  Enter times when interviewers are NOT available.")
    print("  This helps avoid scheduling conflicts.")
    print()
    print("  Format examples:")
    print('    Mon 9-11          (every Monday 9am-11am in the date range)')
    print('    Tue 14-16         (every Tuesday 2pm-4pm)')
    print('    2026-02-05 10-12  (specific date 10am-12pm)')
    print()
    print("  Separate multiple blocks with commas:")
    print('    Mon 9-11, Wed 14-16, Fri 9-10')
    print()
    print("  You can also paste output from a Gemini Gem or AI tool that reads")
    print("  calendar screenshots (see gemini_gem_instructions.md).")
    print()
    print("  Leave blank if you don't have this info yet (you can always")
    print("  re-run later with updated availability).")
    print()
    busy_text = _ask("Busy times to avoid (or blank to skip)", required=False)
    # Also check if they want to load from a file
    if not busy_text:
        busy_file = _ask("Or path to a busy-times file (or blank to skip)", required=False)
        if busy_file and Path(busy_file).exists():
            raw = Path(busy_file).read_text().strip()
            busy_text = raw.replace("\n", ", ").replace("\r", "")
            print(f"    Loaded: {busy_text[:80]}{'...' if len(busy_text) > 80 else ''}")

    print()
    _hr()
    print("  STEP 5: SCHEDULING CONSTRAINTS")
    _hr()
    today_str = date.today().strftime("%Y-%m-%d")
    next_week = (date.today() + timedelta(days=7)).strftime("%Y-%m-%d")
    two_weeks = (date.today() + timedelta(days=14)).strftime("%Y-%m-%d")

    print(f"  Today is {today_str}")
    start_date = _ask_date("Earliest date (YYYY-MM-DD)", default=next_week)
    end_date = _ask_date("Latest date (YYYY-MM-DD)", default=two_weeks)
    print()
    work_start = _ask_int("Work day starts at (hour, 24h format)", default=9)
    work_end = _ask_int("Work day ends at (hour, 24h format)", default=17)
    duration = _ask_int("Interview length in minutes", default=60)
    buffer_time = _ask_int("Buffer time after interview (minutes)", default=15)

    print()
    _hr()
    print("  STEP 6: LOCATION")
    _hr()
    location = _ask("Meeting location or video link", default="Microsoft Teams")

    # --- Confirm before generating ---
    print()
    _hr()
    print("  REVIEW")
    _hr()
    print(f"    Candidate  : {candidate_name} ({candidate_email})")
    print(f"    Timezone   : {tz_result}")
    print(f"    Role       : {role}")
    print(f"    Type       : {interview_type}")
    print(f"    Panel      : {', '.join(p['name'] for p in panelists)}")
    print(f"    Date range : {start_date} to {end_date}")
    print(f"    Hours      : {work_start}:00 - {work_end}:00")
    print(f"    Duration   : {duration} min + {buffer_time} min buffer")
    print(f"    Location   : {location}")
    if busy_text:
        print(f"    Busy times : {busy_text}")
    print()

    confirm = input("  Look good? (Y/n): ").strip().lower()
    if confirm == "n":
        print("\n  Cancelled. Run again to start over.\n")
        return

    # Parse busy times now that we have the date range
    busy_times = parse_busy_times(busy_text, start_date, end_date) if busy_text else []

    params = {
        "candidate_name": candidate_name,
        "candidate_email": candidate_email,
        "candidate_tz": tz_result,
        "role": role,
        "interview_type": interview_type,
        "panelists": panelists,
        "start_date": start_date,
        "end_date": end_date,
        "work_start_hour": work_start,
        "work_end_hour": work_end,
        "duration_min": duration,
        "buffer_min": buffer_time,
        "location": location,
        "busy_times": busy_times,
    }

    run_schedule(params)


# ---------------------------------------------------------------------------
# Sample data (for --demo)
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
    "location": "Microsoft Teams - https://teams.microsoft.com/l/meetup-join/example",
}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _collect_busy_times(busy_arg: str, busy_file_arg: str, start: date, end: date) -> list[tuple[datetime, datetime]]:
    """Merge busy times from --busy string and --busy-file."""
    parts = []
    if busy_arg:
        parts.append(busy_arg)
    if busy_file_arg:
        p = Path(busy_file_arg)
        if p.exists():
            # Read file, join lines with commas (supports one-per-line or comma-separated)
            raw = p.read_text().strip()
            # Normalize newlines to commas
            normalized = raw.replace("\n", ", ").replace("\r", "")
            parts.append(normalized)
        else:
            print(f"  Warning: busy file not found: {busy_file_arg}")
    combined = ", ".join(parts)
    return parse_busy_times(combined, start, end) if combined else []


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
        description="Interview Scheduling Helper - generate time options, email drafts, and .ics invites.",
        epilog="Run with no arguments for interactive guided mode.",
    )
    p.add_argument("--demo", action="store_true", help="Run with sample data to see how it works")
    p.add_argument("--history", action="store_true", help="View past scheduled interviews")
    p.add_argument("--candidate-name", help="Candidate full name")
    p.add_argument("--candidate-email", help="Candidate email address")
    p.add_argument("--candidate-tz", default="US/Eastern",
                   help="Candidate timezone (default: US/Eastern)")
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
    p.add_argument("--busy", default="",
                   help='Busy times to avoid: "Mon 9-11, Wed 14-16, 2026-02-05 10-12"')
    p.add_argument("--busy-file", default="",
                   help="Path to a text file with busy times (one per line or comma-separated)")
    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.history:
        show_history()
        return

    if args.demo:
        print("Running with sample data...\n")
        run_schedule(SAMPLE_PARAMS)
        return

    # If no CLI args provided, launch interactive mode
    has_args = any(
        getattr(args, f, None) is not None
        for f in ["candidate_name", "candidate_email", "role", "interview_type", "panelists", "start_date", "end_date"]
    )

    if not has_args:
        try:
            interactive_mode()
        except KeyboardInterrupt:
            print("\n\n  Cancelled.\n")
        return

    # CLI flag mode - check required args
    missing = []
    for field in ["candidate_name", "candidate_email", "role", "interview_type", "panelists", "start_date", "end_date"]:
        if getattr(args, field, None) is None:
            missing.append(f"--{field.replace('_', '-')}")
    if missing:
        print(f"Error: missing required arguments: {', '.join(missing)}")
        print("Use --demo for sample data, or just run with no arguments for guided mode.")
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
        "busy_times": _collect_busy_times(args.busy, args.busy_file, args.start_date, args.end_date),
    }
    run_schedule(params)


if __name__ == "__main__":
    main()

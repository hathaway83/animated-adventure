# Interview Scheduling Helper

A friendly Python CLI tool that helps recruiters and hiring coordinators
schedule interviews. Generates time proposals, ready-to-send email drafts,
and Outlook-compatible `.ics` calendar invites.

No external APIs, no ATS, no Microsoft Graph — just run it and go.

## Quick Start

```bash
# Interactive guided mode — just answer the prompts
python3 interview_scheduler.py

# See a demo with sample data
python3 interview_scheduler.py --demo

# View past schedules
python3 interview_scheduler.py --history
```

## What It Does

1. **Walks you through the details** — candidate info, role, panel members,
   date range, working hours, duration
2. **Proposes 3 time slots** spread across morning, midday, and late afternoon
   on different weekdays
3. **Generates email drafts** you can copy/paste:
   - Candidate email with time options
   - Internal panel confirmation email
   - Confirmation email (when you pick a slot)
   - Reschedule email (if plans change)
   - Cancellation email (if needed)
4. **Creates `.ics` calendar files** — double-click to add to Outlook
5. **Keeps a history log** of all schedules in `schedule_history.json`

## Three Ways to Use It

### 1. Interactive Mode (recommended)

Just run with no arguments — it walks you through everything:

```
$ python3 interview_scheduler.py

============================================================
  INTERVIEW SCHEDULING HELPER
============================================================

  Let's schedule an interview! I'll walk you through it step by step.
  (Press Ctrl+C at any time to cancel.)

------------------------------------------------------------
  STEP 1: CANDIDATE INFO
------------------------------------------------------------
  Candidate's full name: Jane Doe
  Candidate's email: jane@example.com
  ...
```

### 2. Demo Mode

See example output without typing anything:

```bash
python3 interview_scheduler.py --demo
```

### 3. Command-Line Flags

For power users or scripting:

```bash
python3 interview_scheduler.py \
  --candidate-name "Jane Doe" \
  --candidate-email "jane.doe@example.com" \
  --candidate-tz "US/Pacific" \
  --role "Senior Backend Engineer" \
  --type panel \
  --panelists "Alice Smith <alice@company.com>, Bob Jones <bob@company.com>" \
  --start-date 2026-02-02 \
  --end-date 2026-02-13 \
  --duration 60 \
  --buffer 15 \
  --location "Microsoft Teams — https://teams.microsoft.com/l/meetup-join/your-link"
```

## After Generating

Once the tool runs, you get a **Next Steps** menu:

```
------------------------------------------------------------
  NEXT STEPS
------------------------------------------------------------
    1-3  Confirm a time slot (generates confirmation email + invite)
    r    Generate reschedule email
    c    Generate cancellation email
    Enter to finish
```

- Pick `1`, `2`, or `3` to confirm a slot — generates a `confirmed.ics` and
  a confirmation email draft
- Pick `r` for a reschedule email template
- Pick `c` for a cancellation email template

## Output Files

All saved to `output/`:

| File | Description |
|---|---|
| `candidate_email.txt` | Email to send to the candidate with time options |
| `internal_email.txt` | Email to send to the interview panel |
| `confirmation_email.txt` | Email confirming the chosen slot |
| `reschedule_email.txt` | Email with updated times (if rescheduling) |
| `cancellation_email.txt` | Cancellation notice (if needed) |
| `option_1.ics` .. `option_3.ics` | Calendar invites for each proposed slot |
| `confirmed.ics` | Calendar invite for the confirmed slot |

## Viewing History

```bash
python3 interview_scheduler.py --history
```

Shows all past schedules with candidate, role, panel, times, and status
(proposed / confirmed / cancelled).

## Supported Timezones

US/Eastern, US/Central, US/Mountain, US/Pacific, UTC, Europe/London,
Europe/Berlin, Asia/Kolkata, Asia/Tokyo, Australia/Sydney

## Requirements

Python 3.10+ (standard library only — no pip install needed).

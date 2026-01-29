# Interview Scheduling Helper

A local Python CLI tool that generates interview time proposals, email drafts, and `.ics` calendar invites for Outlook. No external APIs, no ATS, no Microsoft Graph — just standard Python.

## Quick Start

```bash
# Run with sample data
python interview_scheduler.py --demo

# Run with your own data
python interview_scheduler.py \
  --candidate-name "Jane Doe" \
  --candidate-email "jane.doe@example.com" \
  --candidate-tz "US/Eastern" \
  --role "Senior Backend Engineer" \
  --type panel \
  --panelists "Alice Smith <alice@company.com>, Bob Jones <bob@company.com>" \
  --start-date 2026-02-02 \
  --end-date 2026-02-13 \
  --duration 60 \
  --buffer 15 \
  --location "Microsoft Teams — https://teams.microsoft.com/l/meetup-join/example"
```

## What It Does

Given candidate info, role, panel, and scheduling constraints, the tool:

1. **Proposes 3 time slots** spread across different days and times (morning / midday / late afternoon), within the working hours window and date range.
2. **Generates a candidate email draft** listing the options in the candidate's timezone.
3. **Generates an internal confirmation email draft** for the interview panel.
4. **Creates `.ics` files** (one per option) that import cleanly into Outlook.
5. **Optionally confirms a slot** interactively, producing a `confirmed.ics` file.
6. **Logs all schedules** to `schedule_history.json` for reference.

## CLI Arguments

| Argument | Required | Default | Description |
|---|---|---|---|
| `--demo` | — | — | Run with hardcoded sample data |
| `--candidate-name` | Yes | — | Full name |
| `--candidate-email` | Yes | — | Email address |
| `--candidate-tz` | No | `US/Eastern` | Timezone (see supported list below) |
| `--role` | Yes | — | Job title |
| `--type` | Yes | — | `screen`, `onsite`, or `panel` |
| `--panelists` | Yes | — | `"Name <email>, Name <email>"` |
| `--start-date` | Yes | — | `YYYY-MM-DD` |
| `--end-date` | Yes | — | `YYYY-MM-DD` |
| `--work-start` | No | `9` | Start of working day (hour) |
| `--work-end` | No | `17` | End of working day (hour) |
| `--duration` | No | `60` | Interview length (minutes) |
| `--buffer` | No | `15` | Buffer time after interview (minutes) |
| `--location` | No | `Microsoft Teams` | Location or meeting link |

### Supported Timezones

`US/Eastern`, `US/Central`, `US/Mountain`, `US/Pacific`, `UTC`, `Europe/London`, `Europe/Berlin`, `Asia/Kolkata`, `Asia/Tokyo`, `Australia/Sydney`

## Output Files

All outputs are saved to the `output/` directory:

- `candidate_email.txt` — draft email to send to the candidate
- `internal_email.txt` — draft email for the interview panel
- `option_1.ics`, `option_2.ics`, `option_3.ics` — calendar invites per slot
- `confirmed.ics` — created when you confirm a slot interactively

Schedule history is appended to `schedule_history.json` in the project root.

## Example Output

```
============================================================
  INTERVIEW SCHEDULING HELPER
============================================================

Candidate : Jane Doe (jane.doe@example.com)
Role      : Senior Backend Engineer
Type      : panel
Duration  : 60 min + 15 min buffer
Location  : Microsoft Teams — https://teams.microsoft.com/l/meetup-join/example

Proposed slots:
  Option 1: Monday, February 02, 2026 10:00 AM – 11:00 AM (US/Eastern)
  Option 2: Tuesday, February 03, 2026 01:00 PM – 02:00 PM (US/Eastern)
  Option 3: Wednesday, February 04, 2026 03:00 PM – 04:00 PM (US/Eastern)

Candidate email draft → output/candidate_email.txt
Internal email draft  → output/internal_email.txt
ICS Option 1          → output/option_1.ics
ICS Option 2          → output/option_2.ics
ICS Option 3          → output/option_3.ics

History log updated   → schedule_history.json

Confirm a slot (1-3) or press Enter to skip:
```

## Requirements

Python 3.10+ (uses only the standard library).

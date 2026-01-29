"""Generate .ics calendar files for interviews."""
from datetime import datetime
from icalendar import Calendar, Event, vCalAddress, vText
import pytz


def generate_ics(interview):
    """Return bytes of a .ics file for the given Interview model instance."""
    cal = Calendar()
    cal.add("prodid", "-//MiniATS//EN")
    cal.add("version", "2.0")
    cal.add("method", "REQUEST")

    event = Event()
    candidate = interview.candidate
    title = f"Interview: {candidate.full_name} for {candidate.role}"
    event.add("summary", title)

    tz = pytz.timezone(interview.timezone)
    event.add("dtstart", tz.localize(interview.dt_start))
    event.add("dtend", tz.localize(interview.dt_end))
    event.add("dtstamp", datetime.now(tz=pytz.utc))

    if interview.location:
        event.add("location", interview.location)

    description_parts = [
        f"Candidate: {candidate.full_name}",
        f"Role: {candidate.role}",
        f"Type: {interview.interview_type}",
    ]
    if interview.notes:
        description_parts.append(f"Notes: {interview.notes}")
    event.add("description", "\n".join(description_parts))

    # Add attendees
    if interview.attendees:
        for email in interview.attendees.split(","):
            email = email.strip()
            if email:
                attendee = vCalAddress(f"mailto:{email}")
                attendee.params["ROLE"] = vText("REQ-PARTICIPANT")
                event.add("attendee", attendee)

    cal.add_component(event)
    return cal.to_ical()

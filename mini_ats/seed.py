"""Seed the database with default stages, templates, and sample data."""
from datetime import date, datetime, timedelta
from mini_ats.models import db, Stage, Candidate, Note, Interview, EmailTemplate


def seed_stages():
    defaults = [
        ("Applied", 1),
        ("Recruiter Screen", 2),
        ("HM Screen", 3),
        ("Onsite", 4),
        ("Offer", 5),
        ("Hired", 6),
        ("Rejected", 7),
    ]
    for name, order in defaults:
        if not Stage.query.filter_by(name=name).first():
            db.session.add(Stage(name=name, display_order=order))
    db.session.commit()


def seed_templates():
    templates = [
        {
            "name": "Request Availability (Candidate)",
            "subject": "Interview Scheduling — {role} at Our Company",
            "body": (
                "Hi {candidate_name},\n\n"
                "Thank you for your interest in the {role} position. We'd love to schedule a conversation with you.\n\n"
                "Could you please share your availability for the following windows?\n\n"
                "{time_options}\n\n"
                "The interview will be held at {location_or_zoom}.\n\n"
                "Looking forward to hearing from you.\n\n"
                "Best,\n{scheduler_name}"
            ),
        },
        {
            "name": "Confirm Interview",
            "subject": "Interview Confirmed — {role}",
            "body": (
                "Hi {candidate_name},\n\n"
                "Your interview for the {role} position is confirmed:\n\n"
                "Date/Time: {time_options}\n"
                "Location: {location_or_zoom}\n\n"
                "Please let me know if anything changes.\n\n"
                "Best,\n{scheduler_name}"
            ),
        },
        {
            "name": "Reschedule Interview",
            "subject": "Reschedule Request — {role} Interview",
            "body": (
                "Hi {candidate_name},\n\n"
                "We need to reschedule your upcoming interview for the {role} position. "
                "Apologies for the inconvenience.\n\n"
                "Could any of these times work instead?\n\n"
                "{time_options}\n\n"
                "Thank you for your flexibility.\n\n"
                "Best,\n{scheduler_name}"
            ),
        },
        {
            "name": "Rejection (Polite)",
            "subject": "Update on Your Application — {role}",
            "body": (
                "Hi {candidate_name},\n\n"
                "Thank you so much for taking the time to interview for the {role} position. "
                "After careful consideration, we've decided to move forward with other candidates "
                "whose experience more closely aligns with our current needs.\n\n"
                "We truly appreciate your interest and wish you all the best in your job search.\n\n"
                "Warm regards,\n{scheduler_name}"
            ),
        },
        {
            "name": "Please Submit Feedback (Internal)",
            "subject": "Feedback Needed — {candidate_name} for {role}",
            "body": (
                "Hi team,\n\n"
                "A reminder to please submit your interview feedback for {candidate_name} "
                "({role}) at your earliest convenience.\n\n"
                "We'd like to make a decision soon, so feedback by end of day tomorrow "
                "would be greatly appreciated.\n\n"
                "Thanks,\n{scheduler_name}"
            ),
        },
    ]
    for t in templates:
        if not EmailTemplate.query.filter_by(name=t["name"]).first():
            db.session.add(EmailTemplate(**t))
    db.session.commit()


def seed_sample_candidates():
    """Add a few example candidates for demo purposes."""
    if Candidate.query.count() > 0:
        return

    applied = Stage.query.filter_by(name="Applied").first()
    screen = Stage.query.filter_by(name="Recruiter Screen").first()
    hm = Stage.query.filter_by(name="HM Screen").first()
    onsite = Stage.query.filter_by(name="Onsite").first()

    today = date.today()
    candidates = [
        Candidate(
            full_name="Alice Chen",
            email="alice.chen@example.com",
            phone="555-0101",
            role="Research Scientist",
            stage_id=hm.id,
            source="LinkedIn",
            hiring_manager="Dr. Sarah Park",
            recruiter="Jordan Lee",
            last_touch_date=today - timedelta(days=3),
            next_step="Schedule HM screen",
            next_step_due_date=today + timedelta(days=1),
            linkedin_url="https://linkedin.com/in/alicechen",
        ),
        Candidate(
            full_name="Bob Martinez",
            email="bob.martinez@example.com",
            role="Lab Technician",
            stage_id=applied.id,
            source="Indeed",
            hiring_manager="Dr. Raj Patel",
            recruiter="Jordan Lee",
            last_touch_date=today - timedelta(days=10),
            next_step="Initial review",
            next_step_due_date=today - timedelta(days=2),
        ),
        Candidate(
            full_name="Carol Nguyen",
            email="carol.nguyen@example.com",
            phone="555-0303",
            role="Research Scientist",
            stage_id=onsite.id,
            source="Referral",
            hiring_manager="Dr. Sarah Park",
            recruiter="Jordan Lee",
            last_touch_date=today - timedelta(days=1),
            next_step="Onsite panel",
            next_step_due_date=today + timedelta(days=5),
            linkedin_url="https://linkedin.com/in/carolnguyen",
            resume_url="https://example.com/resumes/carol.pdf",
        ),
        Candidate(
            full_name="David Kim",
            email="david.kim@example.com",
            role="QA Analyst",
            stage_id=screen.id,
            source="Company Website",
            hiring_manager="Lisa Wong",
            recruiter="Jordan Lee",
            last_touch_date=today - timedelta(days=8),
            next_step="Recruiter phone screen",
            next_step_due_date=today - timedelta(days=1),
        ),
    ]
    for c in candidates:
        db.session.add(c)
    db.session.commit()

    # Add sample notes
    alice = Candidate.query.filter_by(full_name="Alice Chen").first()
    db.session.add(Note(candidate_id=alice.id, content="Strong background in CRISPR. Published 3 papers.", created_at=datetime.utcnow() - timedelta(days=2)))
    db.session.add(Note(candidate_id=alice.id, content="Passed recruiter screen with flying colors. Moving to HM.", created_at=datetime.utcnow()))
    db.session.commit()


def seed_all():
    seed_stages()
    seed_templates()
    seed_sample_candidates()

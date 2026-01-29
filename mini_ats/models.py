from datetime import datetime, date
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Stage(db.Model):
    __tablename__ = "stages"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    display_order = db.Column(db.Integer, nullable=False, default=0)

    candidates = db.relationship("Candidate", backref="stage_rel", lazy=True)

    def __repr__(self):
        return f"<Stage {self.name}>"


class Candidate(db.Model):
    __tablename__ = "candidates"
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(50), nullable=True)
    role = db.Column(db.String(200), nullable=False)
    stage_id = db.Column(db.Integer, db.ForeignKey("stages.id"), nullable=False)
    source = db.Column(db.String(200), nullable=True)
    hiring_manager = db.Column(db.String(200), nullable=True)
    recruiter = db.Column(db.String(200), nullable=True)
    last_touch_date = db.Column(db.Date, nullable=True)
    next_step = db.Column(db.String(300), nullable=True)
    next_step_due_date = db.Column(db.Date, nullable=True)
    linkedin_url = db.Column(db.String(500), nullable=True)
    resume_url = db.Column(db.String(500), nullable=True)
    archived = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    notes = db.relationship("Note", backref="candidate", lazy=True, order_by="Note.created_at.desc()")
    interviews = db.relationship("Interview", backref="candidate", lazy=True, order_by="Interview.dt_start.desc()")

    @property
    def is_overdue(self):
        if self.next_step_due_date and self.next_step_due_date < date.today():
            return True
        return False

    @property
    def stale_days(self):
        """Return number of business days since last touch, or None."""
        if not self.last_touch_date:
            return None
        delta = date.today() - self.last_touch_date
        # rough business-day calc (exclude weekends)
        total = 0
        current = self.last_touch_date
        from datetime import timedelta
        while current < date.today():
            current += timedelta(days=1)
            if current.weekday() < 5:
                total += 1
        return total

    @property
    def is_stale(self):
        d = self.stale_days
        return d is not None and d >= 5


class Note(db.Model):
    __tablename__ = "notes"
    id = db.Column(db.Integer, primary_key=True)
    candidate_id = db.Column(db.Integer, db.ForeignKey("candidates.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Interview(db.Model):
    __tablename__ = "interviews"
    id = db.Column(db.Integer, primary_key=True)
    candidate_id = db.Column(db.Integer, db.ForeignKey("candidates.id"), nullable=False)
    interview_type = db.Column(db.String(100), nullable=False)
    dt_start = db.Column(db.DateTime, nullable=False)
    dt_end = db.Column(db.DateTime, nullable=False)
    timezone = db.Column(db.String(50), nullable=False, default="US/Pacific")
    attendees = db.Column(db.Text, nullable=True)  # comma-separated emails
    location = db.Column(db.String(500), nullable=True)
    notes = db.Column(db.Text, nullable=True)


class EmailTemplate(db.Model):
    __tablename__ = "email_templates"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, unique=True)
    subject = db.Column(db.String(500), nullable=False)
    body = db.Column(db.Text, nullable=False)

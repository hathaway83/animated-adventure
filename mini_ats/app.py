import csv
import io
from datetime import datetime, date, timedelta

from flask import (
    Flask, render_template, request, redirect, url_for, flash,
    Response, make_response,
)
from mini_ats.models import db, Stage, Candidate, Note, Interview, EmailTemplate
from mini_ats.ics_util import generate_ics


def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///mini_ats.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = "mini-ats-local-secret"
    db.init_app(app)

    with app.app_context():
        db.create_all()
        from mini_ats.seed import seed_all
        seed_all()

    # ── Dashboard ────────────────────────────────────────────────
    @app.route("/")
    def dashboard():
        stages = Stage.query.order_by(Stage.display_order).all()
        pipeline = []
        for s in stages:
            count = Candidate.query.filter_by(stage_id=s.id, archived=False).count()
            pipeline.append({"name": s.name, "count": count, "id": s.id})

        overdue = Candidate.query.filter(
            Candidate.archived == False,
            Candidate.next_step_due_date < date.today(),
        ).all()

        # stale: last_touch > 5 business days — fetch all active, filter in python
        active = Candidate.query.filter_by(archived=False).all()
        stale = [c for c in active if c.is_stale]

        return render_template("dashboard.html", pipeline=pipeline, overdue=overdue, stale=stale)

    # ── Candidate list ───────────────────────────────────────────
    @app.route("/candidates")
    def candidate_list():
        q = request.args.get("q", "").strip()
        stage_id = request.args.get("stage_id", "", type=str)
        role = request.args.get("role", "").strip()
        view = request.args.get("view", "")

        query = Candidate.query.filter_by(archived=False)

        if q:
            like = f"%{q}%"
            query = query.filter(
                db.or_(
                    Candidate.full_name.ilike(like),
                    Candidate.email.ilike(like),
                    Candidate.role.ilike(like),
                )
            )
        if stage_id:
            query = query.filter_by(stage_id=int(stage_id))
        if role:
            query = query.filter(Candidate.role.ilike(f"%{role}%"))
        if view == "overdue":
            query = query.filter(Candidate.next_step_due_date < date.today())
        if view == "stale":
            # fetch all, filter in python
            candidates = query.order_by(Candidate.updated_at.desc()).all()
            candidates = [c for c in candidates if c.is_stale]
        else:
            candidates = query.order_by(Candidate.updated_at.desc()).all()

        stages = Stage.query.order_by(Stage.display_order).all()
        roles = db.session.query(Candidate.role).distinct().all()
        roles = sorted(set(r[0] for r in roles))

        return render_template("candidate_list.html", candidates=candidates, stages=stages,
                               roles=roles, q=q, stage_id=stage_id, role=role, view=view)

    # ── CSV Export ───────────────────────────────────────────────
    @app.route("/candidates/export")
    def candidate_export():
        candidates = Candidate.query.filter_by(archived=False).order_by(Candidate.full_name).all()
        si = io.StringIO()
        w = csv.writer(si)
        w.writerow(["Name", "Email", "Phone", "Role", "Stage", "Source",
                     "Hiring Manager", "Recruiter", "Last Touch", "Next Step",
                     "Next Step Due", "LinkedIn", "Resume", "Created"])
        for c in candidates:
            w.writerow([
                c.full_name, c.email, c.phone or "", c.role,
                c.stage_rel.name, c.source or "", c.hiring_manager or "",
                c.recruiter or "", str(c.last_touch_date or ""),
                c.next_step or "", str(c.next_step_due_date or ""),
                c.linkedin_url or "", c.resume_url or "",
                str(c.created_at.date()) if c.created_at else "",
            ])
        output = make_response(si.getvalue())
        output.headers["Content-Disposition"] = "attachment; filename=candidates.csv"
        output.headers["Content-Type"] = "text/csv"
        return output

    # ── Create candidate ─────────────────────────────────────────
    @app.route("/candidates/new", methods=["GET", "POST"])
    def candidate_new():
        stages = Stage.query.order_by(Stage.display_order).all()
        if request.method == "POST":
            c = Candidate(
                full_name=request.form["full_name"],
                email=request.form["email"],
                phone=request.form.get("phone") or None,
                role=request.form["role"],
                stage_id=int(request.form["stage_id"]),
                source=request.form.get("source") or None,
                hiring_manager=request.form.get("hiring_manager") or None,
                recruiter=request.form.get("recruiter") or None,
                last_touch_date=_parse_date(request.form.get("last_touch_date")),
                next_step=request.form.get("next_step") or None,
                next_step_due_date=_parse_date(request.form.get("next_step_due_date")),
                linkedin_url=request.form.get("linkedin_url") or None,
                resume_url=request.form.get("resume_url") or None,
            )
            db.session.add(c)
            db.session.commit()
            flash(f"Candidate {c.full_name} created.", "success")
            return redirect(url_for("candidate_detail", id=c.id))
        return render_template("candidate_form.html", candidate=None, stages=stages)

    # ── Candidate detail ─────────────────────────────────────────
    @app.route("/candidates/<int:id>")
    def candidate_detail(id):
        c = Candidate.query.get_or_404(id)
        stages = Stage.query.order_by(Stage.display_order).all()
        templates = EmailTemplate.query.order_by(EmailTemplate.name).all()
        return render_template("candidate_detail.html", candidate=c, stages=stages, templates=templates)

    # ── Edit candidate ───────────────────────────────────────────
    @app.route("/candidates/<int:id>/edit", methods=["GET", "POST"])
    def candidate_edit(id):
        c = Candidate.query.get_or_404(id)
        stages = Stage.query.order_by(Stage.display_order).all()
        if request.method == "POST":
            c.full_name = request.form["full_name"]
            c.email = request.form["email"]
            c.phone = request.form.get("phone") or None
            c.role = request.form["role"]
            c.stage_id = int(request.form["stage_id"])
            c.source = request.form.get("source") or None
            c.hiring_manager = request.form.get("hiring_manager") or None
            c.recruiter = request.form.get("recruiter") or None
            c.last_touch_date = _parse_date(request.form.get("last_touch_date"))
            c.next_step = request.form.get("next_step") or None
            c.next_step_due_date = _parse_date(request.form.get("next_step_due_date"))
            c.linkedin_url = request.form.get("linkedin_url") or None
            c.resume_url = request.form.get("resume_url") or None
            db.session.commit()
            flash("Candidate updated.", "success")
            return redirect(url_for("candidate_detail", id=c.id))
        return render_template("candidate_form.html", candidate=c, stages=stages)

    # ── Archive candidate ────────────────────────────────────────
    @app.route("/candidates/<int:id>/archive", methods=["POST"])
    def candidate_archive(id):
        c = Candidate.query.get_or_404(id)
        c.archived = True
        db.session.commit()
        flash(f"{c.full_name} archived.", "info")
        return redirect(url_for("candidate_list"))

    # ── Notes ────────────────────────────────────────────────────
    @app.route("/candidates/<int:id>/notes", methods=["POST"])
    def add_note(id):
        c = Candidate.query.get_or_404(id)
        content = request.form.get("content", "").strip()
        if content:
            db.session.add(Note(candidate_id=c.id, content=content))
            c.last_touch_date = date.today()
            db.session.commit()
            flash("Note added.", "success")
        return redirect(url_for("candidate_detail", id=c.id))

    # ── Interviews ───────────────────────────────────────────────
    @app.route("/candidates/<int:id>/interviews/new", methods=["GET", "POST"])
    def interview_new(id):
        c = Candidate.query.get_or_404(id)
        if request.method == "POST":
            iv = Interview(
                candidate_id=c.id,
                interview_type=request.form["interview_type"],
                dt_start=datetime.fromisoformat(request.form["dt_start"]),
                dt_end=datetime.fromisoformat(request.form["dt_end"]),
                timezone=request.form.get("timezone", "US/Pacific"),
                attendees=request.form.get("attendees") or None,
                location=request.form.get("location") or None,
                notes=request.form.get("notes") or None,
            )
            db.session.add(iv)
            c.last_touch_date = date.today()
            db.session.commit()
            flash("Interview scheduled.", "success")
            return redirect(url_for("candidate_detail", id=c.id))
        return render_template("interview_form.html", candidate=c)

    @app.route("/interviews")
    def interview_list():
        interviews = (
            Interview.query
            .join(Candidate)
            .filter(Candidate.archived == False)
            .order_by(Interview.dt_start)
            .all()
        )
        return render_template("interview_list.html", interviews=interviews)

    @app.route("/interviews/<int:id>/ics")
    def interview_ics(id):
        iv = Interview.query.get_or_404(id)
        cal_bytes = generate_ics(iv)
        resp = make_response(cal_bytes)
        resp.headers["Content-Type"] = "text/calendar; charset=utf-8"
        resp.headers["Content-Disposition"] = f'attachment; filename="interview_{iv.id}.ics"'
        return resp

    # ── Templates / Draft Generation ─────────────────────────────
    @app.route("/templates")
    def template_list():
        templates = EmailTemplate.query.order_by(EmailTemplate.name).all()
        return render_template("template_list.html", templates=templates)

    @app.route("/candidates/<int:cid>/draft/<int:tid>")
    def generate_draft(cid, tid):
        c = Candidate.query.get_or_404(cid)
        t = EmailTemplate.query.get_or_404(tid)
        variables = {
            "candidate_name": c.full_name,
            "role": c.role,
            "time_options": "[Please fill in time options]",
            "location_or_zoom": "[Please fill in location or Zoom link]",
            "scheduler_name": c.recruiter or "[Your name]",
        }
        subject = t.subject
        body = t.body
        for k, v in variables.items():
            subject = subject.replace("{" + k + "}", v)
            body = body.replace("{" + k + "}", v)
        return render_template("draft.html", candidate=c, template=t,
                               subject=subject, body=body)

    # ── Reports ──────────────────────────────────────────────────
    @app.route("/reports")
    def reports():
        # Time-in-stage: average days active candidates have been in current stage
        # (approximated by updated_at — we don't log stage transitions)
        stages = Stage.query.order_by(Stage.display_order).all()
        stage_stats = []
        for s in stages:
            cands = Candidate.query.filter_by(stage_id=s.id, archived=False).all()
            if cands:
                avg_days = sum((date.today() - (c.last_touch_date or c.created_at.date())).days for c in cands) / len(cands)
            else:
                avg_days = 0
            stage_stats.append({"name": s.name, "count": len(cands), "avg_days": round(avg_days, 1)})

        # Stuck candidates: overdue + stale
        active = Candidate.query.filter_by(archived=False).all()
        stuck = [c for c in active if c.is_overdue or c.is_stale]

        # Pipeline-to-offer: candidates currently at Offer or Hired
        offer_stage = Stage.query.filter(Stage.name.in_(["Offer", "Hired"])).all()
        offer_ids = [s.id for s in offer_stage]
        offered = Candidate.query.filter(Candidate.stage_id.in_(offer_ids), Candidate.archived == False).all()
        offer_stats = []
        for c in offered:
            days = (date.today() - c.created_at.date()).days
            offer_stats.append({"name": c.full_name, "role": c.role, "days": days})

        return render_template("reports.html", stage_stats=stage_stats, stuck=stuck, offer_stats=offer_stats)

    @app.route("/reports/stuck/export")
    def stuck_export():
        active = Candidate.query.filter_by(archived=False).all()
        stuck = [c for c in active if c.is_overdue or c.is_stale]
        si = io.StringIO()
        w = csv.writer(si)
        w.writerow(["Name", "Role", "Stage", "Next Step", "Due Date", "Last Touch", "Stale Days", "Overdue"])
        for c in stuck:
            w.writerow([
                c.full_name, c.role, c.stage_rel.name, c.next_step or "",
                str(c.next_step_due_date or ""), str(c.last_touch_date or ""),
                c.stale_days or "", "Yes" if c.is_overdue else "No",
            ])
        output = make_response(si.getvalue())
        output.headers["Content-Disposition"] = "attachment; filename=stuck_candidates.csv"
        output.headers["Content-Type"] = "text/csv"
        return output

    return app


def _parse_date(val):
    if not val:
        return None
    try:
        return date.fromisoformat(val)
    except (ValueError, TypeError):
        return None

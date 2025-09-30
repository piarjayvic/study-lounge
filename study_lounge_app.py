# study_lounge_app.py
import os
import calendar
from datetime import datetime, date
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, abort
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "change-this-secret")  # set a real secret in production

# ---------- DATABASE CONFIG ----------
DATABASE_URL = os.getenv("DATABASE_URL", None)
if DATABASE_URL:
    db_url = DATABASE_URL
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    # ensure SSL (Railway/Postgres providers usually accept sslmode=require)
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"connect_args": {"sslmode": "require"}}
else:
    # local fallback to SQLite (easy testing)
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    db_file = os.path.join(BASE_DIR, "study_lounge.db")
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_file}"
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {}

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# ---------- MODELS ----------
class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    notes = db.Column(db.Text, nullable=True)
    # relationship
    assignments = db.relationship("Assignment", backref="student", cascade="all, delete-orphan", lazy=True)
    skills = db.relationship("StudentSkill", backref="student", cascade="all, delete-orphan", lazy=True)

class Assignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    due_date = db.Column(db.Date, nullable=False)
    is_test = db.Column(db.Boolean, default=False)
    completed = db.Column(db.Boolean, default=False)

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    event_date = db.Column(db.Date, nullable=False)

class StudentSkill(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    subject = db.Column(db.String(150), nullable=False)
    is_strength = db.Column(db.Boolean, default=True)  # True => strength, False => weakness

# create tables
with app.app_context():
    db.create_all()

# ---------- HELPERS ----------
def get_month_matrix(year, month):
    cal = calendar.Calendar(firstweekday=0)  # Monday first
    return cal.monthdayscalendar(year, month)

# ---------- ROUTES ----------
@app.route("/", methods=["GET", "POST"])
def home():
    """Choose Student or Staff (staff must enter code)."""
    error = None
    if request.method == "POST":
        role = request.form.get("role")
        if role == "student":
            session["role"] = "student"
            return redirect(url_for("dashboard"))
        elif role == "staff":
            code = request.form.get("code", "")
            staff_secret = os.getenv("STAFF_CODE", "1234")
            if code == staff_secret:
                session["role"] = "staff"
                return redirect(url_for("dashboard"))
            else:
                error = "Invalid staff code."
    return render_template("home.html", error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/dashboard")
def dashboard():
    """List students and global events. Staff can add/remove; students view-only."""
    if "role" not in session:
        return redirect(url_for("home"))
    role = session.get("role")
    students = Student.query.order_by(Student.name).all()
    events = Event.query.order_by(Event.event_date).all()
    return render_template("index.html", role=role, students=students, events=events)

# ---------- Student CRUD ----------
@app.route("/add_student", methods=["POST"])
def add_student():
    if session.get("role") != "staff":
        abort(403)
    name = request.form.get("name", "").strip()
    notes = request.form.get("notes", "").strip()
    if name:
        s = Student(name=name, notes=notes if notes else None)
        db.session.add(s)
        db.session.commit()
    return redirect(url_for("dashboard"))

@app.route("/delete_student/<int:student_id>", methods=["POST"])
def delete_student(student_id):
    if session.get("role") != "staff":
        abort(403)
    s = Student.query.get_or_404(student_id)
    db.session.delete(s)
    db.session.commit()
    return redirect(url_for("dashboard"))

# ---------- Assignment CRUD (per-student) ----------
@app.route("/student/<int:student_id>")
def student_page(student_id):
    if "role" not in session:
        return redirect(url_for("home"))
    student = Student.query.get_or_404(student_id)
    # month/year params
    try:
        month = int(request.args.get("month", datetime.today().month))
        year = int(request.args.get("year", datetime.today().year))
    except ValueError:
        month = datetime.today().month
        year = datetime.today().year

    # fetch assignments for that student within month
    first_day = date(year, month, 1)
    last_day_num = calendar.monthrange(year, month)[1]
    last_day = date(year, month, last_day_num)
    assignments = Assignment.query.filter(
        Assignment.student_id == student_id,
        Assignment.due_date >= first_day,
        Assignment.due_date <= last_day
    ).order_by(Assignment.due_date).all()

    assignments_by_date = {}
    for a in assignments:
        assignments_by_date.setdefault(a.due_date.isoformat(), []).append(a)

    month_matrix = get_month_matrix(year, month)
    months = [calendar.month_name[i] for i in range(1,13)]
    today_iso = datetime.today().date().isoformat()

    strengths = [sk for sk in student.skills if sk.is_strength]
    weaknesses = [sk for sk in student.skills if not sk.is_strength]

    return render_template(
        "student.html",
        student=student,
        month=month,
        year=year,
        months=months,
        month_matrix=month_matrix,
        assignments_by_date=assignments_by_date,
        today_iso=today_iso,
        strengths=strengths,
        weaknesses=weaknesses,
        role=session.get("role")
    )

@app.route("/student/<int:student_id>/add_assignment", methods=["POST"])
def add_assignment(student_id):
    if session.get("role") != "staff":
        abort(403)
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    due_date_str = request.form.get("due_date", "").strip()
    is_test = True if request.form.get("is_test") == "1" else False
    if not title or not due_date_str:
        return redirect(url_for("student_page", student_id=student_id))
    try:
        due = datetime.strptime(due_date_str, "%Y-%m-%d").date()
    except ValueError:
        return redirect(url_for("student_page", student_id=student_id))
    a = Assignment(student_id=student_id, title=title, description=description if description else None,
                   due_date=due, is_test=is_test)
    db.session.add(a)
    db.session.commit()
    return redirect(url_for("student_page", student_id=student_id, month=due.month, year=due.year))

@app.route("/student/<int:student_id>/delete_assignment/<int:assignment_id>", methods=["POST"])
def delete_assignment(student_id, assignment_id):
    if session.get("role") != "staff":
        abort(403)
    a = Assignment.query.get_or_404(assignment_id)
    db.session.delete(a)
    db.session.commit()
    return redirect(url_for("student_page", student_id=student_id))

@app.route("/toggle_complete/<int:assignment_id>", methods=["POST"])
def toggle_complete(assignment_id):
    a = Assignment.query.get_or_404(assignment_id)
    if session.get("role") not in ("staff", "student"):
        abort(403)
    a.completed = not a.completed
    db.session.commit()
    return jsonify({"ok": True, "completed": a.completed})

# ---------- Skills (strengths/weaknesses) ----------
@app.route("/student/<int:student_id>/add_skill", methods=["POST"])
def add_skill(student_id):
    if session.get("role") != "staff":
        abort(403)
    subject = request.form.get("subject", "").strip()
    level = request.form.get("level", "strength")
    if subject:
        sk = StudentSkill(student_id=student_id, subject=subject, is_strength=(level == "strength"))
        db.session.add(sk)
        db.session.commit()
    return redirect(url_for("student_page", student_id=student_id))

@app.route("/student/<int:student_id>/delete_skill/<int:skill_id>", methods=["POST"])
def delete_skill(student_id, skill_id):
    if session.get("role") != "staff":
        abort(403)
    sk = StudentSkill.query.get_or_404(skill_id)
    db.session.delete(sk)
    db.session.commit()
    return redirect(url_for("student_page", student_id=student_id))

# ---------- Global Events ----------
@app.route("/add_event", methods=["POST"])
def add_event():
    if session.get("role") != "staff":
        abort(403)
    title = request.form.get("title", "").strip()
    event_date_str = request.form.get("event_date", "").strip()
    if title and event_date_str:
        try:
            evd = datetime.strptime(event_date_str, "%Y-%m-%d").date()
        except ValueError:
            return redirect(url_for("dashboard"))
        ev = Event(title=title, event_date=evd)
        db.session.add(ev)
        db.session.commit()
    return redirect(url_for("dashboard"))

@app.route("/delete_event/<int:event_id>", methods=["POST"])
def delete_event(event_id):
    if session.get("role") != "staff":
        abort(403)
    ev = Event.query.get_or_404(event_id)
    db.session.delete(ev)
    db.session.commit()
    return redirect(url_for("dashboard"))

# ---------- Run ----------
if __name__ == "__main__":
    app.run(debug=True)

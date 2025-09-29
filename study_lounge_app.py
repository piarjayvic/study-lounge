import os
from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.secret_key = "super-secret-key"  # change for security

# Use SQLite (easiest + no SSL errors)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(BASE_DIR, "study_lounge.db")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# -------------------
# Database Models
# -------------------
class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)

class Assignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    due_date = db.Column(db.Date, nullable=False)

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event = db.Column(db.String(200), nullable=False)
    event_date = db.Column(db.Date, nullable=False)

with app.app_context():
    db.create_all()

# -------------------
# Routes
# -------------------
@app.route("/", methods=["GET", "POST"])
def home():
    """Login: Student or Staff"""
    error = None
    if request.method == "POST":
        role = request.form.get("role")
        if role == "student":
            session["role"] = "student"
            return redirect(url_for("dashboard"))
        elif role == "staff":
            code = request.form.get("code")
            if code == "admin123":  # change this staff password
                session["role"] = "staff"
                return redirect(url_for("dashboard"))
            else:
                error = "Invalid staff code!"
    return render_template("home.html", error=error)

@app.route("/dashboard")
def dashboard():
    """Main dashboard"""
    role = session.get("role")
    if not role:
        return redirect(url_for("home"))
    students = Student.query.all()
    assignments = Assignment.query.all()
    events = Event.query.all()
    return render_template("index.html", role=role,
                           students=students,
                           assignments=assignments,
                           events=events)

@app.route("/logout")
def logout():
    """Clear session and go home"""
    session.clear()
    return redirect(url_for("home"))

# -------------------
# Student Management
# -------------------
@app.route("/add_student", methods=["POST"])
def add_student():
    if session.get("role") != "staff":
        return redirect(url_for("dashboard"))
    name = request.form.get("name")
    if name:
        db.session.add(Student(name=name))
        db.session.commit()
    return redirect(url_for("dashboard"))

@app.route("/delete_student/<int:id>")
def delete_student(id):
    if session.get("role") != "staff":
        return redirect(url_for("dashboard"))
    student = Student.query.get_or_404(id)
    db.session.delete(student)
    db.session.commit()
    return redirect(url_for("dashboard"))

# -------------------
# Assignment Management
# -------------------
@app.route("/add_assignment", methods=["POST"])
def add_assignment():
    if session.get("role") != "staff":
        return redirect(url_for("dashboard"))
    title = request.form.get("title")
    due_date = request.form.get("due_date")
    if title and due_date:
        db.session.add(Assignment(title=title, due_date=datetime.strptime(due_date, "%Y-%m-%d")))
        db.session.commit()
    return redirect(url_for("dashboard"))

@app.route("/delete_assignment/<int:id>")
def delete_assignment(id):
    if session.get("role") != "staff":
        return redirect(url_for("dashboard"))
    assignment = Assignment.query.get_or_404(id)
    db.session.delete(assignment)
    db.session.commit()
    return redirect(url_for("dashboard"))

# -------------------
# Schedule Management
# -------------------
@app.route("/add_event", methods=["POST"])
def add_event():
    if session.get("role") != "staff":
        return redirect(url_for("dashboard"))
    event = request.form.get("event")
    event_date = request.form.get("event_date")
    if event and event_date:
        db.session.add(Event(event=event, event_date=datetime.strptime(event_date, "%Y-%m-%d")))
        db.session.commit()
    return redirect(url_for("dashboard"))

@app.route("/delete_event/<int:id>")
def delete_event(id):
    if session.get("role") != "staff":
        return redirect(url_for("dashboard"))
    event = Event.query.get_or_404(id)
    db.session.delete(event)
    db.session.commit()
    return redirect(url_for("dashboard"))

# -------------------
# Run
# -------------------
if __name__ == "__main__":
    app.run(debug=True)

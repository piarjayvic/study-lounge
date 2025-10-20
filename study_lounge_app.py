import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy

# ------------------- APP CONFIG -------------------
app = Flask(__name__)
app.secret_key = "super_secret_key"  # Change this for security

db_url = os.getenv("DATABASE_URL")
if not db_url:
    raise RuntimeError("DATABASE_URL not set")

# Render uses the old "postgres://" prefix — convert it:
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+psycopg://", 1)


app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"connect_args": {"sslmode": "require"}}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ------------------- DATABASE MODELS -------------------
class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    strengths = db.Column(db.String(500))
    weaknesses = db.Column(db.String(500))
    assignments = db.relationship("Assignment", backref="student", cascade="all, delete-orphan")

class Assignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    due_date = db.Column(db.String(20))
    completed = db.Column(db.Boolean, default=False)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)

# ------------------- ROUTES -------------------
@app.route("/", methods=["GET", "POST"])
def home():
    """Login / role selection"""
    if request.method == "POST":
        role = request.form.get("role")
        if role == "student":
            session["role"] = "student"
            return redirect(url_for("index"))
        elif role == "staff":
            code = request.form.get("code")
            if code == "admin123":  # <--- change this to your staff code
                session["role"] = "staff"
                return redirect(url_for("index"))
            else:
                return render_template("home.html", error="Invalid staff code.")
    return render_template("home.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/dashboard")
def index():
    """Main dashboard"""
    if "role" not in session:
        return redirect(url_for("home"))

    students = Student.query.all()
    assignments = Assignment.query.all()
    return render_template("index.html", students=students, assignments=assignments, role=session["role"])

@app.route("/student/<int:student_id>")
def student_detail(student_id):
    """Individual student view"""
    if "role" not in session:
        return redirect(url_for("home"))

    student = Student.query.get_or_404(student_id)
    return render_template("student_detail.html", student=student, role=session["role"])

@app.route("/calendar")
def calendar():
    """Calendar view"""
    if "role" not in session:
        return redirect(url_for("home"))

    assignments = Assignment.query.order_by(Assignment.due_date.asc()).all()
    return render_template("calendar.html", assignments=assignments, role=session["role"])

# ------------------- STAFF-ONLY ACTIONS -------------------
@app.route("/add_student", methods=["POST"])
def add_student():
    if session.get("role") != "staff":
        return redirect(url_for("index"))

    name = request.form["name"]
    strengths = request.form.get("strengths")
    weaknesses = request.form.get("weaknesses")
    new_student = Student(name=name, strengths=strengths, weaknesses=weaknesses)
    db.session.add(new_student)
    db.session.commit()
    return redirect(url_for("index"))

@app.route("/delete_student/<int:student_id>", methods=["POST"])
def delete_student(student_id):
    if session.get("role") != "staff":
        return redirect(url_for("index"))

    student = Student.query.get_or_404(student_id)
    db.session.delete(student)
    db.session.commit()
    return redirect(url_for("index"))

@app.route("/add_assignment/<int:student_id>", methods=["POST"])
def add_assignment(student_id):
    if session.get("role") != "staff":
        return redirect(url_for("student_detail", student_id=student_id))

    title = request.form["title"]
    due_date = request.form["due_date"]
    assignment = Assignment(title=title, due_date=due_date, student_id=student_id)
    db.session.add(assignment)
    db.session.commit()
    return redirect(url_for("student_detail", student_id=student_id))

@app.route("/delete_assignment/<int:assignment_id>", methods=["POST"])
def delete_assignment(assignment_id):
    if session.get("role") != "staff":
        return redirect(url_for("index"))

    assignment = Assignment.query.get_or_404(assignment_id)
    db.session.delete(assignment)
    db.session.commit()
    return redirect(url_for("index"))

# ------------------- INIT DB -------------------
with app.app_context():
    db.create_all()

# ------------------- RUN -------------------
if __name__ == "__main__":
    app.run(debug=True)

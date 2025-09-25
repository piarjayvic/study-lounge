from flask import Flask, render_template_string, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os

app = Flask(__name__)

db_url = os.getenv('DATABASE_URL')

if db_url is None:
  raise RuntimeError("DATABASE_URL not set")

# Force psycopg2 + SSL
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)

# Configure SQLAlchemy with SSL
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "connect_args": {
        "sslmode": "require"
    }
}
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)



# ----------------- MODELS -----------------
class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)

class Assignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    completed = db.Column(db.Boolean, default=False)

    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    student = db.relationship('Student', backref=db.backref('assignments', lazy=True))

# Create tables if they don't exist
with app.app_context():
    db.create_all()

# ----------------- ROUTES -----------------
@app.route("/")
def index():
    students = Student.query.all()
    return render_template_string("""
        <h1>Study Lounge</h1>
        <form method="POST" action="/add_student">
            <input type="text" name="name" placeholder="Student name" required>
            <button type="submit">Add Student</button>
        </form>
        <ul>
            {% for student in students %}
                <li><a href="{{ url_for('student_page', student_id=student.id) }}">{{ student.name }}</a></li>
            {% endfor %}
        </ul>
    """, students=students)

@app.route("/add_student", methods=["POST"])
def add_student():
    name = request.form["name"]
    student = Student(name=name)
    db.session.add(student)
    db.session.commit()
    return redirect(url_for("index"))

@app.route("/student/<int:student_id>")
def student_page(student_id):
    student = Student.query.get_or_404(student_id)
    return render_template_string("""
        <h1>{{ student.name }}'s Schedule</h1>
        <form method="POST" action="{{ url_for('add_assignment', student_id=student.id) }}">
            <input type="text" name="title" placeholder="Assignment title" required>
            <input type="date" name="due_date" required>
            <button type="submit">Add Assignment</button>
        </form>
        <ul>
            {% for a in student.assignments %}
                <li>
                    <form method="POST" action="{{ url_for('toggle_assignment', assignment_id=a.id) }}">
                        <input type="checkbox" name="completed" onchange="this.form.submit()" {% if a.completed %}checked{% endif %}>
                        {{ a.title }} (Due: {{ a.due_date.strftime('%Y-%m-%d') }})
                    </form>
                </li>
            {% endfor %}
        </ul>
        <a href="{{ url_for('index') }}">Back</a>
    """, student=student)

@app.route("/student/<int:student_id>/add_assignment", methods=["POST"])
def add_assignment(student_id):
    title = request.form["title"]
    due_date = datetime.strptime(request.form["due_date"], "%Y-%m-%d").date()
    assignment = Assignment(title=title, due_date=due_date, student_id=student_id)
    db.session.add(assignment)
    db.session.commit()
    return redirect(url_for("student_page", student_id=student_id))

@app.route("/assignment/<int:assignment_id>/toggle", methods=["POST"])
def toggle_assignment(assignment_id):
    assignment = Assignment.query.get_or_404(assignment_id)
    assignment.completed = not assignment.completed
    db.session.commit()
    return redirect(url_for("student_page", student_id=assignment.student_id))

# ----------------- MAIN -----------------
if __name__ == "__main__":
    app.run(debug=True)

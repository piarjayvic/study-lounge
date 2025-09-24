"""
Single-file Flask app for a Study Lounge student tracker.
Features:
- Add students
- Click a student to view a month calendar showing assignments/tests
- Add assignments or tests with due dates
- Checkbox to mark assignments as completed (AJAX)
- Stores data in a local SQLite database (study_lounge.db)

Run:
    pip install flask
    python study_lounge_app.py
Open http://127.0.0.1:5000

This file uses only the Python standard library + Flask.
"""
from flask import Flask, g, render_template_string, request, redirect, url_for, jsonify
import sqlite3
import os
import calendar
from datetime import datetime, date

DB_PATH = os.path.join(os.path.dirname(__file__), 'study_lounge.db')

app = Flask(__name__)
app.config['SECRET_KEY'] = 'change-this-in-production'

# ---------- Database helpers ----------

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    cursor = db.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        notes TEXT
    )
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS assignments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        due_date TEXT NOT NULL, -- stored as ISO YYYY-MM-DD
        is_test INTEGER DEFAULT 0,
        completed INTEGER DEFAULT 0,
        FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE
    )
    ''')
    db.commit()

# Initialize DB on first run
with app.app_context():
    init_db()

# ---------- Routes & logic ----------

INDEX_HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Study Lounge — Students</title>
  <style>
    body{font-family: Arial, Helvetica, sans-serif; max-width:900px;margin:20px auto;padding:0 16px}
    header{display:flex;justify-content:space-between;align-items:center}
    .student{padding:10px;border:1px solid #ddd;border-radius:6px;margin:8px 0;display:flex;justify-content:space-between}
    form.inline{display:flex;gap:8px}
    input[type=text]{padding:6px;border-radius:4px;border:1px solid #ccc}
    button{padding:6px 10px;border-radius:6px;border:0;background:#007bff;color:white}
    a.button{display:inline-block;padding:6px 10px;border-radius:6px;background:#28a745;color:white;text-decoration:none}
    .notes{font-size:0.9em;color:#555}
  </style>
</head>
<body>
  <header>
    <h1>Study Lounge</h1>
    <a class="button" href="#addstudent" onclick="document.getElementById('add-student-form').style.display='block';return false;">+ Add Student</a>
  </header>

  <section>
    <div id="students">
      {% for s in students %}
      <div class="student">
        <div>
          <a href="{{ url_for('student_page', student_id=s['id']) }}"><strong>{{ s['name'] }}</strong></a>
          {% if s['notes'] %}<div class="notes">{{ s['notes'] }}</div>{% endif %}
        </div>
        <form method="post" action="{{ url_for('delete_student', student_id=s['id']) }}" onsubmit="return confirm('Delete student and all assignments?');">
          <button type="submit" style="background:#dc3545">Delete</button>
        </form>
      </div>
      {% endfor %}

      {% if not students %}
        <p>No students yet. Add the first student using the + Add Student button above.</p>
      {% endif %}
    </div>
  </section>

  <section id="addstudent" style="margin-top:20px;">
    <div id="add-student-form" style="display:none;border:1px solid #ddd;padding:12px;border-radius:8px">
      <h3>Add Student</h3>
      <form method="post" action="{{ url_for('add_student') }}">
        <div style="display:flex;gap:8px;flex-wrap:wrap">
          <input name="name" placeholder="Student name" required>
          <input name="notes" placeholder="Notes (optional)">
          <button type="submit">Add</button>
        </div>
      </form>
      <p style="font-size:0.9em;color:#666;margin-top:8px">Tip: Click a student name to manage their assignments.</p>
    </div>
  </section>
</body>
</html>
"""


STUDENT_HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Study Lounge — {{ student['name'] }}</title>
  <style>
    body{font-family: Arial, Helvetica, sans-serif;max-width:1100px;margin:20px auto;padding:0 16px}
    header{display:flex;justify-content:space-between;align-items:center}
    .calendar{width:100%;border-collapse:collapse;margin-top:12px}
    .calendar th{padding:8px;background:#f2f2f2}
    .calendar td{vertical-align:top;border:1px solid #eee;padding:6px;height:110px}
    .day-num{font-weight:bold}
    .assignment{border-radius:6px;padding:4px;margin-top:4px;font-size:0.9em;border:1px solid #ccc}
    .test{background:#fff3cd}
    .homework{background:#e9f7ef}
    .completed{opacity:0.6;text-decoration:line-through}
    form.add-assignment{margin-top:12px;display:flex;gap:8px;flex-wrap:wrap}
    input,textarea,select{padding:6px;border-radius:4px;border:1px solid #ccc}
    button{padding:6px 10px;border-radius:6px;border:0;background:#007bff;color:white}
    .small{font-size:0.9em;color:#555}
    a{color:#007bff;text-decoration:none}
  </style>
</head>
<body>
  <header>
    <div>
      <h1>{{ student['name'] }}</h1>
      <div class="small">{{ student['notes'] or '' }}</div>
    </div>
    <div>
      <a href="{{ url_for('index') }}">⬅ Back</a>
    </div>
  </header>

  <section>
    <div style="display:flex;gap:12px;align-items:center;margin-top:8px">
      <form method="get" action="">
        <input type="hidden" name="year" value="{{ year }}">
        <label>Month: <select onchange="this.form.submit()" name="month">
          {% for m in range(1,13) %}
            <option value="{{ m }}" {% if m==month %}selected{% endif %}>{{ m }} - {{ months[m-1] }}</option>
          {% endfor %}
        </select></label>
      </form>
      <form method="get" style="margin:0">
        <input type="hidden" name="month" value="{{ month }}">
        <label>Year: <input name="year" type="number" value="{{ year }}" style="width:90px" onchange="this.form.submit()"></label>
      </form>
    </div>

    <table class="calendar">
      <thead>
        <tr>
          {% for d in ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'] %}
            <th>{{ d }}</th>
          {% endfor %}
        </tr>
      </thead>
      <tbody>
        {% for week in month_matrix %}
          <tr>
          {% for day in week %}
            {% if day==0 %}
              <td></td>
            {% else %}
              {% set day_iso = '%04d-%02d-%02d'|format(year, month, day) %}
              <td>
                <div class="day-num">{{ day }}</div>
                {% for a in assignments_by_date.get(day_iso, []) %}
                  <div class="assignment {% if a['is_test'] %}test{% else %}homework{% endif %} {% if a['completed'] %}completed{% endif %}">
                    <label style="display:flex;align-items:center;gap:8px">
                      <input type="checkbox" data-assign-id="{{ a['id'] }}" class="complete-checkbox" {% if a['completed'] %}checked{% endif %}>
                      <div style="flex:1">
                        <strong>{{ a['title'] }}</strong><br>
                        <small class="small">{{ 'Test' if a['is_test'] else 'Homework' }}</small>
                      </div>
                    </label>
                  </div>
                {% endfor %}
              </td>
            {% endif %}
          {% endfor %}
          </tr>
        {% endfor %}
      </tbody>
    </table>

    <div style="margin-top:12px">
      <h3>Add Assignment / Test</h3>
      <form class="add-assignment" method="post" action="{{ url_for('add_assignment', student_id=student['id']) }}">
        <input name="title" placeholder="Title (e.g. Algebra HW)" required>
        <input name="due_date" type="date" value="{{ today_iso }}" required>
        <select name="is_test">
          <option value="0">Homework</option>
          <option value="1">Test</option>
        </select>
        <input name="description" placeholder="Short description (optional)">
        <button type="submit">Add</button>
      </form>
    </div>

    <div style="margin-top:8px;font-size:0.9em;color:#666">
      Tip: Use the checkboxes in the calendar to mark assignments completed. They will update instantly.
    </div>
  </section>

  <script>
    document.querySelectorAll('.complete-checkbox').forEach(cb => {
      cb.addEventListener('change', ev => {
        const id = cb.dataset.assignId;
        fetch('/toggle_complete/' + id, {method:'POST'})
          .then(r => r.json())
          .then(data => {
            if(!data.ok){
              alert('Could not update.');
              cb.checked = !cb.checked; // revert
            } else {
              // toggle visual style
              const parent = cb.closest('.assignment');
              if(cb.checked) parent.classList.add('completed'); else parent.classList.remove('completed');
            }
          })
          .catch(()=>{alert('Network error'); cb.checked = !cb.checked;});
      });
    });
  </script>
</body>
</html>
"""

@app.route('/')
def index():
    db = get_db()
    cur = db.execute('SELECT * FROM students ORDER BY name COLLATE NOCASE')
    students = cur.fetchall()
    return render_template_string(INDEX_HTML, students=students)

@app.route('/add_student', methods=['POST'])
def add_student():
    name = request.form.get('name','').strip()
    notes = request.form.get('notes','').strip()
    if not name:
        return redirect(url_for('index'))
    db = get_db()
    db.execute('INSERT INTO students (name, notes) VALUES (?, ?)', (name, notes))
    db.commit()
    return redirect(url_for('index'))

@app.route('/delete_student/<int:student_id>', methods=['POST'])
def delete_student(student_id):
    db = get_db()
    db.execute('DELETE FROM assignments WHERE student_id = ?', (student_id,))
    db.execute('DELETE FROM students WHERE id = ?', (student_id,))
    db.commit()
    return redirect(url_for('index'))

@app.route('/student/<int:student_id>')
def student_page(student_id):
    # month/year from query params
    try:
        month = int(request.args.get('month', datetime.today().month))
        year = int(request.args.get('year', datetime.today().year))
    except ValueError:
        month = datetime.today().month
        year = datetime.today().year

    db = get_db()
    cur = db.execute('SELECT * FROM students WHERE id = ?', (student_id,))
    student = cur.fetchone()
    if not student:
        return redirect(url_for('index'))

    # fetch assignments for this student for the month (and maybe adjacent days if you want)
    start_iso = date(year, month, 1).isoformat()
    last_day = calendar.monthrange(year, month)[1]
    end_iso = date(year, month, last_day).isoformat()
    cur = db.execute('SELECT * FROM assignments WHERE student_id = ? AND due_date BETWEEN ? AND ? ORDER BY due_date', (student_id, start_iso, end_iso))
    assignments = [dict(r) for r in cur.fetchall()]

    # group by date
    assignments_by_date = {}
    for a in assignments:
        assignments_by_date.setdefault(a['due_date'], []).append(a)

    # build month matrix (weeks) starting on Monday
    cal = calendar.Calendar(firstweekday=0)  # Monday=0
    month_matrix = cal.monthdayscalendar(year, month)

    months = [calendar.month_name[i] for i in range(1,13)]
    today_iso = datetime.today().date().isoformat()

    return render_template_string(STUDENT_HTML, student=student, month=month, year=year,
                                  month_matrix=month_matrix, assignments_by_date=assignments_by_date,
                                  months=months, today_iso=today_iso)

@app.route('/student/<int:student_id>/add_assignment', methods=['POST'])
def add_assignment(student_id):
    title = request.form.get('title','').strip()
    due_date = request.form.get('due_date','').strip()
    description = request.form.get('description','').strip()
    is_test = 1 if request.form.get('is_test','0') == '1' else 0

    if not title or not due_date:
        return redirect(url_for('student_page', student_id=student_id))

    # validate date format
    try:
        datetime.strptime(due_date, '%Y-%m-%d')
    except ValueError:
        return redirect(url_for('student_page', student_id=student_id))

    db = get_db()
    db.execute('INSERT INTO assignments (student_id, title, description, due_date, is_test) VALUES (?, ?, ?, ?, ?)',
               (student_id, title, description, due_date, is_test))
    db.commit()
    return redirect(url_for('student_page', student_id=student_id, month=int(due_date[5:7]), year=int(due_date[:4])))

@app.route('/toggle_complete/<int:assign_id>', methods=['POST'])
def toggle_complete(assign_id):
    db = get_db()
    cur = db.execute('SELECT completed FROM assignments WHERE id = ?', (assign_id,))
    row = cur.fetchone()
    if not row:
        return jsonify({'ok': False}), 404
    new = 0 if row['completed'] else 1
    db.execute('UPDATE assignments SET completed = ? WHERE id = ?', (new, assign_id))
    db.commit()
    return jsonify({'ok': True, 'completed': bool(new)})

if __name__ == '__main__':
    app.run(debug=True)

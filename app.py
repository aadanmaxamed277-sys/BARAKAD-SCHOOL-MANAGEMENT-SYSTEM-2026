from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "BARAKAD-SCHOOL-SECRET-CHANGE-ME"
DATABASE = "barakad.db"

CLASS_LIST = [
    "1aad", "2aad", "3aad", "4aad",
    "5aad", "6aad", "7aad", "8aad",
    "Form One", "Form Two", "Form Three", "Form Four"
]

PRIMARY_SUBJECTS = [
    "Soomaali", "Cilmiga Bulshada", "Xisaab", "Seynis",
    "Carabi", "English", "Teknooloji", "Islamic"
]

MIDDLE_SUBJECTS = [
    "Soomaali", "Cilmiga Bulshada", "Xisaab", "Seynis",
    "English", "Teknooloji", "Islamic", "Carabi"
]

HIGH_SUBJECTS = [
    "Soomaali", "Math", "Biology", "Chemistry", "Physics",
    "Business", "Juqraafi", "Taariikh", "English",
    "Islamic", "Carabi", "Technology"
]

ALL_PERMISSIONS = [
    "students_view",
    "teachers_view",
    "parents_view",
    "classes_view",
    "fees_view",
    "attendance_view",
    "exams_view",
    "results_view",
    "results_edit",
    "lesson_plan_view",
    "calendar_view",
    "reports_view",
    "users_view",
    "admin_view"
]


def get_db():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db


def table_columns(db, table_name):
    rows = db.execute(f"PRAGMA table_info({table_name})").fetchall()
    return [row["name"] for row in rows]


def add_column_if_missing(db, table_name, column_name, column_definition):
    if column_name not in table_columns(db, table_name):
        db.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
        )


def init_db():
    db = get_db()

    db.execute("""CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        class_name TEXT NOT NULL,
        phone TEXT
    )""")

    db.execute("""CREATE TABLE IF NOT EXISTS teachers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        subject TEXT NOT NULL,
        phone TEXT
    )""")

    db.execute("""CREATE TABLE IF NOT EXISTS parents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT
    )""")

    db.execute("""CREATE TABLE IF NOT EXISTS classes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL
    )""")

    db.execute("""CREATE TABLE IF NOT EXISTS fees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_name TEXT NOT NULL,
        amount REAL NOT NULL,
        status TEXT NOT NULL
    )""")

    db.execute("""CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_name TEXT NOT NULL,
        class_name TEXT NOT NULL,
        date TEXT NOT NULL,
        status TEXT NOT NULL
    )""")

    db.execute("""CREATE TABLE IF NOT EXISTS exams (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        class_name TEXT NOT NULL,
        date TEXT,
        pass_mark REAL DEFAULT 50
    )""")

    db.execute("""CREATE TABLE IF NOT EXISTS results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_name TEXT NOT NULL,
        class_name TEXT,
        exam_id INTEGER,
        subject TEXT NOT NULL,
        marks REAL NOT NULL
    )""")

    db.execute("""CREATE TABLE IF NOT EXISTS lesson_plans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        teacher TEXT NOT NULL,
        subject TEXT NOT NULL,
        class_name TEXT NOT NULL,
        lesson TEXT NOT NULL,
        date TEXT
    )""")

    db.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL
    )""")

    db.execute("""CREATE TABLE IF NOT EXISTS calendar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        date TEXT NOT NULL,
        description TEXT
    )""")

    db.execute("""CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        date TEXT
    )""")

    db.execute("""CREATE TABLE IF NOT EXISTS school_settings (
        id INTEGER PRIMARY KEY CHECK (id=1),
        school_name TEXT NOT NULL DEFAULT 'My School',
        phone TEXT DEFAULT '',
        whatsapp TEXT DEFAULT '',
        address TEXT DEFAULT '',
        logo TEXT DEFAULT 'logo.png'
    )""")

    db.execute(
        """INSERT OR IGNORE INTO school_settings
           (id,school_name,phone,whatsapp,address,logo)
           VALUES (1,'My School','','','','logo.png')"""
    )

    for class_name in CLASS_LIST:
        db.execute(
            "INSERT OR IGNORE INTO classes (name) VALUES (?)",
            (class_name,)
        )

    # Safe migrations for existing BARAKAD databases.
    add_column_if_missing(db, "exams", "pass_mark", "REAL DEFAULT 50")
    add_column_if_missing(db, "exams", "teacher_user_id", "INTEGER")

    add_column_if_missing(db, "results", "class_name", "TEXT")
    add_column_if_missing(db, "results", "exam_id", "INTEGER")
    add_column_if_missing(db, "results", "teacher_user_id", "INTEGER")

    add_column_if_missing(db, "users", "student_name", "TEXT")
    add_column_if_missing(db, "users", "teacher_name", "TEXT")
    add_column_if_missing(db, "users", "permissions", "TEXT DEFAULT ''")
    add_column_if_missing(db, "users", "active", "INTEGER DEFAULT 1")

    # Create the main admin account if it does not exist.
    admin = db.execute(
        "SELECT * FROM users WHERE username=?",
        ("admin",)
    ).fetchone()

    if not admin:
        db.execute(
            """INSERT INTO users
               (username,password,role,student_name,teacher_name,permissions,active)
               VALUES (?,?,?,?,?,?,1)""",
            (
                "admin",
                generate_password_hash("1234"),
                "admin",
                None,
                None,
                ",".join(ALL_PERMISSIONS)
            )
        )
    else:
        # Keep old admin login working if the old database had plain "1234".
        old_password = admin["password"] or ""
        if old_password == "1234":
            db.execute(
                "UPDATE users SET password=? WHERE username=?",
                (generate_password_hash("1234"), "admin")
            )
        db.execute(
            """UPDATE users
               SET role='admin', permissions=?, active=1
               WHERE username='admin'""",
            (",".join(ALL_PERMISSIONS),)
        )

    db.commit()
    db.close()


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None

    db = get_db()
    user = db.execute(
        "SELECT * FROM users WHERE id=? AND active=1",
        (user_id,)
    ).fetchone()
    db.close()
    return user


def permission_list(user):
    if not user:
        return []
    if user["role"] == "admin":
        return ALL_PERMISSIONS
    value = user["permissions"] or ""
    return [p.strip() for p in value.split(",") if p.strip()]


def has_permission(permission):
    user = current_user()
    return bool(user and permission in permission_list(user))


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def permission_required(permission):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = current_user()
            if not user:
                return redirect(url_for("login"))
            if permission not in permission_list(user):
                return (
                    "Lama fasixin. Admin ayaa kuu oggolaan kara qaybtaan.",
                    403
                )
            return view(*args, **kwargs)
        return wrapped
    return decorator


def subjects_for_class(class_name):
    if class_name in ["1aad", "2aad", "3aad", "4aad"]:
        return PRIMARY_SUBJECTS
    if class_name in ["5aad", "6aad", "7aad", "8aad"]:
        return MIDDLE_SUBJECTS
    if class_name in ["Form One", "Form Two", "Form Three", "Form Four"]:
        return HIGH_SUBJECTS
    return []


def get_school_settings():
    db = get_db()
    row = db.execute(
        "SELECT * FROM school_settings WHERE id=1"
    ).fetchone()
    db.close()
    return row


def get_class_list(db):
    rows = db.execute("SELECT name FROM classes ORDER BY id").fetchall()
    names = [row["name"] for row in rows]
    return names or CLASS_LIST


def get_teacher_subject(user, db):
    if not user or user["role"] != "teacher" or not user["teacher_name"]:
        return None
    row = db.execute(
        "SELECT subject FROM teachers WHERE name=? ORDER BY id LIMIT 1",
        (user["teacher_name"],)
    ).fetchone()
    return row["subject"] if row else None


@app.context_processor
def inject_user():
    user = current_user()
    return {
        "logged_user": user,
        "logged_permissions": permission_list(user),
        "school_settings": get_school_settings()
    }


@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE username=? AND active=1",
            (username,)
        ).fetchone()
        db.close()

        valid = False
        if user:
            stored = user["password"] or ""
            try:
                valid = check_password_hash(stored, password)
            except Exception:
                valid = stored == password

        if valid:
            session.clear()
            session["user_id"] = user["id"]
            session["role"] = user["role"]
            return redirect(url_for("dashboard"))

        return "Username ama Password waa khalad."

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")


@app.route("/students")
@permission_required("students_view")
def students():
    db = get_db()
    rows = db.execute(
        "SELECT * FROM students ORDER BY id DESC"
    ).fetchall()
    class_list = get_class_list(db)
    db.close()
    return render_template(
        "students.html",
        students=rows,
        classes=class_list
    )


@app.route("/students/add", methods=["POST"])
@permission_required("students_view")
def add_student():
    name = request.form.get("name")
    class_name = request.form.get("class_name")
    phone = request.form.get("phone")

    db = get_db()
    db.execute(
        "INSERT INTO students (name,class_name,phone) VALUES (?,?,?)",
        (name, class_name, phone)
    )
    db.commit()
    db.close()
    return redirect(url_for("students"))


@app.route("/teachers")
@permission_required("teachers_view")
def teachers():
    db = get_db()
    rows = db.execute(
        "SELECT * FROM teachers ORDER BY id DESC"
    ).fetchall()
    db.close()
    return render_template("teachers.html", teachers=rows)


@app.route("/teachers/add", methods=["POST"])
@permission_required("teachers_view")
def add_teacher():
    name = request.form.get("name")
    subject = request.form.get("subject")
    phone = request.form.get("phone")

    db = get_db()
    db.execute(
        "INSERT INTO teachers (name,subject,phone) VALUES (?,?,?)",
        (name, subject, phone)
    )
    db.commit()
    db.close()
    return redirect(url_for("teachers"))


@app.route("/parents")
@permission_required("parents_view")
def parents():
    db = get_db()
    rows = db.execute(
        "SELECT * FROM parents ORDER BY id DESC"
    ).fetchall()
    db.close()
    return render_template("parents.html", parents=rows)


@app.route("/parents/add", methods=["POST"])
@permission_required("parents_view")
def add_parent():
    name = request.form.get("name")
    phone = request.form.get("phone")

    db = get_db()
    db.execute(
        "INSERT INTO parents (name,phone) VALUES (?,?)",
        (name, phone)
    )
    db.commit()
    db.close()
    return redirect(url_for("parents"))


@app.route("/classes")
@permission_required("classes_view")
def classes():
    db = get_db()
    rows = db.execute(
        "SELECT * FROM classes ORDER BY id"
    ).fetchall()
    db.close()
    return render_template("classes.html", classes=rows)


@app.route("/classes/add", methods=["POST"])
@permission_required("classes_view")
def add_class():
    user = current_user()
    if user["role"] != "admin":
        return ("Class cusub waxaa ku dari kara Admin oo keliya.", 403)

    name = (request.form.get("name") or "").strip()
    if not name:
        return ("Class name waa qasab.", 400)

    db = get_db()
    db.execute(
        "INSERT OR IGNORE INTO classes (name) VALUES (?)",
        (name,)
    )
    db.commit()
    db.close()
    return redirect(url_for("classes"))


@app.route("/fees")
@permission_required("fees_view")
def fees():
    selected_class = request.args.get("class_name", "")

    db = get_db()
    students = []
    if selected_class:
        students = db.execute(
            "SELECT * FROM students WHERE class_name=? ORDER BY name",
            (selected_class,)
        ).fetchall()

    fee_rows = db.execute(
        "SELECT * FROM fees ORDER BY id DESC"
    ).fetchall()

    school_total = db.execute(
        "SELECT COALESCE(SUM(amount),0) FROM fees WHERE status='Paid'"
    ).fetchone()[0]

    class_total = 0
    if selected_class:
        class_total = db.execute(
            """SELECT COALESCE(SUM(f.amount),0)
               FROM fees f
               JOIN students s ON f.student_name=s.name
               WHERE s.class_name=? AND f.status='Paid'""",
            (selected_class,)
        ).fetchone()[0]

    unpaid_total = db.execute(
        "SELECT COALESCE(SUM(amount),0) FROM fees WHERE status='Unpaid'"
    ).fetchone()[0]

    partial_total = db.execute(
        "SELECT COALESCE(SUM(amount),0) FROM fees WHERE status='Partial'"
    ).fetchone()[0]

    class_list = get_class_list(db)
    db.close()

    return render_template(
        "fees.html",
        classes=class_list,
        selected_class=selected_class,
        students=students,
        fees=fee_rows,
        school_total=school_total,
        class_total=class_total,
        unpaid_total=unpaid_total,
        partial_total=partial_total
    )


@app.route("/fees/add", methods=["POST"])
@permission_required("fees_view")
def add_fee():
    student_name = request.form.get("student_name")
    amount = request.form.get("amount")
    status = request.form.get("status")
    class_name = request.form.get("class_name")

    db = get_db()
    db.execute(
        "INSERT INTO fees (student_name,amount,status) VALUES (?,?,?)",
        (student_name, amount, status)
    )
    db.commit()
    db.close()

    return redirect(url_for("fees", class_name=class_name))


@app.route("/attendance")
@permission_required("attendance_view")
def attendance():
    user = current_user()
    db = get_db()
    class_list = get_class_list(db)

    # Students are always restricted to their own class and their own records.
    if user["role"] == "student":
        student = db.execute(
            "SELECT * FROM students WHERE name=? ORDER BY id LIMIT 1",
            (user["student_name"],)
        ).fetchone()
        if not student:
            db.close()
            return render_template(
                "attendance.html",
                classes=class_list, selected_class="", selected_date="",
                students=[], attendance_records=[],
                total_present=0, total_absent=0, total_late=0
            )

        selected_class = student["class_name"]
        selected_date = request.args.get("date", "")
        attendance_records = db.execute(
            """SELECT * FROM attendance
               WHERE student_name=? AND class_name=?
               ORDER BY date DESC""",
            (student["name"], selected_class)
        ).fetchall()
        filtered_records = [
            row for row in attendance_records
            if not selected_date or row["date"] == selected_date
        ]
        total_present = sum(1 for row in attendance_records if row["status"] == "Present")
        total_absent = sum(1 for row in attendance_records if row["status"] == "Absent")
        total_late = sum(1 for row in attendance_records if row["status"] == "Late")

        db.close()
        return render_template(
            "attendance.html",
            classes=class_list,
            selected_class=selected_class,
            selected_date=selected_date,
            students=[student],
            attendance_records=filtered_records,
            total_present=total_present,
            total_absent=total_absent,
            total_late=total_late
        )

    selected_class = request.args.get("class_name", "")
    selected_date = request.args.get("date", "")

    db = get_db()
    students = []
    if selected_class:
        students = db.execute(
            "SELECT * FROM students WHERE class_name=? ORDER BY name",
            (selected_class,)
        ).fetchall()

    attendance_records = []
    if selected_class:
        if selected_date:
            attendance_records = db.execute(
                """SELECT * FROM attendance
                   WHERE class_name=? AND date=?
                   ORDER BY student_name""",
                (selected_class, selected_date)
            ).fetchall()
        else:
            attendance_records = db.execute(
                """SELECT * FROM attendance
                   WHERE class_name=?
                   ORDER BY date DESC,student_name""",
                (selected_class,)
            ).fetchall()

    total_present = sum(1 for row in attendance_records if row["status"] == "Present")
    total_absent = sum(1 for row in attendance_records if row["status"] == "Absent")
    total_late = sum(1 for row in attendance_records if row["status"] == "Late")

    db.close()

    return render_template(
        "attendance.html",
        classes=class_list,
        selected_class=selected_class,
        selected_date=selected_date,
        students=students,
        attendance_records=attendance_records,
        total_present=total_present,
        total_absent=total_absent,
        total_late=total_late
    )


@app.route("/attendance/save", methods=["POST"])
@permission_required("attendance_view")
def save_attendance():
    user = current_user()
    if user["role"] == "student":
        return ("Student ma geli karo Attendance. Kaliya wuu arki karaa.", 403)

    class_name = request.form.get("class_name", "")
    date = request.form.get("date", "")

    db = get_db()
    student_ids = request.form.getlist("student_id")
    statuses = request.form.getlist("status")

    # Only Admin or a Teacher explicitly granted attendance_view can save attendance.
    for student_id, status in zip(student_ids, statuses):
        if status not in ["Present", "Absent", "Late"]:
            continue
        student = db.execute(
            "SELECT * FROM students WHERE id=? AND class_name=?",
            (student_id, class_name)
        ).fetchone()
        if not student:
            continue

        old_record = db.execute(
            """SELECT id FROM attendance
               WHERE student_name=? AND class_name=? AND date=?""",
            (student["name"], class_name, date)
        ).fetchone()

        if old_record:
            db.execute(
                "UPDATE attendance SET status=? WHERE id=?",
                (status, old_record["id"])
            )
        else:
            db.execute(
                """INSERT INTO attendance
                   (student_name,class_name,date,status)
                   VALUES (?,?,?,?)""",
                (student["name"], class_name, date, status)
            )

    db.commit()
    db.close()
    return redirect(url_for("attendance", class_name=class_name, date=date))


@app.route("/exams")
@permission_required("exams_view")
def exams():
    selected_class = request.args.get("class_name", "")
    user = current_user()

    db = get_db()

    if user["role"] == "admin":
        exam_rows = db.execute(
            "SELECT * FROM exams ORDER BY date DESC,id DESC"
        ).fetchall()
    elif user["role"] == "teacher":
        exam_rows = db.execute(
            """SELECT * FROM exams
               WHERE teacher_user_id=?
               ORDER BY date DESC,id DESC""",
            (user["id"],)
        ).fetchall()
    else:
        exam_rows = []

    class_list = get_class_list(db)
    db.close()

    return render_template(
        "exams.html",
        classes=class_list,
        selected_class=selected_class,
        exams=exam_rows
    )


@app.route("/exams/add", methods=["POST"])
@permission_required("exams_view")
def add_exam():
    user = current_user()

    name = request.form.get("name")
    class_name = request.form.get("class_name")
    date = request.form.get("date")

    db = get_db()

    teacher_user_id = None
    if user["role"] == "teacher":
        teacher_user_id = user["id"]

    db.execute(
        """INSERT INTO exams
           (name,class_name,date,pass_mark,teacher_user_id)
           VALUES (?,?,?,?,?)""",
        (name, class_name, date, 50, teacher_user_id)
    )

    db.commit()
    db.close()

    return redirect(
        url_for("exams", class_name=class_name)
    )


@app.route("/results", methods=["GET", "POST"])
@permission_required("results_view")
def results():
    user = current_user()
    selected_class = request.args.get(
        "class_name",
        request.form.get("class_name", "")
    )

    db = get_db()

    if request.method == "POST":
        action = request.form.get("action")

        if action in ["save", "edit"] and "results_edit" not in permission_list(user):
            db.close()
            return (
                "Lama fasixin inaad geliso ama beddesho Results. "
                "Admin ayaa fasaxa Results Edit.",
                403
            )

        if action == "save":
            student_name = request.form.get("student_name")
            exam_id = request.form.get("exam_id")
            subject = request.form.get("subject")
            marks_text = request.form.get("marks")
            pass_mark_text = request.form.get("pass_mark")

            try:
                marks = float(marks_text)
            except Exception:
                marks = -1

            if marks < 0 or marks > 100:
                db.close()
                return ("Marks waa inuu u dhexeeyaa 0 ilaa 100.", 400)

            try:
                pass_mark = float(pass_mark_text)
            except Exception:
                pass_mark = 50

            pass_mark = max(0, min(100, pass_mark))

            exam = db.execute(
                "SELECT * FROM exams WHERE id=? AND class_name=?",
                (exam_id, selected_class)
            ).fetchone()

            if not exam:
                db.close()
                return ("Exam-ka iyo Class-ka isma laha.", 400)

            if user["role"] == "teacher":
                if exam["teacher_user_id"] != user["id"]:
                    db.close()
                    return (
                        "Exam-kan macallinkan looma fasixin.",
                        403
                    )

                teacher_subject = get_teacher_subject(user, db)
                if not teacher_subject or subject != teacher_subject:
                    db.close()
                    return (
                        "Macallinku wuxuu geli karaa Result-ka maadadiisa oo keliya.",
                        403
                    )

            student = db.execute(
                """SELECT * FROM students
                   WHERE name=? AND class_name=?""",
                (student_name, selected_class)
            ).fetchone()

            if not student:
                db.close()
                return (
                    "Ardaygan kuma jiro Class-kan.",
                    400
                )

            db.execute(
                "UPDATE exams SET pass_mark=? WHERE id=?",
                (pass_mark, exam_id)
            )

            old_result = db.execute(
                """SELECT id FROM results
                   WHERE exam_id=?
                   AND student_name=?
                   AND class_name=?
                   AND subject=?""",
                (
                    exam_id,
                    student_name,
                    selected_class,
                    subject
                )
            ).fetchone()

            teacher_user_id = None
            if user["role"] == "teacher":
                teacher_user_id = user["id"]
            elif exam["teacher_user_id"]:
                teacher_user_id = exam["teacher_user_id"]

            if old_result:
                db.execute(
                    """UPDATE results
                       SET marks=?,teacher_user_id=?
                       WHERE id=?""",
                    (
                        marks,
                        teacher_user_id,
                        old_result["id"]
                    )
                )
            else:
                db.execute(
                    """INSERT INTO results
                       (student_name,class_name,exam_id,subject,marks,teacher_user_id)
                       VALUES (?,?,?,?,?,?)""",
                    (
                        student_name,
                        selected_class,
                        exam_id,
                        subject,
                        marks,
                        teacher_user_id
                    )
                )

            db.commit()

        elif action == "edit":
            result_id = request.form.get("result_id")
            student_name = request.form.get("student_name")
            exam_id = request.form.get("exam_id")
            subject = request.form.get("subject")
            marks_text = request.form.get("marks")

            try:
                marks = float(marks_text)
            except Exception:
                marks = 0

            marks = max(0, min(100, marks))

            old = db.execute(
                "SELECT * FROM results WHERE id=?",
                (result_id,)
            ).fetchone()

            if not old:
                db.close()
                return ("Result-ka lama helin.", 404)

            if user["role"] == "teacher":
                if old["teacher_user_id"] != user["id"]:
                    db.close()
                    return (
                        "Result-kan macallinkan looma fasixin.",
                        403
                    )
                teacher_subject = get_teacher_subject(user, db)
                if not teacher_subject or old["subject"] != teacher_subject:
                    db.close()
                    return (
                        "Macallinku wuxuu beddeli karaa Result-ka maadadiisa oo keliya.",
                        403
                    )
                if subject != teacher_subject:
                    db.close()
                    return (
                        "Macallinku wuxuu geli karaa Result-ka maadadiisa oo keliya.",
                        403
                    )

            db.execute(
                """UPDATE results
                   SET student_name=?,exam_id=?,subject=?,marks=?
                   WHERE id=?""",
                (
                    student_name,
                    exam_id,
                    subject,
                    marks,
                    result_id
                )
            )
            db.commit()

        elif action == "delete":
            if user["role"] != "admin":
                db.close()
                return (
                    "Delete Results waxaa sameyn kara Admin oo keliya.",
                    403
                )

            result_id = request.form.get("result_id")
            db.execute(
                "DELETE FROM results WHERE id=?",
                (result_id,)
            )
            db.commit()

    students = []
    exams_for_class = []

    if user["role"] == "student":
        linked_student = user["student_name"]
        if linked_student:
            student_row = db.execute(
                """SELECT * FROM students
                   WHERE name=?""",
                (linked_student,)
            ).fetchone()

            if student_row:
                selected_class = student_row["class_name"]
                students = [student_row]

        exams_for_class = db.execute(
            """SELECT * FROM exams
               WHERE class_name=?
               ORDER BY date DESC,id DESC""",
            (selected_class,)
        ).fetchall() if selected_class else []

    else:
        if selected_class:
            students = db.execute(
                """SELECT * FROM students
                   WHERE class_name=?
                   ORDER BY name""",
                (selected_class,)
            ).fetchall()

            if user["role"] == "teacher":
                exams_for_class = db.execute(
                    """SELECT * FROM exams
                       WHERE class_name=? AND teacher_user_id=?
                       ORDER BY date DESC,id DESC""",
                    (selected_class, user["id"])
                ).fetchall()
            else:
                exams_for_class = db.execute(
                    """SELECT * FROM exams
                       WHERE class_name=?
                       ORDER BY date DESC,id DESC""",
                    (selected_class,)
                ).fetchall()

    if user["role"] == "student":
        raw_results = db.execute(
            """SELECT r.id,r.student_name,r.class_name,r.exam_id,
                      r.subject,r.marks,
                      e.name AS exam_name,
                      e.date AS exam_date,
                      COALESCE(e.pass_mark,50) AS pass_mark
               FROM results r
               LEFT JOIN exams e ON r.exam_id=e.id
               WHERE r.student_name=? AND r.class_name=?
               ORDER BY e.date DESC,r.subject""",
            (user["student_name"], selected_class)
        ).fetchall()
    elif user["role"] == "teacher":
        raw_results = db.execute(
            """SELECT r.id,r.student_name,r.class_name,r.exam_id,
                      r.subject,r.marks,
                      e.name AS exam_name,
                      e.date AS exam_date,
                      COALESCE(e.pass_mark,50) AS pass_mark,
                      r.teacher_user_id
               FROM results r
               LEFT JOIN exams e ON r.exam_id=e.id
               WHERE r.class_name=? AND r.teacher_user_id=? AND r.subject=?
               ORDER BY e.date DESC,r.student_name,r.subject""",
            (selected_class, user["id"], get_teacher_subject(user, db))
        ).fetchall() if selected_class else []
    else:
        raw_results = db.execute(
            """SELECT r.id,r.student_name,r.class_name,r.exam_id,
                      r.subject,r.marks,
                      e.name AS exam_name,
                      e.date AS exam_date,
                      COALESCE(e.pass_mark,50) AS pass_mark
               FROM results r
               LEFT JOIN exams e ON r.exam_id=e.id
               WHERE r.class_name=?
               ORDER BY e.date DESC,r.student_name,r.subject""",
            (selected_class,)
        ).fetchall() if selected_class else []

    averages = {}
    for result in raw_results:
        key = (result["exam_id"], result["student_name"])
        averages.setdefault(key, [])

        try:
            mark = float(result["marks"])
        except Exception:
            mark = 0

        averages[key].append(mark)

    student_averages = {}
    for key, marks_list in averages.items():
        student_averages[key] = (
            sum(marks_list) / len(marks_list)
            if marks_list else 0
        )

    exam_groups = {}
    for key, average in student_averages.items():
        exam_groups.setdefault(key[0], [])
        exam_groups[key[0]].append(
            (key[1], average)
        )

    ranks = {}
    for exam_id, group in exam_groups.items():
        sorted_group = sorted(
            group,
            key=lambda item: item[1],
            reverse=True
        )
        for index, item in enumerate(
            sorted_group,
            start=1
        ):
            ranks[(exam_id, item[0])] = index

    results_list = []

    for result in raw_results:
        student_name = result["student_name"]
        exam_id = result["exam_id"]
        key = (exam_id, student_name)

        try:
            marks = float(result["marks"])
        except Exception:
            marks = 0

        try:
            pass_mark = float(result["pass_mark"])
        except Exception:
            pass_mark = 50

        average = student_averages.get(key, 0)
        status = (
            "Gudbay"
            if marks >= pass_mark
            else "Haray"
        )

        results_list.append({
            "id": result["id"],
            "student_name": student_name,
            "exam_id": exam_id,
            "exam_name": (
                result["exam_name"]
                if result["exam_name"]
                else "Old Result"
            ),
            "exam_date": (
                result["exam_date"]
                if result["exam_date"]
                else ""
            ),
            "subject": result["subject"],
            "marks": marks,
            "percentage": marks,
            "pass_mark": pass_mark,
            "average": round(average, 2),
            "rank": ranks.get(key, "-"),
            "status": status
        })

    # Student attendance summary is included on the Student Results page.
    # Students can see only their own attendance records.
    attendance_summary = {
        "present": 0,
        "absent": 0,
        "late": 0,
        "total": 0,
        "percentage": 0
    }
    attendance_records_student = []

    if user["role"] == "student" and user["student_name"]:
        attendance_records_student = db.execute(
            """SELECT date,class_name,status
               FROM attendance
               WHERE student_name=? AND class_name=?
               ORDER BY date DESC""",
            (user["student_name"], selected_class)
        ).fetchall() if selected_class else []

        attendance_summary["present"] = sum(
            1 for row in attendance_records_student
            if row["status"] == "Present"
        )
        attendance_summary["absent"] = sum(
            1 for row in attendance_records_student
            if row["status"] == "Absent"
        )
        attendance_summary["late"] = sum(
            1 for row in attendance_records_student
            if row["status"] == "Late"
        )
        attendance_summary["total"] = len(attendance_records_student)

        if attendance_summary["total"]:
            attendance_summary["percentage"] = round(
                (attendance_summary["present"] / attendance_summary["total"]) * 100,
                2
            )

    class_list = get_class_list(db)
    teacher_subject_for_view = get_teacher_subject(user, db) if user["role"] == "teacher" else None
    if user["role"] == "teacher" and teacher_subject_for_view:
        allowed_subjects = [teacher_subject_for_view] if teacher_subject_for_view in subjects_for_class(selected_class) else []
    else:
        allowed_subjects = subjects_for_class(selected_class)

    db.close()

    return render_template(
        "results.html",
        classes=class_list,
        selected_class=selected_class,
        students=students,
        exams=exams_for_class,
        results=results_list,
        subjects=allowed_subjects,
        attendance_summary=attendance_summary,
        attendance_records_student=attendance_records_student
    )


@app.route("/lesson-plan")
@permission_required("lesson_plan_view")
def lesson_plan():
    db = get_db()
    rows = db.execute(
        "SELECT * FROM lesson_plans ORDER BY id DESC"
    ).fetchall()
    class_list = get_class_list(db)
    db.close()

    return render_template(
        "lesson_plan.html",
        classes=class_list,
        lesson_plans=rows
    )


@app.route("/lesson-plan/add", methods=["POST"])
@permission_required("lesson_plan_view")
def add_lesson_plan():
    teacher = request.form.get("teacher")
    subject = request.form.get("subject")
    class_name = request.form.get("class_name")
    lesson = request.form.get("lesson")
    date = request.form.get("date")

    if subject not in subjects_for_class(class_name):
        return (
            "Subject-kan kuma jiro Class-ka la doortay.",
            400
        )

    db = get_db()
    db.execute(
        """INSERT INTO lesson_plans
           (teacher,subject,class_name,lesson,date)
           VALUES (?,?,?,?,?)""",
        (
            teacher,
            subject,
            class_name,
            lesson,
            date
        )
    )
    db.commit()
    db.close()

    return redirect(url_for("lesson_plan"))


@app.route("/users")
@permission_required("users_view")
def users():
    db = get_db()
    rows = db.execute(
        """SELECT id,username,role,student_name,
                  teacher_name,permissions,active
           FROM users
           ORDER BY id DESC"""
    ).fetchall()
    students_rows = db.execute(
        "SELECT name,class_name FROM students ORDER BY name"
    ).fetchall()
    teachers_rows = db.execute(
        "SELECT name,subject FROM teachers ORDER BY name"
    ).fetchall()
    db.close()

    return render_template(
        "users.html",
        users=rows,
        students=students_rows,
        teachers=teachers_rows,
        permissions=ALL_PERMISSIONS
    )


@app.route("/users/add", methods=["POST"])
@permission_required("users_view")
def add_user():
    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""
    role = (request.form.get("role") or "").strip().lower()
    student_name = request.form.get("student_name")
    teacher_name = request.form.get("teacher_name")
    permissions = request.form.getlist("permissions")

    if role not in ["teacher", "student"]:
        return (
            "Admin account-kan lama sameyn karo page-kan.",
            400
        )

    if not username or not password:
        return (
            "Username iyo Password waa qasab.",
            400
        )

    if role == "student" and not student_name:
        return (
            "Student account waa inuu leeyahay arday loo xiro.",
            400
        )

    if role == "teacher" and not teacher_name:
        return (
            "Teacher account waa inuu leeyahay macallin loo xiro.",
            400
        )

    clean_permissions = [
        p for p in permissions
        if p in ALL_PERMISSIONS
    ]

    # Students should only receive permissions relevant to viewing their account.
    if role == "student":
        clean_permissions = [
            p for p in clean_permissions
            if p in ["results_view"]
        ]

    db = get_db()

    exists = db.execute(
        "SELECT id FROM users WHERE username=?",
        (username,)
    ).fetchone()

    if exists:
        db.close()
        return (
            "Username-kan hore ayuu u jiraa. Mid kale dooro.",
            400
        )

    db.execute(
        """INSERT INTO users
           (username,password,role,student_name,teacher_name,permissions,active)
           VALUES (?,?,?,?,?,?,1)""",
        (
            username,
            generate_password_hash(password),
            role,
            student_name if role == "student" else None,
            teacher_name if role == "teacher" else None,
            ",".join(clean_permissions)
        )
    )

    db.commit()
    db.close()

    return redirect(url_for("users"))


@app.route("/users/toggle/<int:user_id>", methods=["POST"])
@permission_required("users_view")
def toggle_user(user_id):
    if user_id == current_user()["id"]:
        return (
            "Admin-ka hadda login-ka ku jira lama damin karo.",
            400
        )

    db = get_db()
    user = db.execute(
        "SELECT active FROM users WHERE id=?",
        (user_id,)
    ).fetchone()

    if not user:
        db.close()
        return ("User lama helin.", 404)

    new_value = 0 if user["active"] else 1

    db.execute(
        "UPDATE users SET active=? WHERE id=?",
        (new_value, user_id)
    )
    db.commit()
    db.close()

    return redirect(url_for("users"))


@app.route("/admin")
@permission_required("admin_view")
def admin():
    db = get_db()

    students_count = db.execute(
        "SELECT COUNT(*) FROM students"
    ).fetchone()[0]

    teachers_count = db.execute(
        "SELECT COUNT(*) FROM teachers"
    ).fetchone()[0]

    parents_count = db.execute(
        "SELECT COUNT(*) FROM parents"
    ).fetchone()[0]

    classes_count = db.execute(
        "SELECT COUNT(*) FROM classes"
    ).fetchone()[0]

    exams_count = db.execute(
        "SELECT COUNT(*) FROM exams"
    ).fetchone()[0]

    results_count = db.execute(
        "SELECT COUNT(*) FROM results"
    ).fetchone()[0]

    users_count = db.execute(
        "SELECT COUNT(*) FROM users"
    ).fetchone()[0]

    db.close()

    return render_template(
        "admin.html",
        students_count=students_count,
        teachers_count=teachers_count,
        parents_count=parents_count,
        classes_count=classes_count,
        exams_count=exams_count,
        results_count=results_count,
        users_count=users_count
    )


@app.route("/reports")
@permission_required("reports_view")
def reports():
    db = get_db()
    rows = db.execute(
        "SELECT * FROM reports ORDER BY id DESC"
    ).fetchall()
    db.close()

    return render_template(
        "reports.html",
        reports=rows
    )


@app.route("/reports/add", methods=["POST"])
@permission_required("reports_view")
def add_report():
    title = request.form.get("title")
    content = request.form.get("content")
    date = request.form.get("date")

    db = get_db()
    db.execute(
        "INSERT INTO reports (title,content,date) VALUES (?,?,?)",
        (title, content, date)
    )
    db.commit()
    db.close()

    return redirect(url_for("reports"))


@app.route("/calendar")
@permission_required("calendar_view")
def calendar():
    db = get_db()
    rows = db.execute(
        "SELECT * FROM calendar ORDER BY date"
    ).fetchall()
    db.close()

    return render_template(
        "calendar.html",
        calendar=rows
    )


@app.route("/calendar/add", methods=["POST"])
@permission_required("calendar_view")
def add_calendar():
    title = request.form.get("title")
    date = request.form.get("date")
    description = request.form.get("description")

    db = get_db()
    db.execute(
        """INSERT INTO calendar
           (title,date,description)
           VALUES (?,?,?)""",
        (title, date, description)
    )
    db.commit()
    db.close()

    return redirect(url_for("calendar"))


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    user = current_user()
    db = get_db()

    if request.method == "POST":
        action = request.form.get("action", "")

        if action == "change_my_password":
            old_password = request.form.get("old_password") or ""
            new_password = request.form.get("new_password") or ""
            confirm_password = request.form.get("confirm_password") or ""

            if not check_password_hash(user["password"], old_password):
                db.close()
                return ("Password-kii hore waa khalad.", 400)

            if len(new_password) < 4:
                db.close()
                return ("Password-ka cusub ugu yaraan 4 xaraf ha ahaado.", 400)

            if new_password != confirm_password:
                db.close()
                return ("New Password iyo Confirm Password isma laha.", 400)

            db.execute(
                "UPDATE users SET password=? WHERE id=?",
                (generate_password_hash(new_password), user["id"])
            )
            db.commit()
            db.close()
            return redirect(url_for("settings"))

        if user["role"] != "admin":
            db.close()
            return ("Settings-kan Admin ayaa maamula.", 403)

        if action == "school":
            school_name = (request.form.get("school_name") or "").strip()
            phone = (request.form.get("phone") or "").strip()
            whatsapp = (request.form.get("whatsapp") or "").strip()
            address = (request.form.get("address") or "").strip()

            if not school_name:
                db.close()
                return ("Magaca school-ka waa qasab.", 400)

            db.execute(
                """UPDATE school_settings
                   SET school_name=?,phone=?,whatsapp=?,address=?
                   WHERE id=1""",
                (school_name, phone, whatsapp, address)
            )
            db.commit()
            db.close()
            return redirect(url_for("settings"))

        if action == "admin_account":
            new_username = (request.form.get("username") or "").strip()
            new_password = request.form.get("password") or ""

            if not new_username:
                db.close()
                return ("Admin username waa qasab.", 400)

            duplicate = db.execute(
                "SELECT id FROM users WHERE username=? AND id!=?",
                (new_username, user["id"])
            ).fetchone()
            if duplicate:
                db.close()
                return ("Username-kan hore ayuu u jiraa.", 400)

            if new_password:
                if len(new_password) < 4:
                    db.close()
                    return ("Admin password ugu yaraan 4 xaraf ha ahaado.", 400)
                db.execute(
                    "UPDATE users SET username=?,password=? WHERE id=?",
                    (new_username, generate_password_hash(new_password), user["id"])
                )
            else:
                db.execute(
                    "UPDATE users SET username=? WHERE id=?",
                    (new_username, user["id"])
                )

            db.commit()
            db.close()
            return redirect(url_for("settings"))

        if action == "user_account":
            user_id = request.form.get("user_id")
            new_username = (request.form.get("username") or "").strip()
            new_password = request.form.get("password") or ""

            if not user_id or not new_username:
                db.close()
                return ("User iyo username waa qasab.", 400)

            duplicate = db.execute(
                "SELECT id FROM users WHERE username=? AND id!=?",
                (new_username, user_id)
            ).fetchone()
            if duplicate:
                db.close()
                return ("Username-kan hore ayuu u jiraa.", 400)

            if new_password:
                if len(new_password) < 4:
                    db.close()
                    return ("Password cusub ugu yaraan 4 xaraf ha ahaado.", 400)
                db.execute(
                    "UPDATE users SET username=?,password=? WHERE id=?",
                    (new_username, generate_password_hash(new_password), user_id)
                )
            else:
                db.execute(
                    "UPDATE users SET username=? WHERE id=?",
                    (new_username, user_id)
                )

            db.commit()
            db.close()
            return redirect(url_for("settings"))

    users_rows = []
    school = get_school_settings()
    if user["role"] == "admin":
        users_rows = db.execute(
            "SELECT id,username,role,active FROM users ORDER BY id DESC"
        ).fetchall()

    db.close()
    return render_template(
        "settings.html",
        school=school,
        users=users_rows
    )


@app.route("/about")
@login_required
def about():
    return render_template("about.html")


if __name__ == "__main__":
    init_db()
    app.run(
        debug=True,
        host="0.0.0.0",
        port=5000
    )
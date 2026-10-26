
import os
import json
import sqlite3
from functools import wraps

from dotenv import load_dotenv
from flask import (
    Flask,
    jsonify,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
)
from werkzeug.security import generate_password_hash, check_password_hash

from database import get_connection, initialize_database


# -------------------- APP CONFIGURATION --------------------

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")

if not app.config["SECRET_KEY"]:
    raise RuntimeError(
        "SECRET_KEY is missing. Add a random SECRET_KEY to your .env file."
    )

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)


# -------------------- AUTHENTICATION HELPERS --------------------

def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped_view


def role_required(required_role):
    def decorator(view):
        @wraps(view)
        def wrapped_view(*args, **kwargs):
            if "user_id" not in session:
                flash("Please log in first.")
                return redirect(url_for("login"))

            if session.get("role") != required_role:
                flash("You do not have permission to access that page.")
                return redirect(url_for("dashboard"))

            return view(*args, **kwargs)
        return wrapped_view
    return decorator


# -------------------- PUBLIC PAGES --------------------

@app.route("/")
@app.route("/home")
def home_page():
    return render_template("index.html")


@app.route("/health")
def health():
    return jsonify({"status": "healthy"})


# -------------------- REGISTRATION --------------------

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    role = request.form.get("role", "").strip().lower()

    if not name or len(name) > 100:
        flash("Please enter a name of at most 100 characters.")
        return redirect(url_for("register"))

    if not email or len(email) > 254 or "@" not in email:
        flash("Please enter a valid email address.")
        return redirect(url_for("register"))

    if role not in ("student", "teacher"):
        flash("Please select a valid role.")
        return redirect(url_for("register"))

    if len(password) < 8:
        flash("Password must be at least 8 characters.")
        return redirect(url_for("register"))

    try:
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO users (name, email, password_hash, role)
                VALUES (?, ?, ?, ?)
                """,
                (
                    name,
                    email,
                    generate_password_hash(password),
                    role,
                ),
            )
    except sqlite3.IntegrityError:
        flash("An account with this email already exists.")
        return redirect(url_for("register"))

    flash("Account created successfully. Please log in.")
    return redirect(url_for("login"))


# -------------------- LOGIN AND LOGOUT --------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    with get_connection() as connection:
        user = connection.execute(
            """
            SELECT id, name, email, password_hash, role
            FROM users
            WHERE email = ?
            """,
            (email,),
        ).fetchone()

    if user is None or not check_password_hash(
        user["password_hash"], password
    ):
        flash("Invalid email or password.")
        return redirect(url_for("login"))

    session.clear()
    session["user_id"] = user["id"]
    session["name"] = user["name"]
    session["role"] = user["role"]

    return redirect(url_for("dashboard"))


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.")
    return redirect(url_for("login"))


# -------------------- DASHBOARD REDIRECT --------------------

@app.route("/dashboard")
@login_required
def dashboard():
    if session["role"] == "teacher":
        return redirect(url_for("teacher_dashboard"))

    return redirect(url_for("student_dashboard"))


# -------------------- TEACHER DASHBOARD --------------------

@app.route("/teacher")
@role_required("teacher")
def teacher_dashboard():
    with get_connection() as connection:
        exams = connection.execute(
            """
            SELECT id, title, subject, total_marks
            FROM exams
            WHERE teacher_id = ?
            ORDER BY id DESC
            """,
            (session["user_id"],),
        ).fetchall()

    return render_template(
        "teacher_dashboard.html",
        name=session["name"],
        exams=exams,
    )


# -------------------- STUDENT DASHBOARD --------------------

@app.route("/student")
@role_required("student")
def student_dashboard():
    return (
        f"Welcome, {session['name']}! "
        "Student dashboard coming soon. "
        '<a href="/logout">Log out</a>'
    )


# -------------------- MY EXAMS --------------------

@app.route("/teacher/exams")
@role_required("teacher")
def my_exams():
    with get_connection() as connection:
        exams = connection.execute(
            """
            SELECT
                e.id,
                e.title,
                e.subject,
                e.total_marks,
                COUNT(q.id) AS question_count
            FROM exams e
            LEFT JOIN questions q ON q.exam_id = e.id
            WHERE e.teacher_id = ?
            GROUP BY e.id, e.title, e.subject, e.total_marks
            ORDER BY e.id DESC
            """,
            (session["user_id"],),
        ).fetchall()

    return render_template("my_exams.html", exams=exams)


# -------------------- EXAM DETAILS --------------------

@app.route("/teacher/exams/<int:exam_id>")
@role_required("teacher")
def exam_details(exam_id):
    with get_connection() as connection:
        exam = connection.execute(
            """
            SELECT id, title, subject, total_marks
            FROM exams
            WHERE id = ? AND teacher_id = ?
            """,
            (exam_id, session["user_id"]),
        ).fetchone()

        if exam is None:
            flash("Exam not found.")
            return redirect(url_for("my_exams"))

        rows = connection.execute(
            """
            SELECT
                question_text,
                question_type,
                marks,
                answer_key,
                options_json,
                marking_rubric
            FROM questions
            WHERE exam_id = ?
            ORDER BY id ASC
            """,
            (exam_id,),
        ).fetchall()

    questions = []

    for row in rows:
        question = dict(row)

        try:
            question["options_json"] = (
                json.loads(question["options_json"])
                if question["options_json"]
                else {}
            )
        except (json.JSONDecodeError, TypeError):
            question["options_json"] = {}

        questions.append(question)

    return render_template(
        "exam_details.html",
        exam=exam,
        questions=questions,
    )


# -------------------- CREATE EXAM --------------------

@app.route("/teacher/create-exam", methods=["GET", "POST"])
@role_required("teacher")
def create_exam():
    if request.method == "GET":
        return render_template("create_exam.html")

    title = request.form.get("title", "").strip()
    subject = request.form.get("subject", "").strip()

    try:
        total_marks = float(request.form.get("total_marks", "0"))
    except (TypeError, ValueError):
        flash("Please enter valid total marks.")
        return redirect(url_for("create_exam"))

    if (
        not title
        or len(title) > 150
        or not subject
        or len(subject) > 100
        or not (0 < total_marks <= 10000)
    ):
        flash("Please enter valid exam details.")
        return redirect(url_for("create_exam"))

    types = request.form.getlist("question_type")
    texts = request.form.getlist("question_text")
    marks_values = request.form.getlist("marks")

    if not texts or not (
        len(types) == len(texts) == len(marks_values)
    ):
        flash("Please add at least one complete question.")
        return redirect(url_for("create_exam"))

    option_lists = {
        letter: request.form.getlist(f"option_{letter.lower()}")
        for letter in ("A", "B", "C", "D")
    }

    correct_options = request.form.getlist("correct_option")
    answers = request.form.getlist("answer_key")
    rubrics = request.form.getlist("marking_rubric")

    questions = []
    total_question_marks = 0
    mcq_index = 0
    descriptive_index = 0

    for i, (q_type, text, mark_value) in enumerate(
        zip(types, texts, marks_values), start=1
    ):
        text = text.strip()

        try:
            marks = float(mark_value)
        except (TypeError, ValueError):
            flash(f"Invalid marks for question {i}.")
            return redirect(url_for("create_exam"))

        if (
            not text
            or len(text) > 10000
            or not (0 < marks <= total_marks)
        ):
            flash(f"Please check question {i} and its marks.")
            return redirect(url_for("create_exam"))

        question = {
            "type": q_type,
            "text": text,
            "marks": marks,
            "answer_key": "",
            "options_json": None,
            "rubric": None,
        }

        if q_type == "mcq":
            if any(
                mcq_index >= len(option_lists[letter])
                for letter in ("A", "B", "C", "D")
            ):
                flash(f"Please complete all options for question {i}.")
                return redirect(url_for("create_exam"))

            options = {
                letter: option_lists[letter][mcq_index].strip()
                for letter in ("A", "B", "C", "D")
            }

            if any(not option for option in options.values()):
                flash(f"Please complete all options for question {i}.")
                return redirect(url_for("create_exam"))

            if mcq_index >= len(correct_options):
                flash(f"Please select the correct answer for question {i}.")
                return redirect(url_for("create_exam"))

            correct = correct_options[mcq_index]

            if correct not in options:
                flash(f"Invalid correct option for question {i}.")
                return redirect(url_for("create_exam"))

            question["answer_key"] = correct
            question["options_json"] = json.dumps(options)
            mcq_index += 1

        elif q_type == "descriptive":
            if descriptive_index >= len(answers):
                flash(f"Please enter the reference answer for question {i}.")
                return redirect(url_for("create_exam"))

            answer = answers[descriptive_index].strip()

            rubric = (
                rubrics[descriptive_index].strip()
                if descriptive_index < len(rubrics)
                else ""
            )

            if (
                not answer
                or len(answer) > 20000
                or len(rubric) > 10000
            ):
                flash(f"Please check the reference answer for question {i}.")
                return redirect(url_for("create_exam"))

            question["answer_key"] = answer
            question["rubric"] = rubric or None
            descriptive_index += 1

        else:
            flash(f"Invalid question type for question {i}.")
            return redirect(url_for("create_exam"))

        total_question_marks += marks
        questions.append(question)

    if (
        mcq_index != len(correct_options)
        or descriptive_index != len(answers)
    ):
        flash("Please check your question answers.")
        return redirect(url_for("create_exam"))

    if abs(total_question_marks - total_marks) > 0.001:
        flash("Question marks must add up to the exam total.")
        return redirect(url_for("create_exam"))

    try:
        with get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO exams (
                    title, subject, teacher_id, total_marks
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    title,
                    subject,
                    session["user_id"],
                    total_marks,
                ),
            )

            exam_id = cursor.lastrowid

            for question in questions:
                connection.execute(
                    """
                    INSERT INTO questions (
                        exam_id,
                        question_text,
                        question_type,
                        marks,
                        answer_key,
                        options_json,
                        marking_rubric
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        exam_id,
                        question["text"],
                        question["type"],
                        question["marks"],
                        question["answer_key"],
                        question["options_json"],
                        question["rubric"],
                    ),
                )

    except sqlite3.Error:
        app.logger.exception("Failed to save exam")
        flash("Could not save the exam. Please try again.")
        return redirect(url_for("create_exam"))

    flash("Exam and answer keys saved successfully.")
    return redirect(url_for("my_exams"))


# -------------------- TEACHER RESULTS --------------------

@app.route("/teacher/results")
@role_required("teacher")
def teacher_results():
    return "Teacher Results page is coming soon."


# -------------------- START APPLICATION --------------------

if __name__ == "__main__":
    initialize_database()
    app.run(debug=True)

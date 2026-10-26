
import os
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


# -------------------- PUBLIC PAGES --------------------

@app.route("/")
@app.route("/home")
def home_page():
    return render_template("index.html")


@app.route("/health")
def health():
    return jsonify({"status": "healthy"})


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
            ORDER BY created_at DESC
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


# -------------------- PLACEHOLDER ROUTES --------------------
# These pages will be implemented in upcoming steps.

@app.route("/teacher/exams")
@role_required("teacher")
def my_exams():
    return "My Exams page is coming soon."


@app.route("/teacher/create-exam")
@role_required("teacher")
def create_exam():
    return "Create Exam page is coming soon."


@app.route("/teacher/results")
@role_required("teacher")
def teacher_results():
    return "Teacher Results page is coming soon."


# -------------------- START APPLICATION --------------------

if __name__ == "__main__":
    initialize_database()
    app.run(debug=True)

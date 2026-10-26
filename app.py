from flask import render_template
from flask import Flask, jsonify, request
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_connection, initialize_database

app = Flask(__name__)

# Set a real secret key in an environment variable before deployment.
app.config["SECRET_KEY"] = "dev-only-change-this-secret"


@app.route("/")
def home():
    return jsonify({
        "project": "AI Exam Scanner",
        "status": "running"
    })


@app.route("/health")
def health():
    return jsonify({"status": "healthy"})


@app.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}

    name = data.get("name", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    role = data.get("role", "").strip().lower()

    if not name or not email or not password:
        return jsonify({"error": "Name, email and password are required"}), 400

    if role not in ("student", "teacher"):
        return jsonify({"error": "Role must be student or teacher"}), 400

    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    try:
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO users (name, email, password_hash, role)
                VALUES (?, ?, ?, ?)
                """,
                (name, email, generate_password_hash(password), role)
            )

        return jsonify({"message": "Account created successfully"}), 201

    except Exception as error:
        # Avoid exposing database details to the client.
        if "UNIQUE constraint failed" in str(error):
            return jsonify({"error": "An account with this email already exists"}), 409
        app.logger.exception("Registration failed")
        return jsonify({"error": "Could not create account"}), 500


@app.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}

    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    with get_connection() as connection:
        user = connection.execute(
            "SELECT id, name, email, password_hash, role FROM users WHERE email = ?",
            (email,)
        ).fetchone()

    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Invalid email or password"}), 401

    return jsonify({
        "message": "Login successful",
        "user": {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
            "role": user["role"]
        }
    })

@app.route("/home")
def home_page():
    return render_template("index.html")
if __name__ == "__main__":
    initialize_database()
    app.run(debug=True)

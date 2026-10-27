
import sqlite3
from pathlib import Path

DATABASE_PATH = Path(__file__).parent / "exam_scanner.db"


def get_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database():
    with get_connection() as connection:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL
                    CHECK (role IN ('student', 'teacher')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS exams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                subject TEXT NOT NULL,
                teacher_id INTEGER NOT NULL,
                total_marks REAL NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (teacher_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exam_id INTEGER NOT NULL,
                question_text TEXT NOT NULL,
                question_type TEXT NOT NULL
                    CHECK (question_type IN ('mcq', 'descriptive')),
                marks REAL NOT NULL,
                answer_key TEXT NOT NULL,
                options_json TEXT,
                marking_rubric TEXT,
                FOREIGN KEY (exam_id) REFERENCES exams(id)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exam_id INTEGER NOT NULL,
                student_id INTEGER NOT NULL,
                file_path TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'uploaded'
                    CHECK (status IN (
                        'uploaded',
                        'processing',
                        'review_required',
                        'evaluated',
                        'failed'
                    )),
                total_marks_awarded REAL,
                submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (exam_id) REFERENCES exams(id),
                FOREIGN KEY (student_id) REFERENCES users(id),
                UNIQUE (exam_id, student_id)
            );

            CREATE TABLE IF NOT EXISTS evaluated_answers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                submission_id INTEGER NOT NULL,
                question_id INTEGER NOT NULL,
                extracted_text TEXT,
                marks_awarded REAL,
                feedback TEXT,
                needs_review INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (submission_id) REFERENCES submissions(id)
                    ON DELETE CASCADE,
                FOREIGN KEY (question_id) REFERENCES questions(id),
                UNIQUE (submission_id, question_id)
            );
        """)

        # Safely update existing databases without deleting user accounts.
        question_columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(questions)"
            ).fetchall()
        }

        if "options_json" not in question_columns:
            connection.execute(
                "ALTER TABLE questions ADD COLUMN options_json TEXT"
            )

        if "marking_rubric" not in question_columns:
            connection.execute(
                "ALTER TABLE questions ADD COLUMN marking_rubric TEXT"
            )

    print(f"Database initialized at: {DATABASE_PATH}")


if __name__ == "__main__":
    initialize_database()

    with get_connection() as connection:
        tables = connection.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """).fetchall()

    print("Available tables:")
    for table in tables:
        print(f"- {table['name']}")

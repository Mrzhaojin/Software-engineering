import sqlite3
from flask import current_app, g


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def _column_names(db, table):
    return {row["name"] for row in db.execute(f"PRAGMA table_info({table})").fetchall()}


def _migrate(db):
    """Upgrade a baseline-v1 database in place (no table rebuild)."""
    student_columns = _column_names(db, "students")
    if "grade" not in student_columns:
        db.execute("ALTER TABLE students ADD COLUMN grade INTEGER NOT NULL DEFAULT 1")
    activity_columns = _column_names(db, "activities")
    if "grade_limited" not in activity_columns:
        db.execute("ALTER TABLE activities ADD COLUMN grade_limited INTEGER NOT NULL DEFAULT 0")
    db.execute("PRAGMA user_version = 2")


def init_db():
    db = get_db()
    with current_app.open_resource("schema.sql") as f:
        db.executescript(f.read().decode("utf-8"))
    _migrate(db)
    demo_students = [
        ("S001", "张三", 2),
        ("S002", "李四", 1),
        ("S003", "王五", 3),
        ("S004", "赵六", 4),
    ]
    db.executemany(
        "INSERT OR IGNORE INTO students(student_id, name, grade) VALUES (?, ?, ?)",
        demo_students,
    )
    db.executemany(
        "UPDATE students SET grade = ? WHERE student_id = ?",
        [(grade, student_id) for student_id, _, grade in demo_students],
    )
    db.commit()


def init_app(app):
    app.teardown_appcontext(close_db)
    with app.app_context():
        init_db()
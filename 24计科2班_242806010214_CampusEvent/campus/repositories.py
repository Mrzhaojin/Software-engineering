from datetime import datetime
import sqlite3


def _now():
    return datetime.now().isoformat(timespec="seconds")


class StudentRepository:
    def __init__(self, db):
        self.db = db

    def find_by_id(self, student_id):
        return self.db.execute(
            "SELECT * FROM students WHERE student_id = ?", (student_id,)
        ).fetchone()


class ActivityRepository:
    def __init__(self, db):
        self.db = db

    def find_by_id(self, activity_id):
        return self.db.execute(
            "SELECT * FROM activities WHERE activity_id = ?", (activity_id,)
        ).fetchone()

    def save(self, activity):
        existing = self.find_by_id(activity["activity_id"])
        if existing is None:
            self.db.execute(
                """INSERT INTO activities
                   (activity_id, title, category, start_at, location, capacity, policy_type, grade_limited, deleted_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    activity["activity_id"], activity["title"], activity["category"],
                    activity["start_at"], activity["location"], activity["capacity"],
                    activity["policy_type"], activity.get("grade_limited", 0),
                    activity.get("deleted_at"),
                ),
            )
        else:
            self.db.execute(
                """UPDATE activities
                   SET title=?, category=?, start_at=?, location=?, capacity=?, policy_type=?,
                       grade_limited=?, deleted_at=?
                   WHERE activity_id=?""",
                (
                    activity["title"], activity["category"], activity["start_at"],
                    activity["location"], activity["capacity"], activity["policy_type"],
                    activity.get("grade_limited", 0), activity.get("deleted_at"),
                    activity["activity_id"],
                ),
            )

    def list_active(self, name=None):
        if name:
            return self.db.execute(
                "SELECT * FROM activities WHERE deleted_at IS NULL AND title LIKE ? ORDER BY start_at",
                (f"%{name}%",),
            ).fetchall()
        return self.db.execute(
            "SELECT * FROM activities WHERE deleted_at IS NULL ORDER BY start_at"
        ).fetchall()

    def soft_delete(self, activity_id):
        cur = self.db.execute(
            "UPDATE activities SET deleted_at = ? WHERE activity_id = ? AND deleted_at IS NULL",
            (_now(), activity_id),
        )
        return cur.rowcount == 1


class RegistrationRepository:
    def __init__(self, db):
        self.db = db

    def find_by_id(self, registration_id):
        return self.db.execute(
            "SELECT * FROM registrations WHERE registration_id = ?", (registration_id,)
        ).fetchone()

    def find_active(self, student_id, activity_id):
        return self.db.execute(
            """SELECT * FROM registrations
               WHERE student_id = ? AND activity_id = ? AND status IN ('PENDING', 'APPROVED')""",
            (student_id, activity_id),
        ).fetchone()

    def save(self, registration):
        existing = self.find_by_id(registration["registration_id"])
        if existing is None:
            self.db.execute(
                """INSERT INTO registrations
                   (registration_id, activity_id, student_id, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    registration["registration_id"], registration["activity_id"],
                    registration["student_id"], registration["status"],
                    registration["created_at"], registration["updated_at"],
                ),
            )
        else:
            self.db.execute(
                "UPDATE registrations SET status = ?, updated_at = ? WHERE registration_id = ?",
                (registration["status"], registration["updated_at"], registration["registration_id"]),
            )

    def count_approved(self, activity_id):
        row = self.db.execute(
            "SELECT COUNT(*) AS n FROM registrations WHERE activity_id = ? AND status = 'APPROVED'",
            (activity_id,),
        ).fetchone()
        return row["n"]

    def count_pending(self, activity_id):
        row = self.db.execute(
            "SELECT COUNT(*) AS n FROM registrations WHERE activity_id = ? AND status = 'PENDING'",
            (activity_id,),
        ).fetchone()
        return row["n"]

    def confirm_approval(self, registration_id, capacity):
        cur = self.db.execute(
            """UPDATE registrations
               SET status = 'APPROVED', updated_at = ?
               WHERE registration_id = ?
                 AND status = 'PENDING'
                 AND (SELECT COUNT(*) FROM registrations r2
                      WHERE r2.activity_id = registrations.activity_id
                        AND r2.status = 'APPROVED') < ?""",
            (_now(), registration_id, capacity),
        )
        return cur.rowcount == 1

    def list_by_student(self, student_id):
        return self.db.execute(
            """SELECT r.*, a.title AS activity_title, a.start_at AS activity_start_at
               FROM registrations r JOIN activities a ON a.activity_id = r.activity_id
               WHERE r.student_id = ? ORDER BY r.created_at DESC""",
            (student_id,),
        ).fetchall()

    def list_pending(self):
        return self.db.execute(
            """SELECT r.*, a.title AS activity_title, a.capacity AS activity_capacity,
                      s.name AS student_name
               FROM registrations r
               JOIN activities a ON a.activity_id = r.activity_id
               JOIN students s ON s.student_id = r.student_id
               WHERE r.status = 'PENDING'
               ORDER BY r.created_at""",
        ).fetchall()

    def list_reviewed(self):
        return self.db.execute(
            """SELECT r.*, a.title AS activity_title, s.name AS student_name
               FROM registrations r
               JOIN activities a ON a.activity_id = r.activity_id
               JOIN students s ON s.student_id = r.student_id
               WHERE r.status IN ('APPROVED', 'REJECTED')
               ORDER BY r.updated_at DESC""",
        ).fetchall()

    def list_by_activity(self, activity_id):
        return self.db.execute(
            """SELECT r.*, s.name AS student_name
               FROM registrations r
               JOIN students s ON s.student_id = r.student_id
               WHERE r.activity_id = ?
               ORDER BY r.created_at""",
            (activity_id,),
        ).fetchall()


class MessageRepository:
    def __init__(self, db):
        self.db = db

    def save(self, message):
        cur = self.db.execute(
            """INSERT OR IGNORE INTO messages
               (message_id, student_id, activity_id, content, created_at, is_read, event_key)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                message["message_id"], message["student_id"], message["activity_id"],
                message["content"], message["created_at"], message.get("is_read", 0),
                message["event_key"],
            ),
        )
        return cur.rowcount == 1

    def list_by_student(self, student_id):
        return self.db.execute(
            """SELECT m.*, a.title AS activity_title
               FROM messages m JOIN activities a ON a.activity_id = m.activity_id
               WHERE m.student_id = ? ORDER BY m.created_at DESC""",
            (student_id,),
        ).fetchall()

    def mark_read(self, message_id, student_id):
        cur = self.db.execute(
            "UPDATE messages SET is_read = 1 WHERE message_id = ? AND student_id = ?",
            (message_id, student_id),
        )
        return cur.rowcount == 1

class EmailLogRepository:
    def __init__(self, db):
        self.db = db

    def find_by_event_key(self, event_key):
        return self.db.execute(
            "SELECT * FROM email_logs WHERE event_key = ?", (event_key,)
        ).fetchone()

    def save(self, log):
        self.db.execute(
            """INSERT OR IGNORE INTO email_logs
               (log_id, registration_id, event_type, recipient, subject, content,
                status, error, created_at, event_key)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                log["log_id"], log["registration_id"], log["event_type"],
                log["recipient"], log["subject"], log["content"], log["status"],
                log.get("error"), log["created_at"], log["event_key"],
            ),
        )

    def list(self):
        return self.db.execute(
            "SELECT * FROM email_logs ORDER BY created_at DESC"
        ).fetchall()

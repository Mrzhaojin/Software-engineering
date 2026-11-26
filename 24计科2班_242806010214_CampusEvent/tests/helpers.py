from campus.db import get_db

PASSWORDS = {"admin": "admin123", "S001": "123456", "S002": "123456", "S003": "123456", "S004": "123456"}


def login(client, username):
    client.get("/logout")
    return client.post("/login", data={"username": username, "password": PASSWORDS[username]}, follow_redirects=True)


def create_activity(app, client, title, capacity=2, policy_type="direct", start_at="2030-01-01T10:00", grade_limited=0):
    login(client, "admin")
    resp = client.post("/activities/new", data={
        "title": title,
        "category": "讲座",
        "start_at": start_at,
        "location": "报告厅",
        "capacity": str(capacity),
        "policy_type": policy_type,
        "grade_limited": "1" if grade_limited else "",
    }, follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        row = get_db().execute("SELECT activity_id FROM activities WHERE title = ?", (title,)).fetchone()
        assert row is not None
        return row["activity_id"]


def fetch_one(app, sql, params=()):
    with app.app_context():
        return get_db().execute(sql, params).fetchone()


def fetch_all(app, sql, params=()):
    with app.app_context():
        return get_db().execute(sql, params).fetchall()


def set_start_at(app, activity_id, start_at):
    with app.app_context():
        db = get_db()
        db.execute("UPDATE activities SET start_at = ? WHERE activity_id = ?", (start_at, activity_id))
        db.commit()


def message_count(app, student_id):
    row = fetch_one(app, "SELECT COUNT(*) AS n FROM messages WHERE student_id = ?", (student_id,))
    return row["n"]

def email_logs(app, student_id=None):
    if student_id:
        return fetch_all(app, "SELECT * FROM email_logs WHERE recipient = ? ORDER BY created_at", (f"{student_id}@campus.demo",))
    return fetch_all(app, "SELECT * FROM email_logs ORDER BY created_at")

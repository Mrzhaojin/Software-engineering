import os
import sqlite3
import uuid

from campus import create_app
from campus.db import get_db
from tests.helpers import login, create_activity, fetch_one, fetch_all, set_start_at, message_count, email_logs


def test_login_required(client):
    resp = client.get("/activities")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_create_activity_c1(app, client):
    activity_id = create_activity(app, client, "直接报名活动A", capacity=2)
    row = fetch_one(app, "SELECT * FROM activities WHERE activity_id = ?", (activity_id,))
    assert row["title"] == "直接报名活动A"
    assert row["capacity"] == 2
    assert row["policy_type"] == "direct"
    assert row["deleted_at"] is None


def test_direct_signup_and_message_c2(app, client):
    activity_id = create_activity(app, client, "直接报名B", capacity=2)
    login(client, "S001")
    resp = client.post(f"/activities/{activity_id}/register", follow_redirects=True)
    assert resp.status_code == 200
    reg = fetch_one(app, "SELECT * FROM registrations WHERE activity_id = ? AND student_id = 'S001'", (activity_id,))
    assert reg["status"] == "APPROVED"
    assert message_count(app, "S001") == 1


def test_duplicate_signup_c3(app, client):
    activity_id = create_activity(app, client, "直接报名C", capacity=3)
    login(client, "S001")
    client.post(f"/activities/{activity_id}/register", follow_redirects=True)
    client.post(f"/activities/{activity_id}/register", follow_redirects=True)
    rows = fetch_all(app, "SELECT * FROM registrations WHERE activity_id = ? AND student_id = 'S001'", (activity_id,))
    assert len(rows) == 1


def test_capacity_full_c4(app, client):
    activity_id = create_activity(app, client, "容量活动", capacity=2)
    login(client, "S001")
    client.post(f"/activities/{activity_id}/register", follow_redirects=True)
    login(client, "S002")
    client.post(f"/activities/{activity_id}/register", follow_redirects=True)
    login(client, "S003")
    client.post(f"/activities/{activity_id}/register", follow_redirects=True)
    approved = fetch_one(app, "SELECT COUNT(*) AS n FROM registrations WHERE activity_id = ? AND status = 'APPROVED'", (activity_id,))
    assert approved["n"] == 2
    s3 = fetch_one(app, "SELECT * FROM registrations WHERE activity_id = ? AND student_id = 'S003'", (activity_id,))
    assert s3 is None


def test_audit_pending_c5(app, client):
    activity_id = create_activity(app, client, "审核活动", capacity=2, policy_type="audit")
    login(client, "S001")
    client.post(f"/activities/{activity_id}/register", follow_redirects=True)
    reg = fetch_one(app, "SELECT * FROM registrations WHERE activity_id = ? AND student_id = 'S001'", (activity_id,))
    assert reg["status"] == "PENDING"
    assert message_count(app, "S001") == 1


def test_approve_c6(app, client):
    activity_id = create_activity(app, client, "审核批准", capacity=2, policy_type="audit")
    login(client, "S001")
    client.post(f"/activities/{activity_id}/register", follow_redirects=True)
    reg = fetch_one(app, "SELECT * FROM registrations WHERE activity_id = ? AND student_id = 'S001'", (activity_id,))
    login(client, "admin")
    client.post(f"/admin/registrations/{reg['registration_id']}/approve", follow_redirects=True)
    reg = fetch_one(app, "SELECT * FROM registrations WHERE registration_id = ?", (reg["registration_id"],))
    assert reg["status"] == "APPROVED"
    assert message_count(app, "S001") == 2


def test_reject_c7(app, client):
    activity_id = create_activity(app, client, "审核拒绝", capacity=2, policy_type="audit")
    login(client, "S001")
    client.post(f"/activities/{activity_id}/register", follow_redirects=True)
    reg = fetch_one(app, "SELECT * FROM registrations WHERE activity_id = ? AND student_id = 'S001'", (activity_id,))
    login(client, "admin")
    client.post(f"/admin/registrations/{reg['registration_id']}/reject", follow_redirects=True)
    reg = fetch_one(app, "SELECT * FROM registrations WHERE registration_id = ?", (reg["registration_id"],))
    assert reg["status"] == "REJECTED"
    assert message_count(app, "S001") == 2


def test_approve_full_c8(app, client):
    activity_id = create_activity(app, client, "审核满员", capacity=1, policy_type="audit")
    login(client, "S001")
    client.post(f"/activities/{activity_id}/register", follow_redirects=True)
    login(client, "S002")
    client.post(f"/activities/{activity_id}/register", follow_redirects=True)
    regs = fetch_all(app, "SELECT * FROM registrations WHERE activity_id = ? ORDER BY student_id", (activity_id,))
    assert len(regs) == 2 and all(r["status"] == "PENDING" for r in regs)
    login(client, "admin")
    client.post(f"/admin/registrations/{regs[0]['registration_id']}/approve", follow_redirects=True)
    client.post(f"/admin/registrations/{regs[1]['registration_id']}/approve", follow_redirects=True)
    statuses = fetch_all(app, "SELECT status FROM registrations WHERE activity_id = ?", (activity_id,))
    assert sorted(r["status"] for r in statuses) == ["APPROVED", "PENDING"]


def test_cancel_pending_c9(app, client):
    activity_id = create_activity(app, client, "取消待审核", capacity=2, policy_type="audit")
    login(client, "S001")
    client.post(f"/activities/{activity_id}/register", follow_redirects=True)
    reg = fetch_one(app, "SELECT * FROM registrations WHERE activity_id = ?", (activity_id,))
    client.post(f"/registrations/{reg['registration_id']}/cancel", follow_redirects=True)
    reg = fetch_one(app, "SELECT * FROM registrations WHERE registration_id = ?", (reg["registration_id"],))
    assert reg["status"] == "CANCELLED"


def test_cancel_approved_before_start(app, client):
    activity_id = create_activity(app, client, "直接报名可取消", capacity=2)
    login(client, "S001")
    client.post(f"/activities/{activity_id}/register", follow_redirects=True)
    reg = fetch_one(app, "SELECT * FROM registrations WHERE activity_id = ?", (activity_id,))
    client.post(f"/registrations/{reg['registration_id']}/cancel", follow_redirects=True)
    reg = fetch_one(app, "SELECT * FROM registrations WHERE registration_id = ?", (reg["registration_id"],))
    assert reg["status"] == "CANCELLED"


def test_cancel_after_start_approved_denied(app, client):
    activity_id = create_activity(app, client, "已开始已通过", capacity=2)
    login(client, "S001")
    client.post(f"/activities/{activity_id}/register", follow_redirects=True)
    reg = fetch_one(app, "SELECT * FROM registrations WHERE activity_id = ?", (activity_id,))
    set_start_at(app, activity_id, "2020-01-01T10:00")
    client.post(f"/registrations/{reg['registration_id']}/cancel", follow_redirects=True)
    reg = fetch_one(app, "SELECT * FROM registrations WHERE registration_id = ?", (reg["registration_id"],))
    assert reg["status"] == "APPROVED"


def test_cancel_after_start_pending_allowed(app, client):
    activity_id = create_activity(app, client, "已开始待审核", capacity=2, policy_type="audit")
    login(client, "S001")
    client.post(f"/activities/{activity_id}/register", follow_redirects=True)
    reg = fetch_one(app, "SELECT * FROM registrations WHERE activity_id = ?", (activity_id,))
    set_start_at(app, activity_id, "2020-01-01T10:00")
    client.post(f"/registrations/{reg['registration_id']}/cancel", follow_redirects=True)
    reg = fetch_one(app, "SELECT * FROM registrations WHERE registration_id = ?", (reg["registration_id"],))
    assert reg["status"] == "CANCELLED"


def test_persistence_c10(app, client):
    activity_id = create_activity(app, client, "持久化活动", capacity=2)
    login(client, "S001")
    client.post(f"/activities/{activity_id}/register", follow_redirects=True)
    from campus import create_app
    app2 = create_app({"TESTING": True, "DATABASE": app.config["DATABASE"], "SECRET_KEY": "test"})
    with app2.app_context():
        from campus.db import get_db
        row = get_db().execute("SELECT * FROM registrations WHERE activity_id = ?", (activity_id,)).fetchone()
        assert row is not None and row["status"] == "APPROVED"


def test_soft_delete_hides_and_blocks_signup(app, client):
    activity_id = create_activity(app, client, "待下线活动", capacity=2)
    login(client, "admin")
    client.post(f"/activities/{activity_id}/delete", follow_redirects=True)
    row = fetch_one(app, "SELECT * FROM activities WHERE activity_id = ?", (activity_id,))
    assert row["deleted_at"] is not None
    login(client, "S001")
    resp = client.post(f"/activities/{activity_id}/register", follow_redirects=True)
    assert resp.status_code == 200
    reg = fetch_one(app, "SELECT * FROM registrations WHERE activity_id = ? AND student_id = 'S001'", (activity_id,))
    assert reg is None


def test_activity_validation(app, client):
    login(client, "admin")
    resp = client.post("/activities/new", data={
        "title": "", "category": "", "start_at": "bad", "location": "",
        "capacity": "0", "policy_type": "direct",
    }, follow_redirects=True)
    assert resp.status_code == 200
    row = fetch_one(app, "SELECT COUNT(*) AS n FROM activities")
    assert row["n"] == 0


def test_message_read(app, client):
    activity_id = create_activity(app, client, "消息活动", capacity=2)
    login(client, "S001")
    client.post(f"/activities/{activity_id}/register", follow_redirects=True)
    msg = fetch_one(app, "SELECT * FROM messages WHERE student_id = 'S001'")
    client.post(f"/messages/{msg['message_id']}/read", follow_redirects=True)
    msg = fetch_one(app, "SELECT * FROM messages WHERE message_id = ?", (msg["message_id"],))
    assert msg["is_read"] == 1


def test_duplicate_after_cancel_allowed(app, client):
    activity_id = create_activity(app, client, "取消后可再报", capacity=2)
    login(client, "S001")
    client.post(f"/activities/{activity_id}/register", follow_redirects=True)
    reg = fetch_one(app, "SELECT * FROM registrations WHERE activity_id = ?", (activity_id,))
    client.post(f"/registrations/{reg['registration_id']}/cancel", follow_redirects=True)
    client.post(f"/activities/{activity_id}/register", follow_redirects=True)
    rows = fetch_all(app, "SELECT * FROM registrations WHERE activity_id = ? AND student_id = 'S001'", (activity_id,))
    assert len(rows) == 2
    assert sorted(r["status"] for r in rows) == ["APPROVED", "CANCELLED"]


def test_student_cannot_access_admin_pages(app, client):
    login(client, "S001")
    resp = client.get("/admin/pending")
    assert resp.status_code == 302
    resp = client.get("/activities/new")
    assert resp.status_code == 302


def test_activity_filter(app, client):
    create_activity(app, client, "数据结构讲座", capacity=2)
    create_activity(app, client, "数据库实验", capacity=2)
    login(client, "S001")
    resp = client.get("/activities?name=数据结构", follow_redirects=True)
    body = resp.get_data(as_text=True)
    assert "数据结构讲座" in body
    assert "数据库实验" not in body
def test_reviewed_page_lists_approved_and_rejected(app, client):
    activity_id = create_activity(app, client, "已审核记录活动", capacity=2, policy_type="audit")
    login(client, "S001")
    client.post(f"/activities/{activity_id}/register", follow_redirects=True)
    login(client, "S002")
    client.post(f"/activities/{activity_id}/register", follow_redirects=True)
    regs = fetch_all(app, "SELECT * FROM registrations WHERE activity_id = ? ORDER BY student_id", (activity_id,))
    login(client, "admin")
    client.post(f"/admin/registrations/{regs[0]['registration_id']}/approve", follow_redirects=True)
    client.post(f"/admin/registrations/{regs[1]['registration_id']}/reject", follow_redirects=True)
    resp = client.get("/admin/reviewed", follow_redirects=True)
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "张三" in body and "李四" in body
    assert "APPROVED" in body and "REJECTED" in body


def test_stats_shows_participant_details(app, client):
    activity_id = create_activity(app, client, "统计参与详情活动", capacity=2)
    login(client, "S001")
    client.post(f"/activities/{activity_id}/register", follow_redirects=True)
    login(client, "admin")
    resp = client.get(f"/admin/stats?activity_id={activity_id}", follow_redirects=True)
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "参与详情" in body
    assert "张三" in body and "S001" in body and "APPROVED" in body

def test_grade_limited_allows_grade2_and_3(app, client):
    activity_id = create_activity(app, client, "年级限定通过", capacity=10, grade_limited=1)
    login(client, "S001")
    client.post(f"/activities/{activity_id}/register", follow_redirects=True)
    login(client, "S003")
    client.post(f"/activities/{activity_id}/register", follow_redirects=True)
    regs = fetch_all(app, "SELECT * FROM registrations WHERE activity_id = ? ORDER BY student_id", (activity_id,))
    assert [(r["student_id"], r["status"]) for r in regs] == [("S001", "APPROVED"), ("S003", "APPROVED")]


def test_grade_limited_rejects_grade1_and_4(app, client):
    activity_id = create_activity(app, client, "年级限定拒绝", capacity=10, grade_limited=1)
    login(client, "S002")
    resp = client.post(f"/activities/{activity_id}/register", follow_redirects=True)
    assert "仅限大二、大三" in resp.get_data(as_text=True)
    login(client, "S004")
    resp = client.post(f"/activities/{activity_id}/register", follow_redirects=True)
    assert "仅限大二、大三" in resp.get_data(as_text=True)
    regs = fetch_all(app, "SELECT * FROM registrations WHERE activity_id = ?", (activity_id,))
    assert regs == []


def test_grade_limited_still_respects_capacity(app, client):
    activity_id = create_activity(app, client, "年级限定名额", capacity=1, grade_limited=1)
    login(client, "S001")
    client.post(f"/activities/{activity_id}/register", follow_redirects=True)
    login(client, "S003")
    client.post(f"/activities/{activity_id}/register", follow_redirects=True)
    approved = fetch_one(app, "SELECT COUNT(*) AS n FROM registrations WHERE activity_id = ? AND status='APPROVED'", (activity_id,))
    assert approved["n"] == 1


def test_grade_limited_requires_direct_policy(app, client):
    login(client, "admin")
    resp = client.post("/activities/new", data={
        "title": "非法年级限定审核", "category": "讲座", "start_at": "2030-01-01T10:00",
        "location": "报告厅", "capacity": "2", "policy_type": "audit", "grade_limited": "1",
    }, follow_redirects=True)
    assert resp.status_code == 200
    row = fetch_one(app, "SELECT COUNT(*) AS n FROM activities WHERE title = '非法年级限定审核'")
    assert row["n"] == 0


def test_email_logged_for_direct_signup(app, client):
    activity_id = create_activity(app, client, "邮件直接报名", capacity=2)
    login(client, "S001")
    client.post(f"/activities/{activity_id}/register", follow_redirects=True)
    logs = email_logs(app, "S001")
    assert len(logs) == 1
    assert logs[0]["status"] == "SENT"
    assert logs[0]["event_type"] == "SIGNUP_APPROVED"
    assert logs[0]["recipient"] == "S001@campus.demo"
    assert message_count(app, "S001") == 1


def test_email_logged_for_approval_and_rejection(app, client):
    activity_id = create_activity(app, client, "邮件审批", capacity=2, policy_type="audit")
    login(client, "S001")
    client.post(f"/activities/{activity_id}/register", follow_redirects=True)
    login(client, "S002")
    client.post(f"/activities/{activity_id}/register", follow_redirects=True)
    regs = fetch_all(app, "SELECT * FROM registrations WHERE activity_id = ? ORDER BY student_id", (activity_id,))
    login(client, "admin")
    client.post(f"/admin/registrations/{regs[0]['registration_id']}/approve", follow_redirects=True)
    client.post(f"/admin/registrations/{regs[1]['registration_id']}/reject", follow_redirects=True)
    s1 = email_logs(app, "S001")
    s2 = email_logs(app, "S002")
    assert [x["event_type"] for x in s1] == ["APPROVAL_APPROVED"]
    assert [x["event_type"] for x in s2] == ["APPROVAL_REJECTED"]
    assert all(x["status"] == "SENT" for x in s1 + s2)


def test_email_failure_does_not_rollback_registration(app, client):
    app.config["EMAIL_SIMULATE_FAILURE"] = True
    activity_id = create_activity(app, client, "邮件失败不滚回", capacity=2)
    login(client, "S001")
    client.post(f"/activities/{activity_id}/register", follow_redirects=True)
    reg = fetch_one(app, "SELECT * FROM registrations WHERE activity_id = ? AND student_id = 'S001'", (activity_id,))
    assert reg["status"] == "APPROVED"
    logs = email_logs(app, "S001")
    assert len(logs) == 1
    assert logs[0]["status"] == "FAILED"
    assert logs[0]["error"]
    assert message_count(app, "S001") == 1


def test_email_not_duplicated_for_same_event(app, client):
    activity_id = create_activity(app, client, "邮件去重", capacity=2)
    login(client, "S001")
    client.post(f"/activities/{activity_id}/register", follow_redirects=True)
    client.post(f"/activities/{activity_id}/register", follow_redirects=True)
    assert len(email_logs(app, "S001")) == 1
    count = fetch_one(app, "SELECT COUNT(*) AS n FROM registrations WHERE activity_id = ? AND student_id = 'S001'", (activity_id,))
    assert count["n"] == 1


def test_baseline_database_migrates_to_v2():
    db_dir = os.path.join(os.path.dirname(__file__), "_tmp")
    os.makedirs(db_dir, exist_ok=True)
    db_path = os.path.join(db_dir, f"migrate-{uuid.uuid4().hex}.db")
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE students (student_id TEXT PRIMARY KEY, name TEXT NOT NULL);
        CREATE TABLE activities (
            activity_id TEXT PRIMARY KEY, title TEXT NOT NULL, category TEXT NOT NULL,
            start_at TEXT NOT NULL, location TEXT NOT NULL, capacity INTEGER NOT NULL,
            policy_type TEXT NOT NULL CHECK (policy_type IN ('direct', 'audit')),
            deleted_at TEXT
        );
        INSERT INTO students(student_id, name) VALUES ('S001', '张三');
        INSERT INTO activities(activity_id, title, category, start_at, location, capacity, policy_type)
            VALUES ('legacy-act', '旧活动', '讲座', '2030-01-01T10:00', '报告厅', 2, 'direct');
    """)
    conn.commit()
    conn.close()
    app = create_app({"TESTING": True, "DATABASE": db_path, "SECRET_KEY": "test"})
    with app.app_context():
        student_cols = {r["name"] for r in get_db().execute("PRAGMA table_info(students)")}
        activity_cols = {r["name"] for r in get_db().execute("PRAGMA table_info(activities)")}
        tables = {r["name"] for r in get_db().execute("SELECT name FROM sqlite_master WHERE type='table'")}
        legacy = get_db().execute("SELECT * FROM activities WHERE activity_id='legacy-act'").fetchone()
        version = get_db().execute("PRAGMA user_version").fetchone()[0]
    assert "grade" in student_cols
    assert "grade_limited" in activity_cols
    assert "email_logs" in tables
    assert legacy is not None and legacy["grade_limited"] == 0
    assert version == 2

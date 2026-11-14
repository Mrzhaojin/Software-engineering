"""StudyTask 自动化测试：覆盖 SRS FR-01 ~ FR-10 与验收用例 T1 ~ T10。"""
import sys
import uuid
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app, get_db, task_flag

TMP_ROOT = Path(__file__).resolve().parent / "_tmp"


def new_db_path():
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    return TMP_ROOT / f"test_{uuid.uuid4().hex}.db"


def cleanup(db_path):
    for path in TMP_ROOT.glob(db_path.name + "*"):
        try:
            path.unlink()
        except OSError:
            pass


@pytest.fixture
def app():
    db_path = new_db_path()
    application = create_app({"TESTING": True, "DATABASE": str(db_path)})
    yield application
    cleanup(db_path)


@pytest.fixture
def client(app):
    return app.test_client()


def make_task(client, **overrides):
    data = {
        "name": "数据结构作业",
        "course": "数据结构",
        "description": "完成链表实验报告",
        "due_date": (date.today() + timedelta(days=5)).strftime("%Y-%m-%d"),
        "priority": "高",
    }
    data.update(overrides)
    return client.post("/tasks/new", data=data)


def task_id_of(response):
    return int(response.headers["Location"].rsplit("/", 1)[-1])


def count_tasks(app):
    with app.app_context():
        return get_db().execute("SELECT COUNT(*) FROM tasks").fetchone()[0]


def get_task(app, task_id):
    with app.app_context():
        return get_db().execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()


def page(client, path="/"):
    return client.get(path).get_data(as_text=True)


def test_t1_create_and_view(client):
    resp = make_task(client, name="数据结构作业")
    assert resp.status_code == 302
    task_id = task_id_of(resp)
    detail = page(client, f"/tasks/{task_id}")
    assert "数据结构作业" in detail and "数据结构" in detail
    assert "数据结构作业" in page(client)


def test_t2_blank_name_rejected(app, client):
    resp = make_task(client, name="   ")
    assert resp.status_code == 200
    assert "任务名称不能为空" in resp.get_data(as_text=True)
    assert count_tasks(app) == 0


def test_t3_edit_persists(app, client):
    task_id = task_id_of(make_task(client))
    resp = client.post(
        f"/tasks/{task_id}/edit",
        data={
            "name": "数据结构作业（改）",
            "course": "数据结构",
            "description": "改为完成排序实验",
            "due_date": (date.today() + timedelta(days=5)).strftime("%Y-%m-%d"),
            "priority": "低",
            "status": "进行中",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    row = get_task(app, task_id)
    assert row["name"] == "数据结构作业（改）"
    assert row["description"] == "改为完成排序实验"
    assert row["priority"] == "低"
    assert row["status"] == "进行中"
    assert "改为完成排序实验" in page(client, f"/tasks/{task_id}")


def test_t4_status_transitions(app, client):
    task_id = task_id_of(make_task(client))
    for status in ["进行中", "已完成"]:
        client.post(f"/tasks/{task_id}/status", data={"status": status}, follow_redirects=True)
        assert get_task(app, task_id)["status"] == status


def test_t5_filters_combined(client):
    make_task(client, name="任务A", course="数据结构", priority="高")
    make_task(client, name="任务B", course="数据库", priority="中")
    task_c = task_id_of(make_task(client, name="任务C", course="数据结构", priority="高"))
    client.post(f"/tasks/{task_c}/status", data={"status": "已完成"})

    html = page(client, "/?course=数据结构")
    assert "任务A" in html and "任务C" in html and "任务B" not in html

    html = page(client, "/?course=数据结构&status=待完成&priority=高")
    assert "任务A" in html
    assert "任务B" not in html and "任务C" not in html

    html = page(client, "/?status=已完成")
    assert "任务C" in html and "任务A" not in html and "任务B" not in html

    html = page(client, "/?priority=中")
    assert "任务B" in html and "任务A" not in html


def test_t6_overdue_marker(client):
    make_task(
        client,
        name="逾期任务",
        due_date=(date.today() - timedelta(days=1)).strftime("%Y-%m-%d"),
    )
    assert "逾期" in page(client)


def test_t6_completed_has_no_marker():
    today = date(2026, 11, 13)
    assert task_flag({"status": "已完成", "due_date": "2026-11-01"}, today) is None


def test_t7_due_soon_marker(client):
    make_task(
        client,
        name="即将到期任务",
        due_date=(date.today() + timedelta(days=1)).strftime("%Y-%m-%d"),
    )
    assert "即将到期" in page(client)


def test_t8_stats(client):
    ids = [task_id_of(make_task(client, name=f"任务{i}")) for i in range(5)]
    for task_id in ids[:2]:
        client.post(f"/tasks/{task_id}/status", data={"status": "已完成"})
    html = page(client)
    assert '<span class="stat-value">5</span>' in html
    assert '<span class="stat-value">2</span>' in html
    assert '<span class="stat-value">40%</span>' in html


def test_t8_empty_stats(client):
    html = page(client)
    assert '<span class="stat-value">0</span>' in html
    assert '<span class="stat-value">0%</span>' in html
    assert "没有符合条件的任务" in html


def test_t9_delete(app, client):
    task_id = task_id_of(make_task(client, name="待删除任务"))
    resp = client.post(f"/tasks/{task_id}/delete")
    assert resp.status_code == 302
    assert count_tasks(app) == 0
    assert client.get(f"/tasks/{task_id}").status_code == 404


def test_t10_persistence():
    db_path = new_db_path()
    try:
        app1 = create_app({"TESTING": True, "DATABASE": str(db_path)})
        make_task(app1.test_client(), name="重启后仍在的任务")
        app2 = create_app({"TESTING": True, "DATABASE": str(db_path)})
        assert "重启后仍在的任务" in app2.test_client().get("/").get_data(as_text=True)
    finally:
        cleanup(db_path)


@pytest.mark.parametrize(
    "field,value,message",
    [
        ("due_date", "2026-02-30", "截止日期格式"),
        ("priority", "紧急", "优先级只能"),
        ("course", "", "所属课程不能为空"),
    ],
)
def test_validation_errors(app, client, field, value, message):
    resp = make_task(client, **{field: value})
    assert resp.status_code == 200
    assert message in resp.get_data(as_text=True)
    assert count_tasks(app) == 0


def test_length_limits(client):
    assert "不能超过 100 字" in make_task(client, name="名" * 101).get_data(as_text=True)
    assert "不能超过 60 字" in make_task(client, course="课" * 61).get_data(as_text=True)
    assert "不能超过 1000 字" in make_task(client, description="描" * 1001).get_data(as_text=True)


def test_optional_description(client):
    assert make_task(client, description="").status_code == 302


def test_unknown_task_returns_404(client):
    resp = client.get("/tasks/999")
    assert resp.status_code == 404
    assert "不存在" in resp.get_data(as_text=True)


def test_invalid_status_update_rejected(client):
    task_id = task_id_of(make_task(client))
    resp = client.post(f"/tasks/{task_id}/status", data={"status": "未知状态"})
    assert resp.status_code == 400


def test_flag_logic():
    today = date(2026, 11, 13)

    def task(status, due):
        return {"status": status, "due_date": due}

    assert task_flag(task("待完成", "2026-11-12"), today) == "overdue"
    assert task_flag(task("进行中", "2026-11-13"), today) == "soon"
    assert task_flag(task("待完成", "2026-11-16"), today) == "soon"
    assert task_flag(task("待完成", "2026-11-17"), today) is None
    assert task_flag(task("已完成", "2026-11-01"), today) is None

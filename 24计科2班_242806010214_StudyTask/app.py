"""StudyTask：个人学习任务管理系统（《软件工程》实验一）。

技术边界：Python + Flask + SQLite，单用户本地运行。
"""
import os
import re
import sqlite3
from datetime import date, datetime, timedelta

from flask import Flask, abort, current_app, g, redirect, render_template, request, url_for

STATUSES = ["待完成", "进行中", "已完成"]
PRIORITIES = ["高", "中", "低"]
DATE_FORMAT = "%Y-%m-%d"
SOON_DAYS = 3

# 单行字段（名称、课程）不允许换行/制表等控制字符；描述允许多行。
INVALID_SINGLE_LINE = re.compile(r"[\x00-\x1f\x7f]")
INVALID_DESCRIPTION = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def get_db():
    """获取当前请求/应用上下文内的数据库连接。"""
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app):
    """按 schema.sql 建表（可重复执行）。"""
    schema_path = os.path.join(app.root_path, "schema.sql")
    with open(schema_path, encoding="utf-8") as f:
        script = f.read()
    with app.app_context():
        db = get_db()
        db.executescript(script)
        db.commit()


def task_flag(task, today=None):
    """返回任务提醒标记：overdue（逾期）/ soon（即将到期）/ None。

    规则：已完成任务不提示；截止日期早于今天为逾期；今天起 3 天内到期为即将到期。
    """
    if task["status"] == "已完成":
        return None
    today = today or date.today()
    due = datetime.strptime(task["due_date"], DATE_FORMAT).date()
    if due < today:
        return "overdue"
    if due <= today + timedelta(days=SOON_DAYS):
        return "soon"
    return None


def validate_task(form):
    """校验并规范化表单数据，返回 (data, errors)。"""
    data = {
        "name": (form.get("name") or "").strip(),
        "course": (form.get("course") or "").strip(),
        "description": (form.get("description") or "").strip(),
        "due_date": (form.get("due_date") or "").strip(),
        "priority": (form.get("priority") or "中").strip(),
        "status": (form.get("status") or "待完成").strip(),
    }
    errors = []
    if not data["name"]:
        errors.append("任务名称不能为空。")
    elif len(data["name"]) > 100:
        errors.append("任务名称不能超过 100 字。")
    if not data["course"]:
        errors.append("所属课程不能为空。")
    elif len(data["course"]) > 60:
        errors.append("所属课程不能超过 60 字。")
    if INVALID_SINGLE_LINE.search(data["name"]):
        errors.append("任务名称包含换行或控制字符。")
    if INVALID_SINGLE_LINE.search(data["course"]):
        errors.append("所属课程包含换行或控制字符。")
    if len(data["description"]) > 1000:
        errors.append("任务描述不能超过 1000 字。")
    if INVALID_DESCRIPTION.search(data["description"]):
        errors.append("任务描述包含非法控制字符。")
    if not data["due_date"]:
        errors.append("截止日期不能为空。")
    else:
        try:
            datetime.strptime(data["due_date"], DATE_FORMAT)
        except ValueError:
            errors.append("截止日期格式应为 YYYY-MM-DD。")
    if data["priority"] not in PRIORITIES:
        errors.append("优先级只能是：高、中、低。")
    if data["status"] not in STATUSES:
        errors.append("状态只能是：待完成、进行中、已完成。")
    return data, errors


def get_task_or_404(task_id):
    task = get_db().execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if task is None:
        abort(404)
    return task


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE=os.environ.get("STUDYTASK_DB", os.path.join(app.root_path, "studytask.db")),
    )
    if test_config:
        app.config.update(test_config)

    app.teardown_appcontext(close_db)
    init_db(app)

    @app.route("/")
    def index():
        filters = {
            "course": (request.args.get("course") or "").strip(),
            "status": (request.args.get("status") or "").strip(),
            "priority": (request.args.get("priority") or "").strip(),
        }
        sql = "SELECT * FROM tasks WHERE 1 = 1"
        params = []
        if filters["course"]:
            sql += " AND course = ?"
            params.append(filters["course"])
        if filters["status"]:
            sql += " AND status = ?"
            params.append(filters["status"])
        if filters["priority"]:
            sql += " AND priority = ?"
            params.append(filters["priority"])
        sql += " ORDER BY due_date ASC, id ASC"

        db = get_db()
        today = date.today()
        tasks = []
        for row in db.execute(sql, params).fetchall():
            item = dict(row)
            item["flag"] = task_flag(item, today)
            tasks.append(item)

        total = db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        completed = db.execute(
            "SELECT COUNT(*) FROM tasks WHERE status = '已完成'"
        ).fetchone()[0]
        rate = round(completed * 100 / total) if total else 0
        courses = [
            row[0]
            for row in db.execute(
                "SELECT DISTINCT course FROM tasks ORDER BY course"
            ).fetchall()
        ]
        return render_template(
            "index.html",
            tasks=tasks,
            filters=filters,
            courses=courses,
            statuses=STATUSES,
            priorities=PRIORITIES,
            stats={"total": total, "completed": completed, "rate": rate},
        )

    @app.route("/tasks/new", methods=["GET", "POST"])
    def new_task():
        if request.method == "POST":
            data, errors = validate_task(request.form)
            db = get_db()
            if not errors:
                duplicate = db.execute(
                    "SELECT id FROM tasks WHERE name = ? AND course = ? "
                    "AND description = ? AND due_date = ? AND priority = ? LIMIT 1",
                    (
                        data["name"],
                        data["course"],
                        data["description"],
                        data["due_date"],
                        data["priority"],
                    ),
                ).fetchone()
                if duplicate is not None:
                    errors.append(
                        f"已存在完全相同的任务（编号 {duplicate['id']}），请勿重复创建。"
                    )
            if errors:
                return render_template(
                    "form.html",
                    form_title="新建任务",
                    form_action=url_for("new_task"),
                    task=data,
                    errors=errors,
                    statuses=STATUSES,
                    priorities=PRIORITIES,
                    show_status=False,
                )
            now = _now()
            cur = db.execute(
                "INSERT INTO tasks "
                "(name, course, description, due_date, priority, status, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    data["name"],
                    data["course"],
                    data["description"],
                    data["due_date"],
                    data["priority"],
                    "待完成",
                    now,
                    now,
                ),
            )
            db.commit()
            return redirect(url_for("task_detail", task_id=cur.lastrowid))
        return render_template(
            "form.html",
            form_title="新建任务",
            form_action=url_for("new_task"),
            task={
                "name": "",
                "course": "",
                "description": "",
                "due_date": "",
                "priority": "中",
                "status": "待完成",
            },
            errors=[],
            statuses=STATUSES,
            priorities=PRIORITIES,
            show_status=False,
        )

    @app.route("/tasks/<int:task_id>")
    def task_detail(task_id):
        task = get_task_or_404(task_id)
        return render_template(
            "detail.html",
            task=dict(task),
            flag=task_flag(task),
            statuses=STATUSES,
        )

    @app.route("/tasks/<int:task_id>/edit", methods=["GET", "POST"])
    def edit_task(task_id):
        task = get_task_or_404(task_id)
        if request.method == "POST":
            data, errors = validate_task(request.form)
            data["id"] = task_id
            if errors:
                return render_template(
                    "form.html",
                    form_title="编辑任务",
                    form_action=url_for("edit_task", task_id=task_id),
                    task=data,
                    errors=errors,
                    statuses=STATUSES,
                    priorities=PRIORITIES,
                    show_status=True,
                )
            db = get_db()
            db.execute(
                "UPDATE tasks SET name = ?, course = ?, description = ?, due_date = ?, "
                "priority = ?, status = ?, updated_at = ? WHERE id = ?",
                (
                    data["name"],
                    data["course"],
                    data["description"],
                    data["due_date"],
                    data["priority"],
                    data["status"],
                    _now(),
                    task_id,
                ),
            )
            db.commit()
            return redirect(url_for("task_detail", task_id=task_id))
        return render_template(
            "form.html",
            form_title="编辑任务",
            form_action=url_for("edit_task", task_id=task_id),
            task=dict(task),
            errors=[],
            statuses=STATUSES,
            priorities=PRIORITIES,
            show_status=True,
        )

    @app.route("/tasks/<int:task_id>/delete", methods=["POST"])
    def delete_task(task_id):
        get_task_or_404(task_id)
        db = get_db()
        db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        db.commit()
        return redirect(url_for("index"))

    @app.route("/tasks/<int:task_id>/status", methods=["POST"])
    def update_status(task_id):
        get_task_or_404(task_id)
        status = (request.form.get("status") or "").strip()
        if status not in STATUSES:
            abort(400)
        db = get_db()
        db.execute(
            "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
            (status, _now(), task_id),
        )
        db.commit()
        return redirect(url_for("task_detail", task_id=task_id))

    @app.errorhandler(400)
    def bad_request(_error):
        return render_template("error.html", code=400, message="请求参数不正确。"), 400

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("error.html", code=404, message="页面或任务不存在。"), 404

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000, debug=False)
